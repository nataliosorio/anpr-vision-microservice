# src/infrastructure/Camera/opencv_camera_stream.py

import cv2
import time
import logging
from src.domain.Models.frame import Frame
from src.domain.Interfaces.camera_stream import ICameraStream

logger = logging.getLogger(__name__)


class OpenCVCameraStream(ICameraStream):
    """
    Implementación simplificada para PlateRecognitionServiceV2.
    - Sin thread interno (el pipeline ya maneja captura)
    - read_frame(timeout=...) real
    - reconexión automática ligera
    """

    def __init__(self, url: str, reconnect_attempts: int = 3):
        self.url = url
        self.camera_id = None
        self.parking_id = None
        self.name = None
        self.location = None

        self.cap = None
        self.reconnect_attempts = reconnect_attempts

    # ==========================================================
    # CONNECT
    # ==========================================================
    def connect(self) -> None:
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

        # RTSP → desactivar buffers
        if isinstance(self.url, str) and self.url.startswith("rtsp://"):
            try:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except:
                pass

        if not self.cap or not self.cap.isOpened():
            raise ConnectionError(f"No se pudo abrir el stream: {self.url}")

        logger.info(
            f"🎥 Conectado a {self.name or self.camera_id or self.url} "
            f"(parking={self.parking_id})"
        )

    # ==========================================================
    # READ FRAME CON TIMEOUT
    # ==========================================================
    def read_frame(self, timeout: float = 1.0):
        """
        Lee un frame con timeout real.
        Si falla → reintenta reconectar.
        """
        if self.cap is None:
            if not self._try_reconnect():
                return None

        deadline = time.time() + timeout

        while time.time() < deadline:
            ret, frame = self.cap.read()
            if ret:
                source = getattr(self, "camera_id", None) or self.url
                return Frame(
                    data=frame,
                    timestamp=time.time(),
                    source=source
                )

            # intentar reconectar si no lee
            if not self._try_reconnect():
                break

        return None

    # ==========================================================
    # RECONNECT
    # ==========================================================
    def _try_reconnect(self) -> bool:
        for attempt in range(1, self.reconnect_attempts + 1):
            logger.warning(
                f"[{self.camera_id}] Reintentando conexión {attempt}/{self.reconnect_attempts}..."
            )

            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

            if isinstance(self.url, str) and self.url.startswith("rtsp://"):
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except:
                    pass

            if cap and cap.isOpened():
                self.cap = cap
                logger.info(f"[{self.camera_id}] Reconexión exitosa.")
                return True

            time.sleep(0.2)  # rápido, no 1 segundo

        logger.error(f"[{self.camera_id}] No se pudo reconectar.")
        return False

    # ==========================================================
    # DISCONNECT
    # ==========================================================
    def disconnect(self) -> None:
        if self.cap:
            try:
                self.cap.release()
            except:
                pass
            self.cap = None

        logger.info(f"🔌 Stream cerrado ({self.camera_id}).")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
