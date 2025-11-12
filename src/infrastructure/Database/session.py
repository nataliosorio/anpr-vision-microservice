# src/infrastructure/Database/session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Intentar conectar con la BD configurada
DATABASE_URL = settings.db_url
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    # Probar una conexión mínima
    with engine.connect() as conn:
        conn.execute("SELECT 1")
    logger.info(f"✅ Conectado correctamente a la BD: {DATABASE_URL}")
except Exception as e:
    logger.warning(f"⚠️ No se pudo conectar a {DATABASE_URL}. Usando fallback SQLite. Error: {e}")
    DATABASE_URL = "sqlite:///./anpr_micro.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    logger.info("💾 Base local SQLite inicializada como fallback")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
