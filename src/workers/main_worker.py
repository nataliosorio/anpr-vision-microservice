import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="yolov5")

import logging
import threading
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
from src.infrastructure.Database.base import Base
from src.infrastructure.Database.session import engine
from src.infrastructure.Camera.camera_repository import CameraRepository
from src.infrastructure.Messaging.consumers.camera_sync_consumer import CameraSyncConsumer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ==========================================================
#  Función: ejecutar pipeline de detección por cámara
# ==========================================================
def run_service(cam: Camera):
    """Ejecuta el pipeline completo para una cámara específica."""
    logger.info(f"🎥 Iniciando servicio para cámara {cam.name or cam.camera_id} ({cam.url})")

    camera_stream = create_camera_stream(cam)
    detector = create_plate_detector()
    ocr = EasyOCR_OCRReader()
    tracker = ByteTrackerAdapter()

    kafka_raw = KafkaPublisher(delivery_timeout=5.0)
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
        service.stop()
    except Exception:
        logger.exception(f"❌ Error en servicio de cámara {cam.camera_id}")
    finally:
        kafka_raw.close()


# ==========================================================
#  MAIN ENTRY POINT
# ==========================================================
def main():
    # 1️⃣ Asegurar estructura de base de datos
    Base.metadata.create_all(bind=engine)
    repo = CameraRepository()

    # 2️⃣ Iniciar el consumer de sincronización de cámaras
    try:
        camera_consumer = CameraSyncConsumer(
            topic=settings.kafka_camera_sync_topic,
            group_id=settings.kafka_camera_sync_group,
            auto_offset_reset=settings.kafka_auto_offset_reset,
            enable_auto_commit=settings.kafka_enable_auto_commit,
            bootstrap_servers=settings.kafka_broker
        )
        threading.Thread(target=camera_consumer.start, daemon=True).start()
        logger.info(
            f"🔄 Listener de sincronización de cámaras activo "
            f"(topic={settings.kafka_camera_sync_topic}, group={settings.kafka_camera_sync_group})"
        )
    except Exception:
        logger.exception("⚠️ No se pudo iniciar el consumer de cámaras. Continuando sin sincronización...")

    # 3️⃣ Cargar cámaras locales
    cameras = repo.get_all()
    if not cameras:
        logger.warning("⚠️ No hay cámaras registradas. Creando cámara de prueba...")
        cam = Camera(camera_id="1", url=settings.camera_url, name="ENTRADA")
        repo.save(cam)
        cameras = repo.get_all()

    # 4️⃣ Lanzar un thread por cámara activa
    threads = []
    for cam in cameras:
        t = threading.Thread(target=run_service, args=(cam,), daemon=True)
        t.start()
        threads.append(t)

    logger.info(f"🚀 Lanzadas {len(threads)} cámaras activas")

    # 5️⃣ Mantener proceso vivo y monitorear threads
    try:
        while True:
            for t in threads:
                if not t.is_alive():
                    logger.error(f"❌ Thread de cámara muerto: {t.name}")
            threading.Event().wait(10)
    except KeyboardInterrupt:
        logger.info("🧠 Deteniendo todas las cámaras...")
        try:
            camera_consumer.stop()
        except Exception:
            logger.exception("Error al detener consumer de cámaras")
    finally:
        repo.close()


if __name__ == "__main__":
    main()
