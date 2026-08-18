import datetime
import types
import pytest
from unittest.mock import patch
from core.shared.event_schedular.main import EventScheduler as RealEventScheduler
import core.shared.event_schedular.main as esmod


class FakeResEntry:
    def __init__(self):
        self.work_together_arr = {}
        self.sessions_together_arr = {}
        self.time_with_users = {}
        self.time_constraints = {"day": {}, "week": {}, "session": {}}
        self.onlyUserToUser = {}
        self.onlyUserToSession = {}
        self.events = []
        self.roles = ["Resource"]

class FakeResources:
    """Mimics models.scheduling_models.Resources just enough for tests."""
    def __init__(self, users):
        self.resources = {i: FakeResEntry() for i, _ in enumerate(users)}
        self.slots = {}
        self.frequency_constraints = []
        self.drive_constraints = []
        self.onlyUserToUser = {}
        self.onlyUserToSession = {}

class FakeSolver:
    """Stub for cp_model.CpSolver with a tiny 'parameters' surface."""
    def __init__(self):
        self.parameters = types.SimpleNamespace(
            log_search_progress=False,
            enumerate_all_solutions=False,
        )
    def Solve(self, model, cb):
        return 4

class FakeVarArraySolutionPrinter:
    """Printer used in generate_scheduling_events(). We'll seed one tiny solution."""
    def __init__(self, args, solution_limit):
        self.users = args[5]
        loc_idx = next(i for i, u in enumerate(self.users) if "Location" in u["roles"])
        person_idx = next(i for i, u in enumerate(self.users) if "Person" in u["roles"])
        self._sol = frozenset({loc_idx, person_idx})
        self.all_solutions = {self._sol: [0]}
        self.all_blocks = {self._sol: 0}
        self.all_priorities = {self._sol: 50}
        self.all_solutions_constraints = {}

class FakeVarArraySolutionPrinter2:
    """Printer used in refine_scheduling_constraints(). Returns one 'solution' object."""
    def __init__(self, *args, **kwargs):
        self.all_solutions = [{
            "resourceIds_r": [0, 1],
            "start_r": 10,
            "end_r": 12,
            "new_start": "2026-02-09",
            "start": "2026-02-09T09:00:00.000Z",
            "end":   "2026-02-09T09:30:00.000Z",
        }]

def fake_time_to_slot(hms, weekday, slot_interval):
    h, m, _ = map(int, hms.split(":"))
    per_day = (24 * 60) // slot_interval
    return weekday * per_day + (h * 60 + m) // slot_interval

def fake_slot_to_time(slot, slot_interval):
    per_day = (24 * 60) // slot_interval
    minutes = (slot % per_day) * slot_interval
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}:00"

def fake_detect_range(sorted_indices):
    """Return contiguous [start, end) ranges from a sorted list of ints."""
    if not sorted_indices:
        return []
    ranges = []
    start = prev = sorted_indices[0]
    for x in sorted_indices[1:]:
        if x != prev + 1:
            ranges.append((start, prev + 1))
            start = x
        prev = x
    ranges.append((start, prev + 1))
    return ranges

@pytest.fixture
def patched_env(monkeypatch):
    monkeypatch.setattr(esmod, "Resources", FakeResources, raising=True)
    monkeypatch.setattr(esmod, "VarArraySolutionPrinter", FakeVarArraySolutionPrinter, raising=True)
    monkeypatch.setattr(esmod, "VarArraySolutionPrinter2", FakeVarArraySolutionPrinter2, raising=True)
    monkeypatch.setattr(esmod.cp_model, "CpSolver", FakeSolver, raising=True)

    monkeypatch.setattr(esmod, "time_to_slot", fake_time_to_slot, raising=True)
    monkeypatch.setattr(esmod, "slot_to_time", fake_slot_to_time, raising=True)
    monkeypatch.setattr(esmod, "detect_range", fake_detect_range, raising=True)

    return True


@pytest.fixture
def fake_dg():
    """Minimal Data_Gatherer-like object with the attributes EventScheduler reads."""
    class DG:
        pass

    dg = DG()
    dg.dd_data = {
        "optimizer_sol": True,
        "highPriority": [],
        "soft": [],
        "header": {"X-Tenant-Id": "beta", "Authorization": "Bearer x"},
        "settings": {
            "driveTime": False,
            "blocks": False,
        },
        "host": "http://localhost",
        "part1": True,
        "start_date": "2026-02-09",
        "end_date": "2026-02-10",
        "branch": "b1",
        "expanded_resources": ["P1"],
        "expanded_resources_filter": [],
    }

    # 👇 Fix: expose settings both ways (dd_data["settings"] and settings)
    dg.settings = dg.dd_data["settings"]

    dg.start_date = "2026-02-09"
    dg.end_date = "2026-02-10"
    dg.onCall = False
    dg.branch_id = "b1"
    dg.isolatedResources = []
    dg.home_id = None
    dg.distance_matrix = {}
    dg.resourceCombinationsExclude = []
    dg.expanded_resources = ["P1"]
    dg.expanded_resources_filter = []
    dg.custom_constraints = []

    dg.users = [
        {
            "id": "L1",
            "firstName": "Clinic",
            "roles": ["Location", "Resource"],
            "branches": ["b1"],
            "actual_subgroups": [],
            "needroom": 0,
            "capacity": None,
            "address": "123 Main St",
            "billable": False,
        },
        {
            "id": "P1",
            "firstName": "Alex",
            "lastName": "Doe",
            "roles": ["Person", "Employee", "Resource"],
            "branches": ["b1"],
            "actual_subgroups": [],
            "capacity": None,
            "address": "9 Employee Rd",
            "billable": True,
        },
    ]

    dg.branch_structure = {"b1": ["b1"]}
    dg.activity_table = [{"user": {"id": "P1"}, "efficiency": 80}]
    dg.capacities = [
        {
            "user1": {"id": "P1"},
            "locationDisabled": False,
            "role1": None, "subgroup1": None, "min1": None, "max1": None,
            "role2": None, "subgroup2": None, "min2": None, "max2": None,
            "role3": None, "subgroup3": None, "min3": None, "max3": None,
            "role4": None, "subgroup4": None, "min4": None, "max4": None,
            "role5": None, "subgroup5": None, "min5": None, "max5": None,
        }
    ]

    dg.branches = []
    dg.e_pair = []
    dg.subgroups = {}
    dg.location_raw_data = {}
    dg.flags_data = {}
    dg.events = []
    dg.events2 = []

    dg.availabilities = [
        {
            "av": True,
            "resourceIds": ["P1"],
            "start": "2026-02-09T09:00:00+0000",
            "end":   "2026-02-09T10:00:00+0000",
            "onCall": False,
            "location": ["L1"],
        },
        {
            "av": True,
            "resourceIds": ["L1"],
            "start": "2026-02-09T09:00:00+0000",
            "end":   "2026-02-09T10:30:00+0000",
            "onCall": False,
            "location": ["L1"],
        },
    ]

    return dg

@pytest.fixture
def opts():
    return {
        "is_orange": True,
        "ignoreConstraintArray": [],
        "investigate": [],
        "soft": True,
    }


@pytest.fixture
def es(patched_env, fake_dg, opts):
    return RealEventScheduler(fake_dg, opts)

def test_init_smoke(es, fake_dg):
    assert es.users == fake_dg.users
    assert isinstance(es.resources1, FakeResources)
    assert es.slot_length in (5, 15)


def test_generate_scheduling_events_minimal(es):
    events = es.generate_scheduling_events()
    assert isinstance(events, list)
    assert len(events) >= 1
    e0 = events[0]
    for key in ("title", "resourceIds", "resourceIds_r", "start", "end"):
        assert key in e0
    assert all(isinstance(i, int) for i in e0["resourceIds_r"])
    assert all(rid.endswith("a") for rid in e0["resourceIds"])


@patch("core.shared.event_schedular.main.VarArraySolutionPrinter2", FakeVarArraySolutionPrinter2)
def test_refine_scheduling_constraints_smoke(es, monkeypatch):
    monkeypatch.setattr(esmod.cp_model, "CpSolver", FakeSolver, raising=True)

    es.events_poss_raw = [{
        "title": ["Alex", "Clinic"],
        "resourceIds": [0, 1],
        "start": 10,
        "end": 12,
        "reasons": [],
    }]

    refined = es.refine_scheduling_constraints()
    assert isinstance(refined, list)
    assert len(refined) >= 1
    sol = refined[0]
    assert "start" in sol and "end" in sol

@patch("core.shared.event_schedular.main.VarArraySolutionPrinter", FakeVarArraySolutionPrinter)
@patch("core.shared.event_schedular.main.cp_model.CpSolver", FakeSolver)
def test_generate_scheduling_events_direct(es):
    """
    Direct test for EventScheduler.generate_scheduling_events.
    Ensures it returns a list of events with the expected keys and types.
    """
    events = es.generate_scheduling_events()

    # Basic assertions
    assert isinstance(events, list)
    assert len(events) >= 1

    first_event = events[0]
    # Verify key fields exist
    assert "title" in first_event
    assert "resourceIds" in first_event
    assert "resourceIds_r" in first_event
    assert "start" in first_event
    assert "end" in first_event

    # Verify resourceIds_r is list[int] and resourceIds are str
    assert all(isinstance(r, int) for r in first_event["resourceIds_r"])
    assert all(isinstance(r, str) for r in first_event["resourceIds"])
