"""Grad-CAM 和 HiResCAM 实现 - 可视化 AI 关注的区域"""
import io
import base64
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image
import cv2


def generate_gradcam(
    model: torch.nn.Module,
    image: Image.Image,
    transform: transforms.Compose,
    device: torch.device,
    target_layer_name: str = "layer4",
) -> Optional[np.ndarray]:
    """生成 Grad-CAM 热力图

    Args:
        model: 训练好的模型
        image: PIL 图像
        transform: 图像预处理变换
        device: 计算设备
        target_layer_name: 目标卷积层名称

    Returns:
        热力图 numpy 数组 (H, W),值范围 0-255
    """
    try:
        model.eval()

        # 获取目标层
        target_layer = None
        for name, module in model.named_modules():
            if name == target_layer_name:
                target_layer = module
                break

        if target_layer is None:
            # 退化方案: 使用最后一层
            target_layer = model.layer4[-1].conv3 if hasattr(model.layer4[-1], 'conv3') else None
            if target_layer is None:
                return None

        # 预处理
        if image.mode != "RGB":
            image = image.convert("RGB")
        input_tensor = transform(image).unsqueeze(0).to(device)
        input_tensor.requires_grad_(False)

        # 存储激活值和梯度
        activations = {}
        gradients = {}

        def forward_hook(module, input, output):
            activations["value"] = output.detach()
            output.requires_grad_(True)

        def backward_hook(module, grad_input, grad_output):
            gradients["value"] = grad_output[0].detach()

        # 注册 hook
        forward_handle = target_layer.register_forward_hook(forward_hook)
        backward_handle = target_layer.register_full_backward_hook(backward_hook)

        try:
            # 前向传播
            output = model(input_tensor)

            # 获取预测类别
            pred_class = output.argmax(dim=1).item()

            # 反向传播
            model.zero_grad()
            one_hot = torch.zeros_like(output)
            one_hot[0][pred_class] = 1
            output.backward(gradient=one_hot, retain_graph=False)

            # 计算 Grad-CAM
            if "value" not in activations or "value" not in gradients:
                return None

            activation = activations["value"]  # (1, C, H, W)
            gradient = gradients["value"]      # (1, C, H, W)

            # 全局平均池化梯度
            weights = gradient.mean(dim=(2, 3), keepdim=True)  # (1, C, 1, 1)

            # 加权求和
            cam = (weights * activation).sum(dim=1, keepdim=True)  # (1, 1, H, W)
            cam = F.relu(cam)

            # 上采样到原图大小
            cam = F.interpolate(
                cam,
                size=image.size[::-1],  # (W, H) -> (H, W)
                mode="bilinear",
                align_corners=False,
            )
            cam = cam.squeeze().cpu().numpy()

            # 归一化到 0-255
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8) * 255
            cam = cam.astype(np.uint8)

            return cam

        finally:
            forward_handle.remove()
            backward_handle.remove()

    except Exception as e:
        import logging
        logging.warning(f"Grad-CAM 生成失败: {e}")
        return None


def generate_hirescam(
    model: torch.nn.Module,
    image: Image.Image,
    transform: transforms.Compose,
    device: torch.device,
    target_layer_name: str = "layer4",
) -> Optional[np.ndarray]:
    """生成 HiResCAM 热力图

    HiResCAM vs Grad-CAM:
        - Grad-CAM: 对每个通道的梯度做全局平均池化(单权重),丢失空间信息
        - HiResCAM: 激活 × 梯度 逐元素相乘,保持空间分辨率

    优势:
        - 热力图更精细,不模糊
        - 与原图严格对齐
        - 边界更清晰

    论文: HiResCAM: Faithful Visualization of Neural Networks with High Resolution
    """
    try:
        model.eval()

        # 获取目标层
        target_layer = None
        for name, module in model.named_modules():
            if name == target_layer_name:
                target_layer = module
                break

        if target_layer is None:
            target_layer = model.layer4[-1].conv3 if hasattr(model.layer4[-1], 'conv3') else None
            if target_layer is None:
                return None

        # 预处理
        if image.mode != "RGB":
            image = image.convert("RGB")
        input_tensor = transform(image).unsqueeze(0).to(device)
        input_tensor.requires_grad_(False)

        # 存储激活值和梯度
        activations = {}
        gradients = {}

        def forward_hook(module, input, output):
            activations["value"] = output.detach()
            output.requires_grad_(True)

        def backward_hook(module, grad_input, grad_output):
            gradients["value"] = grad_output[0].detach()

        # 注册 hook
        forward_handle = target_layer.register_forward_hook(forward_hook)
        backward_handle = target_layer.register_full_backward_hook(backward_hook)

        try:
            # 前向传播
            output = model(input_tensor)

            # 获取预测类别
            pred_class = output.argmax(dim=1).item()

            # 反向传播
            model.zero_grad()
            one_hot = torch.zeros_like(output)
            one_hot[0][pred_class] = 1
            output.backward(gradient=one_hot, retain_graph=False)

            if "value" not in activations or "value" not in gradients:
                return None

            activation = activations["value"]  # (1, C, H, W)
            gradient = gradients["value"]      # (1, C, H, W)

            # HiResCAM: 激活 × 梯度 逐元素相乘
            # 不做全局平均池化 - 保持空间分辨率
            cam = activation * gradient  # (1, C, H, W)
            cam = cam.sum(dim=1, keepdim=True)  # (1, 1, H, W)
            cam = F.relu(cam)

            # 上采样到原图大小
            cam = F.interpolate(
                cam,
                size=image.size[::-1],
                mode="bilinear",
                align_corners=False,
            )
            cam = cam.squeeze().cpu().numpy()

            # 归一化到 0-255
            cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8) * 255
            cam = cam.astype(np.uint8)

            return cam

        finally:
            forward_handle.remove()
            backward_handle.remove()

    except Exception as e:
        import logging
        logging.warning(f"HiResCAM 生成失败: {e}")
        return None


def heatmap_to_base64(heatmap: np.ndarray, original_size: tuple, opacity: float = 0.4) -> str:
    """将热力图叠加到原图，转为 base64

    Args:
        heatmap: 热力图数组
        original_size: 原图大小 (W, H)
        opacity: 热力图透明度

    Returns:
        Base64 编码的图片
    """
    # 应用颜色映射
    heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

    # 创建原图
    original = np.ones((original_size[1], original_size[0], 3), dtype=np.uint8) * 255

    # 叠加
    superimposed = cv2.addWeighted(heatmap_colored, opacity, original, 1 - opacity, 0)

    # 转为 PIL
    img = Image.fromarray(superimposed)

    # 转为 base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return f"data:image/png;base64,{img_str}"


def heatmap_to_base64_raw(heatmap: np.ndarray) -> str:
    """将热力图(彩色,无叠加)转为 base64,用于前端独立叠加显示

    Args:
        heatmap: 热力图数组 (H, W), 值范围 0-255

    Returns:
        Base64 编码的图片 (PNG, RGBA 通道)
    """
    # 应用颜色映射 (JET)
    heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    # BGR -> RGB
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)
    # 添加 alpha 通道(用于透明度叠加)
    h, w = heatmap.shape
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., :3] = heatmap_colored
    rgba[..., 3] = heatmap  # alpha 由热力图强度决定

    img = Image.fromarray(rgba, mode="RGBA")

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return f"data:image/png;base64,{img_str}"


def heatmap_to_image(heatmap: np.ndarray, original_size: tuple, opacity: float = 0.4) -> bytes:
    """将热力图叠加到原图，返回 PNG 字节

    Args:
        heatmap: 热力图数组
        original_size: 原图大小 (W, H)
        opacity: 热力图透明度

    Returns:
        PNG 字节
    """
    heatmap_colored = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

    original = np.ones((original_size[1], original_size[0], 3), dtype=np.uint8) * 255

    superimposed = cv2.addWeighted(heatmap_colored, opacity, original, 1 - opacity, 0)

    img = Image.fromarray(superimposed)

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()