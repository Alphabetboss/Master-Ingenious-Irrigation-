# astra_assistant.py

"""
Astra assistant module for Ingenious Irrigation.
Handles domain-specific questions about irrigation, schedules, zones, and diagnostics,
with optional fallback to an LLM (via llm_client or OpenAI API) for general questions.
"""

import re
from typing import Dict, Callable, Optional

# If you have a custom LLM client (e.g. llm_client.py), import it; otherwise, import openai
try:
    from llm_client import ask_llm  # hypothetical function: ask_llm(prompt) -> str
    USE_CUSTOM_LLM = True
except ImportError:
    USE_CUSTOM_LLM = False
    import openai

# Import your existing irrigation modules (these names are examples; adjust to match your repo)
from sprinkler_scheduler import get_next_run_time, set_zone_duration, get_zone_status  # type: ignore
from hydration_engine import get_soil_moisture, run_diagnostic  # type: ignore
from weather_client import get_forecast  # type: ignore
from schedule_manager import list_schedules, add_schedule  # type: ignore

# Persona configuration
ASTRA_NAME = "Astra"
WELCOME_MESSAGE = "Hello, I'm Astra, your irrigation assistant. How can I help?"
SYSTEM_PROMPT = (
    "You are Astra, the AI assistant for the Ingenious Irrigation system. "
    "Provide concise and helpful answers about irrigation zones, schedules, diagnostics, "
    "soil moisture, and weather. If asked unrelated questions, answer generally using a large "
    "language model. Always be friendly, but clear and factual."
)

class AstraAssistant:
    """
    An assistant that routes user questions to either domain-specific handlers or an LLM.
    """
    def __init__(
        self,
        llm_api_key: Optional[str] = None,
        temperature: float = 0.3,
    ) -> None:
        self.temperature = temperature
        self.llm_api_key = llm_api_key
        self.handlers: Dict[str, Callable[[str], str]] = {
            "zone_status": self.handle_zone_status,
            "next_run": self.handle_next_run,
            "set_duration": self.handle_set_duration,
            "soil_moisture": self.handle_soil_moisture,
            "diagnostic": self.handle_diagnostic,
            "weather": self.handle_weather,
            "list_schedule": self.handle_list_schedules,
            "add_schedule": self.handle_add_schedule,
        }

    # --------------------------------------------------------------------------
    # Main entry point

    def respond(self, text: str) -> str:
        """
        Determine the appropriate handler for the user's query.
        If no handler matches, fall back to the LLM.
        """
        cleaned = text.strip().lower()
        if not cleaned:
            return "Please say something so I can help you."

        # Try each handler; if one returns a non-empty string, use it
        for name, handler in self.handlers.items():
            try:
                result = handler(cleaned)
                if result:
                    return result
            except Exception as e:  # Catch errors so one bad handler doesn't break everything
                print(f"Handler {name} raised an error: {e}")

        # Nothing matched, fall back to LLM
        return self.ask_llm(cleaned)

    # --------------------------------------------------------------------------
    # Rule-based handlers

    def handle_zone_status(self, query: str) -> str:
        """
        Respond to questions about the current status of a zone.
        Example: "Is zone 2 running?" or "What's the status of zone 1?"
        """
        match = re.search(r"zone\s*(\d+).*status|status.*zone\s*(\d+)", query)
        if match:
            zone = int(match.group(1) or match.group(2))
            status = get_zone_status(zone)
            return f"Zone {zone} is currently {'running' if status else 'not running'}."
        return ""

    def handle_next_run(self, query: str) -> str:
        """
        Respond to questions about when a zone or schedule will next run.
        Example: "When does the next watering happen?" or "When is zone 3 scheduled?"
        """
        if "next run" in query or ("when" in query and "zone" in query):
            # Optionally extract the zone number; default to all schedules
            match = re.search(r"zone\s*(\d+)", query)
            zone = int(match.group(1)) if match else None
            time_str = get_next_run_time(zone)
            if zone:
                return f"The next run for zone {zone} is {time_str}."
            return f"The next scheduled watering is {time_str}."
        return ""

    def handle_set_duration(self, query: str) -> str:
        """
        Respond to requests to set a zone's watering duration.
        Example: "Set zone 1 to run for 10 minutes."
        """
        match = re.search(r"set\s+zone\s*(\d+)\s+to\s*(\d+)\s*minutes?", query)
        if match:
            zone = int(match.group(1))
            minutes = int(match.group(2))
            set_zone_duration(zone, minutes)
            return f"Okay, zone {zone} will now run for {minutes} minutes."
        return ""

    def handle_soil_moisture(self, query: str) -> str:
        """
        Respond to questions about soil moisture.
        Example: "What's the soil moisture in zone 2?" or "How dry is my lawn?"
        """
        if "soil" in query or "moisture" in query or "dry" in query:
            match = re.search(r"zone\s*(\d+)", query)
            zone = int(match.group(1)) if match else None
            moisture = get_soil_moisture(zone)
            if moisture is not None:
                if zone:
                    return f"The soil moisture in zone {zone} is {moisture:.1f}%."
                return f"The average soil moisture is {moisture:.1f}%."
        return ""

    def handle_diagnostic(self, query: str) -> str:
        """
        Respond to diagnostic requests.
        Example: "Run a diagnostic" or "Check the system health."
        """
        if "diagnostic" in query or "health" in query or "check system" in query:
            report = run_diagnostic()
            return f"Diagnostic complete: {report}"
        return ""

    def handle_weather(self, query: str) -> str:
        """
        Respond to weather-related queries.
        Example: "What's the weather forecast?" or "Will it rain tomorrow?"
        """
        if "weather" in query or "forecast" in query or "rain" in query:
            forecast = get_forecast()
            return f"The upcoming weather forecast: {forecast}"
        return ""

    def handle_list_schedules(self, query: str) -> str:
        """
        Respond to listing watering schedules.
        Example: "Show me my watering schedule."
        """
        if "schedule" in query and ("list" in query or "show" in query):
            schedules = list_schedules()
            if not schedules:
                return "You currently have no watering schedules set."
            # Build a human-friendly description
            lines = [f"- Zone {zone}: every {info['frequency']} at {info['time']}" 
                     for zone, info in schedules.items()]
            return "Here are your current watering schedules:\n" + "\n".join(lines)
        return ""

    def handle_add_schedule(self, query: str) -> str:
        """
        Respond to requests to add a watering schedule.
        Example: "Add a schedule for zone 2 every day at 7 AM."
        """
        match = re.search(
            r"add (?:a )?schedule for zone\s*(\d+)\s*every\s+(\w+)\s+at\s*(\d+)(?::(\d+))?\s*(am|pm)",
            query
        )
        if match:
            zone = int(match.group(1))
            frequency = match.group(2)
            hour = int(match.group(3))
            minute = int(match.group(4) or 0)
            am_pm = match.group(5).lower()
            # Convert to 24-hour time
            if am_pm == "pm" and hour != 12:
                hour += 12
            if am_pm == "am" and hour == 12:
                hour = 0
            add_schedule(zone, frequency, hour, minute)
            return (f"Added a schedule: zone {zone} will water every {frequency} at "
                    f"{hour:02d}:{minute:02d}.")
        return ""

    # --------------------------------------------------------------------------
    # LLM fallback

    def ask_llm(self, user_query: str) -> str:
        """
        Use either a custom llm_client or OpenAI's API to answer general questions.
        """
        prompt = f"{SYSTEM_PROMPT}\n\nUser: {user_query}\n{ASTRA_NAME}:"
        if USE_CUSTOM_LLM:
            # Your custom llm_client.ask_llm(prompt) should return a string
            try:
                answer = ask_llm(prompt)
                return answer.strip()
            except Exception as e:
                print(f"llm_client error: {e}")
                # fall back to generic response
                return "Sorry, I'm having trouble reaching the AI service right now."
        else:
            if not self.llm_api_key:
                return "I don't have an API key configured for answering that right now."
            try:
                openai.api_key = self.llm_api_key
                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_query},
                    ],
                    temperature=self.temperature,
                    max_tokens=150,
                )
                answer = completion.choices[0].message["content"]
                return answer.strip()
            except Exception as e:
                print(f"OpenAI error: {e}")
                return "Sorry, I'm having trouble reaching the AI service right now."
