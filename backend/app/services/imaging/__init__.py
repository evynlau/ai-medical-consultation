"""torchxrayvision 官方范式影像分析"""
from app.services.imaging.xrv_service import (
    XRVAnalysisService,
    get_xrv_service,
    get_pneumonia_service,
    PATHOLOGY_LABELS_CN,
)

__all__ = [
    "XRVAnalysisService",
    "get_xrv_service",
    "get_pneumonia_service",
    "PATHOLOGY_LABELS_CN",
]
