import time
from difflib import SequenceMatcher

class Deduplicator:
    def __init__(self, ttl: float = 3.0, similarity_threshold: float = 0.9):
        """
        :param ttl: Tiempo en segundos para volver a aceptar la misma placa
        :param similarity_threshold: Similitud mínima para considerar textos iguales
        """
        self.ttl = ttl
        self.similarity_threshold = similarity_threshold
        self.last_seen = {}  # {placa: timestamp}

    def is_duplicate(self, plate_text: str) -> bool:
        now = time.time()
        # Limpieza de entradas expiradas
        for prev_text, ts in list(self.last_seen.items()):
            if now - ts > self.ttl:
                self.last_seen.pop(prev_text, None)
                continue

            if plate_text == prev_text:
                return True
            if self._similar(plate_text, prev_text) >= self.similarity_threshold:
                return True

        # Registrar nueva
        self.last_seen[plate_text] = now
        return False

    def _similar(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()
