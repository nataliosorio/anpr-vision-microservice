from dataclasses import dataclass, asdict
import numpy as np

@dataclass
class Frame:
    """
    Representa un frame capturado desde una cámara.
    """
    data: np.ndarray   # imagen en formato numpy array
    timestamp: float   # momento en que se capturó
    source: str        # identificador de la cámara o URL

    @property
    def image(self) -> np.ndarray:
        """Alias para compatibilidad con librerías que esperan 'image'."""
        return self.data

    def to_dict(self) -> dict:
        """
        Convierte el frame a un dict serializable (sin incluir la imagen).
        Ideal para logs o publishers.
        """
        return {
            "timestamp": self.timestamp,
            "source": self.source,
            "shape": self.data.shape if isinstance(self.data, np.ndarray) else None
        }
