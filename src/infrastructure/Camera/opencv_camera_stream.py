# src/infrastructure/Camera/opencv_camera_stream.py
import cv2
import time
import logging
import threading
from src.domain.Models.frame import Frame
from src.domain.Interfaces.camera_stream import ICameraStream

logger = logging.getLogger(__name__)

class OpenCVCameraStream(ICameraStream):
    """
    Implementación de ICameraStream usando OpenCV con lectura en hilo separado.
    Source en Frame será camera_id si está disponible, si no la URL.
    """

    def __init__(self, url: str, reconnect_attempts: int = 3, fps_limit: float = 0.0):
        """
        :param url: URL del stream (RTSP/HTTP/archivo).
        :param reconnect_attempts: Número de intentos de reconexión antes de fallar.
        :param fps_limit: Máx FPS (0 = ilimitado).
        """
        self.url = url
        self.camera_id = None  # puede ser setiado por la factory (create_camera_stream)
        self.cap = None
        self.reconnect_attempts = reconnect_attempts
        self.fps_limit = fps_limit
        self._last_frame_time = 0.0

        # variables para thread
        self._frame_lock = threading.Lock()
        self._latest_frame = None
        self._running = False
        self._thread = None

    def connect(self) -> None:
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

        # Si es RTSP, reducir el buffer a 1
        if isinstance(self.url, str) and self.url.startswith("rtsp://") and self.cap is not None:
            try:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                # no todos los builds de OpenCV soportan set(CAP_PROP_BUFFERSIZE)
                pass

        if not self.cap or not self.cap.isOpened():
            raise ConnectionError(f"No se pudo abrir el stream: {self.url}")

        logger.info(f"Conectado al stream: {self.url}")

        # Lanzar thread de lectura
        self._running = True
        self._thread = threading.Thread(target=self._update_frames, daemon=True)
        self._thread.start()

    def _update_frames(self):
        """ Hilo que lee continuamente frames y mantiene solo el más reciente """
        while self._running:
            if self.cap is None or not self.cap.isOpened():
                if not self._try_reconnect():
                    time.sleep(1)
                continue

            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Error al leer frame, intentando reconectar...")
                if not self._try_reconnect():
                    time.sleep(1)
                continue

            # source preferencial: camera_id si existe, si no la URL
            source = getattr(self, "camera_id", None) or self.url
            with self._frame_lock:
                self._latest_frame = Frame(data=frame, timestamp=time.time(), source=source)

    def read_frame(self):
        """ Devuelve el último frame disponible respetando el fps_limit """
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

    def _try_reconnect(self) -> bool:
        """ Intenta reconectar al stream """
        for attempt in range(1, self.reconnect_attempts + 1):
            logger.info(f"Reintentando conexión ({attempt}/{self.reconnect_attempts})...")
            cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)

            # Si es RTSP, aplicar de nuevo buffersize=1
            if isinstance(self.url, str) and self.url.startswith("rtsp://") and cap is not None:
                try:
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    pass

            if cap and cap.isOpened():
                self.cap = cap
                logger.info("Reconexión exitosa.")
                return True
            time.sleep(1)
        logger.error("No se pudo reconectar al stream.")
        return False

    def disconnect(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None
        logger.info("🔌 Stream cerrado.")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()
