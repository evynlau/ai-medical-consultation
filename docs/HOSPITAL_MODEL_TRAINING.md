# 医院专属 Chest X-ray 模型训练指南

> 本文档基于 `backend/scripts/train hospital_model.py`(注意文件名含空格,共 647 行)实际行为编写;与上一版的主要差异:删除虚构的训练细节,对齐 AdamW + CosineAnnealingWarmRestarts 真实配方,补齐 PPV 校准流程。
>
> ⚠️ **该脚本当前未接入在线服务**(`xrv_service.py` 仍只用 `xrv.models.get_model("densenet121-res224-chex")`)。要走完"专属模型 → 上线"全链路,见末尾「部署到生产」一节。

---

## 0. 与现有 `train_pneumonia.py` 的关系

仓库里其实有**两个**训练脚本,定位不同:

| 脚本 | 行数 | 优化器 | 任务 | 状态 |
|---|---|---|---|---|
| `backend/scripts/train hospital_model.py` | 647 | AdamW + CosineAnnealingWarmRestarts | xrv 预训练 + 微调 → 输出 11 类多标签 + 校准阈值 | **可用,未接入** |
| `backend/scripts/train_pneumonia.py` | 314 | SGD + PolynomialLR | ImageNet ResNet50 + 2 类单标签 (NORMAL/PNEUMONIA) | **可用,未接入** |

> 两者输出都不会被 `xrv_service.py` 自动加载;若想让任一模型生效,需修改 `xrv_service.load_model()` 走 `torch.load()` 分支。

---

## 1. 数据收集与准备

### 1.1 推荐的数据集来源

| 数据集 | 规模 | 特点 | 许可证 |
|---|---|---|---|
| CheXpert (Stanford) | 224k 张 | 多标签, 11 类, 高质量 | Apache 2.0 |
| NIH ChestX-ray8 | ~100k | 单-label, 8 类 | CC-BY 4.0 |
| PadChest | ~150k | 多标签, 37 类, 多中心 | CC-BY-NC-SA |
| MIMIC-CXR | 600k+ | 多标签 | CC-BY |

### 1.2 数据格式要求

#### 方式 A: 目录结构(单-label,子目录即标签)
```
data/hospital/
  train/
    NORMAL/        # 子目录名 = 类名
      img_001.png
      ...
    PNEUMONIA/
      img_101.png
      ...
  val/
    NORMAL/        # 必须有,否则报错
    PNEUMONIA/
```

#### 方式 B: CSV 标注(多-label,推荐)
```
data/hospital/
  train/
    img_001.png
    img_002.png
  val/
    img_101.png
  labels.csv
```
`labels.csv`:
```csv
filename,Atelectasis,Consolidation,Pneumonia,Effusion
img_001.png,1,0,1,0
img_002.png,0,1,0,0
img_101.png,0,0,0,0
```
脚本会自动检测 `labels.csv` 存在 → 走多标签路径;否则走「子目录即单标签」路径。

### 1.3 推荐的训练/验证划分

- **小数据集** (<10k 张): 训练:验证 = 8:2
- **中等** (10k-50k): 训练:验证 = 85:15
- **大数据集** (>50k): 验证集可小些 (5-10%)

---

## 2. 安装依赖

```bash
cd /home/evynlau/桌面/AI-Agent/AI智能问诊系统/backend
source venv/bin/activate

pip install -r requirements.txt
pip install scikit-learn pandas    # 脚本用 sklearn.metrics 和 pd.read_csv
```

> xrv 本身已在 `requirements.txt` 中,`pandas`/`scikit-learn` 默认没装。

---

## 3. 训练专属模型

### 3.1 基本命令(目录结构,单标签)

```bash
python "scripts/train hospital_model.py" \
    --data-dir ./data/hospital \
    --model-name chestx-ray-hospital-v1 \
    --base-model densenet121-res224-chex \
    --num-classes 11 \
    --epochs 50 \
    --batch-size 16 \
    --lr 1e-4
```

### 3.2 多标签 + CSV 模式

```bash
python "scripts/train hospital_model.py" \
    --data-dir ./data/hospital \
    --label-csv ./data/hospital/labels.csv \
    --model-name hospital-v1-multilabel \
    --num-classes 11
```

### 3.3 训练参数说明(基于 argparse 真实默认)

| 参数 | CLI flag | 默认值 | 推荐 |
|---|---|---|---|
| 数据根目录 | `--data-dir` | (必填) | 含 `train/` `val/` 子目录 |
| 模型名 | `--model-name` | (必填) | 影响输出路径 `./checkpoints/<name>/` |
| 标签 CSV | `--label-csv` | `None`(自动检测) | 多标签场景下使用 |
| 基础预训练 | `--base-model` | `densenet121-res224-chex` | 可选: `all` / `nih` / `pc` |
| 类别数 | `--num-classes` | `11` | 与 base-model 病理数一致 |
| 训练轮数 | `--epochs` | `50` | 小数据 30-50,大数据 10-20 |
| 批次大小 | `--batch-size` | `16` | 显存大可调到 32-64 |
| 学习率 | `--lr` | `1e-4` | 迁移学习 1e-4 ~ 1e-5 |
| 权重衰减 | `--weight-decay` | `1e-4` | AdamW 标准 |
| 输出目录 | `--output-dir` | `./checkpoints` | — |

### 3.4 关键训练配方(脚本实际行为)

| 维度 | 实际值 |
|---|---|
| 优化器 | **AdamW**(只对 `model.classifier.parameters()`) |
| 调度器 | `CosineAnnealingWarmRestarts(T_0=10)` |
| 损失函数 | `BCEWithLogitsLoss`(多标签) |
| 训练增强 | `RandomHorizontalFlip` + `RandomRotation(10°)` + Resize 256 + RandomCrop 224 + `Lambda: (x*2-1)*1024` (CXR 归一化) |
| 验证预处理 | `XRayResizer(224)` + `xrv.utils.normalize(arr, 255)` |
| Backbone 冻结 | **默认解冻**(代码 `train hospital_model.py:526-527` 注释了冻结行)。如想冻结,取消注释 |
| Early stopping | `patience=10`,验证 loss 不降则停 |
| 校准 | 训练完跑 `calculate_thresholds(target_ppv=0.8)`,输出 `thresholds.json` |

> ⚠️ 注意:旧版文档写「默认冻结 backbone」,**与代码不符**。当前代码默认 AdamW 只传给 `model.classifier.parameters()`,但是因为 backbone 没被 `requires_grad=False`,实际反向传播时 backbone 也会被更新(只要 loss 流到那)。如果想真正只训 classifier,需手动加 `for p in model.features.parameters(): p.requires_grad = False`(见 §5)。

---

## 4. 输出说明

训练完成后,输出路径: `./checkpoints/<model-name>/`

```
checkpoints/
  chestx-ray-hospital-v1/
    ├── best_model.pt         # 最佳模型权重(按 val_loss 选)
    ├── training_history.json # 每 epoch 的 loss / AUC / AP
    └── thresholds.json       # PPV=80% 的决策阈值
```

### 4.1 `thresholds.json` 格式

```json
{
  "target_ppv": 0.8,
  "pathologies": ["Atelectasis", "Consolidation", "Pneumonia", ...],
  "thresholds": {
    "Atelectasis": 0.18,
    "Consolidation": 0.22,
    "Pneumonia": 0.12,
    ...
  }
}
```

阈值计算流程:遍历 `0.01-0.99` 步长 0.01,选**使 PPV 最接近 0.8** 的阈值;若该病理没有正样本兜底为 0.5。

---

## 5. 高级技巧

### 5.1 真正冻结 Backbone(快速微调)

取消 `train hospital_model.py:526-527` 注释:
```python
# 冻结 backbone,只训练 classifier
for param in model.features.parameters():
    param.requires_grad = False
```
适合数据 < 5k 张,训练速度快很多。

### 5.2 解冻 Backbone + 端到端微调

数据 > 10k 张时推荐。注意**学习率要比 §3 的 1e-4 小一个数量级**(避免破坏预训练):
```python
optimizer = AdamW(model.parameters(), lr=1e-5, weight_decay=1e-4)
```

### 5.3 加强数据增强

修改 `get_train_transforms`(第 224-243 行):
```python
def get_train_transforms(config):
    return transforms.Compose([
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.Resize((256, 256)),
        transforms.RandomCrop(224),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Lambda(lambda x: (x * 2 - 1) * 1024),
    ])
```

> 注意:医学 CXR 上 `RandomRotation(degrees=15)` 偏激进,可能引入解剖结构伪影。

### 5.4 使用早停

`patience=10` 已是脚本默认值(可通过代码内 `TrainingConfig.early_stopping_patience` 调整)。若想关闭,把 CLI 加 `--epochs` 调到目标值即可。

---

## 6. 部署到生产系统(让专属模型生效)

⚠️ **当前 `xrv_service.py` 不会自动加载专属模型**,需要手动改在线服务的 `load_model()` 走「先加载 xrv,再覆盖 classifier / 整体替换」的分支。下面给一个最小修改示例。

### 6.1 修改 `xrv_service.load_model()`

```python
# backend/app/services/imaging/xrv_service.py:load_model
def load_model(self):
    import torchxrayvision as xrv
    import torch

    hospital_ckpt = Path("./checkpoints/chestx-ray-hospital-v1/best_model.pt")
    if hospital_ckpt.exists():
        # 走专属模型
        logger.info(f"加载医院专属模型: {hospital_ckpt}")
        ckpt = torch.load(hospital_ckpt, map_location=self._device)
        # 用 xrv 同样的 backbone 初始化,再覆盖 classifier
        self._xrv_model = xrv.models.get_model("densenet121-res224-chex")
        self._xrv_model.classifier = nn.Linear(1024, len(ckpt["pathologies"]))
        self._xrv_model.load_state_dict(ckpt["model_state_dict"])
        # 加载校准阈值
        thresholds_file = hospital_ckpt.parent / "thresholds.json"
        if thresholds_file.exists():
            self._custom_thresholds = json.loads(thresholds_file.read_text())["thresholds"]
    else:
        # fallback 到 xrv 官方权重
        self._xrv_model = xrv.models.get_model("densenet121-res224-chex")
        self._custom_thresholds = None

    self._xrv_model.to(self._device).eval()
```

### 6.2 让 `_get_thresholds()` 优先用专属阈值

```python
def _get_thresholds(self) -> Dict[str, float]:
    if self._custom_thresholds:
        return self._custom_thresholds
    # 否则用 xrv 官方 op_threshs
    threshs = self._xrv_model.op_threshs.cpu().numpy()
    return {p: float(threshs[i]) for i, p in enumerate(self._xrv_model.pathologies) if p}
```

### 6.3 验证流程

1. 上传一张已知标签的胸片到 `/imaging`
2. 看返回的 `pathologies[]` 中该病理 `positive` 是否正确
3. 检查 `confidence` 是否合理(0.5-0.95 区间可信)

---

## 7. 常见问题

### Q1: 训练 loss 不下降?
- 检查数据路径是否正确
- 检查标签格式 (多标签?CSV 第一列必须叫 `filename`)
- 尝试减小学习率(1e-5)

### Q2: 验证 loss 远高于训练 loss?
- 多半过拟合
- 启用 backbone 冻结(§5.1)
- 增加数据增强(§5.3)
- 加更多数据

### Q3: 训练时 `labels.csv` 加载失败?
- 检查 `filename` 列名是否拼写正确
- 路径是相对 `data_dir` 的(不是 `train/` 子目录)
- 至少要有 `train/` 和 `val/` 两个子目录

### Q4: 如何评估模型好坏?
脚本默认在每个 epoch 输出每个病理的 AUC / AP:
```
[Epoch 5] Val Loss: 0.3421
  AUC_Atelectasis: 0.8521
  AP_Atelectasis: 0.6234
  AUC_Pneumonia: 0.9123
  ...
```
- **AUC**: >0.85 可用,>0.90 良好
- **AP (Average Precision)**: >0.6 可用
- **PPV (精确率)**: 通过 `thresholds.json` 校准到 0.8

### Q5: 训练要多久?
- 5k 张 + 50 epochs + 单 GPU(2080Ti) ≈ 1-2 小时
- 50k 张 + 30 epochs + 单 GPU ≈ 6-8 小时
- 没有 GPU 时极不推荐(预估 24h+)

### Q6: 可以用其他 backbone 吗?
可以。`--base-model` 当前支持:
- `densenet121-res224-all` (224k 张全量)
- `densenet121-res224-chex` (CheXpert,默认)
- `densenet121-res224-nih` (NIH ChestX-ray8)
- `densenet121-res224-pc` (PadChest)

---

## 8. 参考资料

- [torchxrayvision 文档](https://github.com/mlmed/torchxrayvision)
- CheXpert 论文: *CheXpert: A Large Chest Radiograph Dataset with Uncertainty Labels and Expert Comparison* — Stanford
- NIH ChestX-ray8: *ChestX-ray8: Hospital-scale Chest X-ray Database and Benchmarks on Weakly-Supervised Classification and Localization of Common Thorax Diseases*

---

## 9. 快速开始模板(复制粘贴)

### 9.1 单标签(子目录结构)

```bash
# 1. 准备数据
mkdir -p data/hospital/train/NORMAL data/hospital/train/PNEUMONIA
mkdir -p data/hospital/val/NORMAL   data/hospital/val/PNEUMONIA
# 把 .png/.jpg 文件分别放进对应目录

# 2. 训练
cd /home/evynlau/桌面/AI-Agent/AI智能问诊系统/backend
source venv/bin/activate
python "scripts/train hospital_model.py" \
    --data-dir ./data/hospital \
    --model-name hospital-v1 \
    --base-model densenet121-res224-chex \
    --num-classes 2 \
    --epochs 30 \
    --batch-size 16 \
    --lr 1e-4

# 3. 输出在 ./checkpoints/hospital-v1/
#    best_model.pt + training_history.json + thresholds.json
```

### 9.2 多标签(CSV)

```bash
# 1. 准备数据
mkdir -p data/hospital/train data/hospital/val
# 把图片放进 train/ val/
# 写 labels.csv(格式见 §1.2 方式 B)

# 2. 训练
python "scripts/train hospital_model.py" \
    --data-dir ./data/hospital \
    --label-csv ./data/hospital/labels.csv \
    --model-name hospital-v1-multilabel \
    --num-classes 11 \
    --epochs 50
```
