"""医学影像分析服务基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path
import time

import numpy as np
import torch
from PIL import Image


class BaseImagingService(ABC):
    """医学影像分析服务基类"""

    def __init__(self, model_path: str, device: Optional[str] = None):
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.model_path = model_path
        self.model = None
        self.config: Dict[str, Any] = {}

    @abstractmethod
    def load_model(self):
        """加载模型权重"""
        pass

    @abstractmethod
    def preprocess(self, image: Image.Image) -> torch.Tensor:
        """图像预处理"""
        pass

    @abstractmethod
    def predict(self, image: Image.Image) -> Dict[str, Any]:
        """推理"""
        pass

    def _postprocess(self, logits: torch.Tensor, inference_time_ms: float) -> Dict[str, Any]:
        """后处理 - 默认实现"""
        probabilities = torch.softmax(logits, dim=-1).cpu().numpy()[0]
        predicted_idx = int(np.argmax(probabilities))
        confidence = float(probabilities[predicted_idx])
        return {
            "prediction_idx": predicted_idx,
            "probabilities": probabilities.tolist(),
            "confidence": confidence,
            "inference_time_ms": inference_time_ms,
        }