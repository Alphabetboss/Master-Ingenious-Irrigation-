# tests/test_hardware_mock.py
import hardware.mock as mock

def test_open_close_valve():
    res = mock.open_valve("zone1", duration_seconds=10)
    assert res["zone"] == "zone1"
    assert res["action"] == "opened"
    res2 = mock.close_valve("zone1")
    assert res2["action"] == "closed"

def test_read_flow():
    f = mock.read_flow()
    assert "flow_lpm" in f
