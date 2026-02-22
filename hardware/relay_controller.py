from __future__ import annotations
import os
import time
from typing import Dict, Any

try:
    import RPi.GPIO as GPIO
    _HAS_GPIO = True
except Exception:
    _HAS_GPIO = False

RELAY_PIN = int(os.getenv("II_RELAY_PIN", "17"))


def setup() -> bool:
    if _HAS_GPIO:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
    return _HAS_GPIO


def water_for(seconds: float = 10.0) -> Dict[str, Any]:
    seconds = float(seconds)
    if _HAS_GPIO:
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        time.sleep(max(0.0, seconds))
        GPIO.output(RELAY_PIN, GPIO.LOW)
        return {"status": "ok", "pin": RELAY_PIN, "seconds": seconds, "gpio": True}
    else:
        time.sleep(min(0.1, max(0.0, seconds)))
        return {"status": "simulated", "pin": RELAY_PIN, "seconds": seconds, "gpio": False}
