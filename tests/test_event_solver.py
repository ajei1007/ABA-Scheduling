import pytest
import datetime
from unittest.mock import MagicMock, patch
from core.shared.event_solver.main import Solver


@pytest.fixture
def sample_data():
    return {
        "sol_1": MagicMock(
            events2=[],
            users=[],
            events_poss=[],
            created_events=[],
            branches={},
            user_availabilities_general={},
            resources1=MagicMock(frequency_constraints=[], resources={}),
            user_uuid_to_index={},
            flags=[],
        ),
        "sol_2": MagicMock(),
        "sol_3": [],
        "public_ip": "127.0.0.1",
        "time_since_server_started": datetime.datetime.now(),
        "instance_id": "i-1234567890abcdef",
        "host": "http://localhost",
        "branch": "b1",
        "header": {"X-Tenant-Id": "beta", "Authorization": "Bearer token"},
        "start_date": "2026-02-09",
        "end_date": "2026-02-10",
        "new_created_events": [],
        "objectiveactivity": [],
        "mode": "test",
        "run_with_teams": False,
        "daily": False,
        "is_Multi": False,
        "teams": [],
    }


@pytest.fixture
def solver(sample_data):
    return Solver(sample_data)


# --- init ---
def test_solver_initialization(solver, sample_data):
    assert solver.data == sample_data
    assert isinstance(solver.solution1, MagicMock)
    assert solver.creatingEvents == []


# --- prepare_test_insert_payload ---
@patch("core.shared.event_solver.main.serialize_instance", lambda x: x)
@patch("core.shared.event_solver.main.get_drive_time_data", return_value={"drive": "data"})
def test_prepare_test_insert_payload(_mock_drive_time, solver, sample_data):
    sample_data.update({"objectiveactivity": [], "mode": "test"})
    payload = solver.prepare_test_insert_payload({
        "start_date_original": "2026-02-09",
        "resources_team": [],
        "data2_team": [],
        "aut_arr": [],
        "date_original": "2026-02-09"
    })
    assert isinstance(payload, dict)
    assert "solution1" in payload
    assert "data" in payload
    assert payload["solution1"]["events2"] == []


# --- update_from_test_insert_response ---
def test_update_from_test_insert_response(solver):
    response_data = {
        "employees_ids": ["emp1"],
        "availability_person": {"emp1": {0: [(0, 10)]}},
        "efficiency": {"emp1": 90},
        "deletingEvents": [{"id": "d1"}],
        "updatingEvents": [{"id": "u1"}],
        "creatingEvents": [{"id": "c1"}],
        "created_events": [{"id": "c2"}],
        "disabled_constraints": ["c"],
        "deleted_appointments_list": ["appt1"],
        "loc_id_2": "loc123",
        "created_hours": 10,
        "objective_value": 42,
        "deleted_hours": 1,
        "best_bound": 5,
        "status_name": "OPTIMAL",
        "founded": 1,
    }
    solver.update_from_test_insert_response(response_data)
    assert solver.employees_ids == ["emp1"]
    assert solver.created_hours == 10
    assert solver.status_name == "OPTIMAL"
    assert {"id": "c1"} in solver.creatingEvents


# --- get_payload_size ---
def test_get_payload_size(solver):
    payload = {"a": 1, "b": [1, 2, 3]}
    size = solver.get_payload_size(payload)
    assert isinstance(size, int)
    assert size > 0


# --- wait_for_instance_ready ---
@patch("core.shared.event_solver.main.boto3.client")
def test_wait_for_instance_ready(mock_boto, solver):
    mock_ec2 = mock_boto.return_value
    mock_ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"PublicIpAddress": "1.2.3.4"}]}]
    }
    public_ip = solver.wait_for_instance_ready("i-123")
    mock_ec2.get_waiter.assert_called_once_with("instance_running")
    assert public_ip == "1.2.3.4"


# --- wait_for_flask_ready ---
@patch("core.shared.event_solver.main.requests.Session")
def test_wait_for_flask_ready(mock_session_cls, solver):
    mock_session = mock_session_cls.return_value
    mock_resp = mock_session.get.return_value
    mock_resp.status_code = 200
    mock_resp.text = "OK"
    result = solver.wait_for_flask_ready("http://test", timeout_seconds=1)
    assert result == "OK"


# --- terminate_instance ---
@patch("core.shared.event_solver.main.boto3.client")
def test_terminate_instance(mock_boto, solver):
    solver.terminate_instance("i-abc")
    mock_boto.return_value.terminate_instances.assert_called_once()


# --- rocket ---
@patch("core.shared.event_solver.main.max_possible_total_hours", return_value=100)
@patch("core.shared.event_solver.main.weekly_events", return_value={})
@patch("core.shared.event_solver.main.get_groups_array", return_value=[])
@patch("core.shared.event_solver.main.availabilities", return_value=({}, {}, []))
@patch("core.shared.event_solver.main.Get_Data")
def test_rocket_basic(mock_get_data, _mock_avail, _mock_groups, _mock_weekly, _mock_max_hours, solver):
    mock_instance = mock_get_data.return_value
    mock_instance.res.return_value = [{"id": "E1", "roles": ["Employee"], "name": "John"}]
    mock_instance.get_events3.return_value = ([], [])
    mock_instance.get_notWorking.return_value = []
    mock_instance.get_roles_hierarchy.return_value = []
    mock_instance.get_distance_matrix.return_value = []

    solver.solution1.events_poss = []
    solver.solution1.events2 = []
    solver.rocket(solver.data)

    assert isinstance(solver.resources, list)
    assert solver.max_total_hours == 100


# --- part_one / part_two ---
@patch.object(Solver, "rocket", return_value=None)
def test_part_one_and_two(_mock_rocket, solver):
    result1 = solver.part_one()
    result2 = solver.part_two()
    assert isinstance(result1, dict)
    assert "creatingEvents" in result1
    assert "creatingEvents" in result2


# --- run_test_insert ---
@patch.object(Solver, "terminate_instance", return_value=None)
@patch("core.shared.event_solver.main.requests.post")
@patch.object(Solver, "wait_for_flask_ready", return_value="ready")
@patch.object(Solver, "prepare_test_insert_payload", return_value={"fake": "payload"})
def test_run_test_insert(_mock_prepare, _mock_wait, mock_post, _mock_term, solver):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "returned_arr": [],
        "objective_value": 1,
        "status": "OK",
        "created_events": [],
    }
    mock_post.return_value = mock_response

    result = solver.run_test_insert({
        "start_date_original": "2026-02-09",
        "resources_team": [],
        "data2_team": [],
        "aut_arr": [],
        "date_original": "2026-02-09",
    })
    assert isinstance(result, dict)
    assert result["objective_value"] == 1
    mock_post.assert_called_once()


# --- test_runner without teams ---
@patch.object(Solver, "run_test_insert", return_value={"returned_arr": []})
def test_test_runner_no_teams(_mock_run_insert, solver):
    solver.resources = [{"id": "E1", "roles": ["Person"], "branches": ["b1"]}]
    testing_data = {
        "start_date": "2026-02-09",
        "actual_data": [{"scheduled": False, "resourceIds": []}],
    }
    result = solver.test_runner(testing_data)
    assert isinstance(result, dict)
