import cv2
import time
import logging
import threading
from typing import Optional

from src.domain.Models.frame import Frame
from src.domain.Interfaces.camera_stream import ICameraStream

logger = logging.getLogger(__name__)


class OpenCVCameraStream(ICameraStream):
    """
    Implementación de ICameraStream usando OpenCV con lectura en hilo separado.
    - Un hilo interno (_update_frames) lee continuamente del stream y mantiene SOLO el último frame.
    - read_frame(timeout=...) devuelve el último frame disponible sin bloquearse por FFMPEG.
    """

    def __init__(self, url: str, reconnect_attempts: int = 3, fps_limit: float = 0.0):
        """
        :param url: URL del stream (RTSP/HTTP/archivo).
        :param reconnect_attempts: Número de intentos de reconexión antes de fallar.
        :param fps_limit: Máx FPS que se devolverán (0 = ilimitado).
        """
        self.url = url

        # metadata que adjunta la factory
        self.camera_id: Optional[str] = None
        self.parking_id: Optional[int] = None
        self.name: Optional[str] = None
        self.location: Optional[str] = None

        self.cap = None
        self.reconnect_attempts = reconnect_attempts
        self.fps_limit = fps_limit
        self._last_frame_time = 0.0

        # control del hilo interno
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[Frame] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ==========================================================
    # CONNECT
    # ==========================================================
    def connect(self) -> None:
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

        # Si es RTSP, reducir el buffer
        if isinstance(self.url, str) and self.url.startswith("rtsp://") and self.cap is not None:
            try:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                # no todos los builds soportan CAP_PROP_BUFFERSIZE
                pass

        if not self.cap or not self.cap.isOpened():
            raise ConnectionError(f"No se pudo abrir el stream: {self.url}")

        logger.info(
            f"🎥 Conectado a {self.name or self.camera_id or self.url} "
            f"(parking={self.parking_id})"
        )

        # Lanzar hilo de lectura continua
        self._running = True
        self._thread = threading.Thread(target=self._update_frames, daemon=True)
        self._thread.start()

    # ==========================================================
    # THREAD QUE LEE FRAMES CONTINUAMENTE
    # ==========================================================
    def _update_frames(self):
        """ Hilo que lee continuamente frames y mantiene solo el más reciente. """
        while self._running:
            if self.cap is None or not self.cap.isOpened():
                if not self._try_reconnect():
                    time.sleep(1)
                continue

            ret, frame = self.cap.read()
            if not ret:
                logger.warning(
                    f"[{self.camera_id}] Error al leer frame, intentando reconectar..."
                )
                if not self._try_reconnect():
                    time.sleep(1)
                continue

            source = getattr(self, "camera_id", None) or self.url
            with self._frame_lock:
                self._latest_frame = Frame(
                    data=frame,
                    timestamp=time.time(),
                    source=source
                )

    # ==========================================================
    # READ FRAME (NO BLOQUEANTE POR FFMPEG)
    # ==========================================================
    def read_frame(self, timeout: float = 1.0):
        """
        Devuelve el último frame disponible respetando fps_limit.
        No llama directamente a cap.read(), solo usa el buffer interno.
        :param timeout: tiempo máximo esperando a que llegue algún frame.
        """
        deadline = time.time() + timeout

        while time.time() < deadline and self._running:
            with self._frame_lock:
                frame = self._latest_frame

            if frame is not None:
                # limitar FPS si se configuró
                if self.fps_limit > 0:
                    elapsed = time.time() - self._last_frame_time
                    min_interval = 1.0 / self.fps_limit
                    if elapsed < min_interval:
                        # Aún no toca devolver otro frame
                        sleep_for = min(0.005, min_interval - elapsed)
                        time.sleep(max(sleep_for, 0.0))
                        continue

                self._last_frame_time = time.time()
                return frame

            # todavía no hay frames en el buffer
            time.sleep(0.01)

        return None

    # ==========================================================
    # RECONNECT
    # ==========================================================
    def _try_reconnect(self) -> bool:
        """ Intenta reconectar al stream """
        for attempt in range(1, self.reconnect_attempts + 1):
            logger.warning(
                f"[{self.camera_id}] Reintentando conexión {attempt}/{self.reconnect_attempts}..."
            )
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

            if isinstance(self.url, str) and self.url.startswith("rtsp://") and cap is not None:
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

            if cap and cap.isOpened():
                self.cap = cap
                logger.info(f"[{self.camera_id}] Reconexión exitosa.")
                return True

            time.sleep(1)

        logger.error(f"[{self.camera_id}] No se pudo reconectar al stream.")
        return False

    # ==========================================================
    # DISCONNECT
    # ==========================================================
    def disconnect(self) -> None:
        self._running = False

        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=2.0)
            except Exception:
                pass

        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        logger.info(f"🔌 Stream cerrado ({self.camera_id}).")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
