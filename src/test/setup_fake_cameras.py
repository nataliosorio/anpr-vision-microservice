from src.infrastructure.Camera.camera_repository import CameraRepository
from src.domain.Models.camera import Camera

repo = CameraRepository()

for i in range(1, 6):
    cam = Camera(
        camera_id=str(i),
        name=f"FakeCam-{i}",
        parking_id=1,
        url=f"fake://camera{i}.mp4"  # no es real, lo interpretará la fábrica
    )
    repo.save(cam)

print("5 cámaras creadas en la DB local 🎥")
