# hardware/real.py
"""
Minimal safe hardware stub for production hardware driver.
Replace internals with actual GPIO/relay control for your platform.
This file intentionally avoids direct hardware access so it can be
committed and used as a placeholder.
"""

import time
import logging

logger = logging.getLogger(__name__)

# internal state mirror for safety
_state = {
    "zones": {},
    "flow": 0.0
}

def open_valve(zone_id, duration_seconds=None):
    """
    Open a valve for a zone. In this stub we only log and update internal state.
    Replace with actual hardware control (GPIO/relay) in production.
    """
    logger.info("REAL-HW STUB open_valve called for zone=%s duration=%s", zone_id, duration_seconds)
    _state["zones"][zone_id] = {"open": True, "since": time.time(), "duration": duration_seconds}
    # Return a consistent structure like the mock
    return {"zone": zone_id, "action": "opened", "duration": duration_seconds, "note": "stub"}

def close_valve(zone_id):
    logger.info("REAL-HW STUB close_valve called for zone=%s", zone_id)
    _state["zones"][zone_id] = {"open": False, "since": time.time(), "duration": 0}
    return {"zone": zone_id, "action": "closed", "note": "stub"}

def read_flow():
    """
    Read flow sensor. Replace with actual sensor read.
    Returns a dict with flow_lpm key for compatibility.
    """
    # Provide a safe deterministic value until real sensor is wired
    return {"flow_lpm": _state.get("flow", 0.0)}

def health():
    """
    Health check for hardware. In the real implementation, verify GPIO access,
    sensor connectivity, and relay status. Here we return a conservative status.
    """
    try:
        # Basic sanity check: ensure we can access internal state
        _ = _state.get("zones", None)
        return {"ok": True, "mode": "real_stub"}
    except Exception as e:
        logger.exception("Hardware health check failed: %s", e)
        return {"ok": False, "error": str(e)}
