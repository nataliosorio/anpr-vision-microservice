# src/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App
    app_name: str = Field("anpr-microservice", env="APP_NAME")
    app_env: str = Field("development", env="APP_ENV")
    app_port: int = Field(8000, env="APP_PORT")

    # Kafka (defaults pensados para correr en docker-compose)
    kafka_broker: str = Field("kafka:9092", env="KAFKA_BROKER")
    kafka_topic: str = Field("anpr-detections", env="KAFKA_TOPIC")

    # Database & cache
    db_url: str = Field(..., env="DB_URL")
    redis_url: str = Field(..., env="REDIS_URL")

    # Model / YOLO
    model_path: str = Field("./models/best.pt", env="MODEL_PATH")
    conf_threshold: float = Field(0.3, env="CONF_THRESHOLD")
    iou_threshold: float = Field(0.45, env="IOU_THRESHOLD")

    # Runtime flags
    debug_show: bool = Field(False, env="DEBUG_SHOW")
    loop_delay: float = Field(0.0, env="LOOP_DELAY")

    # Dedup / plate rules
    dedup_ttl: float = Field(9.0, env="DEDUP_TTL")           # segundos, default 9.0
    similarity_threshold: float = Field(0.9, env="SIMILARITY_THRESHOLD")
    plate_min_length: int = Field(5, env="PLATE_MIN_LENGTH")

    # OCR
    ocr_lang: str = Field("en", env="OCR_LANG")
    ocr_interval: int = Field(5, env="OCR_INTERVAL")
    ocr_min_length: int = Field(4, env="OCR_MIN_LENGTH")
    ocr_min_confidence: float = Field(0.8, env="OCR_MIN_CONFIDENCE")

    # Camera
    camera_url: str = Field(..., env="CAMERA_URL")
    camera_native: bool = Field(False, env="CAMERA_NATIVE")

    # Switch de detector
    yolo_version: str = Field("v8", env="YOLO_VERSION")

    # YOLOv5 specifics
    yolov5_model_path: str = Field("./models/yolov5n-license-plate.pt", env="YOLOV5_MODEL_PATH")
    yolov5_conf: float = Field(0.25, env="YOLOV5_CONF")
    yolov5_iou: float = Field(0.45, env="YOLOV5_IOU")
    yolov5_img_size: int = Field(640, env="YOLOV5_IMG_SIZE")
    yolov5_agnostic: bool = Field(False, env="YOLOV5_AGNOSTIC")
    yolov5_multi_label: bool = Field(False, env="YOLOV5_MULTI_LABEL")
    yolov5_max_det: int = Field(1000, env="YOLOV5_MAX_DET")
    yolov5_device: str = Field("auto", env="YOLOV5_DEVICE")

    # Hugging Face fallback
    yolov5_hf_repo: str = Field("keremberke/yolov5n-license-plate", env="YOLOV5_HF_REPO")
    yolov5_hf_filename: str = Field("yolov5n-license-plate.pt", env="YOLOV5_HF_FILENAME")

    # ByteTrack
    bytetrack_thresh: float = Field(0.5, env="BYTETRACK_THRESH")
    bytetrack_match_thresh: float = Field(0.8, env="BYTETRACK_MATCH_THRESH")
    bytetrack_buffer_size: int = Field(30, env="BYTETRACK_BUFFER_SIZE")
    bytetrack_fps: int = Field(30, env="BYTETRACK_FPS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# instancia global
settings = Settings()
