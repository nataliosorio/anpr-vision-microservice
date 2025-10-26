# src/domain/Interfaces/deduplicator.py
from typing import Protocol, Optional

class IDeduplicator(Protocol):
    """
    Contrato para deduplicación en el dominio.

    is_duplicate devuelve True si la lectura debe considerarse duplicada
    (y por tanto **no** publicarse). La implementación puede usar
    track_id, texto normalizado y camera_id para aislar ventanas.
    """
    def is_duplicate(self, track_id: Optional[int], plate_text: str, camera_id: Optional[str] = None) -> bool:
        ...
