# hardware/mock.py
import time

_mock_state = {
    "zones": {},
    "flow": 0.0
}

def open_valve(zone_id, duration_seconds=None):
    _mock_state["zones"][zone_id] = {
        "open": True,
        "since": time.time(),
        "duration": duration_seconds
    }
    return {"zone": zone_id, "action": "opened", "duration": duration_seconds}

def close_valve(zone_id):
    _mock_state["zones"][zone_id] = {
        "open": False,
        "since": time.time(),
        "duration": 0
    }
    return {"zone": zone_id, "action": "closed"}

def read_flow():
    # deterministic mock flow value
    return {"flow_lpm": 0.0}

def health():
    # simple health check for mock
    return {"ok": True, "mode": "mock"}
