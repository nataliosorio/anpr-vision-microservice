import logging
from src.domain.Models.camera import Camera
from src.infrastructure.Camera.camera_factory import create_camera_stream
from src.infrastructure.Detector.factory import create_plate_detector
from src.infrastructure.OCR.EasyOCR_OCRReader import EasyOCR_OCRReader
from src.infrastructure.Tracking.byte_tracker import ByteTrackerAdapter
from src.infrastructure.Messaging.retry_publisher import RetryPublisher
from src.infrastructure.Messaging.kafka_publisher import KafkaPublisher
from src.domain.Services.deduplicator_service import DeduplicatorService
from src.infrastructure.Normalizer.plate_normalizer import PlateNormalizer
from src.application.plate_recognition_service import PlateRecognitionService
from src.application.plate_recognition_service_v2 import PlateRecognitionServiceV2
from src.core.config import settings

logger = logging.getLogger(__name__)


def run_camera_service(cam: Camera):
    """Ejecuta el pipeline completo para una cámara específica."""
    logger.info(f"🎥 Iniciando servicio para cámara {cam.name or cam.camera_id} ({cam.url})")

    camera_stream = create_camera_stream(cam)
    detector = create_plate_detector()
    ocr = EasyOCR_OCRReader()
    tracker = ByteTrackerAdapter()

    kafka_raw = KafkaPublisher(delivery_timeout=5.0)
    publisher = RetryPublisher(kafka_raw, attempts=1, base_delay=1.0)

    normalizer = PlateNormalizer(min_len=settings.plate_min_length)
    deduplicator = DeduplicatorService(normalizer=normalizer, ttl=settings.dedup_ttl)

 #  service = PlateRecognitionService(
  #      camera_stream=camera_stream,
   #     detector=detector,
  #      ocr_reader=ocr,
  #      publisher=publisher,
  #      tracker=tracker,
  #      deduplicator=deduplicator,
   #     normalizer=normalizer,
   #     debug_show=settings.debug_show,
   #     loop_delay=settings.loop_delay,
   # )
    service = PlateRecognitionServiceV2(
        camera_stream=camera_stream,
        detector=detector,
        ocr_reader=ocr,
        publisher=publisher,
        tracker=tracker,
        deduplicator=deduplicator,
        normalizer=normalizer,
        debug_show=settings.debug_show,
        max_fps=10.0,   # configurable
    )   


    try:
        service.start()
    except KeyboardInterrupt:
        service.stop()
    except Exception:
        logger.exception(f"❌ Error en servicio de cámara {cam.camera_id}")
    finally:
        kafka_raw.close()
