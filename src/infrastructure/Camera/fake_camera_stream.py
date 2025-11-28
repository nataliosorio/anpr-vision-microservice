import cv2
import time
from src.domain.Models.frame import Frame
from src.domain.Interfaces.camera_stream import ICameraStream


class FakeCameraStream(ICameraStream):
    """
    Simula una cámara usando un archivo de video.
    Compatible 100% con PlateRecognitionServiceV2.
    """

    def __init__(self, video_path: str, camera_id: str, parking_id: int):
        self.video_path = video_path
        self.camera_id = camera_id
        self.parking_id = parking_id

        self.url = f"fake://{video_path}"
        self.name = camera_id
        self.location = None

        self.cap = None

    # ==========================================================
    # CONNECT
    # ==========================================================
    def connect(self):
        self.cap = cv2.VideoCapture(self.video_path)

        if not self.cap.isOpened():
            raise RuntimeError(f"No se pudo abrir video {self.video_path}")

    # ==========================================================
    # READ FRAME CON TIMEOUT
    # ==========================================================
    def read_frame(self, timeout: float = 1.0):
        """
        Devuelve un Frame o None si pasa el timeout.
        Hace loop infinito del video.
        """
        start = time.time()

        while time.time() - start < timeout:
            ok, frame = self.cap.read()

            if ok:
                return Frame(
                    data=frame,
                    timestamp=time.time(),
                    source=self.camera_id
                )

            # Si llega al final del video → reiniciar
            self._restart_video()

        return None

    # ==========================================================
    # INTERNAL: RESTART VIDEO
    # ==========================================================
    def _restart_video(self):
        """Reinicia el archivo simulando un stream continuo."""
        if self.cap:
            self.cap.release()
        self.cap = cv2.VideoCapture(self.video_path)

    # ==========================================================
    # DISCONNECT
    # ==========================================================
    def disconnect(self):
        if self.cap:
            self.cap.release()
            self.cap = None
