import threading
import logging
from typing import Dict
from copy import deepcopy

from src.infrastructure.Camera.camera_repository import CameraRepository
from src.domain.Models.camera import Camera
from src.application.camera_service_runner import run_camera_service, stop_camera_service

logger = logging.getLogger(__name__)


class CameraThreadManager:
    """
    Administra lifecycle completo:
    - crea threads
    - reinicia si cambia la URL
    - mata si se borra
    - revive si el thread muere
    """

    def __init__(self, repo: CameraRepository, refresh_interval: int = 5):
        self.repo = repo
        self.refresh_interval = refresh_interval

        self.threads: Dict[str, threading.Thread] = {}
        self.snapshot: Dict[str, Camera] = {}

        self.running = True

    def start(self):
        logger.info("📡 CameraThreadManager escuchando cambios...")

        while self.running:
            try:
                self.reconcile()
            except Exception:
                logger.exception("❌ Error en reconciliación")
            finally:
                threading.Event().wait(self.refresh_interval)

    # ---------------------------------------------------------
    # RECONCILE
    # ---------------------------------------------------------
    def reconcile(self):
        db_cameras = {c.camera_id: c for c in self.repo.get_all()}

        # 1) nuevas cámaras
        for cam_id, cam in db_cameras.items():

            # no existía → crear
            if cam_id not in self.threads:
                logger.info(f"🆕 Cámara nueva {cam_id}, levantando thread…")
                self._start(cam)
                self.snapshot[cam_id] = deepcopy(cam)
                continue

            # existía → verificar cambios
            old = self.snapshot[cam_id]
            if cam.url != old.url:
                logger.info(f"🔄 Cámara {cam_id} modificada (URL cambió). Reiniciando…")
                self._restart(cam)
                self.snapshot[cam_id] = deepcopy(cam)

            # thread muerto → revivir
            if not self.threads[cam_id].is_alive():
                logger.error(f"💀 Thread de {cam_id} murió. Reiniciando…")
                self._restart(cam)

        # 2) cámaras eliminadas
        for cam_id in list(self.threads.keys()):
            if cam_id not in db_cameras:
                logger.info(f"🗑️ Cámara eliminada {cam_id}, deteniendo thread…")
                self._kill(cam_id)

    # ---------------------------------------------------------
    # THREAD ACTIONS
    # ---------------------------------------------------------
    def _start(self, cam):
        t = threading.Thread(target=run_camera_service, args=(cam,), daemon=True)
        t.start()
        self.threads[cam.camera_id] = t

    def _restart(self, cam):
        self._kill(cam.camera_id)
        self._start(cam)

    def _kill(self, cam_id):
        stop_camera_service(cam_id)
        if cam_id in self.threads:
            del self.threads[cam_id]
        if cam_id in self.snapshot:
            del self.snapshot[cam_id]
