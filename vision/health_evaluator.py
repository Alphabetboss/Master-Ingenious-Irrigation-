from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any
import cv2
import numpy as np


@dataclass
class HealthResult:
    greenness_score: float   # 0..1 (1 = very green/healthy)
    water_flag: bool         # standing water / leak detected
    dry_flag: bool           # brown/dry areas detected
    raw: Dict[str, Any]      # extra info (boxes, confidences, etc.)


class HealthEvaluator:
    def __init__(self, model_path: Optional[str] = None, conf: float = 0.35) -> None:
        self.model_path = model_path
        self.conf = conf
        self._model = None
        if model_path:
            try:
                from ultralytics import YOLO
                self._model = YOLO(model_path)
            except Exception:
                self._model = None  # fallback to HSV method

    # ----------------- fallback HSV -----------------
    def _heuristic_greenness(self, bgr: np.ndarray) -> HealthResult:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # Basic green mask
        lower = np.array([25, 40, 40])
        upper = np.array([85, 255, 255])
        mask_green = cv2.inRange(hsv, lower, upper)
        green_ratio = float(np.count_nonzero(mask_green)) / float(bgr.shape[0] * bgr.shape[1])

        # Dry detector
        lower_dry = np.array([5, 0, 80])
        upper_dry = np.array([25, 125, 255])
        mask_dry = cv2.inRange(hsv, lower_dry, upper_dry)
        dry_ratio = float(np.count_nonzero(mask_dry)) / float(bgr.shape[0] * bgr.shape[1])

        # Water detector
        lower_water = np.array([90, 40, 40])
        upper_water = np.array([130, 255, 255])
        mask_water = cv2.inRange(hsv, lower_water, upper_water)
        water_ratio = float(np.count_nonzero(mask_water)) / float(bgr.shape[0] * bgr.shape[1])

        return HealthResult(
            greenness_score=max(0.0, min(1.0, green_ratio)),
            water_flag=water_ratio > 0.02,
            dry_flag=dry_ratio > 0.06,
            raw={
                "green_ratio": green_ratio,
                "dry_ratio": dry_ratio,
                "water_ratio": water_ratio,
                "method": "HSV-heuristic",
            },
        )

    # ----------------- main entry -----------------
    def evaluate_image(self, image_path: str) -> HealthResult:
        img = cv2.imread(image_path)
        if img is None:
            return HealthResult(
                greenness_score=0.5,
                water_flag=False,
                dry_flag=False,
                raw={"error": "image not found"},
            )

        if self._model is None:
            return self._heuristic_greenness(img)

        # YOLO path
        results = self._model.predict(source=image_path, conf=self.conf, verbose=False)
        boxes = []
        classes = []
        scores = []
        green_score = 0.5
        dry_flag = False
        water_flag = False

        try:
            r = results[0]
            if hasattr(r, "boxes") and r.boxes is not None:
                for b in r.boxes:
                    cls = int(b.cls.item())
                    conf = float(b.conf.item())
                    xyxy = b.xyxy.tolist()[0]
                    boxes.append(xyxy)
                    classes.append(cls)
                    scores.append(conf)

            # Map classes: 0=grass, 1=dead_grass, 2=water
            for cls, sc in zip(classes, scores):
                if cls == 0:
                    green_score = min(1.0, max(green_score, 0.6 + 0.4 * sc))
                elif cls == 1:
                    dry_flag = dry_flag or (sc > 0.35)
                elif cls == 2:
                    water_flag = water_flag or (sc > 0.35)

            return HealthResult(
                greenness_score=green_score,
                water_flag=water_flag,
                dry_flag=dry_flag,
                raw={"boxes": boxes, "classes": classes, "scores": scores, "method": "YOLOv8"},
            )
        except Exception as e:
            hr = self._heuristic_greenness(img)
            hr.raw["yolo_error"] = str(e)
            return hr
