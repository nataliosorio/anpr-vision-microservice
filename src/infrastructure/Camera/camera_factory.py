# src/infrastructure/Camera/camera_factory.py
from typing import Optional
from src.core.config import settings
from src.domain.Interfaces.camera_stream import ICameraStream
from src.domain.Models.camera import Camera

def create_camera_stream(camera: Optional[Camera] = None) -> ICameraStream:
    """
    Factory que devuelve un ICameraStream. Si se pasa un modelo Camera,
    se asegura de que el stream tenga atributos .camera_id y .url para que
    el resto del pipeline use camera_id (trazabilidad, dedup por cámara).
    """
    if settings.camera_native:
        # Si usas Picamera2 en algún host, ajusta aquí
        from src.infrastructure.Camera.picamera2_camera_stream import Picamera2CameraStream
        # Instanciación conservadora: si el constructor acepta Camera, pásalo; si no, lo adjuntamos
        try:
            stream = Picamera2CameraStream(camera) if camera is not None else Picamera2CameraStream()
        except TypeError:
            stream = Picamera2CameraStream()
    else:
        from src.infrastructure.Camera.opencv_camera_stream import OpenCVCameraStream
        url = camera.url if camera is not None else settings.camera_url
        stream = OpenCVCameraStream(url)

    # Anexar metadata útil al stream (retrocompatible)
    stream.url = camera.url if camera is not None else getattr(stream, "url", settings.camera_url)
    stream.camera_id = camera.camera_id if camera is not None else getattr(stream, "camera_id", "default")

    return stream
