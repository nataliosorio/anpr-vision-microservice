import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from dotenv import load_dotenv


# ==========================================================
# 1) Cargar .env raíz
# ==========================================================
load_dotenv(".env")
DEPLOY_ENV = os.getenv("DEPLOY_ENV", "prod").lower()

# ==========================================================
# 2) Cargar .env del entorno
# ==========================================================
ENV_PATH = f"DevOps/{DEPLOY_ENV}/.env"
load_dotenv(ENV_PATH, override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        extra="allow"
    )

    # =========================
    #  App
    # =========================
    deploy_env: str = Field("prod", env="DEPLOY_ENV")
    app_name: str = Field("anpr-microservice", env="APP_NAME")
    app_env: str = Field("prod", env="APP_ENV")
    app_port: int = Field(8000, env="APP_PORT")

    # =========================
    #  Kafka
    # =========================
    kafka_broker: str = Field("kafka:9092", env="KAFKA_BROKER")

    kafka_topic_plate: str = Field("anpr-plates", env="KAFKA_TOPIC_PLATE")
    kafka_topic_cameras: str = Field("anpr-cameras", env="KAFKA_TOPIC_CAMERAS")

    kafka_camera_sync_group: str = Field("anpr-camera-sync-group", env="KAFKA_CAMERA_SYNC_GROUP")
    kafka_auto_offset_reset: str = Field("earliest", env="KAFKA_AUTO_OFFSET_RESET")
    kafka_enable_auto_commit: bool = Field(True, env="KAFKA_ENABLE_AUTO_COMMIT")

    # =========================
    #  Database
    # =========================
    db_url: str = Field("sqlite:///anpr_micro.db", env="DB_URL")

    # =========================
    #  Runtime
    # =========================
    debug_show: bool = Field(False, env="DEBUG_SHOW")
    loop_delay: float = Field(0.0, env="LOOP_DELAY")

    # =========================
    #  Dedup
    # =========================
    dedup_ttl: float = Field(9.0, env="DEDUP_TTL")
    similarity_threshold: float = Field(0.9, env="SIMILARITY_THRESHOLD")
    plate_min_length: int = Field(5, env="PLATE_MIN_LENGTH")
    plate_max_length: int = Field(8, env="PLATE_MAX_LENGTH")
    # =========================
    #  OCR
    # =========================
    ocr_lang: str = Field("en", env="OCR_LANG")
    ocr_interval: int = Field(5, env="OCR_INTERVAL")
    ocr_min_length: int = Field(5, env="OCR_MIN_LENGTH")
    ocr_min_confidence: float = Field(0.85, env="OCR_MIN_CONFIDENCE")

    # =========================
    #  Camera
    # =========================
    camera_url: str = Field(None, env="CAMERA_URL")
    camera_native: bool = Field(False, env="CAMERA_NATIVE")

    # =========================
    #  YOLO Version
    # =========================
    yolo_version: str = Field("v5", env="YOLO_VERSION")

    # =========================
    #  YOLOv5
    # =========================
    yolov5_model_path: str = Field("./models/best.pt", env="YOLOV5_MODEL_PATH")
    yolov5_conf: float = Field(0.6, env="YOLOV5_CONF")
    yolov5_iou: float = Field(0.45, env="YOLOV5_IOU")
    yolov5_img_size: int = Field(640, env="YOLOV5_IMG_SIZE")
    yolov5_agnostic: bool = Field(False, env="YOLOV5_AGNOSTIC")
    yolov5_multi_label: bool = Field(False, env="YOLOV5_MULTI_LABEL")
    yolov5_max_det: int = Field(1000, env="YOLOV5_MAX_DET")
    yolov5_device: str = Field("auto", env="YOLOV5_DEVICE")

    yolov5_hf_repo: str = Field("keremberke/yolov5n-license-plate", env="YOLOV5_HF_REPO")
    yolov5_hf_filename: str = Field("yolov5n-license-plate.pt", env="YOLOV5_HF_FILENAME")

    # =========================
    #  ByteTrack
    # =========================
    bytetrack_thresh: float = Field(0.5, env="BYTETRACK_THRESH")
    bytetrack_match_thresh: float = Field(0.8, env="BYTETRACK_MATCH_THRESH")
    bytetrack_buffer_size: int = Field(30, env="BYTETRACK_BUFFER_SIZE")
    bytetrack_fps: int = Field(30, env="BYTETRACK_FPS")

    # =========================
    #  Monitoring
    # =========================
    prometheus_port: int = Field(9090, env="PROMETHEUS_PORT")
    grafana_port: int = Field(3000, env="GRAFANA_PORT")
    grafana_admin_pass: str = Field("admin123", env="GRAFANA_ADMIN_PASS")


settings = Settings()
