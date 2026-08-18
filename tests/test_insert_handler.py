import pytest
import json
from datetime import datetime

# Import the handler
from core.shared.event_solver.insert_handler import insert_handler

def test_drive_time_zero_duration(monkeypatch):
    """Ensure 0-duration drive events are not created."""

    class FakeAutomate:
        def __init__(*args, **kwargs): pass
        def solve_model(self, *a, **k): pass
        objective_value = 0
        disabled_constraints = []
        employees_ids = []
        availability_persons = {}
        resources1 = type("R", (), {"slots": {}, "priorities": {}})()
        over_availability_events = []
        deletable_events = []
        drive_time_data = {("A","B"): {"mid": 0}}  # <- 0 minutes
        var_data = {"slot_length": 15, "drive_id": "drive_fake"}
        solutions1 = {"user_uuid_to_index": {}, "users": {}, "branches": {}}
        def find_ids_by_role(self, roles): return []
        def get_team_vals(self): return {}
        solver = type("Solver", (), {
            "Value": staticmethod(lambda x: 0),
            "StatusName": staticmethod(lambda: "OPTIMAL"),
            "ObjectiveValue": staticmethod(lambda: 0),
        })()
        printer = type("Printer", (), {"solution_count": staticmethod(lambda: 1)})()
        see_here = []
        del_bol_array = 0
        def get_best_objective_bound(self): return 0

    monkeypatch.setattr("core.shared.event_solver.insert_handler.Automate", FakeAutomate)

    monkeypatch.setattr(
        "core.shared.event_solver.insert_handler.deserialize_instance",
        lambda x: x
    )

    input_event = {
        "start_date_original": datetime.now().isoformat(),
        "resources_team": {},
        "data": {
            "objectiveactivity": "act1",
            "start_date": "2025-09-19",
            "end_date": "2025-09-20",
            "slot_length": 15,
            "drive_id": "drive_fake",
            "notWorking": [],
            "settings": {"driveTime": True},
        },
        "constraint_drive_data": {},
        "date_original": "2025-09-19",
        "data2_team": {},
        "aut_arr": [],
        "overlaped_ids": [],
        "resources": [],
        "roles_hierarchy": {},
        "distance_matrix": {},
        "solution1": {"flags": {}, "resources1": {}, "users": {}, "events2": []},
        "efficiency": {},
        "employees_ids": [],
        "availability_person": {},
    }

    response = insert_handler(input_event, None)
    body = json.loads(response["body"])

    drive_events = [
        ev for ev in body["creatingEvents"] if "drive_fake" in ev.get("users", [])
    ]
    assert not drive_events, "0-duration drive event was incorrectly created!"
