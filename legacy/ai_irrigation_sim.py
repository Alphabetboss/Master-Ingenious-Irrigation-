from __future__ import annotations
from datetime import datetime
import random
from typing import Dict, Any

import numpy as np
import cv2

# ---------------- Configuration ----------------
BASE_WATERING_TIME_MIN = 10  # minutes
ZONE_COUNT = 3


# ---------------- Simulated Sensors ----------------
def simulate_image() -> np.ndarray:
    base_color = random.randint(50, 200)  # darker = less healthy
    return np.full((480, 640, 3), (base_color, base_color + 30, base_color), dtype=np.uint8)


def simulate_humidity() -> float:
    return random.uniform(30, 90)  # %


def simulate_pressure() -> float:
    return random.uniform(0.1, 1.0)  # bar


def simulate_weather_forecast() -> str:
    return random.choice(["Clear", "Rain", "Clouds", "Thunderstorm"])


# ---------------- Hydration Score Logic ----------------
def calculate_greenness_score(image: np.ndarray) -> float:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 40, 40])
    upper_green = np.array([85, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)
    green_ratio = np.sum(mask) / (mask.shape[0] * mask.shape[1] * 255)
    hydration_score = round((1.0 - green_ratio) * 10, 2)
    return float(min(max(hydration_score, 0.0), 10.0))


def adjust_watering_time(base_time_min: int, hydration_score: float) -> int:
    if hydration_score == 5:
        return base_time_min
    elif hydration_score < 5:
        return base_time_min + int((5 - hydration_score) * 2)  # up to +10 mins
    else:
        return max(0, base_time_min - int((hydration_score - 5) * 2))


# ---------------- Emergency Detection ----------------
def detect_emergency(pressure: float, image: np.ndarray) -> str | None:
    if pressure < 0.2:
        return "Possible pipe burst (low pressure)"
    muddy_score = calculate_greenness_score(image)
    if muddy_score >= 9.5:
        return "Possible flood or overwatering detected"
    return None


# ---------------- Simulation Runner ----------------
def run_irrigation_ai() -> None:
    now = datetime.now()
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] Starting AI Irrigation Simulation\n")
    print("Weather forecast:", simulate_weather_forecast())

    for zone in range(ZONE_COUNT):
        zone_id = zone + 1
        print(f"\n🌱 Zone {zone_id}")

        image = simulate_image()
        hydration_score = calculate_greenness_score(image)
        humidity = simulate_humidity()
        pressure = simulate_pressure()

        print(f"Hydration Score: {hydration_score}/10")
        print(f"Humidity: {round(humidity)}%")
        print(f"Pressure: {round(pressure, 2)} bar")

        emergency = detect_emergency(pressure, image)
        if emergency:
            print(f"🚨 EMERGENCY: {emergency}")
            continue

        watering_time = adjust_watering_time(BASE_WATERING_TIME_MIN, hydration_score)
        if watering_time == 0:
            print("💧 Action: Skipping watering (too wet)")
        else:
            print(f"💧 Action: Watering for {watering_time} minutes")


if __name__ == "__main__":
    run_irrigation_ai()
