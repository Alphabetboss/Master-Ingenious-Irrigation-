import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any

from config import SCHEDULE_FILE, STATUS_FILE, WATERING_LOG


@dataclass
class ZoneConfig:
    minutes: int = 10
    enabled: bool = True


DEFAULT_SCHEDULE = {
    "zones": {
        "1": asdict(ZoneConfig())
    }
}


def _load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return default.copy()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default.copy()


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_schedule() -> Dict[str, Any]:
    return _load_json(SCHEDULE_FILE, DEFAULT_SCHEDULE)


def set_zone_duration(zone: int, minutes: int) -> Dict[str, Any]:
    data = get_schedule()
    zones = data.setdefault("zones", {})
    z = zones.setdefault(str(zone), {})
    z["minutes"] = int(minutes)
    z.setdefault("enabled", True)
    _save_json(SCHEDULE_FILE, data)
    return data


def _log_watering(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {msg}\n"
    try:
        with open(WATERING_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def start_watering(zone: int, minutes: int | None = None) -> None:
    status = {
        "watering": True,
        "zone": zone,
        "since": time.time(),
        "minutes": minutes,
    }
    _save_json(STATUS_FILE, status)
    _log_watering(f"START zone={zone} minutes={minutes}")


def stop_watering() -> None:
    status = {
        "watering": False,
        "zone": None,
        "since": None,
        "minutes": None,
    }
    _save_json(STATUS_FILE, status)
    _log_watering("STOP")


def get_status() -> Dict[str, Any]:
    default = {
        "watering": False,
        "zone": None,
        "since": None,
        "minutes": None,
    }
    return _load_json(STATUS_FILE, default)


def build_plan_for_today(score: float | None = None) -> Dict[str, Any]:
    # MVP: just return current schedule; hook AI here later
    return get_schedule()


def mark_ran_today() -> None:
    # MVP: no-op; later you can track last_run date
    pass
