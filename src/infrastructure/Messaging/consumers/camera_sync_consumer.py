import json
import logging
from confluent_kafka import Consumer, KafkaException, KafkaError
from src.core.config import settings
from src.infrastructure.Camera.camera_repository import CameraRepository
from src.domain.Models.camera import Camera

logger = logging.getLogger(__name__)

class CameraSyncConsumer:
    """
    Consumer Kafka encargado de sincronizar las cámaras locales
    cuando el backend envía eventos de cambio.
    """

    def __init__(
        self,
        topic: str = None,
        group_id: str = None,
        auto_offset_reset: str = None,
        enable_auto_commit: bool = None,
        bootstrap_servers: str = None
    ):
        self.topic = topic or settings.kafka_topic_cameras
        self.group_id = group_id or settings.kafka_camera_sync_group

        self.config = {
            "bootstrap.servers": bootstrap_servers or settings.kafka_broker,
            "group.id": self.group_id,
            "auto.offset.reset": auto_offset_reset or settings.kafka_auto_offset_reset,
            "enable.auto.commit": (
                enable_auto_commit
                if enable_auto_commit is not None
                else settings.kafka_enable_auto_commit
            ),
        }

        self.repo = CameraRepository()
        self.consumer = Consumer(self.config)
        self.running = False

    def start(self):
        """Inicia el consumo del tópico."""
        logger.info(f"🎧 Iniciando consumer de cámaras en tópico '{self.topic}' (grupo='{self.group_id}')")
        self.running = True
        self.consumer.subscribe([self.topic])

        while self.running:
            try:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise KafkaException(msg.error())

                self._handle_message(msg.value())

            except Exception as e:
                logger.exception(f"❌ Error procesando mensaje Kafka: {e}")

        self.consumer.close()
        self.repo.close()
        logger.info("🧩 Consumer de cámaras detenido correctamente.")

    def stop(self):
        self.running = False

    def _handle_message(self, raw_data: bytes):
        """Procesa el mensaje entrante y sincroniza la DB local."""
        try:
            payload = json.loads(raw_data.decode("utf-8"))

            # El backend ahora envía:
            # {
            #   "action": "...",
            #   "camera": { ... }
            # }
            event_type = payload.get("action")
            camera_data = payload.get("camera", {})

            # El id de la cámara ahora viene dentro de camera.id
            camera_id = camera_data.get("id")

            if not camera_id:
                logger.warning("Mensaje inválido: sin 'camera.id'")
                return

            # Conversión backend → micro
            asset = camera_data.get("asset", True)
            is_deleted = camera_data.get("isDeleted", False)

            # El micro usa is_active, no asset/isDeleted
            is_active = asset and not is_deleted

            # CREATE o UPDATE
            if event_type in ("CREATE", "UPDATE"):
                cam = Camera(
                    camera_id=str(camera_id),
                    name=camera_data.get("name"),
                    url=camera_data.get("url"),
                    location=None,  # El backend no envía location
                    parking_id=camera_data.get("parkingId"),
                    is_active=is_active,
                )

                self.repo.save(cam)
                logger.info(f"📸 Cámara {camera_id} actualizada/creada desde Kafka")

            # DELETE / DEACTIVATE
            elif event_type in ("DELETE", "DEACTIVATE"):
                self.repo.delete(str(camera_id))
                logger.info(f"🗑️ Cámara {camera_id} eliminada/desactivada desde Kafka")

            else:
                logger.warning(f"Evento desconocido '{event_type}' recibido: {payload}")

        except json.JSONDecodeError:
            logger.warning(f"⚠️ Mensaje Kafka inválido (no es JSON): {raw_data}")
        except Exception:
            logger.exception("Error procesando mensaje de cámara")
