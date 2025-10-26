from src.core.config import settings
from src.domain.Interfaces.plate_detector import IPlateDetector

def create_plate_detector() -> IPlateDetector:
    if settings.yolo_version.lower() == "v5":
        from src.infrastructure.Detector.yolov5_plate_detector import YoloV5PlateDetector
        return YoloV5PlateDetector()
    else:
        # Implementación actual de v8
        from src.infrastructure.Detector.YOLOPlateDetector import YOLOPlateDetector
        return YOLOPlateDetector()
