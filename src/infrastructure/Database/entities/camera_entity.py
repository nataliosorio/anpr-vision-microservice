# src/infrastructure/Database/entities/camera_entity.py
from sqlalchemy import Column, String, Integer, Boolean
from src.infrastructure.Database.base import Base

class CameraEntity(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(100), unique=True, nullable=False, index=True)
    url = Column(String(255), nullable=False)
    name = Column(String(100), nullable=True)
    location = Column(String(150), nullable=True)
    parking_id = Column(Integer, nullable=True, index=True)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return (
            f"<CameraEntity(id={self.id}, camera_id='{self.camera_id}', "
            f"name='{self.name}', location='{self.location}', "
            f"parking_id={self.parking_id}, active={self.is_active})>"
        )
