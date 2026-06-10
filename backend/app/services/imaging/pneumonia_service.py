"""肺炎诊断服务 - ResNet50 二分类"""
import io
import base64
import time
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms, models
from torchvision.models import ResNet50_Weights
from PIL import Image

from app.services.imaging.base import BaseImagingService
from app.utils.logger import logger


# 类别映射
CLASS_NAMES = ["NORMAL", "PNEUMONIA"]
CLASS_LABELS_CN = {"NORMAL": "正常", "PNEUMONIA": "肺炎"}


class PneumoniaService(BaseImagingService):
    """肺炎X光片诊断服务"""

    def __init__(self, model_path: str = "./checkpoints/pneumonia_resnet50.pth"):
        super().__init__(model_path)
        # ImageNet 预训练参数
        self.config = {
            "image_size": 224,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
            "classes": CLASS_NAMES,
            "model_version": "resnet50_v1.0",
        }
        self.transform = None
        self._init_transform()
        self.load_model()

    def _init_transform(self):
        """初始化图像变换"""
        self.transform = transforms.Compose([
            transforms.Resize((self.config["image_size"], self.config["image_size"])),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=self.config["mean"],
                std=self.config["std"],
            ),
        ])

    def load_model(self):
        """加载模型权重 - 如果本地没有，使用预训练 ImageNet 模型作为基础"""
        logger.info(f"加载肺炎模型: {self.model_path}")

        # 构建模型
        self.model = models.resnet50(weights=None)
        in_features = self.model.fc.in_features
        self.model.fc = nn.Linear(in_features, 2)  # 二分类

        # 尝试加载本地权重
        model_file = Path(self.model_path)
        if model_file.exists():
            try:
                checkpoint = torch.load(model_file, map_location=self.device)
                if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                    self.model.load_state_dict(checkpoint["model_state_dict"])
                    if "config" in checkpoint:
                        self.config.update(checkpoint["config"])
                    logger.info(f"✅ 加载本地权重: {self.model_path}")
                else:
                    self.model.load_state_dict(checkpoint)
                    logger.info(f"✅ 加载本地权重: {self.model_path}")
            except Exception as e:
                logger.warning(f"加载本地权重失败 ({e}),使用随机初始化模型")
        else:
            logger.warning(f"⚠️ 模型文件不存在: {self.model_path}，使用 ImageNet 预训练骨干")

            # 使用 ImageNet 预训练权重替换骨干
            try:
                pretrained = models.resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
                # 仅替换骨干权重（除了 fc 层）
                pretrained_dict = pretrained.state_dict()
                model_dict = self.model.state_dict()
                # 过滤掉 fc 层
                pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict and "fc" not in k}
                model_dict.update(pretrained_dict)
                self.model.load_state_dict(model_dict)
                logger.info("✅ 使用 ImageNet 预训练骨干（仅卷积层，全连接层随机初始化）")
            except Exception as e:
                logger.error(f"ImageNet 预训练加载失败: {e}")

        self.model.to(self.device)
        self.model.eval()

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        """图像预处理"""
        # 确保是 RGB 模式
        if image.mode != "RGB":
            image = image.convert("RGB")
        # 应用变换
        tensor = self.transform(image)
        # 增加 batch 维度
        tensor = tensor.unsqueeze(0)
        return tensor.to(self.device)

    def predict(self, image: Image.Image) -> Dict[str, Any]:
        """推理"""
        start_time = time.time()

        # 预处理
        tensor = self.preprocess(image)

        # 模型推理
        with torch.no_grad():
            logits = self.model(tensor)

        inference_time_ms = int((time.time() - start_time) * 1000)

        # 后处理
        result = self._postprocess(logits, inference_time_ms)

        # 添加业务字段
        predicted_class = CLASS_NAMES[result["prediction_idx"]]
        result.update({
            "prediction": predicted_class,
            "prediction_label": CLASS_LABELS_CN[predicted_class],
            "probabilities_dict": {
                CLASS_NAMES[i]: float(result["probabilities"][i])
                for i in range(len(CLASS_NAMES))
            },
            "model_version": self.config["model_version"],
        })

        return result

    def predict_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        """从字节流推理"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"无法解析图像: {e}")

        result = self.predict(image)
        result["original_image_size"] = image.size
        return result

    def predict_with_gradcam(self, image: Image.Image, method: str = "hirescam") -> Tuple[Dict[str, Any], Optional[np.ndarray]]:
        """推理 + 热力图（HiResCAM 更精确，Grad-CAM 兼容性更好）

        Args:
            image: PIL Image
            method: 'hirescam' 或 'gradcam'

        Returns:
            (result, heatmap)
        """
        # 先进行预测
        result = self.predict(image)

        try:
            from app.services.imaging.gradcam import generate_hirescam, generate_gradcam

            # 根据 method 选择算法
            if method == "hirescam":
                heatmap = generate_hirescam(
                    model=self.model,
                    image=image,
                    transform=self.transform,
                    device=self.device,
                )
            else:
                heatmap = generate_gradcam(
                    model=self.model,
                    image=image,
                    transform=self.transform,
                    device=self.device,
                )
            return result, heatmap
        except Exception as e:
            logger.warning(f"热力图生成失败 ({method}): {e}")
            return result, None

    def predict_from_bytes_with_gradcam(self, image_bytes: bytes, method: str = "hirescam") -> Dict[str, Any]:
        """从字节流推理 + 热力图

        Args:
            image_bytes: 图像字节流
            method: 'hirescam' 或 'gradcam'
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"无法解析图像: {e}")

        result, heatmap = self.predict_with_gradcam(image, method=method)
        result["original_image_size"] = image.size

        # 编码原始图像（供前端独立显示+叠加）
        buffered_orig = io.BytesIO()
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(buffered_orig, format="PNG")
        orig_base64 = base64.b64encode(buffered_orig.getvalue()).decode("utf-8")
        result["original_image"] = f"data:image/png;base64,{orig_base64}"

        if heatmap is not None:
            from app.services.imaging.gradcam import heatmap_to_base64, heatmap_to_base64_raw
            result["gradcam"] = heatmap_to_base64(heatmap, image.size)
            result["gradcam_raw"] = heatmap_to_base64_raw(heatmap)

        return result


# 单例
_pneumonia_service: Optional[PneumoniaService] = None


def get_pneumonia_service() -> PneumoniaService:
    global _pneumonia_service
    if _pneumonia_service is None:
        from app.core.config import settings
        model_path = getattr(settings, "PNEUMONIA_MODEL_PATH", "./checkpoints/pneumonia_resnet50.pth")
        _pneumonia_service = PneumoniaService(model_path=model_path)
    return _pneumonia_service