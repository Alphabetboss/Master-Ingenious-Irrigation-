from __future__ import annotations
import sys
import hashlib
import json
from typing import Any, Dict

import requests


def run_zone(host: str, pw_plain: str, zone: int, seconds: int) -> Dict[str, Any]:
    pw_md5 = hashlib.md5(pw_plain.encode()).hexdigest().lower()
    base = f"http://{host}"

    try:
        ja = requests.get(f"{base}/ja", params={"pw": pw_md5}, timeout=5).json()
        nstations = ja.get("nstations") or len(ja.get("stations", {}).get("sn", [])) or 16
    except Exception:
        nstations = 16

    if zone >= nstations:
        raise ValueError(f"Zone {zone} out of range (nstations={nstations})")

    dur = [0] * nstations
    dur[zone] = int(seconds)

    r = requests.get(f"{base}/cr", params={"pw": pw_md5, "t": json.dumps(dur)}, timeout=5)
    return {"status_code": r.status_code, "text": r.text, "nstations": nstations}


if __name__ == "__main__":
    host = sys.argv[1]
    pw_plain = sys.argv[2]
    zone = int(sys.argv[3])
    seconds = int(sys.argv[4])
    res = run_zone(host, pw_plain, zone, seconds)
    print("HTTP", res["status_code"], res["text"])
