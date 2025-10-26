import time
import logging
import threading
import numpy as np

from src.domain.Models.frame import Frame
from src.domain.Interfaces.camera_stream import ICameraStream

logger = logging.getLogger(__name__)

class Picamera2CameraStream(ICameraStream):
    """
    Implementación ICameraStream usando Picamera2 (libcamera) en Raspberry Pi.
    Mantiene solo el frame más reciente (low-latency).
    """
    def __init__(
        self,
        resolution: tuple[int, int] = (1280, 720),
        fps: int = 30,
        fps_limit: float = 0.0,
        denoise: str = "cdn_off",  # 'cdn_off', 'cdn_fast', 'cdn_hq'
        sharpness: float = 1.2,    # pequeño boost para placas
        contrast: float = 1.0,
        brightness: float = 0.0,   # -1..1
        awb: str = "auto",         # 'auto','tungsten','fluorescent','indoor','daylight','cloudy'
        hflip: bool = False,
        vflip: bool = False
    ):
        self.resolution = resolution
        self.fps = fps
        self.fps_limit = fps_limit

        self.denoise = denoise
        self.sharpness = sharpness
        self.contrast = contrast
        self.brightness = brightness
        self.awb = awb
        self.hflip = hflip
        self.vflip = vflip

        self._last_frame_time = 0.0
        self._frame_lock = threading.Lock()
        self._latest_frame = None
        self._running = False
        self._thread = None

        self._picam2 = None

    def connect(self) -> None:
        try:
            from picamera2 import Picamera2, Preview
            from libcamera import Transform
        except Exception as e:
            raise RuntimeError(
                "Picamera2 no está instalado o no carga. Instala con `sudo apt install python3-picamera2`."
            ) from e

        self._picam2 = Picamera2()

        # Configuración de captura para procesado en CPU con OpenCV
        transform = Transform(hflip=self.hflip, vflip=self.vflip)

        # Recomendación: formato 'BGR888' directo para evitar conversiones
        video_config = self._picam2.create_video_configuration(
            main={"size": self.resolution, "format": "BGR888"},
            transform=transform,
            controls={
                "FrameDurationLimits": (int(1e6 // self.fps), int(1e6 // self.fps)),
            },
        )

        self._picam2.configure(video_config)

        # Controles de imagen (evitar ruido y mejorar nitidez para LPR)
        # Algunos controles dependen del sensor; si alguno falla, capturamos excepción suave.
        try:
            self._picam2.set_controls({
                "NoiseReductionMode": 0,  # 0=Off
                "AwbEnable": (self.awb == "auto"),
            })
        except Exception:
            pass

        # Ajustes post-proceso vía Picamera2 no siempre son directos; muchos se hacen en OpenCV.
        # Aquí dejamos el pipeline limpio (denoise off). Nitidez/contraste/brillo los puedes aplicar luego si quieres.

        self._picam2.start()
        logger.info(f"📷 Picamera2 iniciada {self.resolution}@{self.fps}fps, denoise={self.denoise}")

        # Hilo lector (siempre último frame)
        self._running = True
        self._thread = threading.Thread(target=self._update_frames, daemon=True)
        self._thread.start()

    def _update_frames(self):
        while self._running:
            try:
                frame = self._picam2.capture_array()  # ndarray BGR888 (H,W,3)
            except Exception as e:
                logger.error(f"Error capturando frame desde Picamera2: {e}")
                time.sleep(0.2)
                continue

            now = time.time()

            with self._frame_lock:
                # Puedes aplicar post-proceso ligero aquí si lo deseas:
                # p.ej., brillo/contraste/afilar con OpenCV
                # (lo dejo crudo para latencia mínima)
                self._latest_frame = Frame(data=frame, timestamp=now, source="picamera2")

    def read_frame(self) -> Frame | None:
        if self.fps_limit > 0:
            elapsed = time.time() - self._last_frame_time
            min_interval = 1.0 / self.fps_limit
            if elapsed < min_interval:
                return None

        with self._frame_lock:
            frame = self._latest_frame

        if frame is None:
            return None

        self._last_frame_time = time.time()
        return frame

    def disconnect(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        if self._picam2:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                pass
            self._picam2 = None

        logger.info("🔌 Picamera2 cerrada.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
