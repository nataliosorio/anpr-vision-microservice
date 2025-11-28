# src/infrastructure/Camera/camera_repository.py
from typing import List, Optional
from sqlalchemy.orm import Session
from src.domain.Models.camera import Camera
from src.domain.Interfaces.i_camera_repository import ICameraRepository
from src.infrastructure.Database.entities.camera_entity import CameraEntity
from src.infrastructure.Database.session import SessionLocal

class CameraRepository(ICameraRepository):
    """Repositorio de cámaras persistente usando SQLAlchemy."""

    def __init__(self):
        self.db: Session = SessionLocal()

    def get_all(self) -> List[Camera]:
        entities = self.db.query(CameraEntity).all()
        return [Camera.from_entity(e) for e in entities]

    def get_by_id(self, camera_id: str) -> Optional[Camera]:
        entity = (
            self.db.query(CameraEntity)
            .filter(CameraEntity.camera_id == camera_id)
            .first()
        )
        return Camera.from_entity(entity) if entity else None

    def save(self, camera: Camera) -> Camera:
        """Inserta o actualiza una cámara."""
        existing = self.db.query(CameraEntity).filter_by(camera_id=camera.camera_id).first()
        if existing:
            # Actualizar datos existentes
            existing.name = camera.name
            existing.url = camera.url
            existing.location = camera.location
            existing.parking_id = camera.parking_id
            existing.is_active = camera.is_active
            self.db.commit()
            self.db.refresh(existing)
            return Camera.from_entity(existing)

        # Crear nuevo registro
        entity = camera.to_entity()
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return Camera.from_entity(entity)

    def delete(self, camera_id: str) -> None:
        entity = self.db.query(CameraEntity).filter(CameraEntity.camera_id == camera_id).first()
        if entity:
            self.db.delete(entity)
            self.db.commit()

    def close(self):
        """Cierra la sesión de base de datos."""
        self.db.close()
