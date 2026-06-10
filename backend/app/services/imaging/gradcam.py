"""Grad-CAM 和 HiResCAM 实现 - 可视化 AI 关注的区域

针对 torchxrayvision DenseNet 优化:
  - 不使用 forward_hook (会与 dense block 的 inplace op 冲突)
  - 直接用 model.features() 拿特征图,单独 forward classifier
  - feature.retain_grad() 拿梯度
  - 支持多目标类别批量生成热力图(单次前向 + 多次累积 backward)
"""
import io
import base64
from typing import Optional, Union, Callable, List, Dict

import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image
import cv2


def _resolve_input_tensor(image, transform_or_service, device):
    """支持两种 transform:
    1) torchvision Compose: 直接 transform(image).unsqueeze(0)
    2) PneumoniaService 实例: 调用 service._pil_to_xrv_tensor(image)
    """
    if hasattr(transform_or_service, "_pil_to_xrv_tensor"):
        x = transform_or_service._pil_to_xrv_tensor(image)
        return x.to(device)
    return transform_or_service(image).unsqueeze(0).to(device)


def _get_last_conv_output(model):
    """找到最后一层 norm/conv 用于 Grad-CAM"""
    candidates = ("features.norm5", "norm5", "norm4", "layer4", "bn1")
    for c in candidates:
        for name, module in model.named_modules():
            if name == c:
                return module, c
    return None, None


def _cam_from_features(
    features: torch.Tensor,
    gradient: torch.Tensor,
    method: str,
    image_size: tuple,
) -> np.ndarray:
    """从 features 和 gradient 计算 CAM"""
    if method == "hirescam":
        cam = (features * gradient).detach()
    else:  # gradcam
        weights = gradient.mean(dim=(2, 3), keepdim=True).detach()
        cam = weights * features.detach()
    cam = cam.sum(dim=1, keepdim=True)
    cam = F.relu(cam)
    cam = F.interpolate(cam, size=image_size, mode="bilinear", align_corners=False)
    cam = cam.squeeze().cpu().numpy()
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8) * 255
    return cam.astype(np.uint8)


def _generate_cam_single(
    model,
    image,
    transform,
    device,
    method: str = "hirescam",
    target_class_idx: Optional[int] = None,
) -> Optional[np.ndarray]:
    """单次前向+backward 生成单张 CAM (保留供向后兼容)"""
    try:
        model.eval()
        target_layer, _ = _get_last_conv_output(model)
        if target_layer is None:
            return None

        if image.mode != "RGB":
            image = image.convert("RGB")
        input_tensor = _resolve_input_tensor(image, transform, device)
        input_tensor.requires_grad_(False)

        if not hasattr(model, "features") or not hasattr(model, "classifier"):
            return None

        features = model.features(input_tensor)
        features.retain_grad()
        pooled = F.adaptive_avg_pool2d(features, 1).flatten(1)
        logits = model.classifier(pooled)

        if target_class_idx is None:
            pred_class = logits.argmax(dim=1).item()
        else:
            pred_class = int(target_class_idx)

        model.zero_grad()
        one_hot = torch.zeros_like(logits)
        one_hot[0][pred_class] = 1
        logits.backward(gradient=one_hot, retain_graph=False)

        if features.grad is None:
            return None

        return _cam_from_features(features, features.grad, method, image.size[::-1])

    except Exception as e:
        import logging
        logging.warning(f"Grad-CAM/HiResCAM 生成失败 ({method}): {e}")
        return None


def _generate_cam_multi(
    model,
    image,
    transform,
    device,
    method: str,
    target_class_idxs: List[int],
) -> Dict[int, np.ndarray]:
    """单次前向,累积多次 backward,生成多张 CAM

    关键技巧: retain_graph=True 多次反向,共享 features
    """
    results: Dict[int, np.ndarray] = {}
    try:
        model.eval()
        _, _ = _get_last_conv_output(model)
        if image.mode != "RGB":
            image = image.convert("RGB")
        input_tensor = _resolve_input_tensor(image, transform, device)
        input_tensor.requires_grad_(False)

        if not hasattr(model, "features") or not hasattr(model, "classifier"):
            return results

        features = model.features(input_tensor)
        features.retain_grad()
        pooled = F.adaptive_avg_pool2d(features, 1).flatten(1)
        logits = model.classifier(pooled)

        for idx in target_class_idxs:
            model.zero_grad()
            # retain_graph=True: 多次 backward 共享 features
            one_hot = torch.zeros_like(logits)
            one_hot[0][int(idx)] = 1
            logits.backward(gradient=one_hot, retain_graph=True)
            if features.grad is not None:
                results[int(idx)] = _cam_from_features(
                    features, features.grad, method, image.size[::-1]
                )
        return results

    except Exception as e:
        import logging
        logging.warning(f"多目标 Grad-CAM 生成失败: {e}")
        return results


def generate_gradcam(
    model: torch.nn.Module,
    image: Image.Image,
    transform: Union[transforms.Compose, Callable],
    device: torch.device,
    target_layer_name: str = "features.norm5",
    target_class_idx: Optional[int] = None,
) -> Optional[np.ndarray]:
    """生成 Grad-CAM 热力图 (单类别)"""
    return _generate_cam_single(model, image, transform, device, "gradcam", target_class_idx)


def generate_hirescam(
    model: torch.nn.Module,
    image: Image.Image,
    transform: Union[transforms.Compose, Callable],
    device: torch.device,
    target_layer_name: str = "features.norm5",
    target_class_idx: Optional[int] = None,
) -> Optional[np.ndarray]:
    """生成 HiResCAM 热力图 (单类别)"""
    return _generate_cam_single(model, image, transform, device, "hirescam", target_class_idx)


def generate_cam_for_classes(
    model: torch.nn.Module,
    image: Image.Image,
    transform: Union[transforms.Compose, Callable],
    device: torch.device,
    target_class_idxs: List[int],
    method: str = "hirescam",
) -> Dict[int, np.ndarray]:
    """单次前向,批量生成多个类别的热力图

    Returns:
        {class_idx: cam_array} 字典
    """
    return _generate_cam_multi(model, image, transform, device, method, target_class_idxs)


def heatmap_to_base64(heatmap: np.ndarray, original_size: tuple, opacity: float = 0.4) -> str:
    """将热力图叠加到原图,转为 base64"""
    heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

    original = np.ones((original_size[1], original_size[0], 3), dtype=np.uint8) * 255
    superimposed = cv2.addWeighted(heatmap_colored, opacity, original, 1 - opacity, 0)

    img = Image.fromarray(superimposed)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"


def heatmap_to_base64_raw(heatmap: np.ndarray) -> str:
    """将热力图(彩色,无叠加)转为 base64,用于前端独立叠加显示"""
    heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
    h, w = heatmap.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = heatmap_colored
    rgba[..., 3] = heatmap

    img = Image.fromarray(rgba, mode="RGBA")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{img_str}"


def heatmap_to_image(heatmap: np.ndarray, original_size: tuple, opacity: float = 0.4) -> bytes:
    """将热力图叠加到原图,返回 PNG 字节"""
    heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

    original = np.ones((original_size[1], original_size[0], 3), dtype=np.uint8) * 255
    superimposed = cv2.addWeighted(heatmap_colored, opacity, original, 1 - opacity, 0)

    img = Image.fromarray(superimposed)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()
