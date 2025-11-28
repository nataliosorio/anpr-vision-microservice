import logging
import time

from src.infrastructure.Camera.camera_factory import create_camera_stream
from src.application.plate_recognition_service_v2 import PlateRecognitionServiceV2

from src.infrastructure.Detector.factory import create_plate_detector
from src.infrastructure.OCR.EasyOCR_OCRReader import EasyOCR_OCRReader
from src.infrastructure.Tracking.byte_tracker import ByteTrackerAdapter
from src.infrastructure.Messaging.kafka_publisher import KafkaPublisher
from src.infrastructure.Messaging.retry_publisher import RetryPublisher
from src.domain.Services.deduplicator_service import DeduplicatorService
from src.infrastructure.Normalizer.plate_normalizer import PlateNormalizer
from src.core.config import settings

logger = logging.getLogger(__name__)

# camera_id -> instancia de PlateRecognitionServiceV2
_running_services: dict[str, PlateRecognitionServiceV2] = {}


def run_camera_service(cam):
    """
    Levanta un servicio V2 para una cámara y mantiene
    el thread VIVO hasta que alguien llame stop_camera_service(cam_id).
    """
    global _running_services

    logger.info(f"🎥 Starting service for camera {cam.camera_id} ({cam.url})")

    stream = create_camera_stream(cam)

    detector = create_plate_detector()
    ocr = EasyOCR_OCRReader()
    tracker = ByteTrackerAdapter()

    kafka_raw = KafkaPublisher(delivery_timeout=10)
    # attempts=0 -> sin reintentos adicionales (ya hay lógica de timeout en KafkaPublisher)
    publisher = RetryPublisher(kafka_raw, attempts=0, base_delay=1)

    normalizer = PlateNormalizer(
        min_len=settings.plate_min_length,
        max_len=settings.plate_max_length,
    )

    dedup = DeduplicatorService(
        normalizer=normalizer,
        ttl=settings.dedup_ttl,
        similarity_threshold=settings.similarity_threshold,
    )

    service = PlateRecognitionServiceV2(
        camera_stream=stream,
        detector=detector,
        ocr_reader=ocr,
        publisher=publisher,
        tracker=tracker,
        deduplicator=dedup,
        normalizer=normalizer,
        max_fps=settings.max_fps,                 # viene directo de .env
        processing_workers=settings.processing_workers,  # idem
    )

    _running_services[cam.camera_id] = service

    try:
        # Arranca los threads internos (capture/publish/processing)
        service.start()

        # Mantener este hilo bloqueado mientras el servicio siga activo
        while not service.stop_event.is_set():
            time.sleep(1)

    except Exception:
        logger.exception(f"❌ Error en cámara {cam.camera_id}")
    finally:
        # Asegurar stop ordenado
        try:
            service.stop()
        except Exception:
            logger.exception(f"Error deteniendo servicio de cámara {cam.camera_id}")

        # Cerrar producer Kafka
        kafka_raw.close()

        # Limpiar registro
        _running_services.pop(cam.camera_id, None)


def stop_camera_service(cam_id: str):
    """
    Detiene un servicio de cámara existente.
    No borra aquí del diccionario: lo hace run_camera_service() en el finally.
    """
    service = _running_services.get(cam_id)
    if service:
        try:
            service.stop()
        except Exception:
            logger.exception(f"Error deteniendo servicio de cámara {cam_id}")
