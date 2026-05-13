# tests/test_schedule_manager.py
from schedule_manager import ScheduleManager

def test_schedule_save_load(tmp_path):
    p = tmp_path / "schedules.json"
    sm = ScheduleManager(path=str(p))
    sm.clear()
    assert sm.list() == []
    s = {"id": "t1", "zone": "zone1", "duration": 60}
    sm.add(s)
    sm2 = ScheduleManager(path=str(p))
    assert any(item.get("id") == "t1" for item in sm2.list())

def test_health_writable(tmp_path):
    p = tmp_path / "schedules.json"
    sm = ScheduleManager(path=str(p))
    assert sm.health() is True
