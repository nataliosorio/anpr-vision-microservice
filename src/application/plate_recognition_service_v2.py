import logging
import time
import uuid
import cv2
import threading
import queue
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Iterable, Any

from src.domain.Models.detection_result import DetectionResult
from src.domain.Interfaces.camera_stream import ICameraStream
from src.domain.Interfaces.plate_detector import IPlateDetector
from src.domain.Interfaces.ocr_reader import IOCRReader
from src.domain.Interfaces.event_publisher import IEventPublisher
from src.domain.Interfaces.tracker import ITracker
from src.domain.Interfaces.deduplicator import IDeduplicator
from src.domain.Interfaces.text_normalizer import ITextNormalizer
from src.core.config import settings

logger = logging.getLogger(__name__)


class PlateRecognitionServiceV2:
    def __init__(
        self,
        camera_stream: ICameraStream,
        detector: IPlateDetector,
        ocr_reader: IOCRReader,
        publisher: IEventPublisher,
        tracker: ITracker,
        deduplicator: IDeduplicator,
        normalizer: ITextNormalizer,
        debug_show: bool = False,
        max_fps: float = 10.0,   # controla captura real
        processing_workers: int | None = None,
        ocr_worker: bool = True,
    ):
        self.camera_stream = camera_stream
        self.detector = detector
        self.ocr_reader = ocr_reader
        self.publisher = publisher
        self.tracker = tracker
        self.deduplicator = deduplicator
        self.normalizer = normalizer

        self.debug_show = debug_show
        self.max_fps = max_fps
        self.frame_interval = 1.0 / max_fps

        self.camera_id = getattr(camera_stream, "camera_id", None) or "default"
        self.parking_id = getattr(camera_stream, "parking_id", None)

        # Evento de parada
        self.stop_event = threading.Event()

        # Colas
        self.capture_queue = queue.Queue(maxsize=3)
        self.publish_queue = queue.Queue(maxsize=50)

        # Workers
        self.processing_workers = processing_workers or max(1, (os.cpu_count() or 2) - 1)
        self.executor = ThreadPoolExecutor(max_workers=self.processing_workers)
        self.ocr_executor = ThreadPoolExecutor(max_workers=1) if ocr_worker else None

        # Threads
        self.capture_thread = None
        self.publish_thread = None

    # ==========================================================
    #  PUBLIC API
    # ==========================================================
    def start(self):
        """Inicia captura, procesamiento y publicación."""
        logger.info(f"[V2] Iniciando servicio camera_id={self.camera_id}")

        self.camera_stream.connect()
        self.stop_event.clear()

        # Capture thread
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

        # Publish thread
        self.publish_thread = threading.Thread(target=self._publish_loop, daemon=True)
        self.publish_thread.start()

        logger.info(f"[V2] Service iniciado correctamente camera_id={self.camera_id}")

    def stop(self):
        """Detiene todos los hilos y workers."""
        logger.info(f"[V2] Deteniendo servicio camera_id={self.camera_id}...")

        self.stop_event.set()

        # Despertar threads bloqueados
        try:
            self.capture_queue.put_nowait(None)
        except:
            pass
        try:
            self.publish_queue.put_nowait(None)
        except:
            pass

        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.publish_thread:
            self.publish_thread.join(timeout=2)

        self.executor.shutdown(wait=False, cancel_futures=True)
        if self.ocr_executor:
            self.ocr_executor.shutdown(wait=False, cancel_futures=True)

        try:
            self.camera_stream.disconnect()
        except:
            logger.exception("Fallo al desconectar stream")

        try:
            cv2.destroyAllWindows()
        except:
            pass

        logger.info(f"[V2] Servicio detenido correctamente camera_id={self.camera_id}")

    # ==========================================================
    #  CAPTURE LOOP (thread independiente)
    # ==========================================================
    def _capture_loop(self):
        last_frame_time = 0

        while not self.stop_event.is_set():
            now = time.perf_counter()

            # FPS pacing
            if now - last_frame_time < self.frame_interval:
                time.sleep(0.001)
                continue

            frame = self.camera_stream.read_frame(timeout=1.0)
            last_frame_time = now

            if frame is None:
                time.sleep(0.1)
                continue

            try:
                self.capture_queue.put_nowait(frame)
            except queue.Full:
                # last frame wins
                try:
                    _ = self.capture_queue.get_nowait()
                    self.capture_queue.put_nowait(frame)
                except:
                    pass

            # dispatch processing
            self.executor.submit(self._process_frame, frame)

    # ==========================================================
    #  PROCESSING (ejecutado en ThreadPoolExecutor)
    # ==========================================================
    def _process_frame(self, frame):
        if self.stop_event.is_set():
            return

        # Detect plates
        try:
            bboxes = self.detector.detect(frame) or []
        except Exception:
            logger.exception("Detector falló")
            return

        # OCR → worker dedicado (si lo definiste)
        raw_ocr = []
        if bboxes:
            raw_ocr = self._run_ocr(frame, bboxes)

        results = self._normalize_and_track(raw_ocr)

        if not results:
            return

        # Publicación
        try:
            event = self._make_event(results, frame)
            self.publish_queue.put_nowait(event)
        except queue.Full:
            logger.warning("Publish queue llena, evento descartado")

    # ==========================================================
    #  OCR HANDLER
    # ==========================================================
    def _run_ocr(self, frame, bboxes):
        if not self.ocr_executor:
            return [self.ocr_reader.read_text(frame, b) for b in bboxes]

        futures = [self.ocr_executor.submit(self.ocr_reader.read_text, frame, b) for b in bboxes]
        return [f.result() for f in futures]

    # ==========================================================
    #  NORMALIZACIÓN + TRACKING + DEDUP
    # ==========================================================
    def _normalize_and_track(self, raw):
        processed = []

        for r in raw:
            raw_text = getattr(r, "text", None)
            if not raw_text:
                continue

            norm = self.normalizer.normalize(raw_text)
            if not norm:
                continue

            if getattr(r, "confidence", 1.0) < settings.ocr_min_confidence:
                continue

            plate = SimpleNamespace(
                text=norm,
                confidence=getattr(r, "confidence", 1.0),
                bounding_box=getattr(r, "bounding_box", None)
            )
            processed.append(plate)

        if not processed:
            return []

        # tracking
        tracked = self.tracker.update(processed)

        # dedup
        unique = []
        for p in tracked:
            tid = getattr(p, "track_id", None)
            txt = getattr(p, "text", None)

            if not txt:
                continue

            if not self.deduplicator.is_duplicate(tid, txt, self.camera_id):
                unique.append(p)

        return unique

    # ==========================================================
    #  PUBLISH THREAD
    # ==========================================================
    def _publish_loop(self):
        while not self.stop_event.is_set():
            try:
                event = self.publish_queue.get(timeout=1)
            except queue.Empty:
                continue

            if event is None:
                break

            try:
                self.publisher.publish(event)
            except Exception:
                logger.exception("Error al publicar evento")

    # ==========================================================
    #  EVENT FACTORY
    # ==========================================================
    def _make_event(self, plates, frame):
        captured_at = getattr(frame, "timestamp", time.time())
        ev_id = f"{self.camera_id}:{ plates[0].text }:{int(captured_at)}"

        return DetectionResult(
            event_id=ev_id,
            frame_id=str(uuid.uuid4()),
            plates=plates,
            processed_at=time.time(),
            source=getattr(frame, "source", None),
            captured_at=captured_at,
            camera_id=self.camera_id,
            parking_id=self.parking_id,
        )
