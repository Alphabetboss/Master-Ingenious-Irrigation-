"""
Main Flask application for the Ingenious Irrigation dashboard.

This module exposes a small HTTP API for the frontend dashboard as well as
chat endpoints for interacting with the Astra assistant.  It unifies schedule
management, persona handling, LLM integration (with a graceful fallback to a
local intent engine), and static/HTML serving into a single, cohesive script.

The app is designed to be robust: every route returns a JSON response even
on unexpected errors, and chat endpoints never block indefinitely.  If an
external large‑language model (LLM) is configured via the environment it will
be used to generate rich responses; otherwise Astra falls back to a rule‑
based reply that covers common irrigation requests.

Environment variables:
    OPENAI_API_KEY  (optional) – API key for OpenAI; if provided the app will
        attempt to call the ChatCompletion API.  A short timeout is enforced
        to avoid blocking the UI.  On failure, the local intent engine is used.

You can extend or replace the `generate_astra_reply` function to integrate
with any other LLM or backend of your choice.
"""

from __future__ import annotations

import base64
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, render_template, request, send_from_directory

try:
    # Optional: if openai is installed and an API key is set in the environment,
    # the app will attempt to call the API for richer responses.
    import openai  # type: ignore
except ImportError:
    openai = None  # type: ignore

# Import persona definitions and prompt builder.  If this file is missing,
# the app will raise at startup.  See astra_persona.py for details.
from astra_persona import SYSTEM_PROMPT, WELCOME, build_astra_prompt

ROOT: Path = Path(__file__).parent
STATIC: Path = ROOT / "static"
TEMPLATES: Path = ROOT / "templates"
DATA: Path = ROOT / "data"
DATA.mkdir(exist_ok=True)

# Schedule persistence
SCHEDULE_JSON: Path = DATA / "schedule.json"
DEFAULT_SCHEDULE = {"zones": {"1": {"minutes": 10, "enabled": True}}}

app = Flask(__name__, static_folder=str(STATIC), template_folder=str(TEMPLATES))
app.config["TEMPLATES_AUTO_RELOAD"] = True
 }

DEFAULT_SCHEDULE = {
    "zones": {
        "1": {"minutes": 10, "enabled": True},
        "2": {"minutes": 10, "enabled": True},
        "3": {"minutes": 10, "enabled": True},
        "4": {"minutes": 10, "enabled": True},
        "5": {"minutes": 10, "enabled": True},
        "6": {"minutes": 10, "enabled": True},
    }


def load_schedule() -> dict:
    """Return the current schedule dictionary, creating a default if missing."""
    if not SCHEDULE_JSON.exists():
        SCHEDULE_JSON.write_text(json.dumps(DEFAULT_SCHEDULE, indent=2), encoding="utf-8")
    try:
        return json.loads(SCHEDULE_JSON.read_text(encoding="utf-8"))
    except Exception:
        # If the file is corrupt, reset to default to ensure the API still works.
        SCHEDULE_JSON.write_text(json.dumps(DEFAULT_SCHEDULE, indent=2), encoding="utf-8")
        return DEFAULT_SCHEDULE.copy()


def save_schedule(d: dict) -> None:
    """Persist the given schedule dictionary to disk."""
    try:
        SCHEDULE_JSON.write_text(json.dumps(d, indent=2), encoding="utf-8")
    except Exception as e:
        # Log but do not crash; schedule updates should not kill the app.
        print("SCHEDULE SAVE ERROR:", e)


def local_astute_reply(user_text: str) -> str:
    """
    Fast offline fallback: simple intent engine so Astra feels conversational.

    This function tries to recognise common irrigation‑related commands and
    returns helpful responses.  It is intentionally limited in scope so that
    generic chat or domain‑outside questions prompt the user towards the
    assistant's core competencies.
    """
    t = (user_text or "").strip().lower()

    # Greeting or pleasantries.
    if re.search(r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", t):
        return ("Hi! I’m Astra.  I can set timers, start or stop watering, "
                "monitor for leaks, and adjust schedules.  What would you like to do?")

    # Start watering immediately.
    if any(kw in t for kw in ("start now", "run now", "water now", "start watering")):
        return "Starting zone 1 for 10 minutes.  Say “stop” if you want me to cut it short."

    # Stop watering.
    if any(kw in t for kw in ("stop", "cancel", "shut off")):
        return "Okay, watering stopped."

    # Ask about schedule or timer.
    if "schedule" in t or "timer" in t or "time" in t:
        data = load_schedule()
        # Compose a human‑friendly summary of the first zone.
        zones = data.get("zones", {})
        zone1 = zones.get("1", {"minutes": 10, "enabled": True})
        status = "enabled" if zone1.get("enabled", True) else "disabled"
        minutes = zone1.get("minutes", 10)
        return (f"Your default is zone 1 at 5:00 AM for {minutes} minutes, {status}.  "
                "You can ask me to change the zone, time, duration, or frequency.")

    # Leak detection concerns.
    if "leak" in t or "burst" in t or "broken" in t:
        return ("I’ll watch for pressure drops and standing water.  "
                "If I detect a leak, I’ll stop watering and alert you.")

    # Weather or rain checks.
    if any(kw in t for kw in ("weather", "rain", "forecast", "dry", "wet")):
        return ("If rain is expected or the soil looks wet, I’ll skip or reduce watering "
                "so we don’t waste water.")

    # Help request or capabilities.
    if "help" in t or "what can you do" in t or "capabilities" in t:
        return ("I can set watering schedules, start or stop zones, adjust durations, "
                "and avoid overwatering using basic checks.  "
                "Try: “Set zone 1 to 12 minutes every other day at 5:15 AM.”")

    # General questions outside the irrigation domain.
    if any(kw in t for kw in ("who", "what", "where", "when", "why")):
        return ("I’m an irrigation assistant and don’t have general knowledge yet.  "
                "Please ask me about watering schedules, plant health, or system status.")

    # Fallback: provide options to guide the user.
    return ("Got it.  Would you like me to start watering now, adjust the schedule, "
            "or check for issues?")


def generate_astra_reply(prompt: str, timeout: float = 6.0) -> str:
    """
    Generate a reply for Astra using an LLM if available, otherwise fall back.

    This tries to call the OpenAI ChatCompletion API if openai and an API key
    are available.  The call is wrapped in a thread with a timeout so that
    slow or failing API requests do not block the UI.  On any exception or
    timeout the local intent engine is used as a fallback.
    """
    # If openai is not installed or no key is set, immediately use local reply.
    api_key = os.environ.get("OPENAI_API_KEY") if openai else None
    if not api_key:
        return local_astute_reply(prompt)

    openai.api_key = api_key

    # Compose messages: system prompt plus user message.  The system prompt is
    # defined in astra_persona.py and instructs the model how to behave.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    # Use a thread to enforce a timeout; OpenAI client does not natively support it.
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            openai.ChatCompletion.create,
            model="gpt-4",
            messages=messages,
            temperature=0.2,
            max_tokens=256,
        )
        try:
            response = future.result(timeout=timeout)
            reply = response["choices"][0]["message"]["content"].strip()
            # Some models might prefix the assistant name; strip it if present.
            return re.sub(r"^\s*Astra[:,]?\s*", "", reply, flags=re.IGNORECASE)
        except TimeoutError:
            future.cancel()
            print("LLM call timed out; falling back to local reply.")
            return local_astute_reply(prompt)
        except Exception as e:
            print("LLM call failed; falling back to local reply.  Error:", e)
            return local_astute_reply(prompt)


def generate_tts_audio(text: str) -> bytes:
    """
    Placeholder text‑to‑speech converter.

    This function returns empty audio data as a stub.  Replace it with a real
    TTS implementation (e.g., pyttsx3, edge‑tts, or a cloud service) if you
    want to enable the /astra/speak endpoint to return audio.  The frontend
    expects base64‑encoded audio.
    """
    _ = text  # unused in stub
    return b""


@app.after_request
def _no_cache(resp):
    """
    Set cache‑control headers on HTML responses to force fresh loads from the
    server.  This prevents stale templates or JS from being served during
    development or after updates.
    """
    ct = resp.headers.get("Content-Type", "")
    if "text/html" in ct:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp


@app.route("/")
def dashboard():
    """Serve the main dashboard page."""
    return render_template("dashboard.html")


@app.get("/health")
def health():
    """Basic health‑check endpoint."""
    return jsonify({"ok": True})


@app.get("/api/schedule")
def api_get_schedule():
    """Return the current watering schedule."""
    return jsonify(load_schedule())


@app.post("/api/schedule/update")
def api_update_schedule():
    """
    Update the watering duration for a given zone.

    Expects JSON like {"zone": "1", "minutes": 12}.  If the zone does not
    exist it will be created.  Minutes less than zero are coerced to zero.
    """
    j = request.get_json(force=True, silent=True) or {}
    zone = str(j.get("zone", "1"))
    try:
        minutes = int(j.get("minutes", 10))
    except (TypeError, ValueError):
        minutes = 10
    minutes = max(0, minutes)

    data = load_schedule()
    data.setdefault("zones", {})
    data["zones"].setdefault(zone, {"minutes": 10, "enabled": True})
    data["zones"][zone]["minutes"] = minutes
    save_schedule(data)
    return jsonify({"ok": True, "zone": zone, "minutes": minutes})


@app.post("/astra/chat")
def astra_chat():
    """
    Chat endpoint for Astra using the persona prompt builder.

    The client should send JSON like {"message": "..."} and will receive
    {"reply": "..."} in response.  On blank input a polite prompt is returned.
    """
    payload = request.get_json(silent=True) or {}
    user_msg: str = (payload.get("message") or "").strip()
    if not user_msg:
        return jsonify({"reply": "Tell me what you’d like me to do—for example, “start watering now.”"})

    prompt = build_astra_prompt(user_msg, telemetry=None)
    reply = generate_astra_reply(prompt)
    return jsonify({"reply": reply})


@app.get("/astra/speak")
def astra_speak():
    """
    Basic voice endpoint.

    Returns a base64‑encoded representation of speech audio for the welcome
    message.  Replace generate_tts_audio with a real TTS implementation to
    enable audio responses.
    """
    # Use the global WELCOME from astra_persona
    audio_bytes = generate_tts_audio(WELCOME)
    encoded = base64.b64encode(audio_bytes).decode("utf-8")
    return jsonify({"audio": encoded})


@app.post("/chat")
def chat():
    """
    Generic chat endpoint.

    This route bypasses the persona prompt builder and sends the raw user text
    directly to the LLM.  If you want all queries to be scoped by Astra’s
    persona, use /astra/chat instead.  Blank inputs return a friendly
    instructional reply.
    """
    payload = request.get_json(silent=True) or {}
    user_text: str = (payload.get("message") or "").strip()
    if not user_text:
        return jsonify({"reply": "Tell me what you’d like me to do—for example, “start watering now.”"})

    # Without the persona builder we still use the same LLM call but with
    # user_text as the prompt.  This means general queries can be handled
    # (assuming the external model is sufficiently capable).
    reply = generate_astra_reply(user_text)
    return jsonify({"reply": reply})


@app.get("/favicon.ico")
def favicon():
    """
    Serve a favicon from the static directory if it exists.  Return no content
    otherwise.  Browsers will still display a blank icon rather than a 404.
    """
    try:
        fav_path = STATIC / "favicon.ico"
        if fav_path.exists():
            return send_from_directory(str(STATIC), "favicon.ico")
    except Exception:
        pass
    return ("", 204)


if __name__ == "__main__":
    # Bind to all interfaces on port 5051.  In production you might run under
    # gunicorn or uwsgi instead of Flask's built‑in server.
    port = int(os.environ.get("PORT", "5051"))
    app.run(host="0.0.0.0", port=port, debug=True)
