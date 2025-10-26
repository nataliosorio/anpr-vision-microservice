import json
import logging
import threading
import time
from typing import Optional
from datetime import datetime
from confluent_kafka import Producer, KafkaError
from src.domain.Models.detection_result import DetectionResult
from src.domain.Interfaces.event_publisher import IEventPublisher
from src.core.config import settings

logger = logging.getLogger(__name__)

class KafkaPublisher(IEventPublisher):
    """
    Publica PlateDetectedEventRecord en Kafka a partir de DetectionResult.
    Implementa control explícito de callback con polling activo para evitar duplicados y timeouts falsos.
    """

    def __init__(self, delivery_timeout: float = 10.0, producer_conf: Optional[dict] = None):
        base_conf = {
            "bootstrap.servers": settings.kafka_broker,
            "client.id": settings.app_name,
            "enable.idempotence": True,   # evita duplicados en el broker
            "acks": "all",
            "message.send.max.retries": 3,
            "socket.timeout.ms": 30000,
            "request.timeout.ms": 30000,
            "linger.ms": 5,
            "compression.type": "lz4",
            # "debug": "broker,topic,msg",  # opcional: habilita trazas detalladas
        }

        if producer_conf:
            base_conf.update(producer_conf)

        self.producer = Producer(base_conf)
        self.topic = settings.kafka_topic
        self.delivery_timeout = delivery_timeout

        # métricas internas básicas
        self.metrics = {
            "publish_ok": 0,
            "publish_failed": 0,
            "publish_timeout": 0
        }

        self._wait_for_metadata(timeout=15)

    def _wait_for_metadata(self, timeout: int = 15) -> None:
        """Intenta obtener metadata del cluster antes de permitir produces."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                md = self.producer.list_topics(timeout=5.0)
                if md and md.brokers:
                    logger.info("Kafka producer metadata OK: brokers=%s", list(md.brokers.keys()))
                    return
            except Exception as ex:
                logger.debug("Esperando metadata kafka: %s", ex)
            time.sleep(1.0)
        logger.warning("No se obtuvo metadata del broker en %ds; intentos futuros pueden fallar.", timeout)

    # ============================================================
    #  PUBLICAR EVENTO
    # ============================================================
    def publish(self, result: DetectionResult) -> None:
        logger.debug("Publish llamado para event_id=%s frame=%s",
                     getattr(result, "event_id", None), getattr(result, "frame_id", None))

        payload = None
        start_time = time.time()
        try:
            # ------------------------------
            # Adaptar DetectionResult → evento JSON
            # ------------------------------
            plate_text = result.plates[0].text if result.plates else ""
            timestamp_iso = datetime.utcfromtimestamp(result.captured_at).isoformat()

            event = {
                "plate": plate_text,
                "cameraId": result.camera_id or result.source,
                "parkingId": None,
                "timestamp": timestamp_iso,
                "frameId": result.frame_id,
                "imageUrl": None
            }

            payload = json.dumps(event, ensure_ascii=False)
            key = str(result.frame_id or "")
            delivered = {"err": None, "called": False}
            ev = threading.Event()

            # ------------------------------
            # Callback de entrega
            # ------------------------------
            def _cb(err, msg):
                delivered["called"] = True
                delivered["err"] = err
                ev.set()
                if err is not None:
                    logger.error("❌ Kafka delivery callback error: %s", err)
                else:
                    latency = (time.time() - start_time) * 1000
                    logger.info("✅ Kafka delivered topic=%s partition=%s offset=%s latency=%.1fms",
                                msg.topic(), msg.partition(), msg.offset(), latency)

            # ------------------------------
            # Envío del mensaje
            # ------------------------------
            self.producer.produce(
                topic=self.topic,
                key=key,
                value=payload.encode("utf-8"),
                callback=_cb,
            )

            # ------------------------------
            # Polling activo mientras se espera el callback
            # ------------------------------
            deadline = time.time() + self.delivery_timeout
            while not ev.is_set() and time.time() < deadline:
                self.producer.poll(0.1)
                time.sleep(0.05)

            # ------------------------------
            # Validar resultado / timeout
            # ------------------------------
            if not ev.is_set():
                logger.warning("⚠️ Timeout esperando confirmación de Kafka (%.1fs)", self.delivery_timeout)
                try:
                    self.producer.flush(timeout=5.0)
                except Exception:
                    logger.exception("Error durante flush tras timeout")
                self.metrics["publish_timeout"] += 1
                raise Exception("Kafka delivery timeout")

            if delivered["err"] is not None:
                err = delivered["err"]
                msg_err = err.str() if isinstance(err, KafkaError) and hasattr(err, "str") else str(err)
                self.metrics["publish_failed"] += 1
                raise Exception(f"Kafka delivery failed: {msg_err}")

            # ------------------------------
            # Éxito
            # ------------------------------
            self.metrics["publish_ok"] += 1
            logger.debug("Evento publicado correctamente en Kafka topic=%s frame=%s payload=%s",
                         self.topic, key, payload)

        except Exception as ex:
            logger.exception("Error al publicar en Kafka. payload=%s", payload)
            raise ex

    # ============================================================
    #  CIERRE
    # ============================================================
    def close(self, timeout: float = 5.0) -> None:
        try:
            self.producer.flush(timeout=timeout)
            logger.info("Kafka producer flushed/closed")
            logger.info("Métricas finales: %s", self.metrics)
        except Exception:
            logger.exception("Error al flush/close del Kafka producer")
