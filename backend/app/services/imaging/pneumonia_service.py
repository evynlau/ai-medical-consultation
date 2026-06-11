"""胸部 X 光多标签诊断服务 - torchxrayvision DenseNet121

- 模型: densenet121-res224-rsna / densenet121-res224-all (18 维多标签 sigmoid)
- 主任务: 二分类 (PNEUMONIA vs NORMAL) — Pneumonia 索引
- 副任务: 18 维多标签全报告,支持同时为多个病理生成热力图
- 肺部分割: PSPNet 限制热力图到双肺内
"""
import io
import base64
import time
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from app.services.imaging.base import BaseImagingService
from app.utils.logger import logger


# 中文标签映射
PATHOLOGY_LABELS_CN = {
    "Atelectasis": "肺不张",
    "Consolidation": "实变",
    "Infiltration": "浸润",
    "Pneumothorax": "气胸",
    "Edema": "肺水肿",
    "Emphysema": "肺气肿",
    "Fibrosis": "肺纤维化",
    "Effusion": "胸腔积液",
    "Pneumonia": "肺炎",
    "Pleural_Thickening": "胸膜增厚",
    "Cardiomegaly": "心影增大",
    "Nodule": "结节",
    "Mass": "肿块",
    "Hernia": "膈疝",
    "Lung Lesion": "肺内病变",
    "Fracture": "骨折",
    "Lung Opacity": "肺浑浊",
    "Enlarged Cardiomediastinum": "纵隔增宽",
}

CLASS_NAMES = ["NORMAL", "PNEUMONIA"]
CLASS_LABELS_CN = {"NORMAL": "正常", "PNEUMONIA": "肺炎"}


class PneumoniaService(BaseImagingService):
    """胸部 X 光多标签诊断服务"""

    def __init__(self, model_path: str = "./checkpoints/pneumonia_resnet50.pth"):
        super().__init__(model_path)
        self.config = {
            "image_size": 224,
            "classes": CLASS_NAMES,
            "model_version": "densenet121-rsna+densenet121-chex",
            # 主分类模型: RSNA 预训练,在 chest_xray 上 79.88% Acc
            "xrv_weights": "densenet121-res224-rsna",
            # 多标签热力图模型: CheXpert 预训练,11 维有效类别,82% Acc
            # 比 all-model (62%) 区分度好很多
            "xrv_multi_weights": "densenet121-res224-chex",
            "input_resolution": 224,
            # chest_xray 上 Youden 校准: RSNA 用 0.620, CheX 用 0.590
            "pneumonia_threshold": 0.620,
            "chex_pneumonia_threshold": 0.590,
        }
        self._xrv_model = None  # RSNA: 二分类主诊断
        self._xrv_multi = None  # all-model: 18 维多热力图
        self._xrv_transform = None
        self._init_xrv_transform()
        self.load_model()

    def _init_xrv_transform(self):
        """初始化 torchxrayvision 官方预处理链"""
        import torchxrayvision as xrv
        import torchvision
        self._xrv_transform = torchvision.transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(224),
        ])

    def _pil_to_xrv_tensor(self, image: Image.Image) -> torch.Tensor:
        """PIL Image -> xrv 标准 tensor (1, 1, 224, 224) float32"""
        import torchxrayvision as xrv
        gray = image if image.mode == "L" else image.convert("L")
        img = np.asarray(gray).astype(np.float32)
        img = xrv.utils.normalize(img, 255)  # 0-255 -> [-1024, 1024]
        img = self._xrv_transform(img[None, :, :])[0]  # (1, 224, 224)
        return torch.from_numpy(img).unsqueeze(0).unsqueeze(0)

    def load_model(self):
        """加载双模型:
        - RSNA 模型: 二分类主诊断 (Acc 78.68% on chest_xray)
        - all-model: 18 维多标签,用于多类别 Grad-CAM 可视化
        """
        import torchxrayvision as xrv
        logger.info(f"加载 RSNA 模型 (二分类): {self.config['xrv_weights']}")
        self._xrv_model = xrv.models.DenseNet(weights=self.config["xrv_weights"])
        self._xrv_model.to(self.device)
        self._xrv_model.eval()

        self.config["all_pathologies"] = self._xrv_model.pathologies
        self.config["pneumonia_idx"] = self._xrv_model.pathologies.index("Pneumonia")
        self.config["op_threshs"] = {
            self._xrv_model.pathologies[i]: float(self._xrv_model.op_threshs[i].item())
            for i in range(len(self._xrv_model.pathologies))
            if self._xrv_model.pathologies[i]
        }
        logger.info(
            f"✅ RSNA 模型加载完成. Pneumonia idx: {self.config['pneumonia_idx']}"
        )

        logger.info(f"加载多标签模型 (Grad-CAM): {self.config['xrv_multi_weights']}")
        self._xrv_multi = xrv.models.DenseNet(weights=self.config["xrv_multi_weights"])
        self._xrv_multi.to(self.device)
        self._xrv_multi.eval()
        logger.info(f"✅ 多标签模型加载完成. 18 病理已就绪")

        # 兼容旧接口
        self.model = self._xrv_model

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        x = self._pil_to_xrv_tensor(image)
        return x.to(self.device)

    def predict(self, image: Image.Image) -> Dict[str, Any]:
        """推理 - 18 维多标签 (RSNA 模型只 Pneumonia+Lung Opacity 有效)"""
        start_time = time.time()
        x = self.preprocess(image)
        with torch.no_grad():
            outputs = self._xrv_model(x)

        inference_time_ms = int((time.time() - start_time) * 1000)

        all_probs = torch.sigmoid(outputs[0]).cpu().numpy()
        pathologies = self._xrv_model.pathologies

        pneumonia_idx = self.config["pneumonia_idx"]
        pneumonia_prob = float(all_probs[pneumonia_idx])
        pneumonia_thresh = self.config["pneumonia_threshold"]

        predicted_class = "PNEUMONIA" if pneumonia_prob > pneumonia_thresh else "NORMAL"
        confidence = pneumonia_prob if predicted_class == "PNEUMONIA" else (1 - pneumonia_prob)

        # RSNA 模型只 Pneumonia + Lung Opacity 2 类有效
        all_pathology_scores = {
            pathologies[i]: {
                "probability": float(all_probs[i]),
                "threshold": self.config["op_threshs"][pathologies[i]],
                "positive": bool(all_probs[i] > self.config["op_threshs"][pathologies[i]]),
                "label_cn": PATHOLOGY_LABELS_CN.get(pathologies[i], pathologies[i]),
            }
            for i in range(len(pathologies)) if pathologies[i]
        }

        top_findings = [k for k, v in all_pathology_scores.items() if v["positive"]]

        return {
            "prediction": predicted_class,
            "prediction_idx": 1 if predicted_class == "PNEUMONIA" else 0,
            "prediction_label": CLASS_LABELS_CN[predicted_class],
            "probabilities_dict": {
                "NORMAL": float(1 - pneumonia_prob),
                "PNEUMONIA": float(pneumonia_prob),
            },
            "confidence": confidence,
            "pneumonia_probability": pneumonia_prob,
            "pneumonia_threshold": pneumonia_thresh,
            "all_pathology_scores": all_pathology_scores,
            "top_findings": top_findings,
            "model_version": self.config["model_version"],
            "inference_time_ms": inference_time_ms,
        }

    def predict_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"无法解析图像: {e}")
        result = self.predict(image)
        result["original_image_size"] = image.size
        return result

    def predict_with_gradcam(
        self,
        image: Image.Image,
        method: str = "hirescam",
        target_class_idxs: Optional[List[int]] = None,
        cam_source: str = "multi",  # "rsna" 或 "multi"
    ) -> Tuple[Dict[str, Any], Dict[int, np.ndarray]]:
        """推理 + 多类别热力图

        Args:
            target_class_idxs: 要可视化的类别索引列表,None=默认只对 Pneumonia
            cam_source: "rsna" 用 RSNA 模型 (2 维输出,只覆盖 Pneumonia/Lung Opacity)
                        "multi" 用 all-model (18 维全病理,推荐)
        """
        result = self.predict(image)  # RSNA 模型的二分类预测

        if target_class_idxs is None:
            target_class_idxs = [self.config["pneumonia_idx"]]

        try:
            from app.services.imaging.gradcam import generate_cam_for_classes
            cam_model = self._xrv_multi if cam_source == "multi" else self._xrv_model
            cam_dict = generate_cam_for_classes(
                model=cam_model,
                image=image,
                transform=self,
                device=self.device,
                target_class_idxs=target_class_idxs,
                method=method,
            )
            return result, cam_dict
        except Exception as e:
            logger.warning(f"热力图生成失败 ({method}): {e}")
            return result, {}

    def predict_from_bytes_with_gradcam(
        self,
        image_bytes: bytes,
        method: str = "hirescam",
        target_class_idxs: Optional[List[int]] = None,
        cam_source: str = "multi",
    ) -> Dict[str, Any]:
        """从字节流推理 + 多类别热力图

        Args:
            target_class_idxs: 类别索引列表
            cam_source: "rsna" (Pneumonia+Opacity 2 类) 或 "multi" (18 类多标签)
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError(f"无法解析图像: {e}")

        result, cam_dict = self.predict_with_gradcam(
            image, method=method, target_class_idxs=target_class_idxs, cam_source=cam_source
        )
        result["original_image_size"] = image.size

        # 编码原图 (PIL RGB)
        buffered_orig = io.BytesIO()
        rgb = image.convert("RGB") if image.mode != "RGB" else image
        rgb.save(buffered_orig, format="PNG")
        result["original_image"] = (
            f"data:image/png;base64,"
            f"{base64.b64encode(buffered_orig.getvalue()).decode('utf-8')}"
        )

        # 肺部分割 mask (生成一次,多张热力图共用)
        lung_mask = None
        if cam_dict:
            from app.services.imaging.lung_segmentation import segment_lungs_pspnet
            lung_mask = segment_lungs_pspnet(image, device="cpu")
            result["lung_mask_applied"] = lung_mask is not None

        # 每张热力图单独编码
        # 路径名来源取决于 cam_source
        if cam_source == "multi":
            path_names = self._xrv_multi.pathologies
        else:
            path_names = self._xrv_model.pathologies

        from app.services.imaging.gradcam import heatmap_to_base64, heatmap_to_base64_raw
        result["gradcams"] = []
        for idx, cam in cam_dict.items():
            cam_masked = cam * lung_mask if lung_mask is not None else cam
            pathology_name = path_names[idx]
            # 每次都重新算 multi scores (避免缓存污染)
            multi_scores = self._multi_pathology_scores(image)
            score_info = multi_scores.get(pathology_name)
            if score_info is None:
                score_info = {
                    "probability": 0.0,
                    "threshold": 0.5,
                    "positive": False,
                    "label_cn": PATHOLOGY_LABELS_CN.get(pathology_name, pathology_name),
                }
            result["gradcams"].append({
                "class_idx": int(idx),
                "pathology": pathology_name,
                "label_cn": score_info["label_cn"],
                "probability": score_info["probability"],
                "threshold": score_info["threshold"],
                "positive": score_info["positive"],
                "gradcam": heatmap_to_base64(cam_masked, image.size),
                "gradcam_raw": heatmap_to_base64_raw(cam_masked),
            })

        # 兼容旧字段 (第一张)
        if result["gradcams"]:
            main = result["gradcams"][0]
            result["gradcam"] = main["gradcam"]
            result["gradcam_raw"] = main["gradcam_raw"]
        else:
            result["gradcam"] = None
            result["gradcam_raw"] = None

        # 全 18 维多标签报告 (CheX 11 维)
        result["multi_pathology_scores"] = multi_scores

        return result

    def _multi_pathology_scores(self, image: Image.Image) -> Dict[str, Dict[str, Any]]:
        """用 CheXpert 模型推理,返回 11 维有效病理报告"""
        x = self._pil_to_xrv_tensor(image).to(self.device)
        with torch.no_grad():
            outputs = self._xrv_multi(x)
        probs = torch.sigmoid(outputs[0]).cpu().numpy()
        paths = self._xrv_multi.pathologies
        op_threshs = self._xrv_multi.op_threshs.cpu().numpy()
        result = {}
        for i, p in enumerate(paths):
            if not p:
                continue
            result[p] = {
                "probability": float(probs[i]),
                "threshold": float(op_threshs[i]),
                "positive": bool(probs[i] > op_threshs[i]),
                "label_cn": PATHOLOGY_LABELS_CN.get(p, p),
            }
        # 用 CheX 校准阈值重判 Pneumonia (用于报告一致性)
        if "Pneumonia" in result:
            chex_thresh = self.config.get("chex_pneumonia_threshold", 0.590)
            result["Pneumonia"]["threshold"] = chex_thresh
            result["Pneumonia"]["positive"] = bool(result["Pneumonia"]["probability"] > chex_thresh)
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
