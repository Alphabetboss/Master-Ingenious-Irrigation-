from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any
import json
import time


@dataclass
class Inputs:
    # sensors
    soil_moisture_pct: Optional[float] = None   # 0..100 (% VWC or scaled)
    ambient_temp_f: Optional[float] = None
    humidity_pct: Optional[float] = None
    # weather
    rain_24h_in: float = 0.0
    rain_72h_in: float = 0.0
    forecast_rain_24h_in: float = 0.0
    # vision
    greenness_score: Optional[float] = None     # 0..1
    dry_flag: bool = False
    water_flag: bool = False


@dataclass
class HydrationResult:
    need_score: float            # 0..10; lower = needs more water
    advisory: str
    factors: Dict[str, Any]


class HydrationEngine:
    """
    Combines sensors + weather + health AI into a 0..10 inverted scale:
      0 = very dry (water more)
      5 = ok/normal
      10 = oversaturated (skip)
    """

    def __init__(self, cache_file: str = "data/hydration_cache.json") -> None:
        self.cache_path = Path(cache_file)

    # ----------------- persistence -----------------
    def _save(self, payload: Dict[str, Any]) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _load(self) -> Dict[str, Any]:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    # ----------------- core logic -----------------
    def compute(self, inp: Inputs) -> HydrationResult:
        # Start from neutral
        score = 5.0
        reasons = []

        # 1) Soil moisture dominates if present
        if inp.soil_moisture_pct is not None:
            sm = max(0.0, min(100.0, inp.soil_moisture_pct))
            if sm < 20:
                score -= 3.0
                reasons.append("very low soil moisture")
            elif sm < 25:
                score -= 2.0
                reasons.append("low soil moisture")
            elif sm > 55:
                score += 3.0
                reasons.append("very high soil moisture")
            elif sm > 45:
                score += 2.0
                reasons.append("high soil moisture")

        # 2) Weather rain history/forecast (Houston: 1–1.5 in/week target)
        rain_recent = inp.rain_72h_in
        rain_soon = inp.forecast_rain_24h_in
        if rain_recent >= 0.75:
            score += 1.0
            reasons.append("recent heavy rain")
        if rain_recent >= 1.25:
            score += 2.0
        if rain_soon >= 0.25:
            score += 1.0
            reasons.append("rain forecast soon")
        if rain_soon >= 0.75:
            score += 2.0

        # 3) Temperature & humidity
        if inp.ambient_temp_f is not None:
            if inp.ambient_temp_f >= 93:
                score -= 1.0
                reasons.append("very hot (>=93°F)")
            if inp.ambient_temp_f >= 100:
                score -= 0.5
        if inp.humidity_pct is not None and inp.humidity_pct >= 85 and (inp.ambient_temp_f or 0) >= 80:
            score += 0.3
            reasons.append("very humid (reduced evap)")

        # 4) Vision: greenness & flags
        if inp.greenness_score is not None:
            score += (inp.greenness_score - 0.5) * 1.5
        if inp.dry_flag:
            score -= 1.0
            reasons.append("dry/brown patches detected")
        if inp.water_flag:
            score += 2.0
            reasons.append("standing water detected")

        # Clamp
        score = max(0.0, min(10.0, score))

        # Advisory
        if score <= 2.5:
            advisory = "Very dry → increase runtime today."
        elif score <= 4.0:
            advisory = "A bit dry → run normal or +25%."
        elif score <= 6.0:
            advisory = "Optimal → run normal schedule."
        elif score <= 8.0:
            advisory = "Moist → consider -25% or skip if cool."
        else:
            advisory = "Oversaturated → skip watering."

        payload = {
            "ts": int(time.time()),
            "score": score,
            "advisory": advisory,
            "factors": {
                "soil_moisture_pct": inp.soil_moisture_pct,
                "ambient_temp_f": inp.ambient_temp_f,
                "humidity_pct": inp.humidity_pct,
                "rain_24h_in": inp.rain_24h_in,
                "rain_72h_in": inp.rain_72h_in,
                "forecast_rain_24h_in": inp.forecast_rain_24h_in,
                "greenness_score": inp.greenness_score,
                "dry_flag": inp.dry_flag,
                "water_flag": inp.water_flag,
                "reasons": reasons,
            },
        }
        self._save(payload)
        return HydrationResult(score, advisory, payload["factors"])
