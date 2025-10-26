import os
from typing import List, Dict, Any, Optional

import numpy as np
import cv2

from src.domain.Models.frame import Frame
from src.domain.Models.plate import Plate
from src.domain.Interfaces.plate_detector import IPlateDetector
from src.core.config import settings

from loguru import logger


class YoloV5PlateDetector(IPlateDetector):
    """
    Detector de placas basado en YOLOv5 usando la librería 'yolov5' oficial de Ultralytics.
    - Carga pesos locales (.pt) desde settings.yolov5_model_path.
    - Si el archivo no existe, intenta descargarlo desde Hugging Face (settings.yolov5_hf_repo/filename).
    - Normaliza salidas a List[Plate] para encajar con el pipeline existente.
    """

    def __init__(self):
        # Dependencias necesarias (la librería 'yolov5' requiere torch)
        try:
            import yolov5  # noqa: F401
            import torch   # noqa: F401
        except ImportError as e:
            raise ImportError(
                "Falta dependencia para YOLOv5. Instala:\n"
                "  pip install yolov5 torch\n"
                "Tip: torch debe coincidir con tu CUDA si usas GPU."
            ) from e

        import yolov5
        import torch

        # Dispositivo
        self.device = self._resolve_device(torch, settings.yolov5_device)

        # Carga de pesos (local ó HF fallback)
        model_path = self._ensure_weights_available()
        logger.info(f"[YOLOv5] Usando pesos: {model_path}")

        # Cargar modelo
        self.model = yolov5.load(model_path)
        # Seteo de hiperparámetros del NMS
        self.model.conf = float(settings.yolov5_conf)
        self.model.iou = float(settings.yolov5_iou)
        self.model.agnostic = bool(settings.yolov5_agnostic)
        self.model.multi_label = bool(settings.yolov5_multi_label)
        self.model.max_det = int(settings.yolov5_max_det)
        self.imgsz = int(settings.yolov5_img_size)

        # Enviar a device si aplica
        try:
            self.model.to(self.device)
        except Exception:
            # Algunos builds de yolov5 manejan el device internamente.
            pass

        # Clases (la mayoría de modelos LP son una sola clase)
        self.class_names = getattr(self.model, "names", {0: "license-plate"})
        if not self.class_names:
            self.class_names = {0: "license-plate"}

        logger.info(f"[YOLOv5] Device: {self.device}, conf={self.model.conf}, iou={self.model.iou}, imgsz={self.imgsz}")

    def _resolve_device(self, torch, device_cfg: str) -> str:
        if device_cfg == "auto":
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        return device_cfg

    def _ensure_weights_available(self) -> str:
        """
        Verifica que el archivo .pt exista en la ruta configurada.
        """
        local_path = settings.yolov5_model_path
        if not os.path.isfile(local_path):
            raise FileNotFoundError(
                f"No se encontró el modelo YOLOv5 en {local_path}. "
                f"Asegúrate de descargarlo y configurar la ruta en .env"
            )
        return local_path

    def detect(self, frame: Frame) -> List[Plate]:
        """
        Aplica inferencia sobre frame.data (BGR) y devuelve placas normalizadas.
        """
        if frame is None or frame.data is None or frame.data.size == 0:
            return []

        # La API de yolov5 acepta directamente np.ndarray (BGR o RGB; internamente lo maneja)
        try:
            results = self.model(frame.data, size=self.imgsz)
        except Exception as e:
            logger.error(f"[YOLOv5] Error en inferencia: {e}")
            return []

        # results.pred es una lista de tensores [N,6] -> [x1,y1,x2,y2,conf,cls]
        try:
            preds = results.pred[0].detach().cpu().numpy()
        except Exception:
            # Fallback para implementaciones antiguas con .xyxy[0] -> DataFrame
            try:
                df = results.pandas().xyxy[0]
                preds = df[["xmin", "ymin", "xmax", "ymax", "confidence", "class"]].to_numpy()
            except Exception as e:
                logger.error(f"[YOLOv5] No pude parsear las predicciones: {e}")
                return []

        plates: List[Plate] = []
        conf_thr = float(settings.yolov5_conf)

        for det in preds:
            if det.shape[0] < 6:
                continue
            x1, y1, x2, y2, conf, cls_id = det[:6]
            if conf < conf_thr:
                continue

            # Normalizamos bbox a (x, y, w, h) enteros
            x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
            x, y, w, h = int(x1), int(y1), int(x2 - x1), int(y2 - y1)

            # Nombre de clase (por si hace falta filtrar)
            try:
                cname = self.class_names[int(cls_id)]
            except Exception:
                cname = "license-plate"

            # Si tu modelo trae más clases y quieres filtrar solo placas, hazlo aquí:
            # if cname not in ("license-plate", "plate"):
            #     continue

            plates.append(Plate(
                text="",  # lo llenará el OCR luego
                confidence=float(conf),
                bounding_box=(x, y, w, h)
            ))

        return plates
