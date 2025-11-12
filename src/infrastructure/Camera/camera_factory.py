# src/infrastructure/Camera/camera_factory.py
from typing import Optional
from src.core.config import settings
from src.domain.Interfaces.camera_stream import ICameraStream
from src.domain.Models.camera import Camera

def create_camera_stream(camera: Optional[Camera] = None) -> ICameraStream:
    """
    Factory que devuelve un ICameraStream.
    Si se pasa un modelo Camera, se asegura de que el stream tenga
    los metadatos necesarios (camera_id, parking_id, name, location).
    """
    if settings.camera_native:
        # Si usas Picamera2 en algún host, ajusta aquí
        from src.infrastructure.Camera.picamera2_camera_stream import Picamera2CameraStream
        try:
            stream = Picamera2CameraStream(camera) if camera is not None else Picamera2CameraStream()
        except TypeError:
            stream = Picamera2CameraStream()
    else:
        from src.infrastructure.Camera.opencv_camera_stream import OpenCVCameraStream
        url = camera.url if camera is not None else settings.camera_url
        stream = OpenCVCameraStream(url)

    # ==========================================================
    # 📦 Anexar metadatos de la cámara (dominio → stream)
    # ==========================================================
    if camera is not None:
        stream.camera_id = getattr(camera, "camera_id", None)
        stream.url = getattr(camera, "url", settings.camera_url)
        stream.parking_id = getattr(camera, "parking_id", None)
        stream.name = getattr(camera, "name", None)
        stream.location = getattr(camera, "location", None)
    else:
        # fallback: modo "standalone" (por si el micro no tiene BD)
        stream.camera_id = getattr(stream, "camera_id", "default")
        stream.url = getattr(stream, "url", settings.camera_url)
        stream.parking_id = None
        stream.name = "ENTRADA"
        stream.location = None

    return stream
