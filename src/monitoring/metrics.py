from prometheus_client import Gauge, Counter, start_http_server

# FPS capturados por cámara
camera_fps = Gauge(
    "camera_fps",
    "FPS actuales de la cámara",
    ["camera_id"]
)

# Placas detectadas
plates_detected_total = Counter(
    "plates_detected_total",
    "Total de placas detectadas",
    ["camera_id"]
)

# Latencia detector
detector_latency = Gauge(
    "detector_latency_seconds",
    "Tiempo de ejecución del detector por cámara",
    ["camera_id"]
)

# Latencia OCR
ocr_latency = Gauge(
    "ocr_latency_seconds",
    "Tiempo de OCR por cámara",
    ["camera_id"]
)

# Latencia total pipeline
pipeline_latency = Gauge(
    "pipeline_latency_seconds",
    "Tiempo total de procesamiento de frame",
    ["camera_id"]
)

def start_metrics_server(port: int = 9100):
    """Arranca servidor de métricas Prometheus."""
    start_http_server(port)
    print(f"📊 Prometheus metrics disponible en :{port}")
