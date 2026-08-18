import pytest
from unittest.mock import MagicMock, patch
from core.optimizer.optimizer import Optimizer, runOptimizer


@pytest.fixture
def sample_data():
    return {
        "header": {"X-Tenant-Id": "beta", "Authorization": "Bearer testtoken"},
        "start_date": "2026-02-09",
        "end_date": "2026-02-10",
        "branch": "branch123",
        "host": "http://localhost",
        "expanded_resources": ["res1"],
        "expanded_resources_filter": [],
        "uncheckWhiteSolutionConstraints": [],
        "uncheckOrangeSolutionConstraints": [],
        "investigate": [],
        "settings": {"driveTime": False, "orange": True},
        "soft": ["soft1"],
        "highPriority": ["hp1"],
        "teams_ids": [["user1", "user2"]],
        "slot_length": 15,
        "percentage": 0,
    }


# --- Test Initialization ---
def test_initialization(sample_data):
    opt = Optimizer(sample_data)
    assert opt.data == sample_data
    assert opt.start_date.strftime("%Y-%m-%d") == sample_data["start_date"]
    assert opt.end_date.strftime("%Y-%m-%d") == sample_data["end_date"]
    assert opt.total_days == 2


# --- Test assign_colors ---
def test_assign_colors(sample_data):
    opt = Optimizer(sample_data)
    events = [{"id": 1}, {"id": 2, "ov": "t"}]
    colored = opt.assign_colors(events)
    assert colored[0]["colorType"] == "orange"
    assert colored[1]["colorType"] == "yellow"


# --- Test categorize_events ---
@patch("core.optimizer.optimizer.Data_Gatherer")
def test_categorize_events(mock_dg, sample_data):
    mock_instance = mock_dg.return_value
    mock_instance.some_data.get_event_future.return_value = {
        1: {"constraints": []},
        2: {"constraints": [{"description": "<strong>Conflict</strong>"}]},
    }

    opt = Optimizer(sample_data)
    opt.data_gatherer = mock_instance

    unmatch_events = [{"id": 1}, {"id": 2, "ov": "t"}]
    categorized = opt.categorize_events(unmatch_events)

    assert len(categorized) == 2
    assert any("colorType" in e or "reasons" in e for e in categorized)


# --- Test run_optimization_phase ---
@patch("core.optimizer.optimizer.availabilities")
@patch("core.optimizer.optimizer.Optimizer.optimize_team")
@patch("core.optimizer.optimizer.Optimizer.get_solutions")
def test_run_optimization_phase(mock_get_solutions, mock_optimize_team, mock_avail, sample_data):
    fake_solution = MagicMock()
    mock_get_solutions.return_value = [
        [fake_solution],  # solutions_primary[0]
        [fake_solution],  # solutions_primary[1]
        [fake_solution],  # solutions_primary[2]
        [fake_solution],  # solutions_primary[3]
    ]

    mock_optimize_team.return_value = {
        "results": [{
            "creatingEvents": [{"id": "c1"}],
            "deletingEvents": [{"id": "d1"}],
            "updatingEvents": [],
            "disabled_constraints": [],
            "efficiency": {},
            "created_hours": 1,
            "deleted_hours": 0,
            "obj_value": 42,
            "status_name": "OK",
            "max_total_hours": 100,
            "deleted_appointments_list": [],
        }],
        "admin_filler": []
    }

    # prevent real HTTP call
    mock_avail.return_value = ({}, {}, {}, {}, {"employees": {}, "clients": {}})

    opt = Optimizer(sample_data)
    results = opt.run_optimization_phase()

    assert isinstance(results, dict)
    assert "creatingEvents" in results

# --- Test optimize_workflow ---
@patch("core.optimizer.optimizer.requests.get")
@patch("core.optimizer.optimizer.Optimizer.run_optimization_phase")
@patch("core.optimizer.optimizer.Optimizer.calculate_efficiency")
def test_optimize_workflow(mock_efficiency, mock_run_phase, mock_requests, sample_data):
    mock_requests.return_value.json.return_value = {
        "public_ip": "127.0.0.1",
        "instance_id": "test123",
    }
    mock_run_phase.return_value = {
        "creatingEvents": [], "deletingEvents": [], "updatingEvents": [],
        "obj_value": 1, "disabled_constraints": []
    }
    mock_efficiency.return_value = {"total_efficiency": "100%"}

    opt = Optimizer(sample_data)
    results = opt.optimize_workflow()

    assert isinstance(results, list)
    assert "statistics" in results[0]


# --- Test optimize_team ---
@patch("core.optimizer.optimizer.Solver")
def test_optimize_team(mock_solver, sample_data):
    fake_solver = mock_solver.return_value
    fake_solver.part_one.return_value = {
        "creatingEvents": [{"id": "c1"}],
        "deletingEvents": [{"id": "d1"}],
        "updatingEvents": [],
        "disabled_constraints": [],
        "efficiency": {},
        "created_hours": 1,
        "deleted_hours": 0,
        "obj_value": 5,
        "status_name": "OK",
        "max_total_hours": 10,
        "deleted_appointments_list": [],
    }
    fake_solver.part_two.return_value = fake_solver.part_one.return_value

    sample_data["part1"] = True

    opt = Optimizer(sample_data)
    result = opt.optimize_team(
        team_idx=0,
        team=["res1"],
        solutions_primary=[MagicMock(), MagicMock(), MagicMock()],
    )

    assert "results" in result
    assert result["results"][0]["obj_value"] == 5


# --- Test runOptimizer wrapper ---
@patch("core.optimizer.optimizer.Optimizer.optimize_workflow")
def test_runOptimizer(mock_optimize, sample_data):
    mock_optimize.return_value = [{"success": True}]
    result = runOptimizer(sample_data)
    assert result == [{"success": True}]
    mock_optimize.assert_called_once()
