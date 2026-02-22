import time
from typing import Any, Dict


def activate_zone(zone_id: int | str, duration: float) -> Dict[str, Any]:
    print(f"[GPIO] Activating zone {zone_id} for {duration} seconds...")
    time.sleep(max(0.0, float(duration)))
    print(f"[GPIO] Zone {zone_id} watering complete.")
    return {"zone_id": zone_id, "duration": float(duration), "status": "simulated"}
