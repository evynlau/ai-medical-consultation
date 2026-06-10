"""PSPNet 肺部分割 - 14 部位解剖结构分割

使用 torchxrayvision.baseline_models.chestx_det.PSPNet
对比 lungmask 优势:
  - 14 通道语义分割 (左/右肺、心影、纵隔、锁骨、脊柱等)
  - 在 NIH chestX_det 大规模数据集上训练
  - 输出 512x512 概率图,可直接做后处理
  - 不需要 X-ray → HU 转换
  - 一次推理同时产出多部位,可灵活组合 mask
"""
from typing import Optional

import numpy as np
import torch
from PIL import Image


# PSPNet 14 部位索引 (与 xrv.baseline_models.chestx_det.PSPNet().targets 对应)
PSP_TARGETS = [
    'Left Clavicle',        # 0  左锁骨
    'Right Clavicle',       # 1  右锁骨
    'Left Scapula',         # 2  左肩胛
    'Right Scapula',        # 3  右肩胛
    'Left Lung',            # 4  左肺
    'Right Lung',           # 5  右肺
    'Left Hilus Pulmonis',  # 6  左肺门
    'Right Hilus Pulmonis', # 7  右肺门
    'Heart',                # 8  心影
    'Aorta',                # 9  主动脉
    'Facies Diaphragmatica',# 10 膈面
    'Mediastinum',          # 11 纵隔
    'Weasand',              # 12 食管
    'Spine',                # 13 脊柱
]
LEFT_LUNG_IDX = PSP_TARGETS.index('Left Lung')        # 4
RIGHT_LUNG_IDX = PSP_TARGETS.index('Right Lung')      # 5
LEFT_HILUS_IDX = PSP_TARGETS.index('Left Hilus Pulmonis')
RIGHT_HILUS_IDX = PSP_TARGETS.index('Right Hilus Pulmonis')

# 全局 PSPNet 单例
_pspnet_model = None


def _get_pspnet(device: str = "cpu"):
    """懒加载 PSPNet (单例,避免重复加载)"""
    global _pspnet_model
    if _pspnet_model is None:
        import torchxrayvision as xrv
        _pspnet_model = xrv.baseline_models.chestx_det.PSPNet()
        _pspnet_model.to(device)
        _pspnet_model.eval()
    return _pspnet_model


def segment_lungs_pspnet(
    image: Image.Image,
    device: str = "cpu",
) -> Optional[np.ndarray]:
    """使用 PSPNet 生成 14 通道解剖分割,合并双肺+肺门生成肺实质 mask

    Args:
        image: PIL Image (任意模式,自动转灰度)
        device: 'cpu' 或 'cuda'

    Returns:
        binary: uint8 ndarray (H, W), 1=肺实质 0=非肺; 若失败返回 None
    """
    try:
        import torchxrayvision as xrv
        import torchvision
        model = _get_pspnet(device)

        # PIL -> numpy (灰度,float32)
        gray = image if image.mode == "L" else image.convert("L")
        img = np.asarray(gray).astype(np.float32)
        img = xrv.utils.normalize(img, 255)  # 0-255 -> [-1024, 1024]

        # XRayCenterCrop 期望 3D (C, H, W), 包装一下
        img_3d = img[None, :, :]  # (1, H, W)

        # 中心裁剪 + 缩放到 512x512 (PSPNet 输入)
        transform = torchvision.transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(512),
        ])
        img_t = transform(img_3d)  # (1, 512, 512)
        img_t = img_t[0]  # -> (512, 512)

        # (1, 1, 512, 512)
        x = torch.from_numpy(img_t).unsqueeze(0).unsqueeze(0).to(device)

        with torch.no_grad():
            logits = model(x)  # (1, 14, 512, 512)
            probs = torch.sigmoid(logits)  # 多标签 sigmoid

        # 合并 双肺 + 肺门 (肺门权重低,只做平滑过渡)
        lung_mask_512 = (
            probs[0, LEFT_LUNG_IDX] +
            probs[0, RIGHT_LUNG_IDX] +
            probs[0, LEFT_HILUS_IDX] * 0.5 +
            probs[0, RIGHT_HILUS_IDX] * 0.5
        )  # (512, 512) float, 0~2

        binary_512 = (lung_mask_512 > 0.5).cpu().numpy().astype(np.uint8)

        # 上采样回原图大小
        original_size = image.size  # (W, H)
        mask_pil = Image.fromarray(binary_512 * 255, mode="L")
        mask_pil = mask_pil.resize(original_size, Image.BILINEAR)
        binary = (np.asarray(mask_pil) > 127).astype(np.uint8)

        return binary

    except Exception as e:
        import logging
        logging.warning(f"PSPNet lung segmentation failed: {e}")
        return None


def get_anatomical_overlay(
    image: Image.Image,
    device: str = "cpu",
) -> Optional[np.ndarray]:
    """生成 14 通道完整解剖分割 (用于前端可视化)

    Returns:
        overlay: uint8 ndarray (H, W, 3) RGB 彩色编码
            - 红: 双肺
            - 蓝: 心影
            - 绿: 纵隔
    """
    try:
        import torchxrayvision as xrv
        import torchvision
        model = _get_pspnet(device)

        gray = image if image.mode == "L" else image.convert("L")
        img = np.asarray(gray).astype(np.float32)
        img = xrv.utils.normalize(img, 255)

        img_3d = img[None, :, :]
        transform = torchvision.transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(512),
        ])
        img_t = transform(img_3d)[0]

        x = torch.from_numpy(img_t).unsqueeze(0).unsqueeze(0).to(device)
        with torch.no_grad():
            probs = torch.sigmoid(model(x))[0].cpu().numpy()  # (14, 512, 512)

        original_size = image.size
        h, w = original_size[1], original_size[0]
        overlay = np.zeros((h, w, 3), dtype=np.uint8)

        # 双肺 -> 红
        lung_mask = ((probs[LEFT_LUNG_IDX] + probs[RIGHT_LUNG_IDX]) > 0.5).astype(np.uint8)
        lung_pil = Image.fromarray(lung_mask * 255, mode="L").resize(original_size, Image.BILINEAR)
        lung_full = (np.asarray(lung_pil) > 127)
        overlay[lung_full, 0] = 255
        overlay[lung_full, 1] = 100

        # 心影 -> 蓝
        heart_mask = (probs[PSP_TARGETS.index('Heart')] > 0.5).astype(np.uint8)
        heart_pil = Image.fromarray(heart_mask * 255, mode="L").resize(original_size, Image.BILINEAR)
        heart_full = (np.asarray(heart_pil) > 127)
        overlay[heart_full, 2] = 255

        # 纵隔 -> 绿
        medi_mask = (probs[PSP_TARGETS.index('Mediastinum')] > 0.5).astype(np.uint8)
        medi_pil = Image.fromarray(medi_mask * 255, mode="L").resize(original_size, Image.BILINEAR)
        medi_full = (np.asarray(medi_pil) > 127)
        overlay[medi_full, 1] = 200

        return overlay

    except Exception as e:
        import logging
        logging.warning(f"PSPNet anatomical overlay failed: {e}")
        return None


# 向后兼容旧 API
def segment_lungs(image: Image.Image, device: str = "cpu") -> Optional[np.ndarray]:
    """兼容旧 API,实际调用 PSPNet"""
    return segment_lungs_pspnet(image, device)


def get_lung_segmenter():
    """兼容旧 API,返回 PSPNet 包装"""
    return _get_pspnet("cpu")
