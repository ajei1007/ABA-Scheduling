import pytest
from unittest.mock import MagicMock, patch
from core.solution_generator.main import SolutionGenerator, runSolutionGenerator


@pytest.fixture
def sample_data():
    return {
        'header': {'X-Tenant-Id': 'beta', 'Authorization': 'Bearer testtoken'},
        'start_date': '2026-02-09',
        'end_date': '2026-02-10',
        'branch': '0b0d455d-f3ea-4514-b9f1-061cefc9cbeb',
        'expanded_resources': ['390a204a-62f8-47de-a4d0-88e87cab1383'],
        'expanded_resources_filter': [],
        'uncheckWhiteSolutionConstraints': [],
        'uncheckOrangeSolutionConstraints': [],
        'investigate': [],
        'settings': {'driveTime': False, 'orange': True},
        'soft': ['soft1'],
        'highPriority': ['hp1'],
    }


# --- FIX 1: Patch Data_Gatherer so __init__ doesn’t call backend
@patch("core.solution_generator.main.Data_Gatherer")
def test_initialization(mock_data_gatherer, sample_data):
    mock_data_gatherer.return_value = MagicMock()
    sg = SolutionGenerator(sample_data)
    assert sg.data == sample_data
    assert sg.backend_url == "https://beta-api.abaschedules.com/api"
    assert isinstance(sg.formatted_data, dict)

@patch("core.solution_generator.main.EventScheduler")
@patch("core.solution_generator.main.Data_Gatherer")
def test_initialize_solutions(mock_data_gatherer, mock_event_scheduler, sample_data):
    mock_event_scheduler.return_value = MagicMock()
    sg = SolutionGenerator(sample_data)
    sg.initialize_solutions()
    mock_data_gatherer.assert_called_once()
    mock_event_scheduler.assert_called_once()
    assert sg.solutions1 is not None
    assert sg.solutions2 is not None

@patch("core.solution_generator.main.Data_Gatherer")
def test_assign_colors(mock_data_gatherer, sample_data):
    mock_data_gatherer.return_value = MagicMock()
    sg = SolutionGenerator(sample_data)
    events = [{"id": 1}, {"id": 2, "ov": "t"}]
    colored_events = sg.assign_colors(events)
    assert colored_events[0]["colorType"] == "orange"
    assert colored_events[1]["colorType"] == "yellow"


@patch("core.solution_generator.main.Data_Gatherer")
def test_categorize_events(mock_data_gatherer, sample_data):
    mock_instance = mock_data_gatherer.return_value
    mock_instance.some_data.get_event_future.return_value = {
        1: {"constraints": []},
        2: {"constraints": [{"description": "<strong>Conflict</strong>"}]},
    }

    sg = SolutionGenerator(sample_data)
    unmatch_poss_events_new2 = [{"id": 1}, {"id": 2, "ov": "t"}]
    new_match, new_unmatch = sg.categorize_events(unmatch_poss_events_new2)
    assert len(new_match) == 1
    assert len(new_unmatch) == 1
    assert "reasons" in new_unmatch[0]


@patch("core.solution_generator.main.SolutionGenerator")
def test_runSolutionGenerator(mock_solution_generator, sample_data):
    mock_instance = mock_solution_generator.return_value
    mock_instance.run.return_value = {"success": True}
    result = runSolutionGenerator(sample_data)
    mock_solution_generator.assert_called_once_with(sample_data)
    mock_instance.run.assert_called_once()
    assert result == {"success": True}

@pytest.mark.parametrize("drive_time_enabled", [False, True])
@patch("core.solution_generator.main.EventScheduler")
@patch("core.solution_generator.main.Data_Gatherer")
def test_generate_possible_and_unmatched_events_variants(
    mock_data_gatherer, mock_event_scheduler, sample_data, drive_time_enabled
):
    mock_scheduler_instance = MagicMock()
    mock_scheduler_instance.generate_scheduling_events.return_value = [{"id": 1}]
    mock_scheduler_instance.refine_scheduling_constraints.return_value = [{"id": 1}]
    mock_scheduler_instance.main_drive_time.return_value = [
        {"id": 1, "name": "Updated Event 1"},
        {"id": 3, "name": "New Event"},
    ]
    mock_scheduler_instance.users = {1: {"id": 1, "name": "John"}}
    mock_event_scheduler.return_value = mock_scheduler_instance

    sample_data["settings"]["driveTime"] = drive_time_enabled

    sg = SolutionGenerator(sample_data)
    sg.initialize_solutions()
    _, unmatch_poss_events = sg.generate_possible_and_unmatched_events()

    if drive_time_enabled:
        ids = [e["id"] for e in unmatch_poss_events]

        assert sorted(ids) == [1, 3]

        event_1 = next(e for e in unmatch_poss_events if e["id"] == 1)
        assert event_1.get("name") == "Updated Event 1"

        assert len(ids) == len(set(ids))

    else:
        assert unmatch_poss_events == [{"id": 1}]