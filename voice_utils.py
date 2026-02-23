"""
Utilities for generating speech audio for the Ingenious Irrigation AI assistant.

This module provides a helper function to convert arbitrary text into raw
audio bytes using the `pyttsx3` library.  The returned bytes can be
embedded directly in a JSON response (e.g. base64‑encoded) or saved to
disk for playback.  You can swap out the implementation in this module
for a different text‑to‑speech engine if desired.

Dependencies:
    - pyttsx3 (offline TTS engine)

Example usage::

    from voice_utils import generate_tts_audio
    audio_bytes = generate_tts_audio("Hello, world!")
    # Do something with audio_bytes (e.g. base64 encode for HTTP response)
"""

import os
import tempfile
import pyttsx3

def generate_tts_audio(text: str) -> bytes:
    """Convert ``text`` to speech using pyttsx3 and return raw WAV bytes.

    This helper creates a temporary WAV file using pyttsx3's `save_to_file`
    interface, reads the file back into memory, and then removes the
    temporary file.  It is suitable for use in a web API where you need
    to return audio in a single response.

    Args:
        text: The text to synthesize.  If empty, returns an empty byte
            string.

    Returns:
        A byte string containing the WAV audio data.

    Note:
        ``pyttsx3`` uses the system's default speech voices.  You can
        customize the voice or rate by modifying the engine properties
        before calling ``save_to_file``.
    """
    if not text:
        return b""
    # Initialize the speech engine
    engine = pyttsx3.init()
    engine.setProperty("rate", 160)  # You can adjust the speaking rate
    # Create a temporary file to store the synthesized audio
    fd, filename = tempfile.mkstemp(suffix=".wav")
    # Close the file descriptor; pyttsx3 will handle writing
    os.close(fd)
    try:
        # Request pyttsx3 to synthesize the audio into the temp file
        engine.save_to_file(text, filename)
        engine.runAndWait()
        # Read the file contents back into memory
        with open(filename, "rb") as f:
            audio = f.read()
    finally:
        # Clean up the temporary file
        try:
            os.remove(filename)
        except Exception:
            pass
    return audio