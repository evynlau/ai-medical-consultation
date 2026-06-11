"""torchxrayvision 官方范式多分类胸片分析服务

参考:
- https://github.com/mlmed/torchxrayvision/blob/main/scripts/transfer_learning.ipynb
- https://github.com/mlmed/torchxrayvision/blob/main/scripts/model_calibrate.py
- https://github.com/mlmed/torchxrayvision/blob/main/scripts/process_image.py

核心要点 (官方 API):
  model = xrv.models.get_model("densenet121-res224-chex", apply_sigmoid=True)
  out = model(img)  # 已经是校准后的概率,不需要再 sigmoid
  out[i] 对应 model.pathologies[i] 类的概率

输出结构 (按 xrv 范式):
  - 11 个 pathologies (CheX 权重)
  - 每个 pathology 独立 (prob, threshold, positive)
  - 校准阈值通过 ROC Youden index 计算
  - Grad-CAM 走 xrv.models 兼容接口
"""
import io
import base64
import time
import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from app.services.imaging.base import BaseImagingService
from app.utils.logger import logger


# 中文标签映射 (完整 18 类, 缺失的填 None)
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

# chest_xray 校准结果 (从 xrv 官方 ROC Youden 流程算出来)
_CALIBRATION_FILE = Path(__file__).parent / "xrv_calibration.json"


class XRVAnalysisService(BaseImagingService):
    """torchxrayvision 多分类胸片分析服务 (官方范式)"""

    def __init__(self, model_path: str = ""):
        # 父类只用于兼容 BaseImagingService 接口
        super().__init__(model_path or "xrv-densenet121-res224-chex")
        # 官方范式: get_model 加载预训练模型
        self._xrv_model = None
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # PSPNet 用于肺部分割 (限制 Grad-CAM)
        self._pspnet = None
        self._calibration = self._load_calibration()
        self.load_model()
        self._load_pspnet()

    def _load_calibration(self) -> Dict[str, Any]:
        """加载校准结果"""
        if _CALIBRATION_FILE.exists():
            with open(_CALIBRATION_FILE) as f:
                return json.load(f)
        return {}

    def _load_pspnet(self):
        """懒加载 PSPNet (用于肺部分割)"""
        try:
            import torchxrayvision as xrv
            self._pspnet = xrv.baseline_models.chestx_det.PSPNet()
            self._pspnet.to(self._device)
            self._pspnet.eval()
        except Exception as e:
            logger.warning(f"PSPNet 加载失败: {e}")

    def load_model(self):
        """按 xrv 官方方式加载模型"""
        import torchxrayvision as xrv
        logger.info("按 xrv 官方范式加载: densenet121-res224-chex, apply_sigmoid=True")
        # 关键: apply_sigmoid=True 让模型直接输出 [0,1] 校准概率
        self._xrv_model = xrv.models.get_model(
            "densenet121-res224-chex",
            apply_sigmoid=True,
        )
        self._xrv_model.to(self._device)
        self._xrv_model.eval()
        # 关闭预训练 op_threshs (让我们自己校准)
        if hasattr(self._xrv_model, 'op_threshs'):
            self._xrv_model.op_threshs = None
        logger.info(
            f"✅ 加载完成. {len([p for p in self._xrv_model.pathologies if p])} 病理: "
            f"{[p for p in self._xrv_model.pathologies if p]}"
        )
        # 兼容旧接口
        self.model = self._xrv_model

    # =================== 图像预处理 (xrv 官方 transform) ===================

    def _preprocess(self, image: Image.Image) -> torch.Tensor:
        """按 xrv 官方 transform: normalize + XRayCenterCrop + XRayResizer(224)

        输出 4D (1, 1, 224, 224) 适配 features()/classifier()
        """
        import torchxrayvision as xrv
        import torchvision
        gray = image.convert("L") if image.mode != "L" else image
        arr = np.asarray(gray).astype(np.float32)
        arr = xrv.utils.normalize(arr, 255)  # 0-255 -> [-1024, 1024]
        # 官方 transform: 输入 (1, H, W) -> 输出 (1, 224, 224) (保留 channel 维)
        trans = torchvision.transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(224),
        ])
        arr_t = trans(arr[None, :, :])  # (1, 224, 224) - 不要 [0] 拿掉 channel
        return torch.from_numpy(arr_t).unsqueeze(0)  # (1, 1, 224, 224)

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        return self._preprocess(image).to(self._device)

    # =================== 推理 (xrv 官方范式) ===================

    def predict(self, image: Image.Image) -> Dict[str, Any]:
        """xrv 官方推理: model(img) 直接输出概率"""
        start = time.time()
        x = self.preprocess(image)
        with torch.no_grad():
            # apply_sigmoid=True, 输出 (1, 18) 概率
            probs = self._xrv_model(x).cpu().numpy()[0]
        inference_ms = int((time.time() - start) * 1000)

        # 校准阈值
        thresholds = self._get_thresholds()

        # 构造 18 维结果 (空病理填 None)
        results = []
        positive_count = 0
        for idx, pathology in enumerate(self._xrv_model.pathologies):
            if not pathology:
                continue
            prob = float(probs[idx])
            thresh = thresholds.get(pathology, 0.5)
            is_positive = prob > thresh
            if is_positive:
                positive_count += 1
            results.append({
                "index": idx,
                "pathology": pathology,
                "label_cn": PATHOLOGY_LABELS_CN.get(pathology, pathology),
                "probability": prob,
                "threshold": thresh,
                "positive": is_positive,
            })

        # 主诊断: 找阳性概率最高的
        positive_results = [r for r in results if r["positive"]]
        if positive_results:
            main = max(positive_results, key=lambda r: r["probability"] / (r["threshold"] + 1e-8))
            main_diagnosis = main["pathology"]
            main_label_cn = main["label_cn"]
            confidence = main["probability"]
        else:
            # 没有阳性, 主诊断 = 概率最低的 (最正常)
            main = min(results, key=lambda r: r["probability"])
            main_diagnosis = "NORMAL"
            main_label_cn = "未见明显异常"
            confidence = 1.0 - main["probability"]

        return {
            "diagnosis": main_diagnosis,
            "diagnosis_cn": main_label_cn,
            "confidence": float(confidence),
            "positive_count": positive_count,
            "pathologies": results,
            "inference_time_ms": inference_ms,
            "model_name": str(self._xrv_model),
            "model_weights": "densenet121-res224-chex",
            "calibrated": bool(self._calibration),
        }

    def _get_thresholds(self) -> Dict[str, float]:
        """获取每个 pathology 的校准阈值

        优先级:
          1. 自己校准的 (chest_xray 上 ROC Youden for Pneumonia + xrv 自带 op_threshs for 其他)
          2. xrv 自带 op_threshs (PPV=80% 工作点)
          3. 兜底 0.5
        """
        # 1. 自己校准 (xrv_calibration.json)
        if self._calibration and self._calibration.get("op_threshs"):
            pathologies = self._xrv_model.pathologies
            threshs = self._calibration["op_threshs"]
            result = {}
            for i, p in enumerate(pathologies):
                if not p:
                    continue
                if i < len(threshs) and threshs[i] is not None:
                    result[p] = float(threshs[i])
                else:
                    result[p] = 0.5
            # Pneumonia 优先用我们在 chest_xray 上自校准的 Youden
            pneu_cal = self._calibration.get("Pneumonia", {})
            if "youden_threshold" in pneu_cal:
                result["Pneumonia"] = float(pneu_cal["youden_threshold"])
            return result
        # 2. xrv 自带
        if hasattr(self._xrv_model, 'op_threshs') and self._xrv_model.op_threshs is not None:
            threshs = self._xrv_model.op_threshs.cpu().numpy()
            return {
                p: float(threshs[i])
                for i, p in enumerate(self._xrv_model.pathologies)
                if p
            }
        # 3. 兜底
        return {p: 0.5 for p in self._xrv_model.pathologies if p}

    # =================== 肺部分割 (PSPNet, xrv 官方 baseline) ===================

    def _segment_lungs(self, image: Image.Image) -> Optional[np.ndarray]:
        """用 xrv 官方 PSPNet 分割双肺"""
        if self._pspnet is None:
            return None
        try:
            import torchxrayvision as xrv
            import torchvision
            gray = image.convert("L") if image.mode != "L" else image
            arr = np.asarray(gray).astype(np.float32)
            arr = xrv.utils.normalize(arr, 255)
            trans = torchvision.transforms.Compose([
                xrv.datasets.XRayCenterCrop(),
                xrv.datasets.XRayResizer(512),
            ])
            img_3d = arr[None, :, :]  # (1, H, W)
            arr_t = trans(img_3d)[0]  # (512, 512)
            x = torch.from_numpy(arr_t).unsqueeze(0).unsqueeze(0).to(self._device)
            with torch.no_grad():
                logits = self._pspnet(x)
                probs = torch.sigmoid(logits)[0].cpu().numpy()  # (14, 512, 512)

            # 合并双肺 (Left Lung=4, Right Lung=5)
            lung_mask = (probs[4] + probs[5]) > 0.5
            # 上采样回原图
            mask_pil = Image.fromarray(lung_mask.astype(np.uint8) * 255, mode="L")
            mask_pil = mask_pil.resize(image.size, Image.BILINEAR)
            return (np.asarray(mask_pil) > 127).astype(np.uint8)
        except Exception as e:
            logger.warning(f"PSPNet 肺部分割失败: {e}")
            return None

    # =================== Grad-CAM (xrv 兼容) ===================

    def gradcam_for_class(
        self,
        image: Image.Image,
        class_idx: int,
    ) -> Optional[np.ndarray]:
        """对单个 pathology 生成 Grad-CAM (HiResCAM)

        xrv DenseNet 内部结构 (apply_sigmoid=True):
          - features(x): (1, 1024, 7, 7)  -- 4D
          - classifier: nn.Linear(1024, 18)  -- 期望 2D 输入

        因此:
          1. features() 拿 4D 特征, retain_grad
          2. AdaptiveAvgPool2d + flatten -> 2D (1, 1024)
          3. classifier(2D) -> logits (1, 18)
          4. backward, 用 features * features.grad 算 CAM
        """
        try:
            x = self.preprocess(image)  # (1, 1, 224, 224)
            # 1. 拿 4D 特征
            features = self._xrv_model.features(x)  # (1, 1024, 7, 7)
            features.retain_grad()
            # 2. 4D -> 2D 池化展平
            pooled = F.adaptive_avg_pool2d(features, 1).flatten(1)  # (1, 1024)
            # 3. 走 classifier
            logits = self._xrv_model.classifier(pooled)  # (1, 18)

            # 4. 反向传播
            self._xrv_model.zero_grad()
            one_hot = torch.zeros_like(logits)
            one_hot[0][class_idx] = 1
            logits.backward(gradient=one_hot, retain_graph=False)

            if features.grad is None:
                return None

            # 5. HiResCAM: 激活 × 梯度 逐元素
            cam = (features * features.grad).detach()
            cam = cam.sum(dim=1, keepdim=True)  # (1, 1, 7, 7)
            cam = F.relu(cam)
            # 6. 上采样到原图大小
            cam = F.interpolate(cam, size=image.size[::-1], mode="bilinear", align_corners=False)
            cam = cam.squeeze().cpu().numpy()
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8) * 255
            return cam.astype(np.uint8)
        except Exception as e:
            logger.warning(f"Grad-CAM 失败: {e}")
            return None

    def predict_with_gradcam(
        self,
        image: Image.Image,
        target_classes: Optional[List[str]] = None,
        apply_lung_mask: bool = True,
    ) -> Dict[str, Any]:
        """完整推理 + 选中病理的 Grad-CAM 列表

        Args:
            target_classes: 要生成热力图的病理名列表,None=只对阳性病理生成
        """
        result = self.predict(image)
        image_size = image.size

        # 决定要可视化的病理
        if target_classes is None:
            # 默认: 所有阳性 + Pneumonia
            positive = [r for r in result["pathologies"] if r["positive"]]
            target_classes = [r["pathology"] for r in positive]
            if "Pneumonia" not in target_classes:
                target_classes.append("Pneumonia")

        # 编码原图
        buffered = io.BytesIO()
        rgb = image.convert("RGB") if image.mode != "RGB" else image
        rgb.save(buffered, format="PNG")
        original_b64 = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()

        # 肺部分割 mask (共用)
        lung_mask = self._segment_lungs(image) if apply_lung_mask else None

        # 为每个目标病理生成热力图
        gradcams = []
        for pathology in target_classes:
            if not pathology:
                continue
            try:
                class_idx = self._xrv_model.pathologies.index(pathology)
            except ValueError:
                continue
            cam = self.gradcam_for_class(image, class_idx)
            if cam is None:
                continue
            # 应用肺部分割
            if lung_mask is not None:
                cam_masked = cam * lung_mask
            else:
                cam_masked = cam

            # 编码叠加图 + 透明 PNG
            overlay_b64 = self._heatmap_overlay_b64(cam_masked, image_size)
            raw_b64 = self._heatmap_raw_b64(cam_masked)

            # 找对应的 pathology result
            p_info = next((r for r in result["pathologies"] if r["pathology"] == pathology), None)

            gradcams.append({
                "pathology": pathology,
                "label_cn": PATHOLOGY_LABELS_CN.get(pathology, pathology),
                "class_idx": class_idx,
                "probability": p_info["probability"] if p_info else 0.0,
                "threshold": p_info["threshold"] if p_info else 0.5,
                "positive": p_info["positive"] if p_info else False,
                "overlay": overlay_b64,
                "raw": raw_b64,
            })

        result["original_image"] = original_b64
        result["original_image_size"] = list(image_size)
        result["gradcams"] = gradcams
        result["lung_mask_applied"] = lung_mask is not None
        return result

    def predict_from_bytes_with_gradcam(
        self,
        image_bytes: bytes,
        target_classes: Optional[List[str]] = None,
        apply_lung_mask: bool = True,
    ) -> Dict[str, Any]:
        image = Image.open(io.BytesIO(image_bytes))
        return self.predict_with_gradcam(
            image, target_classes=target_classes, apply_lung_mask=apply_lung_mask
        )

    def predict_from_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        image = Image.open(io.BytesIO(image_bytes))
        result = self.predict(image)
        # 编码原图
        buffered = io.BytesIO()
        rgb = image.convert("RGB") if image.mode != "RGB" else image
        rgb.save(buffered, format="PNG")
        result["original_image"] = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()
        result["original_image_size"] = list(image.size)
        return result

    # =================== 图像编码工具 ===================

    def _heatmap_overlay_b64(self, heatmap: np.ndarray, size: tuple, opacity: float = 0.5) -> str:
        import cv2
        heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
        original = np.ones((size[1], size[0], 3), dtype=np.uint8) * 255
        superimposed = cv2.addWeighted(heatmap_colored, opacity, original, 1 - opacity, 0)
        img = Image.fromarray(superimposed)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def _heatmap_raw_b64(self, heatmap: np.ndarray) -> str:
        import cv2
        heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
        h, w = heatmap.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., :3] = heatmap_colored
        rgba[..., 3] = heatmap
        img = Image.fromarray(rgba, mode="RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


# 全局单例
_xrv_service: Optional[XRVAnalysisService] = None


def get_xrv_service() -> XRVAnalysisService:
    global _xrv_service
    if _xrv_service is None:
        _xrv_service = XRVAnalysisService()
    return _xrv_service


# 向后兼容旧 API
def get_pneumonia_service() -> XRVAnalysisService:
    return get_xrv_service()
