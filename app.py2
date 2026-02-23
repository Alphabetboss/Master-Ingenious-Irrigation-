# Removed duplicate minimal loader; main application with schedule API is defined below.
# app.py — UI + basic schedule API so the dashboard stays "online"
from flask import Flask, request, jsonify
from astra_assistant import AstraAssistant, WELCOME_MESSAGE
from pathlib import Path
import json
from flask import Flask, render_template, send_from_directory, request, jsonify
import re
from flask import request, jsonify
ROOT = Path(__file__).parent
TPL  = ROOT / "templates"
STATIC = ROOT / "static"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

import base64
from flask import Flask, render_template, request, jsonify
from astra_persona import build_astra_prompt

app = Flask(__name__)

# TODO: wire these to your actual LLM + TTS
def generate_astra_reply(prompt: str) -> str:
    # Replace with your real LLM call
    # For now, a stub:
    return "I hear you, Austin. The garden is listening too."

def generate_tts_audio(text: str) -> bytes:
    # Replace with your real TTS engine
    # Must return raw audio bytes (e.g., WAV)
    return b""  # placeholder


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.post("/astra/chat")
def astra_chat():
    data = request.get_json(force=True)
    user_msg = data.get("message", "").strip() or "Say hello, Astra."
    # You can pass real telemetry here if you have it
    prompt = build_astra_prompt(user_msg, telemetry=None)
    reply = generate_astra_reply(prompt)
    return jsonify({"reply": reply})


@app.get("/astra/speak")
def astra_speak():
    # Simple greeting for now; you can later reuse the chat reply text
    text = "Hello Austin. Astra online. The soil hums, and your garden is ready to grow."
    audio_bytes = generate_tts_audio(text)
    encoded = base64.b64encode(audio_bytes).decode("utf-8")
    return jsonify({"audio": encoded})
SCHEDULE_JSON = DATA / "schedule.json"
DEFAULT_SCHEDULE = {"zones": {"1": {"minutes": 10, "enabled": True}}}
# Create a single assistant instance (optionally pass an OpenAI API key)
astra = AstraAssistant(llm_api_key="YOUR-OPENAI-KEY-HERE")

@app.get("/astra/hello")
def astra_hello() -> Any:
    """
    Simple GET endpoint for initial handshake with Astra.
    """
    return jsonify({"reply": WELCOME_MESSAGE})

@app.post("/astra/speak")
def astra_speak() -> Any:
    """
    POST endpoint for chatting with Astra. Expects JSON {"text": "..."}.
    Returns JSON {"reply": "..."}.
    """
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()

    if not user_text:
        return jsonify({"reply": "Please send a non-empty message."}), 400

    # Delegate to the assistant
    reply = astra.respond(user_text)
    return jsonify({"reply": reply})

# ... other routes and app setup ...

def load_schedule():
    if not SCHEDULE_JSON.exists():
        SCHEDULE_JSON.write_text(json.dumps(DEFAULT_SCHEDULE, indent=2), encoding="utf-8")
    return json.loads(SCHEDULE_JSON.read_text(encoding="utf-8"))

def save_schedule(d):
    SCHEDULE_JSON.write_text(json.dumps(d, indent=2), encoding="utf-8")

# --- Add near your other imports ---
import re
from flask import request, jsonify

# --- Put this helper anywhere in app.py ---
def local_astute_reply(user_text: str) -> str:
    """Fast offline fallback: simple intent engine so Astra feels conversational."""
    t = user_text.strip().lower()

    # greetings
    if re.search(r"\b(hi|hello|hey|good (morning|afternoon|evening))\b", t):
        return "Hi! I’m Astra. I can set timers, start/stop watering, and keep an eye out for leaks. What would you like to do?"

    # quick intents
    if "start now" in t or "run now" in t or "water now" in t:
        # TODO: hook your real start function here
        return "Starting zone 1 for 10 minutes. Say “stop” if you want me to cut it short."

    if "stop" in t or "cancel" in t:
        # TODO: hook your real stop function here
        return "Okay, watering stopped."

    if "schedule" in t or "timer" in t:
        return "Your default is zone 1 at 5:00 AM for 10 minutes, daily. Want to change zone, time, duration, or frequency?"

    if "leak" in t or "burst" in t:
        return "I’ll watch for pressure drops and standing water. If I detect a leak, I’ll stop watering and alert you."

    if "weather" in t or "rain" in t or "forecast" in t:
        return "If rain is expected or soil looks wet, I’ll skip or reduce watering so we don’t waste water."

    if "help" in t or "what can you do" in t:
        return ("I can set watering schedules, start/stop zones, adjust duration, and avoid overwatering using basic checks. "
                "Try: “Set zone 1 to 12 minutes every other day at 5:15 AM.”")

    # default
    return "Got it. Do you want me to start watering now, adjust the schedule, or check for issues?"

# --- Replace your existing /chat with this robust version ---
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.post("/chat")
def chat():
    """
    Fast, never-hang chat endpoint.
    If you have an external LLM later, call it with a short timeout.
    Always returns JSON {reply: "..."} so the UI never sticks on 'Thinking...'.
    """
    try:
        payload = request.get_json(silent=True) or {}
        user_text = (payload.get("message") or "").strip()
        if not user_text:
            return jsonify({"reply": "Tell me what you’d like me to do—for example, “start watering now.”"}), 200

        # TODO: If you wire in an external model, call it here with a small timeout.
        # If it fails, fall back to local_astute_reply.
        reply = local_astute_reply(user_text)
        return jsonify({"reply": reply}), 200

    except Exception as e:
        # Never hang: log and return a friendly fallback
        print("CHAT ERROR:", repr(e))
        # Always return a JSON response so the route never returns None
        return jsonify({"reply": "Sorry, something went wrong. Please try again."}), 200
# app already created above before route definitions

@app.after_request
def _no_cache(resp):
    ct = resp.headers.get("Content-Type", "")
    if "text/html" in ct:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
    return resp

@app.get("/")
def dashboard():
    return render_template("dashboard.html")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/schedule")
def api_get_schedule():
    return jsonify(load_schedule())

@app.post("/api/schedule/update")
def api_update_schedule():
    j = request.get_json(force=True, silent=True) or {}
    zone = str(j.get("zone", 1))
    minutes = max(0, int(j.get("minutes", 10)))
    data = load_schedule()
    data.setdefault("zones", {})
    data["zones"].setdefault(zone, {"minutes": 10, "enabled": True})
    data["zones"][zone]["minutes"] = minutes
    save_schedule(data)
    return jsonify({"ok": True, "zone": zone, "minutes": minutes})

@app.get("/favicon.ico")
def favicon():
    # Serve a favicon if it exists in the static directory, otherwise return no content.
    try:
        fav_path = STATIC / "favicon.ico"
        if fav_path.exists():
            return send_from_directory(str(STATIC), "favicon.ico")
    except Exception:
        # If anything goes wrong, fall through to returning no content to avoid errors.
        pass
    return ("", 204)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5051, debug=True)
