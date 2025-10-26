from abc import ABC, abstractmethod
from src.domain.Models.detection_result import DetectionResult

class IEventPublisher(ABC):
    """
    Publicador de eventos a sistemas externos (ej. Kafka).
    """
    @abstractmethod
    def publish(self, result: DetectionResult) -> None:
        """Publica un DetectionResult en un broker de mensajes."""
        pass
