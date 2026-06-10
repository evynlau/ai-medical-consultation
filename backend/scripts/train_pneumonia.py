"""训练 ResNet50 肺炎 X 光片分类模型
基于 Chest X-Ray (Pneumonia) 数据集
"""
import os
import argparse
import json
from pathlib import Path
from datetime import datetime

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import SGD
from torch.optim.lr_scheduler import PolynomialLR
from torchvision import transforms, models
from torchvision.models import ResNet50_Weights
from PIL import Image
import numpy as np
from tqdm import tqdm


# ====================== Dataset ======================

class ChestXrayDataset(Dataset):
    """胸部X光片数据集"""

    def __init__(self, data_dir: str, transform=None, mode: str = "train"):
        self.mode = mode
        self.transform = transform
        self.data_list = []

        # 数据结构: data_dir/{train,val,test}/{NORMAL,PNEUMONIA}/
        split_dir = Path(data_dir) / mode
        if not split_dir.exists():
            raise FileNotFoundError(f"数据集目录不存在: {split_dir}")

        # 类别映射: NORMAL=0, PNEUMONIA=1
        for label_name, label_idx in [("NORMAL", 0), ("PNEUMONIA", 1)]:
            class_dir = split_dir / label_name
            if not class_dir.exists():
                print(f"⚠️ 警告: 目录不存在 {class_dir}")
                continue
            for img_file in class_dir.glob("*.jpeg"):
                self.data_list.append((str(img_file), label_idx))
            for img_file in class_dir.glob("*.jpg"):
                self.data_list.append((str(img_file), label_idx))
            for img_file in class_dir.glob("*.png"):
                self.data_list.append((str(img_file), label_idx))

        print(f"[{mode}] 共加载 {len(self.data_list)} 张图片")
        # 统计各类别数量
        labels = [d[1] for d in self.data_list]
        print(f"  - NORMAL: {labels.count(0)}")
        print(f"  - PNEUMONIA: {labels.count(1)}")

    def __len__(self):
        return len(self.data_list)

    def __getitem__(self, idx):
        img_path, label = self.data_list[idx]
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"无法加载图片 {img_path}: {e}")
            # 返回一个空图片
            img = Image.new("RGB", (224, 224))

        if self.transform:
            img = self.transform(img)

        return img, label


# ====================== Model ======================

def build_resnet50(num_classes: int = 2, pretrained: bool = True) -> nn.Module:
    """构建 ResNet50 模型"""
    if pretrained:
        # 使用预训练权重
        weights = ResNet50_Weights.IMAGENET1K_V2
        model = models.resnet50(weights=weights)
    else:
        model = models.resnet50(weights=None)

    # 替换最后的全连接层
    in_features = model.fc.in_features
    model.fc = nn.Linear(in_features, num_classes)

    return model


# ====================== 训练 & 验证 ======================

def train_one_epoch(model, loader, criterion, optimizer, device):
    """训练一个 epoch"""
    model.train()
    total_loss = 0
    correct = 0
    total = 0

    pbar = tqdm(loader, desc="Train")
    for images, labels in pbar:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

        pbar.set_postfix({
            "loss": f"{loss.item():.4f}",
            "acc": f"{100.*correct/total:.2f}%"
        })

    avg_loss = total_loss / total
    accuracy = correct / total
    return avg_loss, accuracy


@torch.no_grad()
def validate(model, loader, criterion, device):
    """验证"""
    model.eval()
    total_loss = 0
    correct_top1 = 0
    correct_top5 = 0
    total = 0

    for images, labels in tqdm(loader, desc="Valid"):
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        total_loss += loss.item() * images.size(0)

        # Top-1
        _, predicted = outputs.max(1)
        correct_top1 += predicted.eq(labels).sum().item()

        # Top-5 (二分类时 top5 准确率始终是1)
        _, top5_pred = outputs.topk(5, dim=1)
        correct_top5 += top5_pred.eq(labels.view(-1, 1).expand_as(top5_pred)).any(dim=1).sum().item()

        total += labels.size(0)

    avg_loss = total_loss / total
    top1_acc = correct_top1 / total
    top5_acc = correct_top5 / total
    return avg_loss, top1_acc, top5_acc


# ====================== 主流程 ======================

def main():
    parser = argparse.ArgumentParser(description="训练肺炎X光片分类模型")
    parser.add_argument("--data-dir", type=str, default="./data/chest_xray",
                        help="数据集根目录")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=0.0125)
    parser.add_argument("--momentum", type=float, default=0.9)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--output", type=str, default="./checkpoints/pneumonia_resnet50.pth")
    parser.add_argument("--num-workers", type=int, default=2)
    args = parser.parse_args()

    # 设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    # 数据变换
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=10),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        ),
    ])

    # 数据集
    train_dataset = ChestXrayDataset(args.data_dir, transform=train_transform, mode="train")
    val_dataset = ChestXrayDataset(args.data_dir, transform=val_transform, mode="val")

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=True
    )

    # 模型
    print("\n构建模型...")
    model = build_resnet50(num_classes=2, pretrained=True)
    model = model.to(device)

    # 损失函数 & 优化器
    criterion = nn.CrossEntropyLoss()
    optimizer = SGD(
        model.parameters(),
        lr=args.lr,
        momentum=args.momentum,
        weight_decay=args.weight_decay
    )

    # 学习率调度
    decay_steps = len(train_loader) * args.epochs
    scheduler = PolynomialLR(
        optimizer,
        total_iters=decay_steps,
        power=0.9,
        end_lr=0.0
    )

    # 训练循环
    print(f"\n开始训练: {args.epochs} epochs, batch_size={args.batch_size}, lr={args.lr}")
    print(f"训练集: {len(train_dataset)} 张")
    print(f"验证集: {len(val_dataset)} 张")
    print("=" * 60)

    best_acc = 0.0
    history = []

    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch+1}/{args.epochs}")
        print("-" * 60)

        # 训练
        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device
        )
        scheduler.step()

        # 验证
        val_loss, top1_acc, top5_acc = validate(
            model, val_loader, criterion, device
        )

        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss,
            "train_acc": train_acc,
            "val_loss": val_loss,
            "top1_acc": top1_acc,
            "top5_acc": top5_acc,
        })

        print(f"\n[Epoch {epoch+1}] Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.4f}")
        print(f"[Epoch {epoch+1}] Val Loss:   {val_loss:.4f} | Top-1: {top1_acc:.4f} | Top-5: {top5_acc:.4f}")

        # 保存最佳模型
        if top1_acc > best_acc:
            best_acc = top1_acc
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state_dict": model.state_dict(),
                "epoch": epoch + 1,
                "best_acc": best_acc,
                "config": {
                    "model": "resnet50",
                    "num_classes": 2,
                    "image_size": 224,
                    "mean": [0.485, 0.456, 0.406],
                    "std": [0.229, 0.224, 0.225],
                }
            }, args.output)
            print(f"💾 保存最佳模型: {args.output} (acc={best_acc:.4f})")

    print("\n" + "=" * 60)
    print(f"训练完成! 最佳验证准确率: {best_acc:.4f}")

    # 保存训练历史
    history_path = Path(args.output).parent / "training_history.json"
    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
    print(f"训练历史已保存: {history_path}")


if __name__ == "__main__":
    main()