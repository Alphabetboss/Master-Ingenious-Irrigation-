# vision/yolo_engine.py
"""
Simple YOLO engine wrapper with fallback to vision.mock.
- If YOLO_MODEL_PATH env var points to a model file and the import succeeds,
  is_ready() will return True after loading.
- Otherwise, falls back to vision.mock to keep the app runnable.
"""

import os
import logging
from importlib import import_module

logger = logging.getLogger(__name__)

YOLO_MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", "").strip()
_engine = None
_mode = "none"

# Try to load a real model if path provided. Keep this non-fatal.
if YOLO_MODEL_PATH:
    try:
        # Example: if you use torch.hub or ultralytics, load model here.
        # We keep this generic and non-blocking; real loading code goes here.
        # from some_yolo_lib import load_model
        # _engine = load_model(YOLO_MODEL_PATH)
        # For now, we mark as not loaded and let user replace this block.
        logger.info("YOLO_MODEL_PATH set but no loader implemented; falling back to mock.")
        _engine = None
        _mode = "unloaded"
    except Exception:
        logger.exception("Failed to load YOLO model; falling back to mock.")
        _engine = None
        _mode = "error"

# If no engine loaded, use mock
if _engine is None:
    try:
        _mock = import_module("vision.mock")
        _engine = _mock
        _mode = "mock"
    except Exception:
        logger.exception("Failed to import vision.mock; vision unavailable.")
        _engine = None
        _mode = "unavailable"

def is_ready():
    """
    Returns True when the vision engine is ready to perform inference.
    """
    if _engine is None:
        return False
    try:
        return bool(getattr(_engine, "is_ready", lambda: True)())
    except Exception:
        logger.exception("vision.is_ready() raised")
        return False

def infer(image):
    """
    Run inference via the loaded engine. Returns engine-specific structure.
    """
    if _engine is None:
        raise RuntimeError("Vision engine not available")
    return getattr(_engine, "infer", lambda img: {"detections": []})(image)
