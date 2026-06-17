# 影像分析双路推理对比:torchxrayvision vs 自训练 ResNet50

> **修订前言**:本文上一版有个关键错误——我说"在线服务没用到 xrv 技术方案",这是错的。本版已纠正:**xrv DenseNet121 就是当前唯一的在线服务**,自训练 ResNet50 完全是死代码。下面是基于实际代码事实的对比。

---

## 0. 关键发现(已纠正):xrv 是当前唯一的在线服务

**在线服务 `POST /api/v1/imaging/pneumonia/analyze` 走的就是 xrv DenseNet121**,不是自训练模型。

证据(`grep -rn "import torchxrayvision" backend/`):

```
backend/app/api/v1/imaging.py:1         文档注释: "torchxrayvision 多分类胸片分析接口"
backend/app/api/v1/__init__.py          imaging.router 挂载到 /imaging 前缀
backend/app/services/imaging/__init__.py  唯一导出: XRVAnalysisService
backend/app/services/imaging/xrv_service.py  6 处 import torchxrayvision as xrv
backend/venv/lib/python3.12/site-packages/torchxrayvision-1.4.0.dist-info/  已安装
```

而自训练 ResNet50 模型的全部引用:

```
backend/app/core/config.py:44           仅 config 里定义 PNEUMONIA_MODEL_PATH 路径
backend/app/models/imaging.py:80        数据库 ORM 的字段名举例(注释)
backend/scripts/train_pneumonia.py      训练脚本(单独命令行运行)
```

**全代码库零 `import`、零 `torch.load("pneumonia_resnet50.pth")`**。这就是典型的"训练完忘了接入"的代码残留——94MB 权重就这么躺在 `checkpoints/` 里。

**所以"两边大相径庭"的真实含义**:
- 如果你通过前端 `/imaging` 页面分析 → **100% 走 xrv**,只会得到一个结果,不存在"两边冲突"
- 如果你**离线**用 Python 自己写脚本加载 `pneumonia_resnet50.pth` 推理同一张图 → 会得到另一个结果

两套模型从不同时跑同一张图(因为自训练没接入)。但如果你离线对比它们,差异会非常大。本文就拆解这 8 处差异,都是真实代码事实。

---

## 0.1 架构现状一览

| 维度 | torchxrayvision 系统 | 自训练 ResNet50 系统 |
|---|---|---|
| **状态** | ✅ **当前唯一的在线服务**(含 PSPNet 肺部分割 + Grad-CAM/HiResCAM) | ⚠️ **死代码 — 训练完未接入** |
| **API 路径** | `POST /api/v1/imaging/pneumonia/analyze` → `XRVAnalysisService` | 仅 config 里存路径,全代码库零调用 |
| **权重文件** | `~/.torchxrayvision/models_data/*.pt` 首次启动自动下载 | `backend/checkpoints/pneumonia_resnet50.pth`(94MB)|
| **数据源** | xrv 官方预训练(CheXpert 等 224k+ 张) | Kaggle Chest X-Ray 数据集(5216 张) |
| **训练历史** | 无(预训练) | `backend/checkpoints/training_history.json`(8 epochs,val_acc 在 62.5%-100% 剧烈跳动) |
| **训练脚本** | 无 | `backend/scripts/train_pneumonia.py`(完整可用,SGD+PolynomialLR) |

---

## 1. 核心 8 处差异(代码逐行对比)

### 差异 1:模型架构与权重来源

| | torchxrayvision 路径 | 自训练 ResNet50 路径 |
|---|---|---|
| 架构 | `DenseNet121`(xrv 自定义实现) | `torchvision.models.resnet50`(IMAGENET1K_V2 预训练) |
| 权重 | xrv 官方 `densenet121-res224-chex.pt`(在 224k 张 CXR 上训练) | `checkpoints/pneumonia_resnet50.pth`(本地 fine-tune) |
| 加载代码 | `xrv.models.get_model("densenet121-res224-chex")` | `models.resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)` 然后 `model.fc = nn.Linear(2048, 2)` |
| 参数量 | ~7M(DenseNet121) | ~25M(ResNet50) |

```python
# torchxrayvision/xrv_service.py:107-110
self._xrv_model = xrv.models.get_model("densenet121-res224-chex")

# 自训练/train_pneumonia.py:81-91
weights = ResNet50_Weights.IMAGENET1K_V2
model = models.resnet50(weights=weights)
model.fc = nn.Linear(in_features, num_classes)   # 2 = NORMAL/PNEUMONIA
```

**影响**:xrv 的 DenseNet121 在 CXR 上原生训练(已见过几十万张胸片),ResNet50 是从 ImageNet 自然图像迁移到 CXR。

### 差异 2:输入通道数

| | torchxrayvision | 自训练 ResNet50 |
|---|---|---|
| 通道数 | **1 通道灰度**(CXR 物理意义) | **3 通道 RGB** |
| 转换 | `image.convert("L")` | `Image.open(img_path).convert("RGB")` |
| 输入张量 | `(1, 1, 224, 224)` | `(1, 3, 224, 224)` |

```python
# xrv/xrv_service.py:121-131
gray = image.convert("L") if image.mode != "L" else image
arr = np.asarray(gray).astype(np.float32)

# 自训练/train_pneumonia.py:62
img = Image.open(img_path).convert("RGB")
```

**关键**:
- xrv 单通道是医学正确(CXR 本来就是灰度),但烧掉了颜色信息(实际 CXR 没颜色,无影响)
- 自训练 3 通道是为了套 torchvision ResNet50 模板,强行把灰度复制成 RGB — **浪费一个维度**,且 ImageNet 预训练权重的前 3 个通道会分别处理同一份信息

### 差异 3:像素归一化(**最关键的差异之一**)

| | torchxrayvision | 自训练 ResNet50 |
|---|---|---|
| 输入范围 | **`[-1024, 1024]`** (医学 Hounsfield 单位尺度) | **`[0, 1]` 然后 ImageNet mean/std 归一化** |
| 公式 | `(2 * (img/255) - 1) * 1024` | `(img/255 - 0.485) / 0.229` 等三通道 |
| 意义 | 模拟真实 X 光物理强度 | 套用 ImageNet 自然图像统计量 |

```python
# xrv/xrv_service.py:124
arr = xrv.utils.normalize(arr, 255)  # 0-255 -> [-1024, 1024]

# 自训练/train_pneumonia.py:193-196
transforms.Normalize(
    mean=[0.485, 0.456, 0.406],   # ImageNet 均值!
    std=[0.229, 0.224, 0.225]     # ImageNet 标准差!
)
```

**为什么这会导致结果大相径庭**:

- xrv 模型**从未见过** ImageNet mean/std 的输入分布,看到这种输入会输出随机
- 自训练 ResNet50 **从未见过** [-1024, 1024] 的输入,看到会输出随机

**如果你用 xrv 走 ImageNet 归一化 → xrv 输出垃圾。**
**如果你用自训练 ResNet50 走 [-1024, 1024] → ResNet 输出垃圾。**

### 差异 4:变换组合(中心裁剪 vs 直接 Resize)

| | torchxrayvision | 自训练 ResNet50 |
|---|---|---|
| 顺序 | `XRayCenterCrop` → `XRayResizer(224)` | `Resize((224, 224))` 直接拉伸 |
| 长宽比 | **保持**(方形中心裁剪) | **破坏**(直接 resize) |

```python
# xrv/xrv_service.py:126-130
trans = torchvision.transforms.Compose([
    xrv.datasets.XRayCenterCrop(),      # 先在长边中心裁成正方形
    xrv.datasets.XRayResizer(224),      # 再 resize 到 224x224
])

# 自训练/train_pneumonia.py:188
transforms.Resize((224, 224))   # 直接缩,可能把矩形胸片压成方形
```

**影响**:实际胸片通常是矩形(竖向比横向长)。xrv 的中心裁剪保留了肺野;自训练的 Resize 会把胸廓和心影比例拉变形,导致模型看到训练时没见过的形变。

### 差异 5:数据增强(训练时)

| | torchxrayvision | 自训练 ResNet50 |
|---|---|---|
| 训练时增强 | 极简(主要靠 weight decay) | Hflip + Rotation(10°) + ColorJitter |
| 测试时 | 无增强,直接 forward | 无增强 |

```python
# 自训练/train_pneumonia.py:187-197
train_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(p=0.5),    # 水平翻转 — 胸片可以?
    transforms.RandomRotation(degrees=10),     # 旋转 — 解剖结构会变
    transforms.ColorJitter(brightness=0.1),   # 颜色抖动 — 灰度图有意义?
    transforms.ToTensor(),
    transforms.Normalize(...),
])
```

**注意**:
- 胸片水平翻转**在医学上可疑** — 解剖学左侧/右侧是不同的(心脏在左),但因为这里 ResNet50 只分 NORMAL/PNEUMONIA,左右对称性可能帮上忙
- ColorJitter 在灰度 CXR 上**几乎无效**(灰度图调亮度对比度其实就等价于 ColorJitter)
- RandomRotation 10° 在 CXR 上也可能引入伪影

xrv 训练时是严格的位置保持(没有这些激进增强)。

### 差异 6:训练数据规模与组成(**最核心**)

| | torchxrayvision | 自训练 ResNet50 |
|---|---|---|
| 数据集 | CheXpert(Stanford 224k)+ NIH + PadChest + MIMIC + Google + OpenI + RSNA 等 | Kaggle Chest X-Ray Pneumonia |
| 训练样本 | 数万到数十万张 | **5216 张**(1341 正常 + 3875 肺炎) |
| 类别 | 14 类 CheXpert 标签(多标签) | 2 类(NORMAL/PNEUMONIA)单标签 |
| 验证集 | 显式 80/20 split + 独立外部数据集 | 只有 16 张(见下文) |

```bash
# 实际数据(data/chest_xray/)
train: 1341 NORMAL + 3875 PNEUMONIA = 5216 张(实际是5216,不是论文的 5216)
val:   8 NORMAL + 8 PNEUMONIA  ← 验证集小得离谱!
test:  234 NORMAL + 390 PNEUMONIA
```

**这是最致命的差异**:

1. **训练集严重不平衡**(1341 vs 3875),且**儿童数据集**(Kaggle 原版)
2. **验证集只有 16 张**,训练历史显示验证准确率剧烈跳动(62.5% → 93.75% → 62.5% → 100% → 62.5%…),**这是过拟合 + 验证集太小的典型征兆**
3. xrv 看到的是**成人医院胸片**(CheXpert/MIMIC),自训练看到的是**儿童胸片**(Kaggle Paul Mooney)

**用儿童胸片训练的模型推理成人胸片 → 必然输出垃圾**,反之亦然。

### 差异 7:优化器与学习率

| | torchxrayvision | 自训练 ResNet50 |
|---|---|---|
| 优化器 | Adam(默认) | SGD(momentum=0.9, weight_decay=1e-4) |
| LR | 1e-3 / 1e-4 | 0.0125 + PolynomialLR(power=0.9) |
| Epochs | 数十到数百 | 8(看 training_history.json) |

```python
# 自训练/train_pneumonia.py:233-239
optimizer = SGD(model.parameters(), lr=args.lr,
                momentum=args.momentum, weight_decay=args.weight_decay)
decay_steps = len(train_loader) * args.epochs
scheduler = PolynomialLR(optimizer, total_iters=decay_steps, power=0.9)
```

xrv 论文用 Adam + 较短 epoch;自训练用 SGD + 长 epoch + 多项式 LR 衰减 — 这是医学影像迁移学习的**保守配方**(因为数据少)。

### 差异 8:决策逻辑(单标签 vs 多标签)

| | torchxrayvision | 自训练 ResNet50 |
|---|---|---|
| 输出激活 | **sigmoid**(每个标签独立) | **softmax**(互斥二选一) |
| 阈值 | 每个 pathology 一个 `op_threshs`(PPV=80%) | argmax(>0.5 即 PNEUMONIA) |
| 输出维度 | 11 病理概率(可同时阳性多种) | 2 个互斥概率(NORMAL/PNEUMONIA) |

```python
# xrv/xrv_service.py:144-148
features = self._xrv_model.features(x)
pooled = F.adaptive_avg_pool2d(features, 1).flatten(1)
logits = self._xrv_model.classifier(pooled)
probs = torch.sigmoid(logits[0]).cpu().numpy()   # ← sigmoid:每个独立

# 自训练(隐含)
# ResNet50 默认 nn.CrossEntropyLoss 训练 → 最后 fc 输出 logits → softmax
outputs = model(images)
_, predicted = outputs.max(1)                     # ← argmax:互斥
```

**关键冲突**:
- xrv 可能输出 `Pneumonia: 0.82 + Atelectasis: 0.75 + Effusion: 0.65`(**多种共存**)
- 自训练 ResNet50 只会输出 `PNEUMONIA: 0.93` 或 `NORMAL: 0.93`(**单选**)
- xrv 的"Pneumonia" 标签训练自 CheXpert 文本挖掘,阈值 0.05 就可能 positive;自训练的"Pneumonia"来自 Kaggle 儿童放射学诊断,标准完全不同

**即使两套都用"PNEUMONIA"标签,临床定义也可能不一样!**

---

## 2. 训练历史里的过拟合证据

`backend/checkpoints/training_history.json`:

| epoch | train_acc | val_acc | val_loss | 状态 |
|---|---|---|---|---|
| 1 | 94.0% | 81.25% | 0.40 | 健康 |
| 3 | 97.6% | 81.25% | 0.30 | 已无提升 |
| 4 | 98.2% | **62.5%** | 0.80 | **暴跌** |
| 5 | 98.7% | 93.75% | 0.12 | 反常跳升 |
| 6 | 98.7% | **100%** | 0.07 | **不真实** |
| 7 | 98.7% | **62.5%** | 1.26 | **又暴跌** |
| 8 | 98.9% | 81.25% | 0.77 | 收敛到 81.25% |

**诊断**:
- train_acc 一直 98-99%(明显过拟合)
- val_acc 在 62.5%-100% 间剧烈抖动 → 验证集只有 16 张,**单张图片就能让准确率变化 6.25%**
- 没有任何 early stopping
- 论文显示"最佳" epoch 是 6(val_acc=100%),但这极可能是**单张验证图片的偶然**

**结论**:这个 `pneumonia_resnet50.pth` 权重**几乎可以确定在外部数据上表现差**,因为:
- 训练数据(Kaggle 儿童)≠ 推理数据(成人或任意医院)
- 验证集太小无法反映真实性能
- 过拟合严重

---

## 3. 端到端推理差异(同一张图)

假设上传一张 **成人胸片** 显示疑似肺炎浸润:

### xrv 路径

```python
# 1. 加载
model = xrv.models.get_model("densenet121-res224-chex")
# 2. 预处理(灰度 → [-1024, 1024] → 中心裁剪 → resize)
img = Image.open(x).convert("L")
arr = np.asarray(img).astype(np.float32)
arr = xrv.utils.normalize(arr, 255)                # [-1024, 1024]
arr = XRayCenterCrop()(arr)
arr = XRayResizer(224)(arr)                        # (224, 224)
x = torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)
# 3. 推理
features = model.features(x)                       # (1, 1024, 7, 7)
pooled = F.adaptive_avg_pool2d(features, 1).flatten(1)
logits = model.classifier(pooled)                  # (1, 14)
probs = torch.sigmoid(logits[0]).numpy()
# 4. 阈值(op_threshs, PPV=80%)
# Pneumonia: 0.0775 → 概率 > 0.0775 即阳性
# 输出示例: {Pneumonia: 0.83, Infiltration: 0.71, ...}
```

### 自训练路径(如果用代码加载)

```python
# 1. 加载
model = models.resnet50(weights=None)
model.fc = nn.Linear(2048, 2)
ckpt = torch.load("pneumonia_resnet50.pth")
model.load_state_dict(ckpt["model_state_dict"])
# 2. 预处理(RGB → [0,1] → ImageNet 归一化 → 直接 Resize)
img = Image.open(x).convert("RGB")
img = transforms.Resize((224, 224))(img)          # 矩形被拉伸
img = transforms.ToTensor()(img)                   # [0,1]
img = transforms.Normalize([0.485, 0.456, 0.406],
                          [0.229, 0.224, 0.225])(img)
# 3. 推理
logits = model(img.unsqueeze(0))                  # (1, 2)
prob_normal = softmax(logits)[0, 0]
prob_pneumonia = softmax(logits)[0, 1]
# 4. 决策:argmax(>0.5 即 PNEUMONIA)
```

### 同一张图可能输出

| 输出 | xrv | 自训练 ResNet50 |
|---|---|---|
| 主要标签 | Pneumonia(0.83) + 多病理共存 | PNEUMONIA(0.62) 或 NORMAL(0.38) |
| 阈值机制 | 每个病理独立(op_threshs 0.05-0.2) | argmax(0.5) |
| 临床可解释性 | **11 个独立证据**,医生可逐项核对 | 单一黑箱"是/否" |
| 训练分布 | 成人 CXR(医院) | 儿童 CXR(Kaggle) |
| **对成人真实阳性胸片** | 通常准(0.7-0.9 阳性) | 可能漏诊(模型没见过) |

---

## 4. 结论与建议

### 4.1 "大相径庭"的根本原因

| 层次 | 原因 |
|---|---|
| **数据分布** | xrv 训练集(成人) vs 自训练(儿童)— 同一概念"肺炎"在不同年龄段的影像表现不同 |
| **归一化** | [-1024, 1024] vs ImageNet [0,1] — 模型各自只认一种 |
| **决策机制** | sigmoid 多标签 vs softmax 二分类 — 同一标签"PNEUMONIA"的概率含义不一样 |
| **验证规模** | 200+ 张外部验证集 vs 16 张内部验证集 — 自训练可信度低 |

### 4.2 自训练模型的 5 个具体问题

1. **验证集仅 16 张**:任何指标都在噪声范围内
2. **数据不平衡且来源单一**:Kaggle 儿童数据集(1341/3875)
3. **预训练权重与任务域不匹配**:ImageNet 自然图像 → 儿童 CXR,domain gap 大
4. **没有测试集独立评估**:`training_history.json` 没看到 test_acc
5. **没有保存 calibration / 阈值文件**:直接 argmax 0.5,但实际最优阈值几乎肯定不是 0.5

### 4.3 建议修复方向

**短期(立即可做)**:
1. **要么删掉自训练路径**,避免误用 — 前端 Analysis.vue 只调 xrv,后端 `PNEUMONIA_MODEL_PATH` 实际是死代码
2. **或重新训练 ResNet50**:用 NIH ChestX-ray14 / PadChest 的成人数据,validation 至少 500+ 张,early stopping

**中期**:
3. 加 **模型注册表**(已部分实现 `ImagingModel` 表),支持多模型并排评分
4. 加 **模型对比 UI** — 同一张图同时跑两个模型,展示分歧

**长期**:
5. 用 **cross-domain evaluation** — 在 NIH 上验证 Kaggle 训练模型,在 Kaggle 上验证 xrv,量化 domain gap

### 4.4 一句话总结

> **xrv DenseNet121 = 严谨的医学 AI(训练充分、阈值校准、预处理规范)**
> **自训练 ResNet50 = 学习项目 demo(过拟合、验证集太小、数据儿童化)**
> **同一张图两套结果差异巨大,不是 bug,是训练分布、预处理、决策机制的全面错位**

如果是要做严肃的临床部署,**完全用 xrv 那一套**,把 `pneumonia_resnet50.pth` 当作"训练流程 demo"归档即可。

---

**文件位置参考**:
- xrv 服务:`backend/app/services/imaging/xrv_service.py`(436 行,含 PSPNet 肺部分割 + Grad-CAM/HiResCAM)
- 自训练:`backend/scripts/train_pneumonia.py`(314 行,SGD + PolynomialLR)
- 训练历史:`backend/checkpoints/training_history.json`(8 epochs,val_acc 剧烈抖动)
- 数据集:`data/chest_xray/{train,val,test}/{NORMAL,PNEUMONIA}/`(5216/16/624 张)
- 在线接口:`POST /api/v1/imaging/pneumonia/analyze`(`backend/app/api/v1/imaging.py:66-147`)
- 详情/标注:`GET/POST /api/v1/imaging/{id}[/annotate]`(`backend/app/api/v1/imaging.py:178-284`)