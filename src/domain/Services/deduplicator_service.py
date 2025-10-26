# src/domain/Services/deduplicator_service.py
from __future__ import annotations
import time
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from src.domain.Interfaces.deduplicator import IDeduplicator
from src.domain.Interfaces.text_normalizer import ITextNormalizer
from src.core.config import settings

# internal entry
@dataclass
class _SeenEntry:
    when: float
    # opcionales para futuro: confidence, bbox, track_id, etc.
    # aquí solo almacenamos timestamp porque la llave contiene track+text

class DeduplicatorService(IDeduplicator):
    """
    Servicio de deduplicación de dominio.

    - scope por camera_id (si no se provee, usa 'default')
    - llave por (track_id_or_none, normalized_text)
    - TTL configurable (lee settings.dedup_ttl si no se pasa)
    - normalizer inyectado (ITextNormalizer) para normalizar/rechazar texto
    """

    def __init__(self, normalizer: ITextNormalizer, ttl: Optional[float] = None):
        self.normalizer = normalizer
        self.ttl = ttl if ttl is not None else getattr(settings, "dedup_ttl", 3.0)
        # estructura: { camera_id: { (track_key, text_norm): _SeenEntry } }
        self._store: Dict[str, Dict[Tuple[Optional[int], str], _SeenEntry]] = {}

    def is_duplicate(self, track_id: Optional[int], plate_text: str, camera_id: Optional[str] = None) -> bool:
        """
        Retorna True si la (track_id, plate_text) ya fue publicada recientemente
        para la misma camera_id; de lo contrario registra la entrada y devuelve False.

        Notas:
        - normaliza plate_text con el normalizer inyectado; si el normalizer
          considera inválido (devuelve "" o None), se considera duplicado/no-publicable.
        - camera_id se usa para aislar scope entre cámaras. Si es None, se usa 'default'.
        """
        cam = camera_id or "default"

        # normalizar y validar
        text_norm = self.normalizer.normalize(plate_text)
        if not text_norm:
            # texto inválido según la política de normalización -> no publicar
            return True

        now = time.time()
        cam_map = self._store.setdefault(cam, {})

        # purgar expirados (ligero, solo por este cam)
        self._purge_cam(cam_map, now)

        key = (track_id, text_norm)
        entry = cam_map.get(key)
        if entry is not None:
            if (now - entry.when) < self.ttl:
                # actualizar TTL tipo sliding
                entry.when = now
                return True

        # no fue visto recientemente -> registrar y permitir publicación
        cam_map[key] = _SeenEntry(when=now)
        return False

    def _purge_cam(self, cam_map: Dict[Tuple[Optional[int], str], _SeenEntry], now: float) -> None:
        """Eliminar entradas expiradas de un mapa por cámara (in-place)."""
        if not cam_map:
            return
        ttl = self.ttl
        # iterar sobre claves en lista para evitar modificar dict durante iteración
        for k, e in list(cam_map.items()):
            if (now - e.when) >= ttl:
                cam_map.pop(k, None)

    # utilidad para tests / operativa: limpiar todo
    def clear(self) -> None:
        self._store.clear()
