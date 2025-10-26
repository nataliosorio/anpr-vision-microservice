import time
import logging
from typing import Any
from src.domain.Interfaces.event_publisher import IEventPublisher

logger = logging.getLogger(__name__)

class RetryPublisher(IEventPublisher):
    """
    Wrapper que reintenta publish hasta N veces con backoff exponencial.
    Solo reintenta si el error parece transitorio (red, timeout, broker unavailable).
    """
    def __init__(self, inner: IEventPublisher, attempts: int = 3, base_delay: float = 0.5):
        self.inner = inner
        self.attempts = max(1, attempts)
        self.base_delay = base_delay

    def _is_transient_error(self, exc: Exception) -> bool:
        """
        Determina si el error amerita reintento.
        Ejemplo: timeouts, desconexión de broker, errores de red.
        """
        msg = str(exc).lower()
        transient_keywords = [
            "timeout",
            "connection",
            "broker",
            "unreachable",
            "not leader",
            "network",
            "flush",
            "transport",
        ]
        return any(k in msg for k in transient_keywords)

    def publish(self, payload: Any) -> None:
        last_exc = None
        for i in range(1, self.attempts + 1):
            try:
                self.inner.publish(payload)
                logger.debug("Publish OK (attempt %d/%d)", i, self.attempts)
                return
            except Exception as e:
                last_exc = e
                if not self._is_transient_error(e):
                    # error permanente → no reintentar
                    logger.error("Non-retryable publish error: %s", e)
                    raise
                wait = self.base_delay * (2 ** (i - 1))
                logger.warning("Publish attempt %d failed (transient), retrying in %.2fs: %s", i, wait, e)
                time.sleep(wait)

        # Si fallaron todos los intentos
        logger.error("❌ All publish attempts failed after %d retries: %s", self.attempts, last_exc)
        raise last_exc
