"""
Astra persona definitions and prompt builder.

This module defines the core persona settings and helper functions for
composing prompts passed to an external large‑language model (LLM).  It is
separated into its own file so that developers can easily customise the
assistant’s behaviour without modifying the main Flask application.

You can adjust SYSTEM_PROMPT and WELCOME to tailor Astra’s tone and default
greeting.  The build_astra_prompt function can be extended to include
relevant telemetry data or contextual information (e.g., current schedule,
soil moisture readings) in the prompt sent to your LLM.
"""

from __future__ import annotations

from typing import Optional
import json

# High‑level instructions for the LLM.  Keep the persona focused on
# irrigation, plant care, and monitoring systems.  If you modify this, be
# mindful of token limits when passing it to the API.
SYSTEM_PROMPT: str = (
    "You are Astra, a friendly and knowledgeable irrigation assistant for the "
    "Ingenious Irrigation system.  Your job is to help users manage watering "
    "schedules, start or stop watering zones, adjust durations and frequencies, "
    "monitor for leaks and issues, and provide guidance about weather and plant "
    "health.  Always be concise and clear.  Avoid guessing when information is "
    "insufficient.  If a question is unrelated to irrigation, politely steer the "
    "user back to relevant tasks.  Use the name 'Astra' when referring to yourself.  "
    "Answer in a helpful tone appropriate for a voice assistant."
)

# Greeting used by the /astra/speak endpoint.  Feel free to personalise this.
WELCOME: str = (
    "Hello Austin.  I'm awake.  The garden feels calm.  What shall we tend today?"
)


def build_astra_prompt(user_msg: str, telemetry: Optional[dict]) -> str:
    """
    Build a complete prompt for the LLM by combining the persona instructions,
    the user's message, and any available telemetry.

    Args:
        user_msg: The raw text received from the user.
        telemetry: Optional dictionary of sensor readings or schedule data.
            If provided it should be a simple Python dict containing JSON‑serialisable
            keys and values.  For example:

                {
                    "soil_moisture": 0.42,
                    "last_run": "2026-02-21T05:00:00Z",
                    "forecast": "Light rain expected at 7 AM"
                }

    Returns:
        A single string to send as the user prompt to the LLM.
    """
    sections = []
    # Always start with the system prompt so the model understands its role.
    sections.append(SYSTEM_PROMPT)

    # If telemetry is provided, encode it as a JSON block.  This allows the
    # model to incorporate real‑time data into its reasoning.
    if telemetry:
        try:
            telemetry_json = json.dumps(telemetry, ensure_ascii=False)
            sections.append(f"Telemetry: {telemetry_json}")
        except Exception:
            # If telemetry cannot be serialised, ignore it to avoid injection.
            pass

    # Finally add the user's message.  Use "User:" and "Astra:" markers to make
    # the dialogue clear to the model.
    sections.append(f"User: {user_msg}")
    sections.append("Astra:")

    # Separate sections by blank lines for readability.
    return "\n\n".join(sections)


__all__ = ["SYSTEM_PROMPT", "WELCOME", "build_astra_prompt"]
