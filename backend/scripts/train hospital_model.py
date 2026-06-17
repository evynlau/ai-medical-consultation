"""医院专属 Chest X-ray 多标签分类模型训练流水线

特征:
- 基于 xrv DenseNet121 (预训练权重迁移学习)
- 支持多标签分类 (11-18 类可选)
- 完整的数据增强/早停/模型校准
- 输出 PPV=80% 的决策阈值

数据格式:
  data_dir/
    train/
      image_001.png
      image_002.png
      ...
    val/
      image_101.png
      ...
      
  labels.csv (可选，如果图片名与标签对应)
    filename,panorama,disease1,disease2,...
    image_001.png,1,0,1,...

使用方法:
  python train_hospital_model.py --data-dir ./data/hospital --model-name chestx-ray-hospital-v1
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
from torchvision import transforms
from PIL import Image
from tqdm import tqdm
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score

import torchxrayvision as xrv


# ====================== 配置类 ======================

class TrainingConfig:
    """训练配置参数"""
    
    # 数据路径
    data_dir: str = "./data/hospital"
    train_split: float = 0.8
    
    # 模型设置
    base_model: str = "densenet121-res224-chex"  # 基础预训练模型
    num_classes: int = 11  # 输出类别数 (与 xrv 的 chex 一致)
    
    # 训练超参数
    batch_size: int = 16
    epochs: int = 50
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4
    
    # 数据增强
    augment_flip: bool = True
    augment_rotate: bool = True
    color_jitter: float = 0.1
    
    # 早停
    early_stopping_patience: int = 10
    
    # 输出路径
    output_dir: str = "./checkpoints"
    
    # 日志
    log_interval: int = 50


# ====================== 数据集类 ======================

class HospitalXrayDataset(Dataset):
    """医院专属 Chest X-ray 多标签数据集"""
    
    def __init__(
        self,
        data_dir: str,
        transforms=None,
        mode: str = "train",
        label_csv: str = None
    ):
        self.data_dir = Path(data_dir)
        self.mode = mode
        self.transforms = transforms
        
        # 加载图片路径
        self.image_paths = []
        
        # 支持两种格式:
        # 1. data_dir/{train,val}/img.png (单标签,子目录名=类名)
        # 2. data_dir/*.png + label_csv (多标签)
        
        if (self.data_dir / "labels.csv").exists() and label_csv is None:
            label_csv = str(self.data_dir / "labels.csv")
        
        if label_csv and os.path.exists(label_csv):
            # 格式2: 多标签 CSV
            self.df = pd.read_csv(label_csv)
            
            # 获取所有列名(排除 filename 列)
            all_cols = list(self.df.columns)
            if 'filename' in all_cols:
                all_cols.remove('filename')
            self.pathologies = all_cols
            
            for _, row in self.df.iterrows():
                img_path = self.data_dir / row['filename']
                if img_path.exists():
                    labels = [int(row[p]) for p in self.pathologies]
                    self.image_paths.append((str(img_path), labels))
        else:
            # 格式1: 单标签目录
            # 检查是否有子目录(如 NORMAL/, PNEUMONIA/)
            subdirs = [d for d in (self.data_dir / mode).glob("*") if d.is_dir()]
            
            if len(subdirs) > 0:
                self.pathologies = sorted([d.name for d in subdirs])
                
                for subdir in subdirs:
                    label_idx = self.pathologies.index(subdir.name)
                    for img_path in subdir.glob("*.png"):
                        labels = [0] * len(self.pathologies)
                        labels[label_idx] = 1
                        if img_path.exists():
                            self.image_paths.append((str(img_path), labels))
            else:
                # 纯文件夹，所有图片默认 NORMAL(全0)
                self.pathologies = ["NORMAL"]
                for img_path in (self.data_dir / mode).glob("*.png"):
                    self.image_paths.append((str(img_path), [0]))
        
        print(f"[{mode}] 加载 {len(self.image_paths)} 张图片")
        print(f"  病理类别: {self.pathologies}")
        
    def __len__(self):
        return len(self.image_paths)
    
    def __getitem__(self, idx):
        img_path, labels = self.image_paths[idx]
        
        try:
            # X光通常是灰度,但 DenseNet 需要 1 通道输入
            img = Image.open(img_path).convert("L")
            
            if self.transforms:
                img = self.transforms(img)
        except Exception as e:
            print(f"加载失败 {img_path}: {e}")
            # 返回空 tensor 作为 fallback
            img = torch.zeros(1, 224, 224)
            labels = [0] * len(self.pathologies)
        
        return img, torch.tensor(labels, dtype=torch.float32)


# ====================== 模型构建 ======================

def build_hospital_model(config: TrainingConfig) -> Tuple[nn.Module, List[str]]:
    """
    构建医院专属模型
    
    Args:
        config: 训练配置
        
    Returns:
        model: 神经网络
        pathologies: 病理标签列表
    """
    
    # 加载 xrv 的预训练模型
    print(f"加载基础模型: {config.base_model}")
    
    if "chex" in config.base_model.lower():
        base_pathologies = [
            'Atelectasis', 'Consolidation', '', 'Pneumothorax',
            'Edema', '', '', 'Effusion', 'Pneumonia', '',
            'Cardiomegaly', '', '', '', 'Lung Lesion',
            'Fracture', 'Lung Opacity', 'Enlarged Cardiomediastinum'
        ]
    elif "nih" in config.base_model.lower():
        base_pathologies = [
            'Atelectasis', 'Consolidation', 'Infiltration', 'Pneumothorax',
            'Edema', 'Emphysema', 'Fibrosis', 'Effusion',
            'Pneumonia', 'Pleural_Thickening', 'Cardiomegaly',
            'Nodule', 'Mass', 'Hernia'
        ]
    else:
        # 默认: all
        base_pathologies = xrv.datasets.default_pathologies
    
    # 根据用户指定的类别数筛选
    selected_pathologies = [p for p in base_pathologies[:config.num_classes] if p]
    
    print(f"目标病理 ({len(selected_pathologies)}类): {selected_pathologies}")
    
    # 加载基础模型(带预训练权重)
    model = xrv.models.get_model(config.base_model)
    
    # 重置 classifier 层
    in_features = model.classifier.in_features
    model.classifier = nn.Linear(in_features, config.num_classes)
    
    print(f"分类器重置: {in_features} -> {config.num_classes}")
    
    return model, selected_pathologies


# ====================== 数据增强 ======================

def get_train_transforms(config: TrainingConfig):
    """训练时的数据增强"""
    transforms_list = [
        transforms.Resize((256, 256)),  # 先放大
        transforms.RandomCrop(224),      # 随机裁剪
        transforms.ToTensor(),
    ]
    
    if config.augment_flip:
        transforms_list.insert(0, transforms.RandomHorizontalFlip(p=0.5))
    
    if config.augment_rotate:
        transforms_list.insert(1, transforms.RandomRotation(degrees=10))
    
    # X光归一化: [-1024, 1024]
    transforms_list.append(
        transforms.Lambda(lambda x: (x * 2 - 1) * 1024)
    )
    
    return transforms.Compose(transforms_list)


def get_val_transforms():
    """验证/测试时的预处理(无增强)"""
    transform = xrv.datasets.XRayResizer(224)
    
    def custom_transform(img):
        # 将 PIL.Image 转为 numpy, 再转 tensor
        import numpy as np
        arr = np.asarray(img).astype(np.float32)
        arr = xrv.utils.normalize(arr, 255)  # [-1024, 1024]
        arr_t = transform(arr[None, :, :])
        return torch.from_numpy(arr_t).unsqueeze(0)
    
    return custom_transform


# ====================== 训练循环 ======================

def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    epoch: int
) -> Tuple[float, float]:
    """训练一个 epoch"""
    model.train()
    
    total_loss = 0.0
    correct = 0
    total = 0
    
    criterion = nn.BCEWithLogitsLoss()
    
    pbar = tqdm(loader, desc=f"Epoch {epoch}")
    for batch_idx, (images, labels) in enumerate(pbar):
        images = images.to(device)
        labels = labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        total_loss += loss.item() * images.size(0)
        
        # 对于多标签分类,每个样本的 accuracy
        preds = (torch.sigmoid(outputs) > 0.5).float()
        correct += (preds == labels).all(dim=1).sum().item()
        total += labels.size(0)
        
        pbar.set_postfix({
            "loss": f"{loss.item():.4f}",
            "acc": f"{100.*correct/total:.2f}%"
        })
    
    avg_loss = total_loss / total
    accuracy = correct / total
    
    return avg_loss, accuracy


@torch.no_grad()
def validate_epoch(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    pathologies: List[str]
) -> Tuple[float, Dict]:
    """验证一个 epoch"""
    model.eval()
    
    criterion = nn.BCEWithLogitsLoss(reduction='sum')
    
    total_loss = 0.0
    all_preds = []
    all_labels = []
    
    for images, labels in tqdm(loader, desc="Valid"):
        images = images.to(device)
        labels = labels.to(device)
        
        outputs = model(images)
        loss = criterion(outputs, labels)
        total_loss += loss.item()
        
        preds = torch.sigmoid(outputs).cpu().numpy()
        labels_np = labels.cpu().numpy()
        
        all_preds.append(preds)
        all_labels.append(labels_np)
    
    # 汇总所有批次
    all_preds = np.vstack(all_preds)
    all_labels = np.vstack(all_labels)
    
    avg_loss = total_loss / len(loader.dataset)
    
    # 计算每个类别的 metrics
    metrics = {"loss": avg_loss}
    
    for i, pathology in enumerate(pathologies):
        if all_labels[:, i].sum() == 0:
            # 这个类别没有正样本
            continue
        
        try:
            auc = roc_auc_score(all_labels[:, i], all_preds[:, i])
            ap = average_precision_score(all_labels[:, i], all_preds[:, i])
            metrics[f"AUC_{pathology}"] = auc
            metrics[f"AP_{pathology}"] = ap
        except Exception as e:
            print(f"计算 {pathology} 的 AUC 失败: {e}")
    
    return avg_loss, metrics


def calculate_thresholds(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    pathologies: List[str],
    target_ppv: float = 0.8
) -> Dict[str, float]:
    """
    计算每个病理的决策阈值(使得 PPV=target_ppv)
    
    使用 Youden index: J = sensitivity + specificity - 1
    找到 maximize(J) 的阈值
    """
    model.eval()
    
    all_probs = []
    all_labels = []
    
    with torch.no_grad():
        for images, labels in tqdm(loader, desc="Calibrating"):
            images = images.to(device)
            outputs = model(images)
            probs = torch.sigmoid(outputs).cpu().numpy()
            
            all_probs.append(probs)
            all_labels.append(labels.numpy())
    
    all_probs = np.vstack(all_probs)
    all_labels = np.vstack(all_labels)
    
    thresholds = {}
    
    for i, pathology in enumerate(pathologies):
        if all_labels[:, i].sum() == 0:
            # 没有正样本
            thresholds[pathology] = 0.5  # 兜底
            continue
        
        probs = all_probs[:, i]
        labels = all_labels[:, i]
        
        # 遍历阈值找最佳 PPV
        best_thresh = 0.5
        best_j = -1
        
        for thresh in np.arange(0.01, 0.99, 0.01):
            preds = (probs >= thresh).astype(int)
            
            tp = ((preds == 1) & (labels == 1)).sum()
            fp = ((preds == 1) & (labels == 0)).sum()
            
            if tp + fp == 0:
                continue
            
            precision = tp / (tp + fp)
            
            # 简单: 直接选 PPV 约为目标阈值的点
            if precision >= target_ppv - 0.05 and precision <= target_ppv + 0.05:
                thresholds[pathology] = thresh
                break
        else:
            # 找不到精确匹配,选最接近的
            min_diff = float('inf')
            for thresh in np.arange(0.01, 0.99, 0.01):
                preds = (probs >= thresh).astype(int)
                tp = ((preds == 1) & (labels == 1)).sum()
                fp = ((preds == 1) & (labels == 0)).sum()
                
                if tp + fp > 0:
                    precision = tp / (tp + fp)
                    diff = abs(precision - target_ppv)
                    
                    if diff < min_diff:
                        min_diff = diff
                        best_thresh = thresh
            
            thresholds[pathology] = best_thresh
    
    return thresholds


# ====================== 主训练流程 ======================

def main():
    parser = argparse.ArgumentParser(description="医院专属 Chest X-ray 模型训练")
    
    # 数据路径
    parser.add_argument("--data-dir", type=str, required=True,
                        help="数据根目录 (包含 train/val 子目录)")
    parser.add_argument("--label-csv", type=str, default=None,
                        help="可选: 标签 CSV 文件")
    
    # 模型设置
    parser.add_argument("--base-model", type=str, default="densenet121-res224-chex",
                        choices=["densenet121-res224-all", "densenet121-res224-chex",
                                 "densenet121-res224-nih", "densenet121-res224-pc"],
                        help="基础预训练模型")
    parser.add_argument("--num-classes", type=int, default=11,
                        help="输出类别数 (与基础模型一致)")
    
    # 训练超参数
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    
    # 输出
    parser.add_argument("--output-dir", type=str, default="./checkpoints")
    parser.add_argument("--model-name", type=str, required=True,
                        help="模型名称 (如: chestx-ray-hospital-v1)")
    
    args = parser.parse_args()
    
    # ====================== 初始化 ======================
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    config = TrainingConfig()
    for k, v in vars(args).items():
        if hasattr(config, k):
            setattr(config, k, v)
    
    # ====================== 准备数据 ======================
    
    print("\n准备数据...")
    
    train_transform = get_train_transforms(config)
    val_transform = get_val_transforms()
    
    train_dataset = HospitalXrayDataset(
        config.data_dir,
        transforms=train_transform,
        mode="train"
    )
    val_dataset = HospitalXrayDataset(
        config.data_dir,
        transforms=val_transform,
        mode="val",
        label_csv=args.label_csv
    )
    
    print(f"训练集: {len(train_dataset)} 张")
    print(f"验证集: {len(val_dataset)} 张")
    
    train_loader = DataLoader(
        train_dataset, batch_size=config.batch_size, shuffle=True,
        num_workers=2, pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=config.batch_size, shuffle=False,
        num_workers=2, pin_memory=True
    )
    
    # ====================== 构建模型 ======================
    
    print("\n构建模型...")
    model, pathologies = build_hospital_model(config)
    model = model.to(device)
    
    # 冻结 backbone (迁移学习策略 1: 只训练 classifier)
    # for param in model.features.parameters():
    #     param.requires_grad = False
    
    optimizer = AdamW(model.classifier.parameters(), lr=config.learning_rate,
                      weight_decay=config.weight_decay)
    scheduler = CosineAnnealingWarmRestarts(optimizer, T_0=10)
    
    criterion = nn.BCEWithLogitsLoss()
    
    # ====================== 训练 ======================
    
    print("\n开始训练...")
    print("=" * 60)
    
    best_val_loss = float('inf')
    patience_counter = 0
    history = []
    
    model_dir = Path(config.output_dir) / config.model_name
    model_dir.mkdir(parents=True, exist_ok=True)
    
    for epoch in range(1, config.epochs + 1):
        print(f"\nEpoch {epoch}/{config.epochs}")
        print("-" * 60)
        
        # 训练
        train_loss, train_acc = train_one_epoch(
            model, train_loader, optimizer, device, epoch
        )
        scheduler.step()
        
        # 验证
        val_loss, val_metrics = validate_epoch(model, val_loader, device, pathologies)
        
        print(f"\n[Epoch {epoch}] Train Loss: {train_loss:.4f} | Acc: {train_acc:.4f}")
        print(f"[Epoch {epoch}] Val Loss:   {val_loss:.4f}")
        for k, v in val_metrics.items():
            if k.startswith("AUC_") or k.startswith("AP_"):
                print(f"  {k}: {v:.4f}")
        
        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            **{k: v for k, v in val_metrics.items() if isinstance(v, (int, float))}
        })
        
        # 早停检查
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            
            # 保存最佳模型(只保存 classifier,保留 backbone 权重)
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": val_loss,
                "pathologies": pathologies,
                "config": {
                    k: v for k, v in vars(config).items()
                    if not k.startswith("_") and isinstance(v, (str, int, float, bool))
                }
            }, model_dir / "best_model.pt")
            
            print(f"✓ 保存最佳模型: {model_dir / 'best_model.pt'} (loss={val_loss:.4f})")
        else:
            patience_counter += 1
            print(f"  No improvement ({patience_counter}/{config.early_stopping_patience})")
        
        if patience_counter >= config.early_stopping_patience:
            print("\n触发早停,停止训练!")
            break
        
        # 定期保存训练历史
        with open(model_dir / "training_history.json", "w") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    
    # ====================== 模型校准 (计算阈值) ======================
    
    print("\n" + "=" * 60)
    print("模型校准: 计算 PPV=80% 的决策阈值...")
    
    # 如果有独立的校准集,用它;否则用验证集
    if (Path(config.data_dir) / "calibrate").exists():
        cal_dataset = HospitalXrayDataset(
            config.data_dir,
            transforms=val_transform,
            mode="calibrate"
        )
        cal_loader = DataLoader(cal_dataset, batch_size=config.batch_size, shuffle=False)
    else:
        print("  -> 没有独立校准集,使用验证集")
        cal_loader = val_loader
    
    thresholds = calculate_thresholds(model, cal_loader, device, pathologies, target_ppv=0.8)
    
    # 保存阈值
    threshold_file = model_dir / "thresholds.json"
    with open(threshold_file, "w") as f:
        json.dump({
            "target_ppv": 0.8,
            "pathologies": pathologies,
            "thresholds": thresholds
        }, f, indent=2)
    
    print(f"\n保存阈值: {threshold_file}")
    for p, t in thresholds.items():
        print(f"  {p}: {t:.4f}")
    
    # ====================== 完成 ======================
    
    print("\n" + "=" * 60)
    print("训练完成!")
    print(f"\n模型路径: {model_dir}")
    print(f"最佳验证损失: {best_val_loss:.4f}")
    print(f"阈值文件: {threshold_file}")


if __name__ == "__main__":
    main()
