# main.py (worker) - minimal
import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="yolov5")

import logging
from src.core.config import settings
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    cam = Camera(camera_id="1", url=settings.camera_url, name="ENTRADA")
    camera_stream = create_camera_stream(cam)

    detector = create_plate_detector()
    ocr = EasyOCR_OCRReader()
    tracker = ByteTrackerAdapter()

    # Publisher: Kafka + Retry
    kafka_raw = KafkaPublisher(delivery_timeout=5.0)   # usa settings.kafka_broker y settings.kafka_topic
    publisher = RetryPublisher(kafka_raw, attempts=3, base_delay=1.0)

    normalizer = PlateNormalizer(min_len=settings.plate_min_length)
    deduplicator = DeduplicatorService(normalizer=normalizer, ttl=settings.dedup_ttl)

    service = PlateRecognitionService(
        camera_stream=camera_stream,
        detector=detector,
        ocr_reader=ocr,
        publisher=publisher,
        tracker=tracker,
        deduplicator=deduplicator,
        normalizer=normalizer,
        debug_show=settings.debug_show,
        loop_delay=settings.loop_delay,
    )

    try:
        service.start()
    except KeyboardInterrupt:
        logger.info("Deteniendo por KeyboardInterrupt")
        service.stop()
    except Exception:
        logger.exception("Error en worker")
    finally:
        try:
            kafka_raw.close()
        except Exception:
            logger.exception("Error cerrando Kafka producer")

if __name__ == "__main__":
    main()
