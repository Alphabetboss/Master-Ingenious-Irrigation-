from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

DATA = Path(__file__).resolve().parent / "data"
DATA.mkdir(exist_ok=True)
CACHE = DATA / "weather_cache.json"


def get_weather() -> Dict[str, Any]:
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"source": "stub", "temp_f": 78.0, "humidity": 0.55, "rain_in_last_24h": 0.0}
