from ultralytics import YOLO
from typing import List
from src.domain.Models.frame import Frame
from src.domain.Models.plate import Plate
from src.domain.Interfaces.plate_detector import IPlateDetector
from src.core.config import settings

class YOLOPlateDetector(IPlateDetector):
    """
    Detector de placas usando YOLOv8 (modelo Koushim).
    Aplica filtros de confianza e IOU para resultados más limpios.
    """

    def __init__(self):
        # Carga del modelo desde la ruta configurada en .env
        self.model = YOLO(settings.model_path)
        self.conf_threshold = settings.conf_threshold
        self.iou_threshold = settings.iou_threshold

    def detect(self, frame: Frame) -> List[Plate]:
        """
        Detecta placas en un frame dado y devuelve una lista de Plate.
        """
        results = self.model.predict(
            source=frame.data,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            verbose=False
        )

        plates: List[Plate] = []

        for r in results[0].boxes:
            conf = float(r.conf[0])
            if conf < self.conf_threshold:
                continue  # descartar detecciones poco confiables

            x1, y1, x2, y2 = map(int, r.xyxy[0])
            plates.append(Plate(
                text="",  # OCR llenará este campo después
                confidence=conf,
                bounding_box=(x1, y1, x2 - x1, y2 - y1)
            ))

        return plates
