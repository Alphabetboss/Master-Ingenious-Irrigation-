import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

DATA_DIR = ROOT_DIR / "data"
MODELS_DIR = ROOT_DIR / "models"
LOGS_DIR = ROOT_DIR / "data"  # reuse data for logs in MVP

DATA_DIR.mkdir(exist_ok=True)
MODELS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

MODEL_PATH = MODELS_DIR / "yolov8n.pt"

SCHEDULE_FILE = DATA_DIR / "schedule.json"
STATUS_FILE = DATA_DIR / "status.json"
WATERING_LOG = DATA_DIR / "watering.log"

# Placeholder for future keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
