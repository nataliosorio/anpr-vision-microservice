from fastapi import FastAPI
from src.core.config import settings

app = FastAPI(title=settings.app_name)

@app.get("/health")
def health_check():
    return {"status": "ok", "env": settings.app_env}
