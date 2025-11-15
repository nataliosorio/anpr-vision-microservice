import warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="yolov5")

import logging
import threading

from src.core.config import settings
from src.infrastructure.Database.base import Base
from src.infrastructure.Database.session import engine
from src.infrastructure.Camera.camera_repository import CameraRepository
from src.infrastructure.Messaging.consumers.camera_sync_consumer import CameraSyncConsumer

from src.application.camera_thread_manager import CameraThreadManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    # Crear DB local si no existe
    Base.metadata.create_all(bind=engine)
    repo = CameraRepository()

    # 1️⃣ Iniciar consumer de sincronización con backend
    try:
        camera_consumer = CameraSyncConsumer(
            topic=settings.kafka_camera_sync_topic,
            group_id=settings.kafka_camera_sync_group,
            auto_offset_reset=settings.kafka_auto_offset_reset,
            enable_auto_commit=settings.kafka_enable_auto_commit,
            bootstrap_servers=settings.kafka_broker,
        )
        threading.Thread(target=camera_consumer.start, daemon=True).start()
        logger.info("🔄 CameraSyncConsumer iniciado")
    except Exception:
        logger.exception("⚠️ No se pudo iniciar CameraSyncConsumer")

    # 2️⃣ Iniciar el gestor de threads de cámaras
    manager = CameraThreadManager(repo)
    threading.Thread(target=manager.start, daemon=True).start()

    logger.info("🚀 CameraThreadManager ejecutándose")

    # 3️⃣ Mantener proceso vivo
    try:
        while True:
            threading.Event().wait(5)
    except KeyboardInterrupt:
        logger.info("🧠 Deteniendo microservicio...")


if __name__ == "__main__":
    main()
