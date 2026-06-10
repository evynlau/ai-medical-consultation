"""肺炎诊断服务 - torchxrayvision DenseNet121 (RSNA 预训练)

使用 mlmed/torchxrayvision 的 densenet121-res224-rsna 权重
- 在 RSNA Pneumonia Challenge 数据集预训练
- 18 维多标签输出,sigmoid 概率 (非 softmax)
- 我们只关心 'Pneumonia' 索引 (idx=8) 做二分类判断
- Grad-CAM 直接对 Pneumonia 索引计算,空间分辨率更好
"""
import io
import base64
import time
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

from app.services.imaging.base import BaseImagingService
from app.utils.logger import logger


# 类别映射
CLASS_NAMES = ["NORMAL", "PNEUMONIA"]
CLASS_LABELS_CN = {"NORMAL": "正常", "PNEUMONIA": "肺炎"}


class PneumoniaService(BaseImagingService):
    """肺炎X光片诊断服务 (torchxrayvision DenseNet121)"""

    def __init__(self, model_path: str = "./checkpoints/pneumonia_resnet50.pth"):
        super().__init__(model_path)
        # 18 类多标签 (与 densenet121-res224-rsna.targets 对应)
        # RSNA 模型在 Pneumonia Detection Challenge 上专门优化,二分类表现优于 all-model
        self.config = {
            "image_size": 224,
            "classes": CLASS_NAMES,
            "model_version": "densenet121-rsna-v1.4",
            "xrv_weights": "densenet121-res224-rsna",
            "input_resolution": 224,
            # 用 chest_xray train+val 集 (1200 张) Youden 校准得到
            # 0.5 阈值会全判 PNEUMONIA (Sens=1, Spec=0)
            # 0.620 阈值: Acc=0.798, Sens=0.868, Spec=0.728
            "pneumonia_threshold": 0.620,
        }
        self._xrv_model = None
        self._xrv_transform = None
        self._init_xrv_transform()
        self.load_model()

    def _init_xrv_transform(self):
        """初始化 torchxrayvision 官方预处理链"""
        import torchxrayvision as xrv
        import torchvision
        # 官方推荐:X-Ray 中心裁剪 + 缩放
        self._xrv_transform = torchvision.transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(224),
        ])

    def _pil_to_xrv_tensor(self, image: Image.Image) -> torch.Tensor:
        """PIL Image -> xrv 标准 tensor (1, 1, 224, 224) float32"""
        import torchxrayvision as xrv
        # 灰度
        gray = image if image.mode == "L" else image.convert("L")
        img = np.asarray(gray).astype(np.float32)
        # xrv 归一化: 0-255 -> [-1024, 1024]
        img = xrv.utils.normalize(img, 255)
        # (C, H, W) -> (1, 224, 224)
        img = self._xrv_transform(img[None, :, :])[0]
        return torch.from_numpy(img).unsqueeze(0).unsqueeze(0)  # (1, 1, 224, 224)

    def load_model(self):
        """加载 torchxrayvision DenseNet121 (RSNA 预训练)"""
        logger.info(f"加载 torchxrayvision DenseNet121 (RSNA): {self.config['xrv_weights']}")
        try:
            import torchxrayvision as xrv
            self._xrv_model = xrv.models.DenseNet(weights=self.config["xrv_weights"])
            self._xrv_model.to(self.device)
            self._xrv_model.eval()
            # pathologies 是 xrv 自带属性
            self.config["all_pathologies"] = self._xrv_model.pathologies
            self.config["pneumonia_idx"] = self._xrv_model.pathologies.index("Pneumonia")
            logger.info(
                f"✅ 加载完成. Pneumonia 索引: {self.config['pneumonia_idx']}, "
                f"targets: {[t for t in self._xrv_model.pathologies if t]}"
            )
        except Exception as e:
            logger.error(f"加载 xrv DenseNet 失败: {e}")
            raise

        # 兼容旧接口:把 xrv 包装成 torchvision-style
        self.model = self._xrv_model

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        """图像预处理 (返回 xrv tensor)"""
        x = self._pil_to_xrv_tensor(image)
        return x.to(self.device)

    def predict(self, image: Image.Image) -> Dict[str, Any]:
        """推理 - 18 维多标签输出"""
        start_time = time.time()
        x = self.preprocess(image)
        with torch.no_grad():
            outputs = self._xrv_model(x)  # (1, 18)

        inference_time_ms = int((time.time() - start_time) * 1000)

        # 取 Pneumonia 索引的概率
        pneumonia_idx = self.config["pneumonia_idx"]
        pneumonia_prob = float(torch.sigmoid(outputs[0, pneumonia_idx]).item())

        # 阈值:用 chest_xray 自校准的 Youden 阈值 (0.620)
        # 比 RSNA 官方 op_threshs(0.135) 和 0.5 都更准
        pneumonia_thresh = self.config["pneumonia_threshold"]

        # 二分类:Pneumonia 概率 > 优化阈值 => PNEUMONIA
        predicted_class = "PNEUMONIA" if pneumonia_prob > pneumonia_thresh else "NORMAL"
        probabilities_dict = {
            "NORMAL": float(1 - pneumonia_prob),
            "PNEUMONIA": float(pneumonia_prob),
        }
        confidence = pneumonia_prob if predicted_class == "PNEUMONIA" else (1 - pneumonia_prob)

        # 多标签原始输出 (供医生参考)
        all_outputs = torch.sigmoid(outputs[0]).cpu().numpy()
        all_pathologies = self._xrv_model.pathologies
        pathology_scores = {
            all_pathologies[i]: float(all_outputs[i])
            for i in range(len(all_pathologies)) if all_pathologies[i]
        }

        return {
            "prediction": predicted_class,
            "prediction_idx": 1 if predicted_class == "PNEUMONIA" else 0,
            "prediction_label": CLASS_LABELS_CN[predicted_class],
            "probabilities": [probabilities_dict["NORMAL"], probabilities_dict["PNEUMONIA"]],
            "probabilities_dict": probabilities_dict,
            "confidence": confidence,
            "pneumonia_probability": pneumonia_prob,
            "pneumonia_threshold": pneumonia_thresh,
            "all_pathology_scores": pathology_scores,
            "model_version": self.config["model_version"],
            "inference_time_ms": inference_time_ms,
        }

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
        """推理 + 热力图 (Grad-CAM/HiResCAM 都对 Pneumonia 索引计算)

        Args:
            image: PIL Image
            method: 'hirescam' 或 'gradcam'
        """
        result = self.predict(image)

        try:
            from app.services.imaging.gradcam import generate_hirescam, generate_gradcam

            if method == "hirescam":
                heatmap = generate_hirescam(
                    model=self._xrv_model,
                    image=image,
                    transform=self,
                    device=self.device,
                    target_class_idx=self.config["pneumonia_idx"],
                )
            else:
                heatmap = generate_gradcam(
                    model=self._xrv_model,
                    image=image,
                    transform=self,
                    device=self.device,
                    target_class_idx=self.config["pneumonia_idx"],
                )
            return result, heatmap
        except Exception as e:
            logger.warning(f"热力图生成失败 ({method}): {e}")
            return result, None

    def predict_from_bytes_with_gradcam(self, image_bytes: bytes, method: str = "hirescam") -> Dict[str, Any]:
        """从字节流推理 + 热力图"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"无法解析图像: {e}")

        result, heatmap = self.predict_with_gradcam(image, method=method)
        result["original_image_size"] = image.size

        # 编码原始图像
        buffered_orig = io.BytesIO()
        if image.mode != "RGB":
            rgb = image.convert("RGB")
        else:
            rgb = image
        rgb.save(buffered_orig, format="PNG")
        orig_base64 = base64.b64encode(buffered_orig.getvalue()).decode("utf-8")
        result["original_image"] = f"data:image/png;base64,{orig_base64}"

        # 应用 PSPNet 肺部分割,限制热力图到双肺内
        if heatmap is not None:
            from app.services.imaging.lung_segmentation import segment_lungs_pspnet
            lung_mask = segment_lungs_pspnet(image, device="cpu")
            if lung_mask is not None:
                heatmap_masked = heatmap * lung_mask
                logger.info(
                    f"肺部分割后热力图强度: "
                    f"原图 {heatmap.sum()} -> 肺内 {heatmap_masked.sum()}"
                )
                heatmap = heatmap_masked
            from app.services.imaging.gradcam import heatmap_to_base64, heatmap_to_base64_raw
            result["gradcam"] = heatmap_to_base64(heatmap, image.size)
            result["gradcam_raw"] = heatmap_to_base64_raw(heatmap)
            result["lung_mask_applied"] = lung_mask is not None

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
