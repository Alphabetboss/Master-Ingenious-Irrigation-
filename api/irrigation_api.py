from __future__ import annotations
import os
import io
import json
import time
import datetime as dt
from pathlib import Path
from typing import Dict, Any

from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
import numpy as np
from PIL import Image
import cv2
import importlib

from engine.garden_ai_engine import GardenAIEngine, ZoneContext

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
LOG = DATA_DIR / "hydration_log.jsonl"
API_KEY = os.getenv("II_API_KEY", "dev-key")

app = Flask(__name__, static_folder="static", template_folder="templates")

# ---------------- schedule manager or stub ----------------
_schedule_module = None
try:
    _schedule_module = importlib.import_module("scheduler.schedule_manager")
except Exception:
    _schedule_module = None

if _schedule_module is not None:
    start_watering = getattr(_schedule_module, "start_watering")
    stop_watering = getattr(_schedule_module, "stop_watering")
    get_status = getattr(_schedule_module, "get_status")
    skip_next_run = getattr(_schedule_module, "skip_next_run")
    resume_schedule = getattr(_schedule_module, "resume_schedule")
    set_zone_duration = getattr(_schedule_module, "set_zone_duration")
else:
    _current = {"watering": False, "active_zone": None, "minutes": 0}

    def start_watering(zone=1, minutes=None):
        _current.update({"watering": True, "active_zone": zone, "minutes": int(minutes or 0)})
        return True

    def stop_watering():
        _current.update({"watering": False, "active_zone": None, "minutes": 0})
        return True

    def get_status():
        return dict(_current)

    def skip_next_run():
        return True

    def resume_schedule():
        return True

    def set_zone_duration(zone: int, minutes: int):
        _current.update({"active_zone": zone, "minutes": int(minutes)})
        return True


def authed() -> bool:
    return request.headers.get("X-API-Key", "") == API_KEY


# ---------------- Garden AI Engine ----------------
YOLO_WEIGHTS = os.getenv("II_YOLO_WEIGHTS", str((ROOT / "models" / "ingenious_yolov8.pt").resolve()))
engine = GardenAIEngine(model_path=YOLO_WEIGHTS, hydration_cache_file=str(DATA_DIR / "hydration_cache.json"))


# ---------------- logging helpers ----------------
def log_hydration(entry: Dict[str, Any]) -> None:
    entry = dict(entry)
    entry["ts"] = dt.datetime.utcnow().isoformat() + "Z"
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def tail_log(n=200):
    if not LOG.exists():
        return []
    lines = LOG.read_text(encoding="utf-8").splitlines()[-n:]
    return [json.loads(x) for x in lines if x.strip()]


# ---------------- web UI ----------------
@app.get("/")
def home():
    return render_template("index.html")


# ---------------- irrigation control API ----------------
@app.post("/api/irrigation/start")
def api_start():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    ok = start_watering(zone=1)
    return jsonify({"ok": bool(ok)})


@app.post("/api/irrigation/stop")
def api_stop():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    ok = stop_watering()
    return jsonify({"ok": bool(ok)})


@app.get("/api/irrigation/status")
def api_status():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_status())


@app.post("/api/irrigation/skip")
def api_skip():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"ok": skip_next_run()})


@app.post("/api/irrigation/resume")
def api_resume():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"ok": resume_schedule()})


@app.post("/api/irrigation/zone/<int:zone>/duration")
def api_set_zone_duration(zone: int):
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    minutes = int(data.get("minutes", 10))
    ok = set_zone_duration(zone=zone, minutes=minutes)
    return jsonify({"ok": bool(ok), "zone": zone, "minutes": minutes})


# ---------------- hydration AI API ----------------
@app.post("/api/hydration/analyze")
def api_hydration_analyze():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401

    img_bytes = None
    if "image" in request.files:
        file = request.files["image"]
        fname = secure_filename(file.filename or f"upload_{int(time.time())}.png")
        raw = file.read()
        img_bytes = raw
        (UPLOADS / fname).write_bytes(raw)
        image_path = str(UPLOADS / fname)
    else:
        img_bytes = request.get_data()
        fname = f"upload_{int(time.time())}.png"
        image_path = str(UPLOADS / fname)
        if img_bytes:
            (UPLOADS / fname).write_bytes(img_bytes)

    if not img_bytes:
        return jsonify({"error": "no image received"}), 400

    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        img_bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        return jsonify({"error": f"decode failed: {e}"}), 400

    # Use GardenAIEngine
    zone = ZoneContext(zone_id="zone_1", name="Front Lawn", camera_image_path=image_path)
    eval_result = engine.evaluate_zone(zone)

    res = {
        "zone_id": eval_result.zone_id,
        "hydration_score": eval_result.hydration.need_score,
        "hydration_advisory": eval_result.hydration.advisory,
        "health": {
            "greenness_score": eval_result.health.greenness_score,
            "water_flag": eval_result.health.water_flag,
            "dry_flag": eval_result.health.dry_flag,
        },
        "weather": eval_result.weather,
        "safety_triggered": eval_result.safety_triggered,
        "safety_reason": eval_result.safety_reason,
    }

    log_hydration({"source": "upload", **res})
    return jsonify(res)


@app.get("/api/hydration/log")
def api_hydration_log():
    if not authed():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(tail_log(200))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
