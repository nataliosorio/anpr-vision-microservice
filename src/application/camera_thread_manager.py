import threading
import logging
from typing import Dict
from copy import deepcopy

from src.infrastructure.Camera.camera_repository import CameraRepository
from src.domain.Models.camera import Camera
from src.application.camera_service_runner import run_camera_service

logger = logging.getLogger(__name__)


class CameraThreadManager:
    def __init__(self, repo: CameraRepository, refresh_interval: int = 10):
        self.repo = repo
        self.refresh_interval = refresh_interval

        self.threads: Dict[str, threading.Thread] = {}
        self.cameras: Dict[str, Camera] = {}   # snapshot local para detectar cambios

        self.running = True

    def start(self):
        logger.info("📡 CameraThreadManager iniciado y escuchando cambios en DB local")

        while self.running:
            try:
                self.reconcile()
            except Exception:
                logger.exception("❌ Error en reconciliación de cámaras")
            finally:
                threading.Event().wait(self.refresh_interval)

    def reconcile(self):
        # Obtener cámaras desde DB
        db_cameras = {c.camera_id: c for c in self.repo.get_all()}

        # 1️⃣ Cámaras nuevas
        for cam_id, cam in db_cameras.items():
            if cam_id not in self.threads:
                logger.info(f"🆕 Cámara nueva detectada ({cam_id}). Iniciando thread...")
                self._start_thread(cam)
                self.cameras[cam_id] = deepcopy(cam)
                continue

            # 2️⃣ Cámaras modificadas (ej: cambió URL)
            old_cam = self.cameras[cam_id]
            if cam.url != old_cam.url:
                logger.info(f"🔄 Cámara {cam_id} modificada (URL cambió). Reiniciando thread...")
                self._restart_thread(cam)
                self.cameras[cam_id] = deepcopy(cam)

        # 3️⃣ Cámaras eliminadas
        for cam_id in list(self.threads.keys()):
            if cam_id not in db_cameras:
                logger.info(f"🗑️ Cámara eliminada ({cam_id}). Matando thread...")
                self._kill_thread(cam_id)

    def _start_thread(self, cam: Camera):
        t = threading.Thread(target=run_camera_service, args=(cam,), daemon=True)
        t.start()
        self.threads[cam.camera_id] = t
        logger.info(f"🚀 Thread iniciado para cámara {cam.camera_id}")

    def _restart_thread(self, cam: Camera):
        self._kill_thread(cam.camera_id)
        self._start_thread(cam)

    def _kill_thread(self, cam_id: str):
        if cam_id in self.threads:
            logger.info(f"✋ Solicitando detener thread para cámara {cam_id}")
            # El thread se detendrá cuando run_camera_service termine solo
            del self.threads[cam_id]
