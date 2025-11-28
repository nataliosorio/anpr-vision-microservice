# src/infrastructure/Camera/camera_factory.py
from typing import Optional
from src.core.config import settings
from src.domain.Interfaces.camera_stream import ICameraStream
from src.domain.Models.camera import Camera

def create_camera_stream(camera: Optional[Camera] = None) -> ICameraStream:
    """
    Factory responsable de crear el stream correcto (OpenCV, Picamera2 o FakeCameraStream).
    También adjunta la metadata de la cámara al stream resultante.
    """

# ==========================================================
# 🧪 1) Fake camera para pruebas y stress tests
# ==========================================================
    if settings.use_fake_cam:
        from src.infrastructure.Camera.fake_camera_stream import FakeCameraStream

        video_path = settings.camera_url.replace("fake://", "")  # usa el video que tengas en settings
        stream = FakeCameraStream(
            video_path=video_path,
            camera_id=camera.camera_id if camera else "fake",
            parking_id=camera.parking_id if camera else None
        )

    # ==========================================================
    # 🎥 2) Picamera2 modo nativo (solo hardware compatible)
    # ==========================================================
    elif settings.camera_native:
        from src.infrastructure.Camera.picamera2_camera_stream import Picamera2CameraStream
        stream = Picamera2CameraStream(camera)

    # ==========================================================
    # 📷 3) OpenCV (modo normal RTSP/HTTP/file)
    # ==========================================================
    else:
        from src.infrastructure.Camera.opencv_camera_stream import OpenCVCameraStream
        url = camera.url if camera is not None else settings.camera_url
        stream = OpenCVCameraStream(url)

    # ==========================================================
    # 🧩 4) Metadata desde modelo Camera → stream
    # ==========================================================
    if camera is not None:
        stream.camera_id = getattr(camera, "camera_id", None)
        stream.url = getattr(camera, "url", settings.camera_url)
        stream.parking_id = getattr(camera, "parking_id", None)
        stream.name = getattr(camera, "name", None)
        stream.location = getattr(camera, "location", None)
    else:
        # fallback cuando no hay DB pero se quiere arrancar
        stream.camera_id = "default"
        stream.url = getattr(stream, "url", settings.camera_url)
        stream.parking_id = None
        stream.name = "ENTRADA"
        stream.location = None

    return stream
