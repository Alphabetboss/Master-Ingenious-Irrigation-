"""
Offline voice assistant for the Ingenious Irrigation system.

This module combines speech recognition, a local language model, and
text‑to‑speech synthesis into a simple command‑line loop.  It records
audio from the user's microphone, transcribes it using the Vosk
speech‑to‑text engine, generates a response via a local LLM (using
``llm_client.local_chat``) with a fallback intent engine, and speaks
the reply aloud using ``pyttsx3``.

Before running this script, make sure you have installed the following
dependencies in your Python environment:

    pip install sounddevice vosk pyttsx3

You will also need to download a Vosk model (e.g. the "vosk‑model‑small‑en‑us")
and set ``VOSK_MODEL_PATH`` to point to the directory containing ``model"
files.  For better transcription accuracy, choose a model appropriate
for your language and microphone quality.
"""

import json
import queue
import time
from pathlib import Path
from typing import Optional

import numpy as np  # type: ignore
import sounddevice as sd  # type: ignore
from vosk import Model, KaldiRecognizer  # type: ignore
import pyttsx3

from llm_client import local_chat, LLMError  # type: ignore

################################################################################
# Configuration
################################################################################

# Index of the microphone device to use.  Set to ``None`` to use the
# system default input device.  You can run ``python -c 'import sounddevice; print(sounddevice.query_devices())'``
# in your environment to list available devices and choose the appropriate index.
DEVICE_INDEX: Optional[int] = None

# The sample rate Vosk was trained on.  Do not change this unless you know
# exactly what you are doing.  Vosk models typically expect 16000 Hz.
MODEL_SAMPLE_RATE: int = 16000

# Path to your Vosk model directory.  You must download a model and unpack
# it somewhere accessible.  See https://alphacephei.com/vosk/models for
# available models.
VOSK_MODEL_PATH: str = "models/vosk-model-small-en-us-0.15"

################################################################################
# Fallback intent engine
################################################################################

def _fallback_reply(user_text: str) -> str:
    """Return a simple, intent‑driven reply for common irrigation queries.

    This helper provides a deterministic response when the local LLM is
    unavailable.  You can extend or modify these patterns to cover
    additional intents specific to your application domain.
    """
    t = user_text.strip().lower()
    if not t:
        return "Please say something so I can help you."
    # Greetings
    if any(greet in t for greet in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]):
        return ("Hello! I’m Astra. I can set timers, start or stop watering, and "
                "keep an eye out for leaks. What would you like to do?")
    # Start watering
    if any(kw in t for kw in ["start now", "run now", "water now"]):
        return "Starting zone 1 for 10 minutes. Say \"stop\" if you want me to cut it short."
    # Stop watering
    if any(kw in t for kw in ["stop", "cancel"]):
        return "Okay, watering stopped."
    # Scheduling
    if "schedule" in t or "timer" in t:
        return ("Your default is zone 1 at 5:00 AM for 10 minutes, daily. "
                "Would you like to change the zone, time, duration, or frequency?")
    # Leak detection
    if any(kw in t for kw in ["leak", "burst"]):
        return ("I’ll watch for pressure drops and standing water. "
                "If I detect a leak, I’ll stop watering and alert you.")
    # Weather
    if any(kw in t for kw in ["weather", "rain", "forecast"]):
        return ("If rain is expected or the soil looks wet, I’ll skip or reduce watering "
                "so we don’t waste water.")
    # Help
    if "help" in t or "what can you do" in t:
        return ("I can set watering schedules, start or stop zones, adjust duration, "
                "and avoid overwatering using basic checks. Try: \"Set zone 1 to 12 minutes every other day at 5:15 AM.\"")
    # Default
    return "Got it. Do you want me to start watering now, adjust the schedule, or check for issues?"

################################################################################
# Speech recognition setup
################################################################################

# Attempt to load the Vosk model.  Handle failures gracefully.
try:
    _vosk_model = Model(VOSK_MODEL_PATH)
    _recognizer = KaldiRecognizer(_vosk_model, MODEL_SAMPLE_RATE)
except Exception as _e:
    _vosk_model = None
    _recognizer = None
    print("Warning: Vosk model could not be loaded:", _e)

# Queue to receive audio chunks from the callback
_audio_queue: queue.Queue[bytes] = queue.Queue()

def _audio_callback(indata, frames, time_info, status):
    if status:
        print("Audio callback status:", status)
    # indata is a memoryview; convert to raw bytes
    _audio_queue.put(bytes(indata))

def record_and_transcribe(timeout: float = 6.0) -> str:
    """Record audio from the microphone and transcribe it using Vosk.

    Args:
        timeout: Maximum number of seconds to wait for speech before returning.

    Returns:
        The recognized text, or an empty string if nothing was detected.
    """
    if _recognizer is None:
        print("ASR recognizer is not available (Vosk model missing).")
        return ""
    # Reset the recognizer state between sessions
    _recognizer.Reset()
    # Start capturing audio
    try:
        with sd.RawInputStream(
            samplerate=MODEL_SAMPLE_RATE,
            blocksize=1024,
            dtype='int16',
            channels=1,
            callback=_audio_callback,
            device=DEVICE_INDEX,
        ):
            start_time = time.time()
            while True:
                try:
                    data = _audio_queue.get(timeout=timeout + 1)
                except queue.Empty:
                    # Timeout: finalize any partial result
                    result = json.loads(_recognizer.FinalResult())
                    return result.get("text", "")
                # Feed audio to the recognizer
                if _recognizer.AcceptWaveform(data):
                    result = json.loads(_recognizer.Result())
                    return result.get("text", "")
                # Check overall timeout
                if time.time() - start_time > timeout:
                    result = json.loads(_recognizer.FinalResult())
                    return result.get("text", "")
    except Exception as e:
        print("Error while recording audio:", e)
        return ""

################################################################################
# LLM response handling
################################################################################

def respond_to_text(user_input: str) -> str:
    """Generate a reply to user_input using the local LLM with fallback.

    The function first attempts to call ``local_chat`` from ``llm_client``.  If
    that call fails (e.g. the local model is down), it falls back to
    ``_fallback_reply`` to ensure the assistant always responds.

    Args:
        user_input: The user's spoken input (already transcribed).

    Returns:
        A reply string appropriate to the input.
    """
    try:
        return local_chat(user_input)
    except LLMError:
        return _fallback_reply(user_input)

################################################################################
# Text‑to‑speech
################################################################################

# Initialize the speech engine once.  ``pyttsx3`` is thread‑safe if you avoid
# interleaving calls from multiple threads.
_tts_engine = pyttsx3.init()
_tts_engine.setProperty("rate", 160)

def speak_text(text: str) -> None:
    """Speak the given text out loud using pyttsx3.

    This function blocks until the speech has finished.
    """
    if not text:
        return
    # Remove any assistant name prefix (e.g. "Astra:") for a cleaner voice
    cleaned = text.replace("Astra:", "").strip()
    print("Astra:", cleaned)
    _tts_engine.say(cleaned)
    _tts_engine.runAndWait()

################################################################################
# Main loop
################################################################################

def main() -> None:
    """Run an interactive voice loop until the user presses Ctrl+C."""
    print("=== Ingenious Irrigation Voice Assistant ===")
    print("Press Enter to start recording. Press Ctrl+C to exit.")
    try:
        while True:
            input("Press Enter to speak...")
            text = record_and_transcribe(timeout=8.0)
            if not text.strip():
                print("No speech detected. Try again.")
                continue
            reply = respond_to_text(text)
            speak_text(reply)
    except KeyboardInterrupt:
        print("\nExiting voice assistant.")
    except Exception as e:
        print("Unexpected error:", e)


if __name__ == "__main__":
    main()