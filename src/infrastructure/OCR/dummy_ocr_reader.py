from domain.Models.frame import Frame
from domain.Models.plate import Plate
from domain.Interfaces.ocr_reader import IOCRReader

class DummyOCRReader(IOCRReader):
    """
    Implementación dummy que simplemente devuelve el mismo texto fijo.
    """

    def read_text(self, frame: Frame, plate: Plate) -> Plate:
        plate.text = "FAKE123"
        plate.confidence = 0.99
        return plate
