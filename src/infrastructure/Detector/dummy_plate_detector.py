import random
from typing import List
from domain.Models.frame import Frame
from domain.Models.plate import Plate
from domain.Interfaces.plate_detector import IPlateDetector

class DummyPlateDetector(IPlateDetector):
    """
    Implementación dummy que inventa placas de manera aleatoria.
    """

    def detect(self, frame: Frame) -> List[Plate]:
        # Simulamos probabilidad de detectar una placa
        if random.random() > 0.7:
            plate = Plate(
                text="ABC123",
                confidence=0.95,
                bounding_box=(50, 50, 200, 100)
            )
            return [plate]
        return []
