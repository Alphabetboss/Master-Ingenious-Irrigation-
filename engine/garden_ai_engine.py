# engine/garden_ai_engine.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any

import time

from hydration.hydration_engine import HydrationEngine, Inputs as HydrationInputs, HydrationResult
from vision.health_evaluator import HealthEvaluator, HealthResult
from weather.weather_client import get_weather
from safety.burst_guard import BurstGuard


@dataclass
class ZoneContext:
    """Static-ish info about a zone."""
    zone_id: str
    name: Optional[str] = None
    camera_image_path: Optional[str] = None  # latest frame path if available


@dataclass
class ZoneEvaluation:
    """Unified view of a zone's state and recommendation."""
    zone_id: str
    hydration: HydrationResult
    health: HealthResult
    weather: Dict[str, Any]
    safety_triggered: bool
    safety_reason: str
    raw: Dict[str, Any]


class GardenAIEngine:
    """
    Unified brain that fuses:
      - Vision (HealthEvaluator)
      - Weather (weather_client)
      - Sensors (soil moisture, temp, humidity)
      - HydrationEngine (0..10 need score)
      - Safety (BurstGuard, optional)
    It does NOT directly toggle hardware; it decides and reports.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        hydration_cache_file: str = "data/hydration_cache.json",
        burst_guard: Optional[BurstGuard] = None,
    ) -> None:
        # Vision / health
        self.health_evaluator = HealthEvaluator(model_path=model_path)

        # Hydration scoring
        self.hydration_engine = HydrationEngine(cache_file=hydration_cache_file)

        # Optional safety layer
        self.burst_guard = burst_guard

    # ------------------------------------------------------------------ #
    # Core evaluation
    # ------------------------------------------------------------------ #
    def evaluate_zone(
        self,
        zone: ZoneContext,
        *,
        soil_moisture_pct: Optional[float] = None,
        ambient_temp_f: Optional[float] = None,
        humidity_pct: Optional[float] = None,
        rain_24h_in: Optional[float] = None,
        rain_72h_in: Optional[float] = None,
        forecast_rain_24h_in: Optional[float] = None,
    ) -> ZoneEvaluation:
        """
        Evaluate a single zone by fusing:
          - latest camera image (if provided)
          - weather (from weather_client + overrides)
          - sensor inputs
        Returns a ZoneEvaluation with hydration + health + safety.
        """

        # 1) Vision / health
        if zone.camera_image_path:
            health = self.health_evaluator.evaluate_image(zone.camera_image_path)
        else:
            # Neutral health if no image
            health = HealthResult(
                greenness_score=0.5,
                water_flag=False,
                dry_flag=False,
                raw={"error": "no image path provided", "method": "neutral"},
            )

        # 2) Weather
        weather = get_weather() or {}
        # Normalize weather keys from your weather_client stub:
        # { 'temp_f': 78.0, 'humidity': 0.55, 'rain_in_last_24h': 0.0 }
        temp_f = ambient_temp_f if ambient_temp_f is not None else weather.get("temp_f")
        hum_pct = humidity_pct if humidity_pct is not None else (
            weather.get("humidity") * 100.0 if isinstance(weather.get("humidity"), (int, float)) else None
        )

        # Rain inputs: prefer explicit overrides, else derive from weather if present
        r24 = rain_24h_in if rain_24h_in is not None else weather.get("rain_in_last_24h", 0.0)
        # For now, we don't have 72h or forecast in weather_client stub; caller can pass them
        r72 = rain_72h_in or 0.0
        r_fore = forecast_rain_24h_in or 0.0

        # 3) Build HydrationEngine inputs
        h_inp = HydrationInputs(
            soil_moisture_pct=soil_moisture_pct,
            ambient_temp_f=temp_f,
            humidity_pct=hum_pct,
            rain_24h_in=r24,
            rain_72h_in=r72,
            forecast_rain_24h_in=r_fore,
            greenness_score=health.greenness_score,
            dry_flag=health.dry_flag,
            water_flag=health.water_flag,
        )

        hydration = self.hydration_engine.compute(h_inp)

        # 4) Safety check (if BurstGuard is wired in)
        safety_triggered = False
        safety_reason = ""
        if self.burst_guard is not None:
            should_stop, reason = self.burst_guard.check()
            safety_triggered = bool(should_stop)
            safety_reason = reason or ""

        # 5) Assemble unified result
        raw = {
            "zone": {
                "zone_id": zone.zone_id,
                "name": zone.name,
                "camera_image_path": zone.camera_image_path,
            },
            "hydration_factors": hydration.factors,
            "health_raw": health.raw,
            "weather_raw": weather,
            "ts": int(time.time()),
        }

        return ZoneEvaluation(
            zone_id=zone.zone_id,
            hydration=hydration,
            health=health,
            weather=weather,
            safety_triggered=safety_triggered,
            safety_reason=safety_reason,
            raw=raw,
        )
