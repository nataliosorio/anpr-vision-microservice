from abc import ABC, abstractmethod
from src.domain.Models.frame import Frame
from src.domain.Models.plate import Plate
from typing import List

class IPlateDetector(ABC):
    """
    Detector de placas en un frame.
    """
    @abstractmethod
    def detect(self, frame: Frame) -> List[Plate]:
        """Detecta placas en el frame y devuelve lista de Plate."""
        pass
