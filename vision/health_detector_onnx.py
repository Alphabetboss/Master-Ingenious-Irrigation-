from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Tuple, Any

import numpy as np
import cv2
import onnxruntime as ort

MODEL_PATH = Path("ml/models/yolov8n.onnx")
CLASSES_PATH = Path("ml/data/classes.txt")
IMG_SIZE = 640
CONF_THRES = 0.25
IOU_THRES = 0.45
PROVIDERS = ["CPUExecutionProvider"]


def load_classes(path: Path) -> List[str]:
    if path.exists():
        return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return ["grass", "water", "dead_grass"]


def letterbox(im: np.ndarray, new_shape=IMG_SIZE, color=(114, 114, 114)) -> Tuple[np.ndarray, float, Tuple[int, int]]:
    if isinstance(new_shape, int):
        new_shape = (new_shape, new_shape)
    h, w = im.shape[:2]
    r = min(new_shape[0] / h, new_shape[1] / w)
    new_unpad = (int(round(w * r)), int(round(h * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return im, r, (left, top)


def xywh2xyxy(x: np.ndarray) -> np.ndarray:
    y = np.zeros_like(x)
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    inter = (np.minimum(boxes[:, 2], box[2]) - np.maximum(boxes[:, 0], box[0])).clip(0) * (
        np.minimum(boxes[:, 3], box[3]) - np.maximum(boxes[:, 1], box[1])
    ).clip(0)
    area1 = (box[2] - box[0]) * (box[3] - box[1])
    area2 = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / (area1 + area2 - inter + 1e-6)


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thres=0.45) -> List[int]:
    idxs = scores.argsort()[::-1]
    keep: List[int] = []
    while idxs.size > 0:
        i = idxs[0]
        keep.append(int(i))
        if idxs.size == 1:
            break
        ious = iou(boxes[i], boxes[idxs[1:]])
        idxs = idxs[1:][ious < iou_thres]
    return keep


class YoloV8ONNX:
    def __init__(self, model_path: Path = MODEL_PATH, providers=PROVIDERS) -> None:
        if not Path(model_path).exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        self.sess = ort.InferenceSession(str(model_path), providers=providers)
        self.inp_name = self.sess.get_inputs()[0].name
        self.classes = load_classes(CLASSES_PATH)

    def infer(self, img_bgr: np.ndarray, conf_thres=CONF_THRES, iou_thres=IOU_THRES) -> Dict[str, Any]:
        orig = img_bgr.copy()
        h0, w0 = orig.shape[:2]

        img, r, (dw, dh) = letterbox(orig, IMG_SIZE)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = (img.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]

        out = self.sess.run(None, {self.inp_name: img})[0]
        pred = np.squeeze(out, 0)
        if pred.shape[0] < pred.shape[1]:
            pred = pred.T

        boxes_xywh = pred[:, :4]
        scores_per_class = pred[:, 4:]

        class_ids = scores_per_class.argmax(1)
        scores = scores_per_class.max(1)

        m = scores >= conf_thres
        boxes_xywh = boxes_xywh[m]
        scores = scores[m]
        class_ids = class_ids[m]

        if boxes_xywh.size == 0:
            return {"detections": [], "hydration_score": 5.0, "meta": {"w": w0, "h": h0}}

        boxes = xywh2xyxy(boxes_xywh)
        boxes[:, [0, 2]] -= dw
        boxes[:, [1, 3]] -= dh
        boxes /= r
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, w0)
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, h0)

        keep = nms(boxes, scores, iou_thres)
        boxes, scores, class_ids = boxes[keep], scores[keep], class_ids[keep]

        dets: List[Dict[str, Any]] = []
        for box, sc, cid in zip(boxes, scores, class_ids):
            x1, y1, x2, y2 = box.tolist()
            cname = self.classes[int(cid)] if int(cid) < len(self.classes) else f"class_{int(cid)}"
            dets.append(
                {
                    "class_id": int(cid),
                    "class_name": cname,
                    "confidence": float(sc),
                    "box_xyxy": [float(x1), float(y1), float(x2), float(y2)],
                }
            )

        score = hydration_score(dets, (w0, h0))
        return {"detections": dets, "hydration_score": score, "meta": {"w": w0, "h": h0}}


def hydration_score(dets: List[Dict[str, Any]], size: Tuple[int, int]) -> float:
    w, h = size
    area = w * h + 1e-6

    water_like = {"water", "standing_water", "mushy_grass", "mud"}
    dry_like = {"dead_grass", "dry_soil", "brown_patch"}
    healthy_like = {"grass", "healthy_grass", "green_grass"}

    frac = {"water": 0.0, "dry": 0.0, "healthy": 0.0}
    confs: List[float] = []

    for d in dets:
        x1, y1, x2, y2 = d["box_xyxy"]
        a = max(0.0, (x2 - x1)) * max(0.0, (y2 - y1)) / area
        name = d["class_name"]
        c = d["confidence"]
        confs.append(c)
        if name in water_like:
            frac["water"] += a
        if name in dry_like:
            frac["dry"] += a
        if name in healthy_like:
            frac["healthy"] += a

    mean_conf = float(np.mean(confs)) if confs else 0.5
    sat = (0.60 * frac["water"] + 0.20 * frac["healthy"] - 0.50 * frac["dry"] + 0.10 * mean_conf)
    score = max(0.0, min(10.0, 10.0 * sat))
    if not dets:
        score = 5.0
    return float(score)
