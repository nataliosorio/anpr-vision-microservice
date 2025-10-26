# src/domain/Models/camera.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Camera:
    """
    Modelo de cámara: identificador lógico (camera_id) + URL + metadatos opcionales.
    Usar camera.id como 'camera_id' estable para dedup/tracing.
    """
    camera_id: str           # p.ej. "cam_entrance_1"
    url: str                 # RTSP/HTTP URL
    name: Optional[str] = None
    location: Optional[str] = None
