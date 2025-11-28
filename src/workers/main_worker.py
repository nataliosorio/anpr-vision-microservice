import warnings
warnings.filterwarnings("ignore")

import logging
import threading

from src.core.config import settings
from src.infrastructure.Database.base import Base
from src.infrastructure.Database.session import engine
from src.infrastructure.Camera.camera_repository import CameraRepository
from src.infrastructure.Messaging.consumers.camera_sync_consumer import CameraSyncConsumer

from src.application.camera_thread_manager import CameraThreadManager
from src.monitoring.metrics import start_metrics_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    Base.metadata.create_all(bind=engine)
    repo = CameraRepository()

    start_metrics_server(port=9100)

    # Kafka consumer
    try:
        consumer = CameraSyncConsumer(
            topic=settings.kafka_topic_cameras,
            group_id=settings.kafka_camera_sync_group,
            bootstrap_servers=settings.kafka_broker,
            auto_offset_reset=settings.kafka_auto_offset_reset,
            enable_auto_commit=settings.kafka_enable_auto_commit,
        )
        threading.Thread(target=consumer.start, daemon=True).start()
        logger.info("🔄 CameraSyncConsumer iniciado.")
    except Exception:
        logger.exception("⚠️ No se pudo iniciar consumer Kafka")

    # Thread Manager
    manager = CameraThreadManager(repo)
    threading.Thread(target=manager.start, daemon=True).start()

    logger.info("🚀 Microservicio ANPR iniciado.")

    try:
        while True:
            threading.Event().wait(5)
    except KeyboardInterrupt:
        logger.info("🧠 Deteniendo…" )


if __name__ == "__main__":
    main()
