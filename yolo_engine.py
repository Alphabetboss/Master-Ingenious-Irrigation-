from pathlib import Path
from typing import Dict

from ultralytics import YOLO
from config import MODEL_PATH


_model = None


def _get_model():
    global _model
    if _model is None:
        _model = YOLO(str(MODEL_PATH))
    return _model


def analyze_image(image_path: str | Path) -> Dict[str, float]:
    model = _get_model()
    results = model(str(image_path))[0]

    summary = {
        "healthy_grass": 0,
        "dead_grass": 0,
        "water": 0,
    }

    for box in results.boxes:
        cls_name = results.names[int(box.cls)]
        summary[cls_name] = summary.get(cls_name, 0) + 1

    total = sum(summary.values()) or 1
    for k in summary:
        summary[k] /= total

    return summary
