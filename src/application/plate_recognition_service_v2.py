import logging
import time
import uuid
import cv2
import threading
import queue
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from src.monitoring.metrics import (
    camera_fps, plates_detected_total,
    detector_latency, ocr_latency, pipeline_latency
)

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
        max_fps: float = 10.0,
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

        self.stop_event = threading.Event()

        # queues
        # 👇 cola acotada de captura (modo last-wins)
        self.capture_queue = queue.Queue(maxsize=3)
        self.publish_queue = queue.Queue(maxsize=50)

        # worker pools
        self.processing_workers = processing_workers or max(1, (os.cpu_count() or 2) - 1)
        # Solo usamos executor para OCR (paralelizar bboxes dentro de un frame si quieres)
        self.ocr_executor = ThreadPoolExecutor(max_workers=1) if ocr_worker else None

        # threads
        self.capture_thread: threading.Thread | None = None
        self.publish_thread: threading.Thread | None = None
        self.processing_threads: list[threading.Thread] = []

    # ---------------------------------------------------------
    # START / STOP
    # ---------------------------------------------------------
    def start(self):
        logger.info(f"[V2] Iniciando cámara {self.camera_id}")

        self.stop_event.clear()
        self.camera_stream.connect()

        # hilo de captura
        self.capture_thread = threading.Thread(
            target=self._capture_loop,
            name=f"capture-{self.camera_id}",
            daemon=True,
        )
        self.capture_thread.start()

        # hilo de publicación
        self.publish_thread = threading.Thread(
            target=self._publish_loop,
            name=f"publish-{self.camera_id}",
            daemon=True,
        )
        self.publish_thread.start()

        # workers de procesamiento que consumen de capture_queue
        for i in range(self.processing_workers):
            t = threading.Thread(
                target=self._processing_worker_loop,
                name=f"proc-{self.camera_id}-{i}",
                daemon=True,
            )
            t.start()
            self.processing_threads.append(t)

    def stop(self):
        logger.info(f"[V2] Deteniendo cámara {self.camera_id}")

        self.stop_event.set()
        try:
            # Sentinelas para despertar a los workers de procesamiento
            for _ in range(self.processing_workers):
                self.capture_queue.put_nowait(None)
            # Sentinela para publish_loop
            self.publish_queue.put_nowait(None)
        except Exception:
            pass

        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.publish_thread:
            self.publish_thread.join(timeout=2)

        for t in self.processing_threads:
            t.join(timeout=2)

        if self.ocr_executor:
            self.ocr_executor.shutdown(wait=False, cancel_futures=True)

        try:
            self.camera_stream.disconnect()
        except Exception:
            logger.exception("Error desconectando cámara")

    # ---------------------------------------------------------
    # CAPTURE LOOP
    # ---------------------------------------------------------
    def _capture_loop(self):
        last_frame_time = 0
        fps_counter = 0
        fps_timer = time.time()

        while not self.stop_event.is_set():
            now = time.perf_counter()

            if now - last_frame_time < self.frame_interval:
                time.sleep(0.001)
                continue

            frame = self.camera_stream.read_frame(timeout=1.0)
            last_frame_time = now

            if frame is None:
                time.sleep(0.1)
                continue

            fps_counter += 1
            if time.time() - fps_timer >= 1:
                camera_fps.labels(camera_id=self.camera_id).set(fps_counter)
                logger.debug(f"[V2][{self.camera_id}] FPS actual: {fps_counter}")
                fps_counter = 0
                fps_timer = time.time()

            # Encolar frame con política "last wins"
            try:
                self.capture_queue.put_nowait(frame)
            except queue.Full:
                try:
                    _ = self.capture_queue.get_nowait()
                    self.capture_queue.put_nowait(frame)
                except Exception:
                    # si no se puede, simplemente se descarta este frame
                    pass

    # ---------------------------------------------------------
    # PROCESSING WORKERS
    # ---------------------------------------------------------
    def _processing_worker_loop(self):
        while not self.stop_event.is_set():
            try:
                frame = self.capture_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if frame is None:
                self.capture_queue.task_done()
                break

            try:
                self._process_frame(frame)
            finally:
                self.capture_queue.task_done()

        logger.info(f"[V2][{self.camera_id}] Worker de procesamiento terminado")

    # ---------------------------------------------------------
    # PROCESSING (por frame)
    # ---------------------------------------------------------
    def _process_frame(self, frame):
        t0 = time.perf_counter()

        try:
            # detector
            t1 = time.perf_counter()
            bboxes = self.detector.detect(frame) or []
            detector_latency.labels(camera_id=self.camera_id).set(time.perf_counter() - t1)

            if not bboxes:
                logger.debug(f"[V2][{self.camera_id}] Sin bboxes en este frame.")
                return

            # ocr
            t2 = time.perf_counter()
            raw_ocr = self._run_ocr(frame, bboxes)
            ocr_latency.labels(camera_id=self.camera_id).set(time.perf_counter() - t2)

            if not raw_ocr:
                logger.debug(f"[V2][{self.camera_id}] OCR vacío (sin texto útil).")
                return

            plates = self._normalize_and_track(raw_ocr, frame)
            if not plates:
                logger.debug(f"[V2][{self.camera_id}] Después de normalizar/tracking no hay placas únicas.")
                return

            # publish
            event = self._make_event(plates, frame)
            try:
                self.publish_queue.put_nowait(event)
            except queue.Full:
                logger.warning(f"[V2][{self.camera_id}] publish_queue llena, descartando evento.")

            pipeline_latency.labels(camera_id=self.camera_id).set(time.perf_counter() - t0)

        except Exception:
            logger.exception(f"[V2][{self.camera_id}] Error procesando frame")

    # ---------------------------------------------------------
    # OCR
    # ---------------------------------------------------------
    def _run_ocr(self, frame, bboxes):
        if not self.ocr_executor:
            return [self.ocr_reader.read_text(frame, b) for b in bboxes]

        futures = [self.ocr_executor.submit(self.ocr_reader.read_text, frame, b) for b in bboxes]
        results = []
        for f in futures:
            try:
                results.append(f.result())
            except Exception:
                logger.exception(f"[V2][{self.camera_id}] OCR falló en una bbox")
        return results

    # ---------------------------------------------------------
    # NORMALIZATION + TRACKING
    # ---------------------------------------------------------
    def _normalize_and_track(self, raw, frame=None):
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

            processed.append(SimpleNamespace(
                text=norm,
                confidence=getattr(r, "confidence", 1.0),
                bounding_box=getattr(r, "bounding_box", None),
            ))

        if not processed:
            logger.debug(f"[V2][{self.camera_id}] processed=0 después de normalizer/filtrado.")
            return []

        # calcular image_size
        image_size = None
        if frame is not None:
            try:
                img = getattr(frame, "data", None)
                if img is not None:
                    h, w = img.shape[:2]
                    image_size = (h, w)
            except Exception:
                pass

        # tracker.update con compatibilidad V1/V2
        try:
            if image_size:
                tracked = self.tracker.update(processed, image_size=image_size)
            else:
                tracked = self.tracker.update(processed)
        except TypeError:
            tracked = self.tracker.update(processed)
        except Exception:
            logger.exception(f"[V2][{self.camera_id}] Tracker.update falló")
            return []

        tracked = tracked or []

        unique = []
        for p in tracked:
            tid = getattr(p, "track_id", None)
            txt = getattr(p, "text", None)

            if not txt:
                continue

            try:
                if not self.deduplicator.is_duplicate(tid, txt, self.camera_id):
                    unique.append(p)
            except TypeError:
                try:
                    if not self.deduplicator.is_duplicate(tid, txt):
                        unique.append(p)
                except Exception:
                    logger.exception(f"[V2][{self.camera_id}] Deduplicator falló para track={tid} text={txt}")
            except Exception:
                logger.exception(f"[V2][{self.camera_id}] Deduplicator falló para track={tid} text={txt}")

        if unique:
            plates_detected_total.labels(camera_id=self.camera_id).inc()

        logger.debug(
            f"[V2][{self.camera_id}] raw={len(raw)} processed={len(processed)} "
            f"tracked={len(tracked)} unique={len(unique)}"
        )

        return unique

    # ---------------------------------------------------------
    # PUBLISH LOOP
    # ---------------------------------------------------------
    def _publish_loop(self):
        while not self.stop_event.is_set():
            try:
                event = self.publish_queue.get(timeout=1)
            except queue.Empty:
                continue

            if event is None:
                self.publish_queue.task_done()
                break

            try:
                self.publisher.publish(event)
            except Exception:
                logger.exception(f"[V2][{self.camera_id}] Error publicando evento")
            finally:
                self.publish_queue.task_done()

        logger.info(f"[V2][{self.camera_id}] Publish loop terminado")

    # ---------------------------------------------------------
    # EVENT FACTORY
    # ---------------------------------------------------------
    def _make_event(self, plates, frame):
        captured_at = getattr(frame, "timestamp", time.time())
        ev_id = f"{self.camera_id}:{plates[0].text}:{int(captured_at)}"

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
