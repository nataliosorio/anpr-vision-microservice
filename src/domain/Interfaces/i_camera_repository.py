from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.Models.camera import Camera

class ICameraRepository(ABC):

    @abstractmethod
    def get_all(self) -> List[Camera]:
        pass

    @abstractmethod
    def get_by_id(self, camera_id: str) -> Optional[Camera]:
        pass

    @abstractmethod
    def save(self, camera: Camera) -> Camera:
        pass

    @abstractmethod
    def delete(self, camera_id: str) -> None:
        pass
