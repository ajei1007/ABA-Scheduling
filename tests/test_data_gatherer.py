import pytest
from unittest.mock import MagicMock, patch
from core.shared.data_gatherer import Data_Gatherer


@pytest.fixture
def sample_dict_data():
    return {
        "branch": "branch123",
        "start_date": "2026-02-09",
        "end_date": "2026-02-10",
        "sandboxMode": False,
        "settings": {"isOnboarding": False},
        "isolatedResources": ["res1"],
        "home_id": "home123",
        "expanded_resources": ["res2"],
        "resourceCombinationsExclude": [],
        "expanded_resources_filter": [],
        "onCall": True,
        "optimizer_sol": True,
    }


# --- Test Initialization and _calculate_days ---
@patch("core.shared.data_gatherer.Get_Data")
def test_initialization_and_days(mock_get_data, sample_dict_data):
    fake_get_data = mock_get_data.return_value
    # Mock all the Get_Data methods used
    fake_get_data.get_availability.return_value = ["avail"]
    fake_get_data.get_capacities.return_value = ["cap"]
    fake_get_data.get_subgroups.return_value = ["sub"]
    fake_get_data.get_custom_constraints.return_value = ["constraint"]
    fake_get_data.get_branch_structure.return_value = ["branch_struct"]
    fake_get_data.get_event_pair.return_value = ["pair"]
    fake_get_data.get_events2.return_value = ([], [])  # users + events
    fake_get_data.get_branches.return_value = ["branch"]
    fake_get_data.get_location_raw_data.return_value = ["loc"]
    fake_get_data.get_activity_table.return_value = ["activity"]
    fake_get_data.get_flags.return_value = {"flag": True}

    dg = Data_Gatherer(sample_dict_data)

    # Verify calculated days
    assert dg.num_of_days == 1  # Feb 9 → Feb 10

    # Ensure mocked methods called
    fake_get_data.get_availability.assert_called_once()
    fake_get_data.get_events2.assert_called_once()

    # Ensure attributes populated
    assert dg.availabilities == ["avail"]
    assert dg.capacities == ["cap"]
    assert dg.custom_constraints == ["constraint"]
    assert isinstance(dg.users, list)
    assert dg.flags_data == {"flag": True}


# --- Test onboarding mode (users not filtered) ---
@patch("core.shared.data_gatherer.Get_Data")
def test_onboarding_mode(mock_get_data, sample_dict_data):
    sample_dict_data["settings"]["isOnboarding"] = True

    fake_get_data = mock_get_data.return_value
    # Return list, not tuple
    fake_get_data.get_events2.return_value = [[{"id": "u1"}], [["ev1"]]]

    dg = Data_Gatherer(sample_dict_data)

    assert dg.users == [{"id": "u1"}]
    assert dg.events == ["ev1"]

# --- Test get_data_summary helper ---
@patch("core.shared.data_gatherer.Get_Data")
def test_get_data_summary(mock_get_data, sample_dict_data):
    fake_get_data = mock_get_data.return_value
    fake_get_data.get_availability.return_value = ["avail"]
    fake_get_data.get_capacities.return_value = ["cap"]
    fake_get_data.get_subgroups.return_value = ["sub"]
    fake_get_data.get_custom_constraints.return_value = ["constraint"]
    fake_get_data.get_branch_structure.return_value = ["branch_struct"]
    fake_get_data.get_event_pair.return_value = ["pair"]
    fake_get_data.get_events2.return_value = ([{"id": "u1"}], [["ev1"]])
    fake_get_data.get_branches.return_value = ["branch"]
    fake_get_data.get_location_raw_data.return_value = ["loc"]
    fake_get_data.get_activity_table.return_value = ["activity"]
    fake_get_data.get_flags.return_value = {"flag": True}

    dg = Data_Gatherer(sample_dict_data)
    summary = dg.get_data_summary()

    assert "availabilities" in summary
    assert "capacities" in summary
    assert summary["events"] == len(dg.events)
    assert summary["activity_table"] == ["activity"]
