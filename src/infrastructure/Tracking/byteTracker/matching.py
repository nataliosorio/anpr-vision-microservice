import cv2
import numpy as np
import scipy
import lap
from scipy.spatial.distance import cdist

from cython_bbox import bbox_overlaps as bbox_ious
from src.infrastructure.Tracking.byteTracker import kalman_filter
import time


def merge_matches(m1, m2, shape):
    O, P, Q = shape
    m1 = np.asarray(m1)
    m2 = np.asarray(m2)

    M1 = scipy.sparse.coo_matrix((np.ones(len(m1)), (m1[:, 0], m1[:, 1])), shape=(O, P))
    M2 = scipy.sparse.coo_matrix((np.ones(len(m2)), (m2[:, 0], m2[:, 1])), shape=(P, Q))

    mask = M1 * M2
    match = mask.nonzero()
    match = list(zip(match[0], match[1]))
    unmatched_O = tuple(set(range(O)) - set([i for i, j in match]))
    unmatched_Q = tuple(set(range(Q)) - set([j for i, j in match]))

    return match, unmatched_O, unmatched_Q


def _indices_to_matches(cost_matrix, indices, thresh):
    matched_cost = cost_matrix[tuple(zip(*indices))]
    matched_mask = (matched_cost <= thresh)

    matches = indices[matched_mask]
    unmatched_a = tuple(set(range(cost_matrix.shape[0])) - set(matches[:, 0]))
    unmatched_b = tuple(set(range(cost_matrix.shape[1])) - set(matches[:, 1]))

    return matches, unmatched_a, unmatched_b


def linear_assignment(cost_matrix, thresh):
    if cost_matrix.size == 0:
        return (
            np.empty((0, 2), dtype=int),
            tuple(range(cost_matrix.shape[0])),
            tuple(range(cost_matrix.shape[1])),
        )
    matches, unmatched_a, unmatched_b = [], [], []
    cost, x, y = lap.lapjv(cost_matrix, extend_cost=True, cost_limit=thresh)
    for ix, mx in enumerate(x):
        if mx >= 0:
            matches.append([ix, mx])
    unmatched_a = np.where(x < 0)[0]
    unmatched_b = np.where(y < 0)[0]
    matches = np.asarray(matches, dtype=int)
    return matches, unmatched_a, unmatched_b


# ---------- IoU helpers ----------

def _ious_numpy(a32, b32):
    """
    Fallback puro NumPy en formato TLBR:
    a32, b32: (N,4)/(M,4) con [top, left, bottom, right]
    """
    a = np.asarray(a32, dtype=np.float32)
    b = np.asarray(b32, dtype=np.float32)
    N, M = a.shape[0], b.shape[0]
    if N == 0 or M == 0:
        return np.zeros((N, M), dtype=np.float32)

    # inter TLBR
    top = np.maximum(a[:, None, 0], b[None, :, 0])
    left = np.maximum(a[:, None, 1], b[None, :, 1])
    bottom = np.minimum(a[:, None, 2], b[None, :, 2])
    right = np.minimum(a[:, None, 3], b[None, :, 3])

    inter_w = np.clip(right - left, 0, None)
    inter_h = np.clip(bottom - top, 0, None)
    inter = inter_w * inter_h

    area_a = (a[:, 3] - a[:, 1]) * (a[:, 2] - a[:, 0])
    area_b = (b[:, 3] - b[:, 1]) * (b[:, 2] - b[:, 0])

    union = area_a[:, None] + area_b[None, :] - inter
    iou = np.where(union > 0, inter / union, 0.0).astype(np.float32, copy=False)
    return iou


def ious(atlbrs, btlbrs):
    """
    Compute IoU matrix en TLBR.
    Soporta listas o arrays. Hace cast y contiguidad para el binario Cython.
    """
    nA = len(atlbrs)
    nB = len(btlbrs)
    if nA == 0 or nB == 0:
        return np.zeros((nA, nB), dtype=np.float32)

    # Muchos builds de cython-bbox esperan float64; hacemos cast seguro.
    a64 = np.ascontiguousarray(np.asarray(atlbrs, dtype=np.float64))
    b64 = np.ascontiguousarray(np.asarray(btlbrs, dtype=np.float64))
    try:
        out = bbox_ious(a64, b64)  # devuelve float64 normalmente
        return np.asarray(out, dtype=np.float32, order="C")
    except ValueError:
        # Si hay mismatch de DTYPE, usamos fallback NumPy robusto
        return _ious_numpy(a64.astype(np.float32), b64.astype(np.float32))


def iou_distance(atracks, btracks):
    """
    Compute cost based on IoU: cost = 1 - IoU
    """
    if (len(atracks) > 0 and isinstance(atracks[0], np.ndarray)) or (len(btracks) > 0 and isinstance(btracks[0], np.ndarray)):
        atlbrs = atracks
        btlbrs = btracks
    else:
        atlbrs = [track.tlbr for track in atracks]
        btlbrs = [track.tlbr for track in btracks]
    _ious = ious(atlbrs, btlbrs)
    cost_matrix = 1.0 - _ious
    return cost_matrix


def v_iou_distance(atracks, btracks):
    """
    IoU entre cajas predichas (usa tlwh_to_tlbr en cada track)
    """
    if (len(atracks) > 0 and isinstance(atracks[0], np.ndarray)) or (len(btracks) > 0 and isinstance(btracks[0], np.ndarray)):
        atlbrs = atracks
        btlbrs = btracks
    else:
        atlbrs = [track.tlwh_to_tlbr(track.pred_bbox) for track in atracks]
        btlbrs = [track.tlwh_to_tlbr(track.pred_bbox) for track in btracks]
    _ious = ious(atlbrs, btlbrs)
    cost_matrix = 1.0 - _ious
    return cost_matrix


def embedding_distance(tracks, detections, metric='cosine'):
    """
    :param tracks: list[STrack]
    :param detections: list[BaseTrack]
    :param metric:
    :return: cost_matrix np.ndarray (float32)
    """
    cost_matrix = np.zeros((len(tracks), len(detections)), dtype=np.float32)
    if cost_matrix.size == 0:
        return cost_matrix

    det_features = np.asarray([track.curr_feat for track in detections], dtype=np.float32)
    track_features = np.asarray([track.smooth_feat for track in tracks], dtype=np.float32)

    # cdist devuelve float64; casteamos a float32 por consistencia
    cm = np.maximum(0.0, cdist(track_features, det_features, metric)).astype(np.float32, copy=False)
    return cm


def gate_cost_matrix(kf, cost_matrix, tracks, detections, only_position=False):
    if cost_matrix.size == 0:
        return cost_matrix
    gating_dim = 2 if only_position else 4
    gating_threshold = kalman_filter.chi2inv95[gating_dim]
    measurements = np.asarray([det.to_xyah() for det in detections])
    for row, track in enumerate(tracks):
        gating_distance = kf.gating_distance(track.mean, track.covariance, measurements, only_position)
        cost_matrix[row, gating_distance > gating_threshold] = np.inf
    return cost_matrix


def fuse_motion(kf, cost_matrix, tracks, detections, only_position=False, lambda_=0.98):
    if cost_matrix.size == 0:
        return cost_matrix
    gating_dim = 2 if only_position else 4
    gating_threshold = kalman_filter.chi2inv95[gating_dim]
    measurements = np.asarray([det.to_xyah() for det in detections])
    for row, track in enumerate(tracks):
        gating_distance = kf.gating_distance(track.mean, track.covariance, measurements, only_position, metric='maha')
        cost_matrix[row, gating_distance > gating_threshold] = np.inf
        cost_matrix[row] = lambda_ * cost_matrix[row] + (1.0 - lambda_) * gating_distance
    return cost_matrix


def fuse_iou(cost_matrix, tracks, detections):
    if cost_matrix.size == 0:
        return cost_matrix
    reid_sim = 1.0 - cost_matrix
    iou_dist = iou_distance(tracks, detections)
    iou_sim = 1.0 - iou_dist
    fuse_sim = reid_sim * (1.0 + iou_sim) / 2.0
    det_scores = np.array([det.score for det in detections], dtype=np.float32)
    det_scores = np.expand_dims(det_scores, axis=0).repeat(cost_matrix.shape[0], axis=0)
    # fuse_sim = fuse_sim * (1 + det_scores) / 2
    fuse_cost = 1.0 - fuse_sim
    return fuse_cost


def fuse_score(cost_matrix, detections):
    if cost_matrix.size == 0:
        return cost_matrix
    iou_sim = 1.0 - cost_matrix
    det_scores = np.array([det.score for det in detections], dtype=np.float32)
    det_scores = np.expand_dims(det_scores, axis=0).repeat(cost_matrix.shape[0], axis=0)
    fuse_sim = iou_sim * det_scores
    fuse_cost = 1.0 - fuse_sim
    return fuse_cost
