# src/domain/Models/camera.py
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.infrastructure.Database.entities.camera_entity import CameraEntity

@dataclass
class Camera:
    """
    Modelo de dominio para una cámara de reconocimiento.
    No depende del ORM ni de infraestructura.
    """
    camera_id: str
    url: str
    name: Optional[str] = None
    location: Optional[str] = None
    parking_id: Optional[int] = None
    is_active: bool = True

    @staticmethod
    def from_entity(entity: "CameraEntity") -> "Camera":
        """Convierte una entidad SQLAlchemy a un modelo de dominio."""
        return Camera(
            camera_id=entity.camera_id,
            url=entity.url,
            name=entity.name,
            location=getattr(entity, "location", None),
            parking_id=getattr(entity, "parking_id", None),
            is_active=getattr(entity, "is_active", True)
        )

    def to_entity(self):
        """Convierte el modelo de dominio a una entidad SQLAlchemy (para persistencia)."""
        from src.infrastructure.Database.entities.camera_entity import CameraEntity
        return CameraEntity(
            camera_id=self.camera_id,
            url=self.url,
            name=self.name,
            location=self.location,
            parking_id=self.parking_id,
            is_active=self.is_active,
        )
