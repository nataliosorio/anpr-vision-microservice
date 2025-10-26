# src/infrastructure/Tracking/byte_tracker_adapter.py
from typing import List, Tuple, Optional
import numpy as np
import logging
from types import SimpleNamespace

from src.domain.Interfaces.tracker import ITracker
from src.domain.Models.plate import Plate
from src.infrastructure.Tracking.byteTracker.byte_tracker import BYTETracker
from src.core.config import settings

logger = logging.getLogger(__name__)


def xywh_to_xyxy(x: int, y: int, w: int, h: int) -> Tuple[float, float, float, float]:
    x_min = float(x)
    y_min = float(y)
    x_max = float(x + w)
    y_max = float(y + h)
    return x_min, y_min, x_max, y_max


def iou_xyxy(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a.size == 0 or b.size == 0:
        return np.zeros((a.shape[0], b.shape[0]), dtype=np.float32)

    a_exp = a[:, None, :]  # [P,1,4]
    b_exp = b[None, :, :]  # [1,T,4]

    inter_x1 = np.maximum(a_exp[..., 0], b_exp[..., 0])
    inter_y1 = np.maximum(a_exp[..., 1], b_exp[..., 1])
    inter_x2 = np.minimum(a_exp[..., 2], b_exp[..., 2])
    inter_y2 = np.minimum(a_exp[..., 3], b_exp[..., 3])

    inter_w = np.maximum(0.0, inter_x2 - inter_x1)
    inter_h = np.maximum(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    area_a = np.maximum(0.0, (a_exp[..., 2] - a_exp[..., 0])) * np.maximum(0.0, (a_exp[..., 3] - a_exp[..., 1]))
    area_b = np.maximum(0.0, (b_exp[..., 2] - b_exp[..., 0])) * np.maximum(0.0, (b_exp[..., 3] - b_exp[..., 1]))

    union = area_a + area_b - inter_area + 1e-6
    return inter_area / union


class ByteTrackerAdapter(ITracker):
    def __init__(self):
        self._args_dict = {
            "track_thresh": settings.bytetrack_thresh,
            "match_thresh": settings.bytetrack_match_thresh,
            "track_buffer": settings.bytetrack_buffer_size,
            "frame_rate": settings.bytetrack_fps,
            "mot20": False,
        }
        args_ns = SimpleNamespace(**self._args_dict)
        self._tracker = BYTETracker(args_ns, frame_rate=settings.bytetrack_fps)
        self._iou_threshold = getattr(settings, "bytetrack_iou_threshold", 0.1)

    def update(self, plates: List[Plate], image_size: Optional[Tuple[int, int]] = None) -> List[Plate]:
        if not plates:
            return plates
        if image_size is None:
            raise RuntimeError("ByteTrackerAdapter.update requiere image_size=(height, width).")

        height, width = image_size

        detections = []
        for plate in plates:
            x, y, w, h = plate.bounding_box
            x_min, y_min, x_max, y_max = xywh_to_xyxy(x, y, w, h)
            score = float(getattr(plate, "confidence", 1.0))
            detections.append([x_min, y_min, x_max, y_max, score])

        detections_np = (
            np.array(detections, dtype=np.float32)
            if detections
            else np.empty((0, 5), dtype=np.float32)
        )

        online_tracks = self._tracker.update(detections_np, (height, width), (height, width))

        track_boxes, track_ids = [], []
        for track in online_tracks:
            box_xyxy = getattr(track, "tlbr", None)
            if box_xyxy is None or len(box_xyxy) != 4:
                continue
            track_boxes.append(np.array(box_xyxy, dtype=np.float32))
            track_ids.append(int(track.track_id))

        if len(track_boxes) == 0:
            for plate in plates:
                plate.track_id = None
            return plates

        track_boxes_np = np.vstack(track_boxes).astype(np.float32)
        plate_boxes_np = np.array(
            [xywh_to_xyxy(*p.bounding_box) for p in plates],
            dtype=np.float32,
        )

        iou_matrix = iou_xyxy(plate_boxes_np, track_boxes_np)
        best_track_index = np.argmax(iou_matrix, axis=1)
        best_iou = np.max(iou_matrix, axis=1)

        for i, plate in enumerate(plates):
            plate.track_id = track_ids[best_track_index[i]] if best_iou[i] >= self._iou_threshold else None

        return plates
