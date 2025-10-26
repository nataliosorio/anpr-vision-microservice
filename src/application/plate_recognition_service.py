# src/application/plate_recognition_service.py
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="yolov5")

import time
import uuid
import cv2
import logging
import threading
import queue
import os
from types import SimpleNamespace
from typing import Any, Iterable

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


class PlateRecognitionService:
    def __init__(
        self,
        camera_stream: ICameraStream,
        detector: IPlateDetector,
        ocr_reader: IOCRReader,
        publisher: IEventPublisher,
        tracker: ITracker,
        deduplicator: IDeduplicator,
        normalizer: ITextNormalizer,
        debug_show: bool = True,
        loop_delay: float = 0.0,
    ):
        self.camera_stream = camera_stream
        self.detector = detector
        self.ocr_reader = ocr_reader
        self.publisher = publisher
        self.tracker = tracker
        self.deduplicator = deduplicator
        self.normalizer = normalizer

        self.debug_show = debug_show
        self.loop_delay = loop_delay

        self.running = False
        self.frame_idx = 0
        self.camera_id = getattr(self.camera_stream, "camera_id", None) or "default"
        self.target_dt = getattr(settings, "target_frame_seconds", 0.0)

        # Configurables (mover a settings si quieres)
        self.capture_queue_size = getattr(settings, "capture_queue_size", 6)
        self.processing_workers = max(1, getattr(settings, "processing_workers", max(1, (os.cpu_count() or 2) - 1)))
        self.publish_queue_size = getattr(settings, "publish_queue_size", 50)
        self.capture_queue: "queue.Queue" = queue.Queue(maxsize=self.capture_queue_size)
        self.publish_queue: "queue.Queue" = queue.Queue(maxsize=self.publish_queue_size)

        self.workers = []
        self.publisher_thread = None
        self.capture_thread = None

    # ----- START / STOP: spawn threads -----
    def start(self):
        self.camera_stream.connect()
        self.running = True
        logger.info("Servicio de reconocimiento iniciado (camera_id=%s) workers=%d queue=%d", self.camera_id, self.processing_workers, self.capture_queue_size)

        # start publisher thread
        self.publisher_thread = threading.Thread(target=self._publisher_loop, name="publisher-thread", daemon=True)
        self.publisher_thread.start()

        # start processing workers
        for i in range(self.processing_workers):
            t = threading.Thread(target=self._processing_worker, name=f"proc-worker-{i}", daemon=True)
            t.start()
            self.workers.append(t)

        # capture loop runs in main thread (or spawn thread if you prefer)
        try:
            self._capture_loop()
        except KeyboardInterrupt:
            logger.info("Interrupción recibida - deteniendo")
            self.stop()
        except Exception:
            logger.exception("Error en capture loop")
            self.stop()

    def stop(self):
        logger.info("Parando servicio, esperando threads...")
        self.running = False

        # unblock queues
        try:
            while not self.capture_queue.empty():
                self.capture_queue.get_nowait()
        except Exception:
            pass

        # signal publisher to stop
        try:
            self.publish_queue.put_nowait(None)
        except Exception:
            pass

        # join worker threads
        for t in self.workers:
            t.join(timeout=1.0)
        if self.publisher_thread:
            self.publisher_thread.join(timeout=1.0)

        try:
            self.camera_stream.disconnect()
        except Exception:
            logger.exception("Error al desconectar camera_stream")
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

        logger.info("Servicio detenido correctamente")

    # ----- Capture loop: solo lee y encola -----
    def _capture_loop(self):
        while self.running:
            loop_start = time.perf_counter()
            frame = self.camera_stream.read_frame()
            if frame is None:
                logger.debug("No se pudo leer frame, reintentando...")
                time.sleep(0.2)
                self._pace(loop_start)
                continue

            # intenta encolar sin bloquear demasiado
            try:
                self.capture_queue.put(frame, block=True, timeout=0.5)
            except queue.Full:
                # si la cola está llena, descarta el frame más antiguo y mete este (modo "last-wins")
                try:
                    _ = self.capture_queue.get_nowait()
                    self.capture_queue.put_nowait(frame)
                    logger.debug("Capture queue llena: descartado frame viejo, encolado nuevo")
                except Exception:
                    logger.debug("No se pudo encolar frame (queue full)")
            self._pace(loop_start)

    # ----- Processing worker: hace todo el pipeline por frame -----
    def _processing_worker(self):
        while self.running:
            try:
                frame = self.capture_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            if frame is None:
                continue

            t0 = time.perf_counter()
            # 1) Detectar bboxes
            try:
                t1 = time.perf_counter()
                plates_bboxes = self.detector.detect(frame) or []
                t_detect = time.perf_counter() - t1
            except Exception:
                logger.exception("Detector falló al procesar frame; saltando frame")
                self.capture_queue.task_done()
                continue

            # 2) OCR (según intervalo)
            raw_ocr_results = []
            run_ocr = (self.frame_idx % max(1, getattr(settings, "ocr_interval", 1))) == 0
            if run_ocr and plates_bboxes:
                t2 = time.perf_counter()
                for bbox in plates_bboxes:
                    try:
                        raw = self.ocr_reader.read_text(frame, bbox)
                        raw_ocr_results.append(raw)
                    except Exception:
                        logger.exception("OCR falló para bbox=%s", getattr(bbox, "bounding_box", getattr(bbox, "bbox", bbox)))
                t_ocr = time.perf_counter() - t2
            else:
                t_ocr = 0.0

            # 3) Normalización y filtrado (igual que antes)
            t3 = time.perf_counter()
            normalized_results = []
            for r in raw_ocr_results:
                raw_text = getattr(r, "text", None)
                if not raw_text:
                    continue
                norm = self.normalizer.normalize(raw_text)
                if not norm:
                    continue
                conf = getattr(r, "confidence", 1.0)
                if conf < getattr(settings, "ocr_min_confidence", 0.0):
                    continue
                bb = getattr(r, "bounding_box", None) or getattr(r, "bbox", None) or None
                plate_obj = SimpleNamespace()
                plate_obj.text = norm
                plate_obj.confidence = conf
                plate_obj.bounding_box = bb
                normalized_results.append(plate_obj)
            t_norm = time.perf_counter() - t3

            # 4) Tracking
            t4 = time.perf_counter()
            try:
                h, w = getattr(frame, "data", None).shape[:2] if getattr(frame, "data", None) is not None else getattr(frame, "image").shape[:2]
                tracked_results = self.tracker.update(normalized_results, image_size=(h, w)) if normalized_results else []
            except TypeError:
                tracked_results = self.tracker.update(normalized_results) if normalized_results else []
            except Exception:
                logger.exception("Tracker.update falló")
                tracked_results = []
            t_track = time.perf_counter() - t4

            # 5) Dedup + filter + queue to publisher
            t5 = time.perf_counter()
            unique_results = []
            for plate in tracked_results:
                text = getattr(plate, "text", None)
                track_id = getattr(plate, "track_id", None)
                if not text:
                    continue
                if len(text) > getattr(settings, "plate_max_length", 6):
                    continue
                try:
                    is_dup = self.deduplicator.is_duplicate(track_id=track_id, plate_text=text, camera_id=self.camera_id)
                except TypeError:
                    is_dup = self.deduplicator.is_duplicate(track_id=track_id, plate_text=text)
                except Exception:
                    logger.exception("Deduplicator error para track=%s text=%s", track_id, text)
                    is_dup = True
                if not is_dup:
                    unique_results.append(plate)
            t_dedup = time.perf_counter() - t5

            if unique_results:
                captured_at = getattr(frame, "timestamp", None) or time.time()
                source = getattr(frame, "source", None) or getattr(self.camera_stream, "url", None) or getattr(settings, "camera_url", None)
                event_id = self._build_event_id(self.camera_id, unique_results, captured_at)
                result = DetectionResult(
                    event_id=event_id,
                    frame_id=str(uuid.uuid4()),
                    plates=unique_results,
                    processed_at=time.time(),
                    source=source,
                    captured_at=captured_at,
                    camera_id=self.camera_id
                )
                # enqueue for publishing (no bloqueante largo)
                try:
                    self.publish_queue.put(result, block=False)
                except queue.Full:
                    logger.warning("Publish queue llena, descartando evento")

            total = time.perf_counter() - t0
            logger.debug(
                "Processed frame: detect=%.3fs ocr=%.3fs norm=%.3fs track=%.3fs dedup=%.3fs total=%.3fs",
                t_detect, t_ocr, t_norm, t_track, t_dedup, total,
            )

            self.frame_idx += 1
            self.capture_queue.task_done()

    # ----- Publisher thread -----
    def _publisher_loop(self):
        while True:
            try:
                item = self.publish_queue.get()
            except Exception:
                continue
            if item is None:
                break
            try:
                self.publisher.publish(item)
            except Exception:
                logger.exception("Error al publicar evento")
            self.publish_queue.task_done()

    # helpers
    def _build_event_id(self, camera_id: str, plates: Iterable[Any], captured_at: float) -> str:
        first = next(iter(plates))
        track_id = getattr(first, "track_id", "na")
        text = getattr(first, "text", "NA")
        return f"{camera_id}:{track_id}:{text}:{int(captured_at)}"

    def _pace(self, loop_start: float) -> None:
        if getattr(self, "target_dt", 0.0):
            elapsed = time.perf_counter() - loop_start
            sleep = max(0.0, self.target_dt - elapsed)
            if sleep > 0:
                time.sleep(sleep)
        elif self.loop_delay > 0:
            time.sleep(self.loop_delay)
