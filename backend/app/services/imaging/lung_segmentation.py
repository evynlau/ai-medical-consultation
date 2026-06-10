"""肺部分割 - 使用图像处理方法"""
import os
from typing import Optional

import numpy as np
import cv2
from PIL import Image


def segment_lungs(image: Image.Image) -> np.ndarray:
    """对胸片进行肺部分割（模块化函数）

    Args:
        image: PIL Image (RGB 或 灰度)

    Returns:
        二值 mask 数组 (H, W), 肺内=1, 肺外=0
    """
    # 转 numpy 灰度图
    img = np.array(image.convert('L'))

    # Step 1: 反转图像 - 肺部（暗）变亮，便于二值化
    inverted = cv2.bitwise_not(img)

    # Step 2: Otsu 自动二值化
    _, binary = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Step 3: 形态学开运算去小噪点，闭运算连通肺部
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))

    # 先开后闭：去噪 + 连通
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_open)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_close)

    # Step 4: 找到所有白色连通域（肺部 candidate）
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        cleaned, connectivity=8
    )

    if num_labels <= 1:
        return np.zeros_like(img, dtype=np.uint8)

    # 按面积排序（排除背景 0）
    areas = stats[1:, cv2.CC_STAT_AREA]
    sorted_indices = np.argsort(areas)[::-1]  # 降序

    # Step 5: 策略 - 累加连通域直到覆盖大约40-60%的图像
    mask = np.zeros_like(img, dtype=np.uint8)
    img_size = img.size
    target_coverage_min = img_size * 0.38
    target_coverage_max = img_size * 0.55

    current_total = 0
    for idx in sorted_indices:
        area = areas[idx]
        # 跳过太小的噪点（<1%）
        if area < img_size * 0.01:
            break
        mask[labels == idx + 1] = 1
        current_total += area
        # 达到目标覆盖范围就停止
        if current_total >= target_coverage_min:
            break

    # Step 6: 填充肺部内部空洞（如肋骨投影）
    mask = _fill_lung_holes(mask)

    return mask


def _fill_lung_holes(mask: np.ndarray) -> np.ndarray:
    """填充肺部区域中的空洞

    算法：使用连通域分析找出所有内部空洞并填充
    """
    # 转为二值（0和1）
    binary_mask = (mask > 0).astype(np.uint8)

    # 连通域分析（4连通以检测内部孔洞）
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary_mask, connectivity=4
    )

    if num_labels <= 1:
        return binary_mask

    h, w = mask.shape
    filled_mask = np.zeros_like(binary_mask)

    # 找出背景（与边缘连通的区域）和肺部（内部区域）
    for i in range(1, num_labels):
        x = int(centroids[i][0])
        y = int(centroids[i][1])

        # 如果连通域碰到图像边界，则是背景
        is_edge = (
            labels[y, 0] == i or       # 左边缘
            labels[y, w-1] == i or     # 右边缘
            labels[0, x] == i or   # 上边缘
            labels[h-1, x] == i    # 下边缘
        )

        if not is_edge:
            # 这是内部区域（空洞），填充它
            filled_mask[labels == i] = 1

    # 原始肺部 + 填充的空洞
    result = binary_mask | filled_mask
    return result.astype(np.uint8)


# 单例 - 默认使用 CPU (训练时推荐 CPU，推理时可改用 GPU)
_segmentation_model: Optional[object] = None


def get_lung_segmenter(device: str = "cpu", method: str = "simple") -> object:
    """获取肺部分割器实例"""
    global _segmentation_model
    if _segmentation_model is None:
        _segmentation_model = True  # 表示已初始化
    return segment_lungs  # 返回函数


def segment_lungs_with_cache(image: Image.Image, image_hash: Optional[str] = None) -> np.ndarray:
    """带缓存的分割接口"""
    if image_hash is None:
        import hashlib
        img_bytes = image.tobytes()
        image_hash = hashlib.md5(img_bytes).hexdigest()

    cache_dir = "data/processed_lungs"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"lungmask_{image_hash}.npy")

    if os.path.exists(cache_path):
        return np.load(cache_path)

    mask = segment_lungs(image)
    np.save(cache_path, mask)
    return mask
