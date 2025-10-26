from abc import ABC, abstractmethod
from src.domain.Models.frame import Frame

class ICameraStream(ABC):
    """
    Abstracción de un stream de cámara.
    """
    @abstractmethod
    def connect(self) -> None:
        """Conecta al stream de video."""
        pass

    @abstractmethod
    def read_frame(self) -> Frame | None:
        """Lee un frame del stream. Devuelve None si falla."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Cierra la conexión al stream."""
        pass
