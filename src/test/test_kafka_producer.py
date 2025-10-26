import json
import time
from confluent_kafka import Producer
from src.core.config import settings

def delivery_report(err, msg):
    """ Callback que confirma si el mensaje fue entregado """
    if err is not None:
        print(f"❌ Error al entregar mensaje: {err}")
    else:
        print(f"✅ Mensaje entregado a {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")

def main():
    conf = {
        "bootstrap.servers": settings.kafka_broker,
        "client.id": settings.app_name,
    }
    producer = Producer(conf)

    # Mensaje de prueba
    test_payload = {
        "event": "test",
        "timestamp": time.time(),
        "message": "Hello Kafka 👋 from ANPR microservice"
    }

    print(f"📤 Enviando mensaje a topic: {settings.kafka_topic}")
    producer.produce(
        topic=settings.kafka_topic,
        key="test-key",
        value=json.dumps(test_payload, ensure_ascii=False),
        callback=delivery_report
    )

    # Procesa callbacks de entrega
    producer.flush()

if __name__ == "__main__":
    main()
