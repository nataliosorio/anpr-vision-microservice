# src/domain/Interfaces/tracker.py
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from src.domain.Models.plate import Plate

class ITracker(ABC):
    """
    Contrato para cualquier algoritmo de tracking de placas.

    Nota importante: el método `update` puede recibir opcionalmente
    el tamaño de la imagen (height, width) para que adaptadores que
    lo requieran (p.ej. ByteTrack) no dependan de llamadas externas.
    """

    @abstractmethod
    def update(self, plates: List[Plate], image_size: Optional[Tuple[int, int]] = None) -> List[Plate]:
        """
        Actualiza el estado del tracker con las nuevas detecciones.

        Parameters
        ----------
        plates : List[Plate]
            Lista de placas detectadas en el frame actual. Cada placa
            contiene al menos el bounding box y el texto OCR (si ya fue
            reconocido).

        image_size : Optional[Tuple[int,int]]
            (height, width) del frame. Recomendado para trackers que
            necesitan normalizar coordenadas o configurar internamente.

        Returns
        -------
        List[Plate]
            Lista de placas con `track_id` asignado.
        """
        pass
