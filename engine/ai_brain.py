# engine/ai_brain.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class SignalPacket:
    soil: float = 0.4              # 0.0..1.0 (lower = drier)
    tempF: float = 85.0
    rain_mm_24h: float = 0.0
    ai_flags: Dict[str, Any] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SignalPacket":
        return cls(
            soil=float(d.get("soil", 0.4)),
            tempF=float(d.get("tempF", 85.0)),
            rain_mm_24h=float(d.get("rain_mm_24h", 0.0)),
            ai_flags=d.get("ai_flags") or {},
        )


def decide_minutes_from_signals(base_minutes: int, s: Dict[str, Any]) -> int:
    """
    Legacy rule-based watering adjustment.
    Signals expected shape:
      {"soil": 0.0..1.0, "tempF": 75, "rain_mm_24h": 0, "ai_flags":{"standing_water":False,"very_dry":False}}
    """
    pkt = SignalPacket.from_dict(s)
    flags = pkt.ai_flags or {}

    # Reduce or skip if recent rain / standing water
    if flags.get("standing_water") or pkt.rain_mm_24h >= 8:  # ~8 mm ≈ 0.3 in
        return 0

    minutes = float(base_minutes)

    # Hot boost
    if pkt.tempF >= 93:
        minutes += 6
    elif pkt.tempF >= 88:
        minutes += 3

    # Soil dryness boost/cut
    if pkt.soil <= 0.25:
        minutes += 6
    elif pkt.soil <= 0.35:
        minutes += 3
    elif pkt.soil >= 0.70:
        minutes -= 5

    # Gentle cut if any rain
    if 2 <= pkt.rain_mm_24h < 8:
        minutes = max(0.0, minutes - 5)

    return max(0, min(int(minutes), 45))
