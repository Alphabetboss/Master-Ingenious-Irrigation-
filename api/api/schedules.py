# api/schedules.py
from flask import Blueprint, request, jsonify
from schedule_manager import ScheduleManager
import uuid

schedules_bp = Blueprint("schedules", __name__)
_sm = ScheduleManager()

def _json_error(msg, code=400):
    return jsonify({"error": msg}), code

@schedules_bp.route("/schedules", methods=["GET"])
def list_schedules():
    return jsonify({"schedules": _sm.list()}), 200

@schedules_bp.route("/schedules", methods=["POST"])
def add_schedule():
    if not request.is_json:
        return _json_error("Expected JSON body", 400)
    payload = request.get_json()
    # Minimal validation
    if not isinstance(payload, dict):
        return _json_error("Invalid schedule payload", 400)
    # Ensure an id exists
    if "id" not in payload:
        payload["id"] = str(uuid.uuid4())
    _sm.add(payload)
    return jsonify({"schedule": payload}), 201

@schedules_bp.route("/schedules/<schedule_id>", methods=["DELETE"])
def delete_schedule(schedule_id):
    # Simple delete by id
    current = _sm.list()
    new = [s for s in current if str(s.get("id")) != str(schedule_id)]
    if len(new) == len(current):
        return _json_error("Schedule not found", 404)
    # overwrite schedules file
    _sm._schedules = new
    _sm._save()
    return jsonify({"deleted": schedule_id}), 200

@schedules_bp.route("/schedules/clear", methods=["POST"])
def clear_schedules():
    _sm.clear()
    return jsonify({"cleared": True}), 200
