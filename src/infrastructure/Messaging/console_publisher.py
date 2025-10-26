import json
from src.domain.Interfaces.event_publisher import IEventPublisher
from src.domain.Models.detection_result import DetectionResult

class ConsolePublisher(IEventPublisher):
    """
    Implementación dummy que imprime resultados en consola de forma legible.
    """

    def publish(self, result: DetectionResult) -> None:
        try:
            # Armar dict base
            output = {
                "frame_id": getattr(result, "frame_id", None),
                "processed_at": getattr(result, "processed_at", None),
                "source": getattr(result, "source", None),
                "captured_at": getattr(result, "captured_at", None),
                "plates": []
            }

            # Convertir cada Plate en dict
            for p in getattr(result, "plates", []):
                if hasattr(p, "text"):
                    output["plates"].append({
                        "text": p.text,
                        "confidence": getattr(p, "confidence", None),
                        "bbox": getattr(p, "bounding_box", None)
                    })
                else:
                    # fallback: si es string u otro tipo
                    output["plates"].append(str(p))

            # Imprimir resultado
            print("📢 Publicando resultado:")
            print(json.dumps(output, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"❌ Error al imprimir resultado en consola: {e}")
