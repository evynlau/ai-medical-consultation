"""Grad-CAM 和 HiResCAM 实现 - 可视化 AI 关注的区域

针对 torchxrayvision DenseNet 优化:
  - 不使用 forward_hook (会与 dense block 的 inplace op 冲突)
  - 直接用 model.features() 拿特征图,单独 forward classifier
  - feature.retain_grad() 拿梯度
"""
import io
import base64
from typing import Optional, Union, Callable

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


def _generate_cam(
    model,
    image,
    transform,
    device,
    method: str = "hirescam",
    target_class_idx: Optional[int] = None,
) -> Optional[np.ndarray]:
    """核心 Grad-CAM/HiResCAM 实现

    策略: features() 拿特征 + retain_grad() 拿梯度
    """
    try:
        model.eval()

        target_layer, layer_name = _get_last_conv_output(model)
        if target_layer is None:
            return None

        # 1. 预处理
        if image.mode != "RGB":
            image = image.convert("RGB")
        input_tensor = _resolve_input_tensor(image, transform, device)
        input_tensor.requires_grad_(False)

        # 2. 拿特征 (torchxrayvision DenseNet 自带 .features())
        if hasattr(model, "features"):
            features = model.features(input_tensor)  # (1, C, H, W)
        else:
            # 退化: 手动 forward 到 target_layer
            raise NotImplementedError("Model has no .features() method")

        # 3. retain grad
        features.retain_grad()

        # 4. forward classifier head
        # torchxrayvision DenseNet 分类头是 model.classifier (nn.Linear)
        if hasattr(model, "classifier"):
            # features: (1, C, H, W) -> (1, C) via adaptive avg pool
            pooled = F.adaptive_avg_pool2d(features, 1).flatten(1)
            logits = model.classifier(pooled)  # (1, 18)
        else:
            return None

        # 5. 选目标类别
        if target_class_idx is None:
            pred_class = logits.argmax(dim=1).item()
        else:
            pred_class = int(target_class_idx)

        # 6. 反向传播
        model.zero_grad()
        one_hot = torch.zeros_like(logits)
        one_hot[0][pred_class] = 1
        logits.backward(gradient=one_hot, retain_graph=False)

        if features.grad is None:
            return None

        activation = features  # (1, C, H, W)
        gradient = features.grad  # (1, C, H, W)

        # 7. 计算 CAM
        if method == "hirescam":
            cam = (activation * gradient).detach()  # 逐元素
        else:
            # gradcam: 全局平均池化梯度
            weights = gradient.mean(dim=(2, 3), keepdim=True).detach()
            cam = weights * activation.detach()

        cam = cam.sum(dim=1, keepdim=True)  # (1, 1, H, W)
        cam = F.relu(cam)

        # 8. 上采样到原图大小
        cam = F.interpolate(
            cam,
            size=image.size[::-1],
            mode="bilinear",
            align_corners=False,
        )
        cam = cam.squeeze().cpu().numpy()

        # 9. 归一化
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8) * 255
        cam = cam.astype(np.uint8)

        return cam

    except Exception as e:
        import logging
        logging.warning(f"Grad-CAM/HiResCAM 生成失败 ({method}): {e}")
        return None


def generate_gradcam(
    model: torch.nn.Module,
    image: Image.Image,
    transform: Union[transforms.Compose, Callable],
    device: torch.device,
    target_layer_name: str = "features.norm5",
    target_class_idx: Optional[int] = None,
) -> Optional[np.ndarray]:
    """生成 Grad-CAM 热力图"""
    return _generate_cam(model, image, transform, device, "gradcam", target_class_idx)


def generate_hirescam(
    model: torch.nn.Module,
    image: Image.Image,
    transform: Union[transforms.Compose, Callable],
    device: torch.device,
    target_layer_name: str = "features.norm5",
    target_class_idx: Optional[int] = None,
) -> Optional[np.ndarray]:
    """生成 HiResCAM 热力图"""
    return _generate_cam(model, image, transform, device, "hirescam", target_class_idx)


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
