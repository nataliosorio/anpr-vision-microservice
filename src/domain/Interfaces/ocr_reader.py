from abc import ABC, abstractmethod
from src.domain.Models.frame import Frame
from src.domain.Models.plate import Plate

class IOCRReader(ABC):
    """
    Lector OCR para extraer texto de las placas detectadas.
    """
    @abstractmethod
    def read_text(self, frame: Frame, plate: Plate) -> Plate:
        """
        Extrae texto de la región de la placa.
        Devuelve un Plate con el campo 'text' actualizado.
        """
        pass
