# schedule_manager.py
import json
import os
from typing import List, Dict

SCHEDULE_FILE = "schedules.json"

class ScheduleManager:
    def __init__(self, path: str = SCHEDULE_FILE):
        self.path = path
        self._schedules: List[Dict] = []
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    self._schedules = json.load(f)
            except Exception:
                self._schedules = []
        else:
            self._schedules = []

    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self._schedules, f, indent=2)

    def list(self) -> List[Dict]:
        return self._schedules

    def add(self, schedule: Dict) -> Dict:
        self._schedules.append(schedule)
        self._save()
        return schedule

    def clear(self):
        self._schedules = []
        self._save()

    def health(self) -> bool:
        # health is true if we can write to the schedule file directory
        try:
            dirpath = os.path.dirname(os.path.abspath(self.path)) or "."
            testfile = os.path.join(dirpath, ".sched_write_test")
            with open(testfile, "w") as f:
                f.write("ok")
            os.remove(testfile)
            return True
        except Exception:
            return False
