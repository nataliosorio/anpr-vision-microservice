# src/domain/Services/deduplicator_service.py
from __future__ import annotations
import time
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from src.domain.Interfaces.deduplicator import IDeduplicator
from src.domain.Interfaces.text_normalizer import ITextNormalizer
from src.core.config import settings


@dataclass
class _SeenEntry:
    """
    Entrada interna de deduplicación.
    """
    when: float                 # último timestamp visto
    text: str                   # texto normalizado
    last_track_id: Optional[int] = None
    hits: int = 0               # cuántas veces se ha visto dentro de ventana


class DeduplicatorService(IDeduplicator):
    """
    Servicio de deduplicación de dominio.

    - scope por camera_id (si no se provee, usa 'default')
    - dos niveles:
        1) (track_id, text_norm) -> evita spam dentro del mismo track ByteTrack
        2) text_norm (con similitud) -> evita duplicados cuando cambia el track_id
           o el OCR varía ligeramente.
    - TTL configurable (settings.dedup_ttl)
    - umbral de similitud configurable (settings.similarity_threshold)
    - normalizer inyectado (ITextNormalizer) para normalizar/rechazar texto
    """

    def __init__(
        self,
        normalizer: ITextNormalizer,
        ttl: Optional[float] = None,
        similarity_threshold: Optional[float] = None,
    ):
        self.normalizer = normalizer
        self.ttl = ttl if ttl is not None else float(getattr(settings, "dedup_ttl", 30.0))
        self.similarity_threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else float(getattr(settings, "similarity_threshold", 0.9))
        )

        # Estructuras:
        #  - por cámara, por (track_id, text_norm)
        self._by_cam_track: Dict[str, Dict[Tuple[Optional[int], str], _SeenEntry]] = {}
        #  - por cámara, por text_norm (cluster de textos similares)
        self._by_cam_text: Dict[str, Dict[str, _SeenEntry]] = {}

    # ---------------------------------------------------------
    #  API PRINCIPAL
    # ---------------------------------------------------------
    def is_duplicate(
        self,
        track_id: Optional[int],
        plate_text: str,
        camera_id: Optional[str] = None
    ) -> bool:
        """
        Retorna True si la detección se considera duplicada en la ventana de TTL
        para la misma cámara.

        Estrategia:
        1) Normaliza el texto; si el normalizer lo rechaza -> NO publicamos.
        2) Dedup por (track_id, text_norm) → evita spam mientras ByteTrack mantiene el mismo ID.
        3) Dedup por texto + similitud → si ya se vio una placa muy similar recientemente
           en la misma cámara, y está dentro de TTL, tampoco publicamos.
        """
        cam = camera_id or "default"

        # 1) Normalizar y validar
        text_norm = self.normalizer.normalize(plate_text)
        if not text_norm:
            # texto inválido según la política de normalización -> no publicar
            return True

        now = time.time()

        cam_track_map = self._by_cam_track.setdefault(cam, {})
        cam_text_map = self._by_cam_text.setdefault(cam, {})

        # 2) Purgar expirados para esta cámara
        self._purge_cam(cam, now)

        # -------------------------------------------------
        # 2.1) Deduplicación por (track_id, text_norm)
        # -------------------------------------------------
        if track_id is not None:
            key_track = (track_id, text_norm)
            entry_track = cam_track_map.get(key_track)

            if entry_track is not None and (now - entry_track.when) < self.ttl:
                # Ya vimos este track+texto hace poco → duplicado
                entry_track.when = now
                entry_track.hits += 1
                entry_track.last_track_id = track_id
                return True

            # Registrar / refrescar la entrada de este track
            cam_track_map[key_track] = _SeenEntry(
                when=now,
                text=text_norm,
                last_track_id=track_id,
                hits=1,
            )

        # -------------------------------------------------
        # 2.2) Deduplicación por texto + similitud
        # -------------------------------------------------
        best_key = None
        best_entry: Optional[_SeenEntry] = None
        best_sim = 0.0

        for key_text, entry in cam_text_map.items():
            sim = self._similarity(text_norm, key_text)
            if sim > best_sim:
                best_sim = sim
                best_key = key_text
                best_entry = entry

        if best_entry is not None and best_sim >= self.similarity_threshold:
            # Mismo cluster de placa (similaridad alta)
            if (now - best_entry.when) < self.ttl:
                # Dentro de la ventana -> duplicado
                best_entry.when = now
                best_entry.hits += 1
                if track_id is not None:
                    best_entry.last_track_id = track_id
                return True
            else:
                # Fuera de ventana → consideramos NUEVA detección (ej. otro ingreso)
                best_entry.when = now
                best_entry.hits += 1
                if track_id is not None:
                    best_entry.last_track_id = track_id
                return False

        # -------------------------------------------------
        # 2.3) Primer vez que vemos este texto (o ninguno similar)
        # -------------------------------------------------
        cam_text_map[text_norm] = _SeenEntry(
            when=now,
            text=text_norm,
            last_track_id=track_id,
            hits=1,
        )
        return False

    # ---------------------------------------------------------
    #  HELPERS
    # ---------------------------------------------------------
    def _purge_cam(self, cam: str, now: float) -> None:
        """Eliminar entradas expiradas para una cámara (in-place)."""
        ttl = self.ttl

        track_map = self._by_cam_track.get(cam)
        if track_map:
            for k, e in list(track_map.items()):
                if (now - e.when) >= ttl:
                    track_map.pop(k, None)

        text_map = self._by_cam_text.get(cam)
        if text_map:
            for k, e in list(text_map.items()):
                if (now - e.when) >= ttl:
                    text_map.pop(k, None)

    def _similarity(self, a: str, b: str) -> float:
        """
        Similaridad tipo "ratio de Levenshtein":
        1.0 = idéntico; 0.0 = completamente distinto.
        """
        if a == b:
            return 1.0

        la, lb = len(a), len(b)
        if la == 0 or lb == 0:
            return 0.0

        # DP simple (strings muy cortas, <= 8 chars → coste despreciable)
        dp = [[0] * (lb + 1) for _ in range(la + 1)]
        for i in range(la + 1):
            dp[i][0] = i
        for j in range(lb + 1):
            dp[0][j] = j

        for i in range(1, la + 1):
            ca = a[i - 1]
            for j in range(1, lb + 1):
                cb = b[j - 1]
                cost = 0 if ca == cb else 1
                dp[i][j] = min(
                    dp[i - 1][j] + 1,         # borrado
                    dp[i][j - 1] + 1,         # inserción
                    dp[i - 1][j - 1] + cost,  # sustitución
                )

        dist = dp[la][lb]
        max_len = max(la, lb)
        return 1.0 - (dist / max_len)

    # utilidad para tests / operativa: limpiar todo
    def clear(self) -> None:
        self._by_cam_track.clear()
        self._by_cam_text.clear()
