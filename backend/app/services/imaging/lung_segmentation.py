"""肺部分割 - lungmask 主导 + 形态学后处理"""
import os
from typing import Optional

import numpy as np
import cv2
from PIL import Image
import SimpleITK as sitk

try:
    from lungmask.mask import LMInferer
    LUNGMASK_AVAILABLE = True
except ImportError:
    LUNGMASK_AVAILABLE = False


# 单例 - 避免每次重新加载模型
_lung_mask_inferer: Optional[object] = None
_lung_mask_device: str = "cpu"


def _get_inferer(device: str = "cpu"):
    """懒加载 lungmask inferer（单例）

    Args:
        device: 'cpu' 或 'cuda'
    """
    global _lung_mask_inferer, _lung_mask_device
    if not LUNGMASK_AVAILABLE:
        return None
    if _lung_mask_inferer is None or _lung_mask_device != device:
        force_cpu = (device == "cpu")
        # R231CovidWeb 是为X光片训练的，禁用 volume_postprocessing
        _lung_mask_inferer = LMInferer(
            modelname="R231CovidWeb",
            force_cpu=force_cpu,
            volume_postprocessing=False,
        )
        _lung_mask_device = device
    return _lung_mask_inferer


def _xray_to_hu(img_gray: np.ndarray) -> np.ndarray:
    """X光 (0-255) -> CT HU (-1024~600) 线性映射"""
    return (img_gray.astype(np.float32) / 255.0) * 1624.0 - 1024.0


def _lungmask_segment(image: Image.Image, device: str = "cpu") -> Optional[np.ndarray]:
    """用 lungmask 分割肺部

    lungmask 训练时用 CT HU 单位，X光片需要先做线性映射

    Args:
        image: PIL Image
        device: 设备

    Returns:
        二值 mask (H, W) 或 None（失败时）
    """
    if not LUNGMASK_AVAILABLE:
        return None

    img_gray = np.array(image.convert('L'))
    hu = _xray_to_hu(img_gray)
    sitk_image = sitk.GetImageFromArray(hu.reshape(1, *hu.shape).astype(np.float32))

    try:
        inferer = _get_inferer(device)
        mask = inferer.apply(sitk_image)

        # mask shape: (1, H, W) - 去掉第一维
        mask_2d = mask[0] if mask.ndim == 3 else mask
        # mask: 1=左肺, 2=右肺, 0=其他
        binary_mask = (mask_2d > 0).astype(np.uint8)

        # 确保输出尺寸与原图一致
        if binary_mask.shape != img_gray.shape:
            binary_mask = cv2.resize(
                binary_mask,
                (img_gray.shape[1], img_gray.shape[0]),
                interpolation=cv2.INTER_NEAREST
            )

        return binary_mask
    except Exception as e:
        import logging
        logging.warning(f"lungmask 分割失败: {e}")
        return None


def _post_process(mask: np.ndarray) -> np.ndarray:
    """后处理：膨胀 + 连通域过滤 + 填充空洞

    解决 lungmask 对肺炎浸润区识别不全的问题

    Args:
        mask: 初始二值 mask

    Returns:
        后处理后的二值 mask
    """
    if mask.sum() == 0:
        return mask

    # 1) 闭运算：连接小裂缝
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)

    # 2) 适度膨胀：弥补肺浸润区被lungmask误剔除
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    dilated = cv2.dilate(closed, kernel_dilate, iterations=1)

    # 3) 连通域分析：去掉孤立的噪点
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        dilated, connectivity=8
    )

    if num_labels <= 1:
        return mask

    # 保留较大的连通域（>3% 图像面积）
    img_size = dilated.size
    min_area = img_size * 0.03
    filtered = np.zeros_like(dilated)

    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            filtered[labels == i] = 1

    # 4) 填充肺内部空洞（如肋骨投影）
    filtered = _fill_holes(filtered)

    return filtered


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    """填充 mask 内部的孔洞"""
    if mask.sum() == 0:
        return mask

    binary_mask = mask.astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary_mask, connectivity=4
    )

    if num_labels <= 1:
        return binary_mask

    h, w = mask.shape
    filled_mask = np.zeros_like(binary_mask)

    for i in range(1, num_labels):
        x = int(centroids[i][0])
        y = int(centroids[i][1])
        # 检查是否碰到图像边缘（背景）
        is_edge = (
            labels[y, 0] == i or
            labels[y, w-1] == i or
            labels[0, x] == i or
            labels[h-1, x] == i
        )
        if not is_edge:
            filled_mask[labels == i] = 1

    return (binary_mask | filled_mask).astype(np.uint8)


def _threshold_segment(image: Image.Image, lungmask_hint: Optional[np.ndarray] = None) -> np.ndarray:
    """用阈值法补充 lungmask 的结果

    如果提供了 lungmask_hint，则只在 hint 周围补充

    Args:
        image: PIL Image
        lungmask_hint: 可选 lungmask 的结果，用于限制阈值法范围

    Returns:
        二值 mask
    """
    img = np.array(image.convert('L'))

    # 反转：肺部（暗）变亮
    inverted = cv2.bitwise_not(img)
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)
    cleaned = (cleaned > 0).astype(np.uint8)

    # 如果有 lungmask hint，膨胀 hint 形成邻域 mask
    # 阈值法结果只保留在邻域内的部分
    if lungmask_hint is not None and lungmask_hint.sum() > 0:
        # 膨胀 lungmask 创建一个"邻域窗口"（用于补充肺炎浸润区）
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (30, 30))
        neighborhood = cv2.dilate(lungmask_hint, kernel_dilate, iterations=3)
        cleaned = cleaned & neighborhood

    # 移除与边缘连通的区域（背景）
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, connectivity=4)
    if num_labels <= 1:
        return np.zeros_like(img, dtype=np.uint8)

    h, w = img.shape
    edge_labels = set()
    # 检查四条边
    edge_labels.update(np.unique(labels[0, :]))
    edge_labels.update(np.unique(labels[h-1, :]))
    edge_labels.update(np.unique(labels[:, 0]))
    edge_labels.update(np.unique(labels[:, w-1]))

    img_size = img.size
    min_area = img_size * 0.03

    mask = np.zeros_like(img, dtype=np.uint8)
    for i in range(1, num_labels):
        if i in edge_labels:
            continue
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        mask[labels == i] = 1

    return mask


def segment_lungs(image: Image.Image, device: str = "cpu") -> np.ndarray:
    """对胸片进行肺部分割

    策略：
        1. 优先用 lungmask 识别左右肺
        2. 在 lungmask 邻域内用阈值法补充被漏掉的肺炎浸润区
        3. 后处理：填充、过滤、合并

    Args:
        image: PIL Image (RGB 或 灰度)
        device: 'cpu' 或 'cuda'

    Returns:
        二值 mask 数组 (H, W), 肺内=1, 肺外=0
    """
    h, w = image.height, image.width

    # 1) 尝试 lungmask
    raw_mask = _lungmask_segment(image, device=device)

    # 2) 在 lungmask 邻域内用阈值法补充
    if raw_mask is not None and raw_mask.sum() > 0:
        threshold_supplement = _threshold_segment(image, lungmask_hint=raw_mask)
        # 合并：lungmask + 阈值法补充
        if threshold_supplement.sum() > 0:
            combined = ((raw_mask > 0) | (threshold_supplement > 0)).astype(np.uint8)
        else:
            combined = raw_mask

        # 后处理
        processed = _post_process(combined)
        if processed.sum() > 0:
            return processed

    # 3) 回退到纯阈值法
    threshold_mask = _threshold_segment(image)
    if threshold_mask.sum() > 0:
        return threshold_mask

    # 4) 最后兜底
    if raw_mask is not None:
        return raw_mask
    return np.zeros((h, w), dtype=np.uint8)


def get_lung_segmenter(device: str = "cpu"):
    """获取肺部分割函数（接口兼容性）"""
    return segment_lungs


# 缓存
_cache_dir: str = "data/processed_lungs"
os.makedirs(_cache_dir, exist_ok=True)


def segment_lungs_with_cache(image: Image.Image, image_hash: Optional[str] = None, device: str = "cpu") -> np.ndarray:
    """带缓存的肺部分割"""
    import hashlib

    if image_hash is None:
        img_bytes = image.tobytes()
        image_hash = hashlib.md5(img_bytes).hexdigest()

    cache_path = os.path.join(_cache_dir, f"lungmask_{image_hash}.npy")

    if os.path.exists(cache_path):
        return np.load(cache_path)

    mask = segment_lungs(image, device=device)
    np.save(cache_path, mask)
    return mask
