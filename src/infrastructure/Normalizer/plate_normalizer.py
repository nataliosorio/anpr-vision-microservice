# src/infrastructure/Normalizer/plate_normalizer.py
import re
from typing import Optional
from src.domain.Interfaces.text_normalizer import ITextNormalizer
from src.core.config import settings


class PlateNormalizer(ITextNormalizer):
    """
    Normaliza texto de placas:
    - Mayúsculas
    - Quitar separadores habituales
    - Aceptar solo A-Z0-9
    - Rechazar si fuera de rango [min_len, max_len]
    - Rechazar si no tiene mezcla razonable de letras y dígitos
    """
    _ALNUM = re.compile(r"[^A-Z0-9]")

    def __init__(self, min_len: Optional[int] = None, max_len: Optional[int] = None):
        self.min_len = min_len or getattr(settings, "plate_min_length", 6)
        self.max_len = max_len or getattr(settings, "plate_max_length", 6)

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        t = text.strip().upper()
        for ch in (" ", "-", "_", ".", "/", "\\"):
            t = t.replace(ch, "")

        # dejar sólo A-Z0-9
        t = self._ALNUM.sub("", t)

        # validar longitudes
        if len(t) < self.min_len or len(t) > self.max_len:
            return ""

        # mezcla letras / dígitos mínima
        letters = sum(c.isalpha() for c in t)
        digits = sum(c.isdigit() for c in t)
        if letters < 2 or digits < 2:
            # cosas tipo "AAAAAA", "111111", "ABCD12" (según min_len) pasan,
            # pero ruido puro no.
            return ""

        return t
