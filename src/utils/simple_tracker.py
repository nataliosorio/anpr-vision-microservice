"""A simple centroid-based tracker for licence plate detections.

This tracker maintains a mapping of active tracks by comparing the
centroids of bounding boxes between frames. When a new detection is
close to the centroid of an existing track (within a configurable
distance threshold), it inherits that track's ID. Otherwise, a new
track is created. Tracks expire automatically after a period of
inactivity.

The implementation is intentionally lightweight and does not depend
on external libraries. For production deployments, consider swapping
this class for a more robust tracker (e.g. a Kalman filter or a
ByteTrack implementation) that can better handle occlusions and
object motion.
"""

import time
from math import sqrt
from typing import Dict, List, Tuple

from src.domain.Models.plate import Plate


class SimpleTracker:
    """Assigns persistent IDs to detected plates across frames."""

    def __init__(self, ttl: float = 3.0, max_distance: float = 50.0):
        """
        Initialise the tracker.

        Args:
            ttl: Time-to-live in seconds for a track. If a track is not
                updated within ``ttl`` seconds it is discarded.
            max_distance: Maximum Euclidean distance (in pixels) between
                the centroid of a detection and an existing track's
                centroid for them to be considered the same object.
        """
        self.ttl = ttl
        self.max_distance = max_distance
        self.next_id = 0
        self.tracks: Dict[int, Dict[str, Tuple]] = {}

    def _center(self, bbox: Tuple[int, int, int, int]) -> Tuple[float, float]:
        x, y, w, h = bbox
        return (x + w / 2.0, y + h / 2.0)

    def update(self, plates: List[Plate]) -> List[Plate]:
        """
        Assign track IDs to the provided detections.

        Args:
            plates: A list of :class:`Plate` objects representing the
                current frame's detections. The ``bounding_box`` field
                of each plate must be populated.

        Returns:
            The same list of ``Plate`` instances with the ``track_id``
            attribute populated.
        """
        now = time.time()

        # Remove expired tracks
        for tid in list(self.tracks.keys()):
            if now - self.tracks[tid]['last_seen'] > self.ttl:
                del self.tracks[tid]

        for plate in plates:
            cx, cy = self._center(plate.bounding_box)
            assigned_id = None
            best_distance = self.max_distance

            # Match to existing track
            for tid, track in self.tracks.items():
                tx, ty = self._center(track['bbox'])
                dist = sqrt((cx - tx) ** 2 + (cy - ty) ** 2)
                if dist < best_distance:
                    best_distance = dist
                    assigned_id = tid

            # Create new track if no match was found
            if assigned_id is None:
                assigned_id = self.next_id
                self.next_id += 1

            # Update track info
            self.tracks[assigned_id] = {
                'bbox': plate.bounding_box,
                'last_seen': now
            }
            plate.track_id = assigned_id

        return plates
