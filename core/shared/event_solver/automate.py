import os
import datetime
import traceback
import random
import uuid
import math
import gc
import base64
import json
import threading
from core.shared.utils import *
from get_data import Get_Data
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from ortools.sat.python import cp_model
from models.solver_models import Resources
from itertools import combinations
from core.shared.calculate_drive_time import (
    get_drive_time_data,
    return_interval_drive_time,
    post_drive_time_data,
)
from core.optimizer.cp_solver_handler import cp_solver_lambda_handler
from core.shared.utils import serialize_instance, deserialize_instance

# from utils.timing_utils import measure_time, visualize_timings


class _StopToken:
    """A mutable flag used by the watchdog to request an early stop."""

    stop_now = False


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables, heartbeat_event=0, stop_token=10000):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0
        self.time_now = 0
        self.objective = None
        self._beat = heartbeat_event
        self._stop_token = stop_token

    def OnSolutionCallback(self):
        self.__solution_count += 1
        ##HEARTBEAT
        # # ❶ pulse the heartbeat so the watchdog knows a solution arrived
        # self._beat.set()

        # # ❷ did watchdog request shutdown?
        # if self._stop_token.stop_now:
        #     print("Watchdog requested stop → stopping search.")
        #     self.StopSearch()
        # self.__solution_count += 1
        # walltime = self.WallTime()
        # objective_now = self.ObjectiveValue()
        # print(
        #     "liver1", walltime, self.objective, objective_now, walltime - self.time_now
        # )
        # if self.objective is None or self.objective + 1000 <= objective_now:
        #     self.time_now = walltime
        #     self.objective = objective_now
        # elif walltime - self.time_now > 50:
        #     print("stop now", walltime)
        #     self.StopSearch()
        ##HEARTBEAT

        for v in self.__variables:
            print("%s = %i" % (v, self.Value(v)), end=" ")

    def solution_count(self):
        return self.__solution_count


def watchdog(solver, beat_event, stop_token, wait_sec=10):
    """Kill the solve if no heartbeat for `wait_sec` seconds."""
    while True:
        if beat_event.wait(wait_sec):
            # got a solution → reset and wait again
            beat_event.clear()
        else:
            print(f"No solution in {wait_sec}s – stopping solver.")
            if hasattr(solver, "InterruptSolve"):  # OR-Tools ≥ 9.12
                solver.InterruptSolve()
            else:
                stop_token.stop_now = True  # triggers callback stop
            return


class Automate:
    def __init__(
        self,
        resources,
        roles_hierarchy,
        given_data,
        drive_data,
        resources_not,
        distance_matrix,
        solution1,
    ):
        self.model = cp_model.CpModel()
        self.testModel = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.solutions1 = solution1

        self.solver_value = {}
        self.constraint_booleans = {}
        self.constraint_booleans_soft = []
        self.constraint_booleans_hard = []
        self.break_booleans = {}
        self.soft_time_constraint_vars = {}
        self.caravel_session_length_constraints = []
        self.add_a_b_constraints = []

        self.min_max_amounts = {}

        self.see_here = []

        self.flags = solution1.get("flags", {})

        self.resources1 = Resources(solution1["users"])
        self.created_events = [event["data"] for event in solution1["created_events"]]
        self.distance_matrix = distance_matrix
        self.powerful_time = 400
        self.fast_time = 75
        self.max_time = (
            self.fast_time if given_data["mode"] == "fast" else self.powerful_time
        )
        self.var_data = given_data
        self.constraint_drive_data = drive_data
        self.roles_hierarchy = roles_hierarchy

        self.start_date = datetime.datetime.strptime(
            self.var_data["start_date"], "%Y-%m-%d"
        ).date()
        self.end_date = datetime.datetime.strptime(
            self.var_data["end_date"], "%Y-%m-%d"
        ).date()

        # True when the difference is more than 1 day, False otherwise
        self.is_week = (self.end_date - self.start_date).days > 1
        print(
            "self.is_week",
            self.is_week,
            (self.end_date - self.start_date).days,
            self.start_date,
            self.end_date,
        )

        self.resource_supervision_pair = [{}, {}, {}, {}, {}, {}, {}]

        self.scheduled_dict = {}
        self.person_blocks = {}
        self.gap_list = []
        self.events_break_session_length_long = {}
        self.events_break_session_length_short = {}
        self.blocks = []
        self.clients_durations = {i: 0 for i in self.find_ids_by_role(["Client"])}

        self.constraint_bols = []
        self.events_bol = []
        self.no_gap_priority = []
        self.gaps_to_minimize = []
        self.priority_array = []
        self.fake_gap_durations = []
        self.hard_bools = []
        self.block_slot_adam = []

        self.delete_bool = []
        self.update_bool = []
        self.deletable_events = []
        self.individual_fake_boolean = {}
        self.fake_whites = {}
        self.team_vals = {}
        self.created_fake_variables = {}
        self.not_updated_count = 0

        self.resource_gaps = [{}, {}, {}, {}, {}, {}, {}]
        self.resource_first_appointment_start = [{}, {}, {}, {}, {}, {}, {}]
        self.resource_last_appointment_end = [{}, {}, {}, {}, {}, {}, {}]

        self.bol_appointments_dict = {}
        self.persons_bol_appointments = {}
        self.count_fake = []
        self.disabled_constraints = []

        self.drive_time_data = {}
        self.over_availability_events = []
        self.availability_persons = []
        self.employees_ids = []

        self.best_objective_bound = 0
        self.min_obj = 0
        self.max_possible = 0
        self.direct_events_sum = 0
        self.orange_sum = 0
        self.del_bol_array = 0
        self.update_bol_array = 0
        self.objective_value = 0
        self.printer = []
        self.status_name = ""

        self.timings = {}
        self.matches_frequency_timings = {}

    def get_team_vals(self):
        return self.team_vals

    def get_status_name(self):
        return self.status_name

    def get_best_objective_bound(self):
        return self.best_objective_bound

    def find_ids_by_role(self, roles):
        resources_ids = []
        for id, resource in self.resources1.resources.items():
            for resource_role in resource.roles:
                if resource_role in self.roles_hierarchy.keys():
                    if (
                        len(intersection(roles, self.roles_hierarchy[resource_role]))
                        > 0
                    ):
                        resources_ids.append(id)
        return list(set(resources_ids))

    def get_appointments(self, resources_list, use_slots=True, slots={}):
        if use_slots:
            slots = self.resources1.slots

        if not slots:
            return {}

        resource_sets = [frozenset(resources) for resources in resources_list]

        appointments = {
            resource_ids: event
            for resource_ids, event in slots.items()
            if all(
                resource_set & frozenset(resource_ids) for resource_set in resource_sets
            )
        }

        return appointments

    # def add_a_b_schedule(self):
    #     # Only run for Caravel
    #     if (
    #         self.var_data.get("companyId") != "b51dfb8f-a6c4-41be-913c-19fe0d911062"
    #         or not self.is_week
    #     ):
    #         return

    #     direct_activity_id = "6adaecd0-ffb8-4011-8037-412569ca3dda"
    #     clients = list(set(self.find_ids_by_role(["Client"])))
    #     rbt = set(self.find_ids_by_role(["RBT"]))
    #     print("rbt2", rbt)
    #     bt = set(self.find_ids_by_role(["BT"]))
    #     print("bt3", bt)
    #     advrbt = set(self.find_ids_by_role(["AdvRBT"]))
    #     print("advrbt5", advrbt)
    #     employees = rbt | bt | advrbt
    #     print("trinklet", employees)

    #     client_employee_mwf = {}
    #     client_employee_tr = {}

    #     def extract_status(appointment):
    #         return appointment[6] if hasattr(appointment[6], "Not") else appointment[11]

    #     for client_id in clients:
    #         mwf_appointments = self.get_appointments(
    #             [[client_id], ["1", "3", "5"], [direct_activity_id]]
    #         )
    #         tr_appointments = self.get_appointments(
    #             [[client_id], ["2", "4"], [direct_activity_id]]
    #         )

    #         for schedule_dict, store in [
    #             (mwf_appointments, client_employee_mwf),
    #             (tr_appointments, client_employee_tr),
    #         ]:
    #             for key, value in schedule_dict.items():
    #                 status = extract_status(value)
    #                 for employee_id in key:
    #                     if employee_id in employees:
    #                         pair = (client_id, employee_id)
    #                         store.setdefault(pair, []).append(status)

    #     # Build constraints
    #     all_pairs = set(client_employee_mwf.keys()) | set(client_employee_tr.keys())
    #     for pair in all_pairs:
    #         bool_mwf = self.model.NewBoolVar("mwf_present")
    #         bool_tr = self.model.NewBoolVar("tr_present")
    #         bool_total = self.model.NewBoolVar("client_emp_pair_schedule")

    #         if pair in client_employee_mwf:
    #             self.model.AddMaxEquality(bool_mwf, client_employee_mwf[pair])
    #         else:
    #             self.model.Add(bool_mwf == 0)

    #         if pair in client_employee_tr:
    #             self.model.AddMaxEquality(bool_tr, client_employee_tr[pair])
    #         else:
    #             self.model.Add(bool_tr == 0)

    #         self.model.Add(bool_total + bool_mwf + bool_tr <= 2)
    #         self.constraint_booleans_soft.append(bool_total)
    def prefered_session_lengths(self):
        if self.var_data.get("companyId") != "b51dfb8f-a6c4-41be-913c-19fe0d911062":
            return
        c_min = 90 // self.var_data["slot_length"]
        c_max = 180 // self.var_data["slot_length"]
        direct_activity_id = "6adaecd0-ffb8-4011-8037-412569ca3dda"
        appts = self.get_appointments([[direct_activity_id]])
        for a in appts.values():
            b = self.model.NewBoolVar(f"ap")
            self.caravel_session_length_constraints.append(b)
            # happening = self.flag(a)
            self.model.Add(a[3] >= c_min).OnlyEnforceIf(b)
            self.model.Add(a[4] <= c_max).OnlyEnforceIf(b)
            # self.model.Add().OnlyEnforceIf(happening)

    def add_a_b_schedule(self):
        """
        Soft-score each client–employee pair per week:

            +3  → exactly Mon-Wed-Fri  (d1,d3,d5 = 1  and  d2,d4 = 0)
            +2  → exactly Tue-Thu      (d2,d4   = 1  and  d1,d3,d5 = 0)
            0  → idle, or any other weekday pattern
        """
        # ───────────────────── guard clause ────────────────────────────
        if (
            True
            or self.var_data.get("companyId") != "b51dfb8f-a6c4-41be-913c-19fe0d911062"
            or not self.is_week
        ):
            return
        c_min = 90 // self.var_data["slot_length"]

        direct_activity_id = "6adaecd0-ffb8-4011-8037-412569ca3dda"
        DAY_CODES = ["1", "2", "3", "4", "5"]  # 1=Mon … 5=Fri

        # ───────────── collect actors ──────────────────────────────────
        clients = set(self.find_ids_by_role(["Client"]))
        employees = (
            set(self.find_ids_by_role(["RBT"]))
            | set(self.find_ids_by_role(["BT"]))
            | set(self.find_ids_by_role(["AdvRBT"]))
        )

        # ───────────── (c,e,d) → list[BoolVar] of appointment flags ───

        appt_lists = defaultdict(list)
        for c in clients:
            for d in DAY_CODES:
                appts = self.get_appointments([[c], [d], [direct_activity_id]])
                for emp_set, row in appts.items():
                    f = self.flag(row)
                    for e in emp_set:
                        if e in employees:
                            appt_lists[(c, e, d)].append(f)

        # include idle pairs
        all_pairs = {(c, e) for c in clients for e in employees}

        for c, e in all_pairs:
            # ---- 0/1 “worked on weekday d” ----------------------------
            worked = {}
            for d in DAY_CODES:
                b = self.model.NewBoolVar(f"worked_{d}_{c}_{e}")
                lst = appt_lists.get((c, e, d), [])
                if lst:
                    self.model.AddMaxEquality(b, lst)  # OR of same-day appts
                else:
                    self.model.Add(b == 0)
                worked[d] = b

            d1, d2, d3, d4, d5 = (
                worked["1"],
                worked["2"],
                worked["3"],
                worked["4"],
                worked["5"],
            )

            # ---- M/W/F flag ------------------------------------------
            mwf = self.model.NewBoolVar(f"exact_MWF_{c}_{e}")
            self.model.Add(d1 + d3 + d5 == 3).OnlyEnforceIf(mwf)
            self.model.Add(d2 + d4 == 0).OnlyEnforceIf(mwf)
            self.model.Add(d1 + d3 + d5 != 3).OnlyEnforceIf(mwf.Not())

            # ---- T/R flag --------------------------------------------
            tr = self.model.NewBoolVar(f"exact_TR_{c}_{e}")
            self.model.Add(d2 + d4 == 2).OnlyEnforceIf(tr)
            self.model.Add(d1 + d3 + d5 == 0).OnlyEnforceIf(tr)
            self.model.Add(d2 + d4 != 2).OnlyEnforceIf(tr.Not())

            # ---- mutual exclusivity (optional but safe) --------------
            self.model.Add(mwf + tr <= 1)

            # ---- weighted soft objective -----------------------------
            # 3 copies of mwf → weight 3; 2 copies of tr → weight 2
            self.add_a_b_constraints.extend([mwf * 1, mwf * 1, mwf * 1, tr * 1, tr * 1])
            # self.constraint_booleans_soft.extend(
            #     [mwf * 1, mwf * 1, mwf * 1, tr * 1, tr * 1]
            # )

    # def add_a_b_schedule(self):
    #     """
    #     Add one IntVar score per (client, employee):

    #         score = +1 for every good 2-day combo  (MW, MF, WF, TR)
    #             – 1 for every other 2-day combo worked that week
    #             0 if the pair works 0 or 1 day

    #     Range: –6 … +4   (10 unordered weekday pairs)
    #     """
    #     # ───────── guard clause: only run in Caravel weekly master build ─────
    #     if (
    #         self.var_data.get("companyId") != "b51dfb8f-a6c4-41be-913c-19fe0d911062"
    #         or not self.is_week
    #     ):
    #         return

    #     direct_activity_id = "6adaecd0-ffb8-4011-8037-412569ca3dda"
    #     DAY_CODES = ["1", "2", "3", "4", "5"]  # 1=Mo … 5=Fr
    #     GOOD_PAIRS = {("1", "3"), ("1", "5"), ("3", "5"), ("2", "4")}  # MW MF WF TR

    #     # ───────── collect actors ────────────────────────────────────────────
    #     clients = set(self.find_ids_by_role(["Client"]))
    #     direct_activity_id = "6adaecd0-ffb8-4011-8037-412569ca3dda"

    #     # if self.data.get("part1") and self.is_week:
    #     for client_id in clients:
    #         for index in range(0, 6):
    #             client_val = self.get_appointments(
    #                 [[client_id], [direct_activity_id], [str(index)]]
    #             )
    #             cli = [num[6] for num in client_val.values()]
    #             if len(cli) > 0:
    #                 self.model.Add(sum(cli) <= 4)

    #     employees = (
    #         set(self.find_ids_by_role(["RBT"]))
    #         | set(self.find_ids_by_role(["BT"]))
    #         | set(self.find_ids_by_role(["AdvRBT"]))
    #     )

    #     # ───────── build (client, employee, day) → [BoolVar] list ────────────
    #     def flag(row):  # row[6] or row[11] is already Bool/0-1
    #         return row[6] if hasattr(row[6], "Not") else row[11]

    #     appt_lists = defaultdict(list)
    #     for c in clients:
    #         for d in DAY_CODES:
    #             appts = self.get_appointments([[c], [d], [direct_activity_id]])
    #             for emp_set, row in appts.items():
    #                 f = flag(row)
    #                 for e in emp_set:
    #                     if e in employees:
    #                         appt_lists[(c, e, d)].append(f)

    #     # container for the objective (create once)
    #     if not hasattr(self, "constraint_scores"):
    #         self.constraint_scores = []

    #     # include idle pairs too (so they still score 0)
    #     all_pairs = {(c, e) for c in clients for e in employees}

    #     for c, e in all_pairs:
    #         # ---- 0/1 worked on weekday d ------------------------------------
    #         worked = {}
    #         for d in DAY_CODES:
    #             b = self.model.NewBoolVar(f"worked_{d}_{c}_{e}")
    #             lst = appt_lists.get((c, e, d), [])
    #             if lst:
    #                 self.model.AddMaxEquality(b, lst)  # OR of same-day appts
    #             else:
    #                 self.model.Add(b == 0)
    #             worked[d] = b

    #         # ---- build a BoolVar for each unordered weekday pair ------------
    #         pair_vars_good = []
    #         pair_vars_bad = []

    #         for d1, d2 in combinations(DAY_CODES, 2):
    #             p = self.model.NewBoolVar(f"pair_{d1}{d2}_{c}_{e}")

    #             # p == AND(worked[d1], worked[d2])
    #             self.model.Add(p <= worked[d1])
    #             self.model.Add(p <= worked[d2])
    #             self.model.Add(p >= worked[d1] + worked[d2] - 1)

    #             if (d1, d2) in GOOD_PAIRS or (d2, d1) in GOOD_PAIRS:
    #                 pair_vars_good.append(p)
    #             else:
    #                 pair_vars_bad.append(p)

    #         # ---- sum good / bad pairs ---------------------------------------
    #         good_sum = self.model.NewIntVar(0, len(pair_vars_good), f"good_sum_{c}_{e}")
    #         bad_sum = self.model.NewIntVar(0, len(pair_vars_bad), f"bad_sum_{c}_{e}")
    #         self.model.Add(good_sum == sum(pair_vars_good))
    #         self.model.Add(bad_sum == sum(pair_vars_bad))

    #         # ---- final score  score = good_sum – bad_sum  -------------------
    #         score = self.model.NewIntVar(
    #             -len(pair_vars_bad), len(pair_vars_good), f"score_{c}_{e}"
    #         )
    #         self.model.Add(score == good_sum - bad_sum)

    #         # ---- push into objective list -----------------------------------
    #         self.constraint_booleans_hard.append(score * 10)

    # def add_a_b_schedule(self):
    #     """
    #     Per (client, employee) pair:

    #         score = (+1 × good two-day pairs)
    #             – (1 × bad  two-day pairs)
    #             – (1 × one-day-only pattern)

    #         good pairs: MW, MF, WF, TR
    #         idle (0 days) scores 0.
    #     """
    #     # ───────── guard clause ─────────
    #     if (
    #         True
    #         or self.var_data.get("companyId") != "b51dfb8f-a6c4-41be-913c-19fe0d911062"
    #         or not self.is_week
    #     ):
    #         return

    #     direct_activity_id = "6adaecd0-ffb8-4011-8037-412569ca3dda"
    #     DAY_CODES = ["1", "2", "3", "4", "5"]  # 1=Mo … 5=Fr
    #     GOOD_PAIRS = {("1", "3"), ("1", "5"), ("3", "5"), ("2", "4")}  # MW MF WF TR
    #     MAX_BAD_PAIRS = 6  # 10 total – 4 good
    #     SCORE_MIN = -(MAX_BAD_PAIRS + 1)  # +1 extra for possible one-day penalty
    #     SCORE_MAX = 4  # at most 4 good pairs in a 5-day week

    #     # ───────── actors ─────────
    #     clients = set(self.find_ids_by_role(["Client"]))
    #     employees = (
    #         set(self.find_ids_by_role(["RBT"]))
    #         | set(self.find_ids_by_role(["BT"]))
    #         | set(self.find_ids_by_role(["AdvRBT"]))
    #     )

    #     # optional daily cap already in your snippet
    #     # for client_id in clients:
    #     #     for idx in range(6):
    #     #         appts = self.get_appointments([[client_id], [direct_activity_id], [str(idx)]])
    #     #         caps  = [row[6] for row in appts.values()]
    #     #         if caps:
    #     #             self.model.Add(sum(caps) <= 4)

    #     # ───────── build (c,e,d) → [BoolVar] list ─────────
    #     def flag(row):
    #         return row[6] if hasattr(row[6], "Not") else row[11]

    #     appt_lists = defaultdict(list)
    #     for c in clients:
    #         for d in DAY_CODES:
    #             appts = self.get_appointments([[c], [d], [direct_activity_id]])
    #             for emp_set, row in appts.items():
    #                 f = flag(row)
    #                 for e in emp_set:
    #                     if e in employees:
    #                         appt_lists[(c, e, d)].append(f)

    #     # container for objective terms
    #     if not hasattr(self, "constraint_scores"):
    #         self.constraint_scores = []

    #     # evaluate every possible pair (idle pairs score 0)
    #     for c in clients:
    #         for e in employees:
    #             # ---- worked[d] booleans ----
    #             worked = {}
    #             for d in DAY_CODES:
    #                 b = self.model.NewBoolVar(f"worked_{d}_{c}_{e}")
    #                 lst = appt_lists.get((c, e, d), [])
    #                 if lst:
    #                     self.model.AddMaxEquality(b, lst)
    #                 else:
    #                     self.model.Add(b == 0)
    #                 worked[d] = b

    #             # ---- total days worked ----
    #             tot_days = self.model.NewIntVar(0, 5, f"tot_{c}_{e}")
    #             self.model.Add(tot_days == sum(worked.values()))

    #             # one-day penalty flag
    #             one_day = self.model.NewBoolVar(f"one_day_{c}_{e}")
    #             self.model.Add(tot_days == 1).OnlyEnforceIf(one_day)
    #             self.model.Add(tot_days != 1).OnlyEnforceIf(one_day.Not())

    #             # ---- pair scoring ----
    #             good_vars, bad_vars = [], []
    #             for d1, d2 in combinations(DAY_CODES, 2):
    #                 p = self.model.NewBoolVar(f"pair_{d1}{d2}_{c}_{e}")
    #                 self.model.Add(p <= worked[d1])
    #                 self.model.Add(p <= worked[d2])
    #                 self.model.Add(p >= worked[d1] + worked[d2] - 1)
    #                 if (d1, d2) in GOOD_PAIRS or (d2, d1) in GOOD_PAIRS:
    #                     good_vars.append(p)
    #                 else:
    #                     bad_vars.append(p)

    #             good_sum = self.model.NewIntVar(0, len(good_vars), f"good_{c}_{e}")
    #             bad_sum = self.model.NewIntVar(0, len(bad_vars), f"bad_{c}_{e}")
    #             self.model.Add(good_sum == sum(good_vars))
    #             self.model.Add(bad_sum == sum(bad_vars))

    #             # ---- final score ----
    #             score = self.model.NewIntVar(SCORE_MIN, SCORE_MAX, f"score_{c}_{e}")
    #             score2 = self.model.NewIntVar(SCORE_MIN, SCORE_MAX, f"score_{c}_{e}")
    #             self.model.Add(score == 0 - bad_sum - one_day)
    #             # self.model.Add(score == good_sum)

    #             # ---- push into objective list ----
    #             self.constraint_booleans_soft.append(
    #                 score * 10
    #             )  # same 10× weight you used

    # @measure_time
    def optimize_schedule_objective(self, id):
        # objective_role = self.var_data["objective_role"]
        # Get for all resources, no more objective role
        objective_role = ["Resource"]
        # Get for all resources, no more objective role
        objective_activity = self.var_data["objectiveactivity"]
        objective_activity_without = [
            activity
            for activity in objective_activity
            if activity not in self.var_data["notWorking"]
        ]
        objective_activity_not_working = [
            activity
            for activity in objective_activity
            if activity in self.var_data["notWorking"]
        ]

        # if self.var_data["run_with_teams"]:
        #     print("Running with teams")
        #     objective_role = [self.var_data["objective_role"][0]]
        # else:
        #     print("Running without teams")

        if self.var_data["is_lunch_constraint"]:
            self.var_data["maxEmployeeHoursPerDay"] += 0.5

        employees = list(set(self.find_ids_by_role(["Employee"])))
        clients = list(set(self.find_ids_by_role(["Client"])))
        people = employees + clients
        self.employees_ids = employees
        # This Break ordering broke Caravel
        # caravel
        # if self.var_data.get("companyId") == "b51dfb8f-a6c4-41be-913c-19fe0d911062":
        #     for emp_id in self.employees_ids:
        #         for index in range(0, 6):
        #             break1 = self.get_appointments(
        #                 [
        #                     [emp_id],
        #                     [str(index)],
        #                     ["20744cf1-0828-4777-acd4-99c9f9dbe28f"],
        #                 ]
        #             )
        #             break2 = self.get_appointments(
        #                 [
        #                     [emp_id],
        #                     [str(index)],
        #                     ["45f4ed9e-053e-402a-903f-6f86b7c7a329"],
        #                 ]
        #             )
        #             break1_ends = [num[4] for num in break1.values()]
        #             break2_starts = [num[3] for num in break2.values()]
        #             for b1 in break1_ends:
        #                 for b2 in break2_starts:
        #                     print("break_caravel")
        #                     self.model.Add(b1 <= b2)
        # This Break ordering broke Caravel

        av_arr_for_fake = {person_id: {i: [] for i in range(8)} for person_id in people}
        slot_length = (24 * 60) // self.var_data["slot_length"]
        for person_id in people:
            for slot in self.solutions1["user_availabilities_general"][person_id]:
                slot_index = slot[0] // slot_length
                av_arr_for_fake[person_id][slot_index].append(slot)

        val = self.get_appointments(
            [self.find_ids_by_role(objective_role), objective_activity]
        )
        val_without = self.get_appointments(
            [self.find_ids_by_role(objective_role), objective_activity_without]
        )
        val_not_working = self.get_appointments(
            [self.find_ids_by_role(objective_role), objective_activity_not_working]
        )
        percentage_now = self.var_data["percentage"]
        print('self.var_data["percentage"]', self.var_data["percentage"])
        if self.var_data["percentage"] != 0:
            self.var_data["percentage"] = 15
            percentage_now = 1
            del_bol_array, update_bol_array = [], []
            for appointment in val.values():
                if appointment[5]:
                    del_bol_array.append(appointment[11])
                    update_bol_array.append(appointment[16])

            if del_bol_array and update_bol_array:
                # self.model.Add(
                #     sum(del_bol_array)
                #     >= len(del_bol_array) - self.var_data["percentage"]
                # )
                # self.model.Add(
                #     sum(update_bol_array)
                #     >= len(update_bol_array) - self.var_data["percentage"] * 1
                #     # >= len(update_bol_array)
                # )
                self.model.Add(
                    sum(del_bol_array) + sum(update_bol_array)
                    >= len(del_bol_array)
                    + len(update_bol_array)
                    - self.var_data["percentage"]
                )
            else:
                self.model.Add(sum(del_bol_array) == 0)

        del_bol_array = self.delete_bool
        update_bol_array = self.update_bool

        try:
            appointments_dict = {}
            len_roles = len(objective_role)
            len_activities = len(objective_activity)

            for role_idx, role in enumerate(objective_role):
                for activity_idx, activity in enumerate(objective_activity):
                    key = (len_roles - role_idx) * (len_activities - activity_idx)
                    app_value = self.get_appointments(
                        [self.find_ids_by_role([role]), [activity]]
                    )
                    if key not in appointments_dict:
                        appointments_dict[key] = []
                    appointments_dict[key].append(app_value)

            white_durations, orange_durations = [], []
            not_work_durations = []
            white_durations_weighted, orange_durations_weighted = [], []
            white_priorities, orange_priorities = [], []
            white_on, orange_on = [], []
            all_keys = set()
            print("self.resources1.priorities", self.resources1.priorities)
            print("val_without.items()", val_without.items())
            # max_idx = len(objective_activity)
            max_idx = len(objective_activity_without)
            base = 1
            for key, appointment in val.items():
                all_keys.add(key)
            for key, appointment in val_not_working.items():
                not_work_durations.append(appointment[0])
            print("val_without", len(val_without.values()), len(val.values()))
            # Build all priorities first
            all_priorities = [
                self.resources1.priorities[k]["priorities"]
                for k in val_without.keys()
                if k in self.resources1.priorities
            ]

            # Normalize them
            normalized_map = {
                value: rank
                for rank, value in enumerate(sorted(set(all_priorities), reverse=True))
            }
            max_priorities = len(normalized_map)
            for key, appointment in val_without.items():
                # for key, appointment in val.items():
                # for activity_idx, activity in enumerate(objective_activity):
                for activity_idx, activity in enumerate(objective_activity_without):
                    if activity in key:
                        # ranking = (10 - activity_idx)*1000
                        # ranking = base * 2 ** (max_idx - activity_idx)
                        ranking = base * 5 ** (max_idx - activity_idx)
                        print("ranking1", ranking)
                        print("priority_key", key)
                        if key in self.resources1.priorities:
                            priority = self.resources1.priorities[key]["priorities"]
                            normalized_priority = normalized_map.get(
                                priority, len(normalized_map) + 1
                            )
                            ranking2 = base * 2 ** (
                                max_priorities - normalized_priority
                            )
                            print(
                                "normalized_priority",
                                max_priorities,
                                normalized_priority,
                                ranking2,
                            )
                            print("herro_priority", priority)
                            if not appointment[10]:
                                white_durations.append(appointment[0])
                                white_durations_weighted.append(
                                    appointment[0] * ranking * ranking2
                                )
                                white_priorities.append(appointment[0] * priority)
                                white_on.append(self.flag(appointment))
                            else:
                                orange_durations.append(appointment[0])
                                orange_durations_weighted.append(
                                    appointment[0] * ranking * ranking2
                                )
                                orange_priorities.append(appointment[0] * priority)
                                orange_on.append(self.flag(appointment))

            for key, slot in self.resources1.slots.items():
                if key not in all_keys and not slot[5]:
                    print("gotcha2")
                    # self.model.Add(slot[0] == 0)

            # self.solver.parameters.search_branching = cp_model.FIXED_SEARCH
            # self.model.AddDecisionStrategy(
            #     self.constraint_booleans_hard + white_durations + orange_durations,
            #     cp_model.CHOOSE_FIRST,
            #     cp_model.SELECT_MAX_VALUE,
            # )

            analyzer_booleans = list(self.constraint_booleans.values())
            analyzer_score = self.model.NewIntVar(
                0, len(analyzer_booleans), "analyzer_score"
            )
            # self.constraint_booleansself.constraint_booleans self.model.Add(analyzer_score == sum(analyzer_booleans))
            # self.model.Add(len(self.constraint_booleans_hard) == sum(self.constraint_booleans_hard))
            # self.model.Add(len(self.constraint_booleans_soft) == sum(self.constraint_booleans_soft))
            self.model.Add(sum(white_durations + orange_durations) > 0)

            # self.testModel.CopyFrom(self.model)
            self.testModel = self.model.clone()
            flat_resource_gaps = [
                gap_var  # the IntVar itself
                for gap_dict in self.resource_gaps  # loop over each dict in the list
                for gap_var in gap_dict.values()  # grab every IntVar in that dict
            ]
            # caravel
            print("flat_resource_gaps", flat_resource_gaps)
            if (
                True
                or self.var_data.get("companyId")
                == "b51dfb8f-a6c4-41be-913c-19fe0d911062"
            ):
                print(
                    "caravel company",
                    len(white_on),
                    len(orange_on),
                )
                # val_direct = []
                # if (
                #     self.var_data.get("companyId")
                #     == "b51dfb8f-a6c4-41be-913c-19fe0d911062"
                # ):
                #     direct_activity_id = "2faf27ca-9120-486c-9738-83714f0ee50d"
                # val = self.get_appointments([direct_activity_id])
                # print("looker2", len(val))
                # val_direct = [v[0] for v in val.values()]
                if self.var_data["percentage"] != 0:
                    self.model.Maximize(
                        sum(flat_resource_gaps) * -1 * (10**10)
                        + sum(self.constraint_booleans_hard) * (10**8)
                        + sum(white_durations_weighted + orange_durations_weighted)
                        * (10**4)
                        - sum(orange_durations_weighted) * (10**2)
                        + sum(self.constraint_booleans_soft) * 1
                        + sum(del_bol_array) * 500
                        - sum(not_work_durations) * 1
                        + sum(update_bol_array) * 300
                        - sum(white_on + orange_on) * (10**1)
                    )
                else:
                    print("lovve")
                    self.model.Maximize(
                        sum(del_bol_array) * (10**12)
                        + sum(flat_resource_gaps) * -1 * (10**10)
                        + sum(self.constraint_booleans_hard) * (10**8)
                        + sum(white_durations_weighted + orange_durations_weighted)
                        * (10**4)
                        - sum(orange_durations_weighted) * (10**2)
                        + sum(self.constraint_booleans_soft) * 1
                        - sum(not_work_durations) * 1
                        + sum(update_bol_array) * 300
                        - sum(white_on + orange_on) * (10**1)
                    )

            else:
                self.model.Maximize(
                    sum(white_durations + orange_durations) * 10000
                    + sum(del_bol_array) * 500
                    + sum(update_bol_array) * 300
                    + sum(white_priorities + orange_priorities) * 100
                    + sum(
                        var
                        for constraints in self.soft_time_constraint_vars.values()
                        for var in constraints
                    )
                    * 100
                    - sum(white_on)
                    - sum(orange_on) * 2
                )

            self.testModel.Maximize(analyzer_score)

        except Exception as e:
            print("Error occurred : ", e)
            traceback.print_exc()

    def solve_with_analyzer(self):
        max_time = self.var_data.get("max_time_in_seconds", 180.0)

        print("🔍 Running Initial Optimization...")

        # Initialize Solver
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.max_time
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.num_search_workers = os.cpu_count()
        self.solver.parameters.random_seed = 42
        self.solver.log_frequency_in_seconds = 10
        self.solver.num_violation_ls = 2  # guideline: workers // 8
        self.solver.random_half_branching = True  # new branching heuristic
        self.solver.share_level = 2  # share bounds + objective
        # init_model = cp_model.CpModel()
        init_model = self.model.clone()
        # init_model.CopyFrom(self.model)
        # for constraint_id, bool_var in self.constraint_booleans.items():
        #     init_model.Add(bool_var == 1)

        # shared objects
        ##HEARTBEAT
        # beat_event = threading.Event()
        # stop_token = _StopToken()
        # solution_printer = VarArraySolutionPrinter([], beat_event, stop_token)
        ##HEARTBEAT
        solution_printer = VarArraySolutionPrinter([])
        self.printer = solution_printer
        ##HEARTBEAT
        # start watchdog thread
        # threading.Thread(
        #     target=watchdog,
        #     args=(self.solver, beat_event, stop_token, 1),  # 5-second stall limit
        #     daemon=True,
        # ).start()
        ##HEARTBEAT

        status = self.solver.Solve(init_model, self.printer)

        print(f"🔹 Initial Solver Status: {self.solver.StatusName(status)}")

        if status == cp_model.FEASIBLE or status == cp_model.OPTIMAL:
            print(f"✅ Initial Optimization was {status}. Returning Solution.")
            self.status_name = self.solver.StatusName(status)
            self.best_objective_bound = self.solver.BestObjectiveBound()
            self.objective_value = self.solver.ObjectiveValue()

            enforced_constraints = {}
            count = 0
            for user_a_id, constraints in self.soft_time_constraint_vars.items():
                enforced_count = 0
                for soft_var in constraints:
                    value = self.solver.Value(soft_var)
                    if value == 1:
                        enforced_count += 1
                        enforced_constraints[soft_var.Name()] = value

                count += enforced_count
                print(
                    f"Employee {user_a_id}: {enforced_count} time constraints enforced."
                )

            print(f"Total Time Constraints Enforced: {count}")
            return

        print("❌ Initial Optimization was Infeasible. Running Analyzer...")

        constraints_to_disable = []

        print("✅ Start Analyzer Solver...")

        test_solver = cp_model.CpSolver()
        test_solver.parameters.max_time_in_seconds = self.max_time
        test_solver.parameters.log_search_progress = True
        test_solver.parameters.random_seed = 42
        test_solver.parameters.num_search_workers = os.cpu_count()
        test_solver.log_frequency_in_seconds = 10
        test_solver.num_violation_ls = 2  # guideline: workers // 8
        test_solver.random_half_branching = True  # new branching heuristic
        test_solver.share_level = 2  # share bounds + objective
        test_status = test_solver.Solve(self.testModel, solution_printer)

        if test_status == cp_model.FEASIBLE or test_status == cp_model.OPTIMAL:
            print("✅ Solution Found:")
            for constraint_id, boolean_var in self.constraint_booleans.items():
                value = test_solver.Value(boolean_var)
                if value == 0:
                    constraints_to_disable.append(constraint_id)
                status_text = "ENABLED" if value == 1 else "DISABLED"
                constraint = next(
                    (
                        item
                        for item in self.solutions1["resources1"][
                            "frequency_constraints"
                        ]
                        if item["id"] == constraint_id
                    ),
                    None,
                )
                print(
                    f"🔹constraint {constraint_id}({constraint['type']}-{constraint['description'] if 'description' in constraint else 'No description'}): {status_text}"
                )
        else:
            print("Return infeasible value")

        print(f"🔹Disabled Constraints: {constraints_to_disable}")

        # ✅ Skip re-solving if no constraints were disabled
        if not constraints_to_disable:
            print("🔁 No constraints were disabled. Skipping re-solve.")
            self.status_name = test_solver.StatusName(test_status)
            self.best_objective_bound = test_solver.BestObjectiveBound()
            self.objective_value = test_solver.ObjectiveValue()
            self.disabled_constraints = []
            return  # ⛔ Exit early

        for constraint_id, bool_var in self.constraint_booleans.items():
            if constraint_id in constraints_to_disable:
                self.model.Add(bool_var == 0)
            else:
                self.model.Add(bool_var == 1)

        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.max_time
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.random_seed = 42
        self.solver.parameters.num_search_workers = os.cpu_count()
        self.solver.log_frequency_in_seconds = 10
        self.solver.num_violation_ls = 2  # guideline: workers // 8
        self.solver.random_half_branching = True  # new branching heuristic
        self.solver.share_level = 2  # share bounds + objective

        print("🔄 Re-solving with infeasible constraints removed...")
        status = self.solver.Solve(self.model, solution_printer)

        print(f"Solver finished with status: {self.solver.StatusName(status)}")
        self.status_name = self.solver.StatusName(status)
        self.best_objective_bound = self.solver.BestObjectiveBound()
        self.objective_value = self.solver.ObjectiveValue()

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            print("✅ Solution Found:")
            for constraint_id, boolean_var in self.constraint_booleans.items():
                value = self.solver.Value(boolean_var)
                status_text = "ENABLED" if value == 1 else "DISABLED"
                constraint = next(
                    (
                        item
                        for item in self.solutions1["resources1"][
                            "frequency_constraints"
                        ]
                        if item["id"] == constraint_id
                    ),
                    None,
                )
                print(
                    f"🔹constraint {constraint_id}({constraint['type']}-{constraint['description'] if 'description' in constraint else 'No description'}): {status_text}"
                )
            print(f"🔹Disabled Constraints: {constraints_to_disable}")
            self.disabled_constraints = constraints_to_disable
        else:
            print("❌ No feasible solution found.")

    def call_cp_solver(self, url, payload):
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error calling Lambda URL: {e}")
            return {"error": str(e)}

    # @measure_time
    def solve(self):
        max_time = (
            240.0
            if self.var_data.get("companyId") == "090121f7-8598-463e-92c4-f501c2576e60"
            else self.var_data.get("max_time_in_seconds", 180.0)
        )
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.max_time
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.num_search_workers = os.cpu_count()
        self.solver.log_callback = print
        solution_printer = VarArraySolutionPrinter([])
        self.printer = solution_printer
        self.solver.parameters.random_seed = 42

        self.solver.log_frequency_in_seconds = 10
        self.solver.num_violation_ls = 2  # guideline: workers // 8
        self.solver.random_half_branching = True  # new branching heuristic
        self.solver.share_level = 2  # share bounds + objective

        status = self.solver.Solve(self.model, solution_printer)
        self.status_name = self.solver.StatusName(status)
        self.best_objective_bound = self.solver.BestObjectiveBound()
        self.objective_value = self.solver.ObjectiveValue()

    # @measure_time
    def data_insert(self, data):
        current_utc_time = datetime.datetime.now(datetime.timezone.utc).time()
        now = str(current_utc_time)[:8]

        people5 = self.find_ids_by_role(["Person"])
        activity5 = self.find_ids_by_role(["Activity"])
        resource5 = self.find_ids_by_role(["Resource"])
        funders = self.find_ids_by_role(["Funder"])
        location_ids = self.find_ids_by_role(["Location"])
        clients_ids = self.find_ids_by_role(["Client"])
        emp_ids = self.find_ids_by_role(["Employee"])

        not_in = set(funders + location_ids)
        resource_without_funder = [r for r in resource5 if r not in not_in]

        av_arr_for_fake_raw = self.solutions1["user_availabilities_general"]
        av_arr_for_fake = {id: {i: [] for i in range(8)} for id in people5}
        people_array_filter = []

        slot_length = (24 * 60) // self.var_data["slot_length"]
        for person_id in people5:
            for slot in av_arr_for_fake_raw[person_id]:
                index = slot[0] // slot_length
                av_arr_for_fake[person_id][index].append(slot)

        self.availability_persons = av_arr_for_fake

        self.persons_bol_appointments = {person: [] for person in people5}

        waitlist_count = 1
        event_ids = []
        # fake_events = sum(
        #     (
        #         self.var_data["fake_user_starts_ends"][ss_id]["fakes"]
        #         for ss_id in people5
        #     ),
        #     [],
        # )
        fake_events = []
        data_arr = data + self.created_events + self.var_data["gg"] + fake_events

        priority_arr = []
        key_to_tuple = {}
        print("data_arr2", data_arr)
        for info in data_arr:
            if not info.get("scheduled"):
                slots = time_to_int(info, self.var_data["slot_length"])
                interval_start, duration, interval_end = slots[:3]

                resource_ids = [res[:-1] for res in info["resourceIds"]]
                people_array_filter += intersection(people5, resource_ids)

                intersection_of_resources = sorted(
                    set(intersection(resource_without_funder, resource_ids))
                )
                resource_list = [
                    res[:-1] if not info["scheduled"] else res
                    for res in sorted(info["resourceIds"])
                ]
                weekday_index = interval_start // (
                    (24 * 60) // self.var_data["slot_length"]
                )
                my_obj = {
                    "start": interval_start,
                    "duration": duration,
                    "end": interval_end,
                    "key": (
                        tuple([interval_start])
                        + tuple([interval_end])
                        + tuple(["not_scheduled"])
                        + tuple([str(weekday_index)])
                        + tuple(resource_list)
                    ),
                }

                self.bol_appointments_dict[tuple(intersection_of_resources)] = []
                if tuple(intersection_of_resources) in self.scheduled_dict.keys():
                    self.scheduled_dict[tuple(intersection_of_resources)].append(my_obj)
                else:
                    self.scheduled_dict[tuple(intersection_of_resources)] = [my_obj]

            loc_id2 = info.get("loc_id2", "")
            priority = info.get("priority")
            if isinstance(priority, int) and priority not in priority_arr:
                priority_arr.append(priority)

        priority_arr.sort(reverse=True)

        current_time = f"{self.var_data['start_date']}T{now}.000Z"
        current_time_slot = time_to_int(
            {"start": current_time, "end": current_time}, self.var_data["slot_length"]
        )[0]

        counter = 0
        data_arr.sort(key=lambda info: info["scheduled"])
        skip_these = []
        for info in data_arr:
            block = info.get("block", 0) if self.var_data["part1"] else 0
            weight = (
                priority_arr.index(info["priority"]) * 10000
                if isinstance(info.get("priority"), int)
                else 0
            )

            slots = time_to_int(info, self.var_data["slot_length"])
            interval_start = slots[0]
            duration = slots[1]
            interval_end = slots[2]
            weekday_index = slots[3]

            address = info.get("address", None)
            loc_id = info.get("loc_id", "")

            yellow_sol = info.get("ov", False)
            info["id"] = info.get("id", str(uuid.uuid4()))

            resource_list = [
                res[:-1] if not info["scheduled"] else res
                for res in sorted(info["resourceIds"])
            ]

            intersection_of_resources = sorted(
                list(
                    set(
                        intersection(
                            resource_without_funder,
                            [i[:-1] for i in info["resourceIds"]],
                        )
                    )
                )
            )
            if not info["scheduled"] and duration > 0:
                fake_bool = False
                if "capacity" in info.keys():
                    duration = info["end_r"] - info["start_r"]
                    interval_start = info["start_r"]
                    interval_end = info["end_r"]

                duration_int = self.model.NewIntVar(
                    0, duration, f'session_length_{info["title"]}_{duration}'
                )
                start_int = self.model.NewIntVar(
                    interval_start, interval_end, f"start_{interval_start}"
                )
                end_int = self.model.NewIntVar(
                    interval_start, interval_end, f"end_{interval_end}"
                )
                bol_appointment = self.model.NewBoolVar(f'bol_{info["id"]}')

                if "capacity" in info.keys():
                    self.model.Add(duration_int == duration).OnlyEnforceIf(
                        bol_appointment
                    )
                    self.model.Add(start_int == interval_start).OnlyEnforceIf(
                        bol_appointment
                    )
                    self.model.Add(end_int == interval_end).OnlyEnforceIf(
                        bol_appointment
                    )
                    # self.model.Add(duration_int == 0).OnlyEnforceIf(
                    #     bol_appointment.Not()
                    # )
                    # self.model.Add(duration_int == duration).OnlyEnforceIf(bol_appointment)
                    counter = counter + 1
                # print('seeker',info)
                # print('yimmer',info["priority"])
                self.priority_array.append(info["priority"] * bol_appointment)

                event_interval = self.model.NewOptionalIntervalVar(
                    start_int, duration_int, end_int, bol_appointment, "interval"
                )

                priority_actual = max(1, 1000 - int(info.get("priority", 0)))
                resource_tuple = tuple(intersection_of_resources)

                if resource_tuple in self.scheduled_dict.keys():
                    for n in self.scheduled_dict[resource_tuple]:
                        if interval_start >= n["start"] and interval_end <= n["end"]:
                            n.update({"bol_appointment": bol_appointment})
                            n.update({"priority": priority_actual})

                for resource_id in intersection_of_resources:
                    if resource_id in self.persons_bol_appointments:
                        self.persons_bol_appointments[resource_id].append(
                            bol_appointment
                        )

                self.model.Add(duration_int == 0).OnlyEnforceIf(bol_appointment.Not())
                self.model.Add(duration_int > 0).OnlyEnforceIf(bol_appointment)

                self.bol_appointments_dict[tuple(intersection_of_resources)].append(
                    bol_appointment
                )

                weekday_index = interval_start // (
                    (24 * 60) // self.var_data["slot_length"]
                )

                self.resources1.priorities[
                    tuple([interval_start])
                    + tuple([interval_end])
                    + tuple(["not_scheduled"])
                    + tuple([str(weekday_index)])
                    + tuple(resource_list)
                ] = {"priorities": priority_actual, "faker": False, "info": info}

                key_to_tuple[resource_tuple] = (
                    tuple([interval_start])
                    + tuple([interval_end])
                    + tuple(["not_scheduled"])
                    + tuple([str(weekday_index)])
                    + tuple(resource_list)
                )

                self.resources1.slots[
                    tuple([interval_start])
                    + tuple([interval_end])
                    + tuple(["not_scheduled"])
                    + tuple([str(weekday_index)])
                    + tuple(resource_list)
                ] = [
                    duration_int,
                    1,
                    event_interval,
                    start_int,
                    end_int,
                    False,
                    bol_appointment,
                    address,
                    waitlist_count,
                    info["id"],
                    info["orange_sol"],
                    2,
                    loc_id,
                    yellow_sol,
                    weight,
                    loc_id2,
                    2,
                    fake_bool,
                    False,
                    duration,
                ]

            if info["scheduled"]:
                print("loopie")
                # if intersection(info["resourceIds"], self.var_data["nonbillable"]):
                #     info.update({"type": "delete"})
                #     self.over_availability_events.append(info)
                #     continue

                inter_notWorking = intersection(
                    info["resourceIds"], self.var_data["notWorking"]
                )

                bol_users = "users" in info
                faker = "faker" in info

                # if self.var_data["lunch_id"] in info["resourceIds"] or (
                #     bol_users and str(self.var_data["lunch_id"]) in info["users"]
                # ):
                #     if faker:
                #         continue
                #     info.update({"type": "delete"})
                #     if not faker:
                #         self.over_availability_events.append(info)

                #     continue

                # if self.var_data.get("admin_id") in info["resourceIds"]:
                #     info.update({"type": "delete"})
                #     self.over_availability_events.append(info)
                #     continue

                # if inter_notWorking and intersection(
                #     inter_notWorking, self.var_data["objectiveactivity"]
                # ):
                #     info.update({"type": "delete"})
                #     self.over_availability_events.append(info)
                #     continue
                #     self.var_data["percentage"] += 1

                con = False

                for constraint in self.solutions1["resources1"][
                    "frequency_constraints"
                ]:
                    if constraint["type"] == "sessionlength":
                        c_min = (
                            int(constraint["minSeconds"])
                            // 60
                            // self.var_data["slot_length"]
                        )
                        c_max = (
                            int(constraint["maxSeconds"])
                            // 60
                            // self.var_data["slot_length"]
                        )

                        for user_c in constraint["users_consequence"]:
                            user_c_id = self.solutions1["resources1"]["resources"][
                                user_c
                            ].id
                            if user_c_id in info["resourceIds"]:
                                if duration > c_max:
                                    self.events_break_session_length_long[
                                        info["id"]
                                    ] = duration
                                elif duration < c_min:
                                    self.events_break_session_length_short[
                                        info["id"]
                                    ] = duration
                                break

                other_branches_activity = any(
                    id_b not in resource5 for id_b in info["resourceIds"]
                )
                weekday_index = interval_start // (
                    (24 * 60) // self.var_data["slot_length"]
                )

                for res_id in info["resourceIds"]:
                    if res_id not in av_arr_for_fake.keys():
                        continue

                    availability = av_arr_for_fake[res_id][weekday_index]
                    if not availability:
                        continue

                    set_a = {
                        time
                        for interval in availability
                        for time in range(interval[0], interval[1] + 1)
                    }
                    print("interval_start2", interval_start, interval_end)
                    set_b = set(range(interval_start, interval_end + 1))
                    if set_b - set_a:
                        pass_event = True

                id_for_bool = info["id"]
                fake_bool = info.get("title") == "ByPass Activity"
                orange_sol = info.get("orange_sol", False)

                del_bol = self.model.NewBoolVar("del_bol")
                update_bol = self.model.NewBoolVar("update_bol")

                if other_branches_activity or (
                    datetime.datetime.now().date()
                    == datetime.datetime.strptime(
                        self.var_data["start_date"], "%Y-%m-%d"
                    ).date()
                    and interval_start < current_time_slot
                ):
                    self.model.Add(del_bol == 1)
                    self.model.Add(update_bol == 1)

                start_int_bol = self.model.NewBoolVar(f"start_int_bol-{id_for_bool}")
                end_int_bol = self.model.NewBoolVar(f"end_int_bol-{id_for_bool}")

                if info["id"] == "e139c6b3-7472-4632-af5d-839b8eeda688":
                    print("ladida", info["resourceIds"], info)
                resource_list = sorted(set(info["resourceIds"]))
                intersection_of_resources = sorted(
                    set(intersection(resource_without_funder, info["resourceIds"]))
                )

                interval_start_embed, interval_end_embed = interval_start, interval_end

                emp_id_arr = sorted(intersection(emp_ids, info["resourceIds"]))
                client_id_arr = sorted(intersection(clients_ids, info["resourceIds"]))

                client_id = client_id_arr[0] if client_id_arr else None
                emp_id2 = emp_id_arr[0] if emp_id_arr else None

                need_arr = []
                if client_id and emp_id_arr:
                    for emp_id in emp_id_arr:
                        if emp_id != emp_id2:
                            tup = tuple(sorted([client_id, emp_id]))
                            need_arr.extend(
                                n["bol_appointment"]
                                for n in self.scheduled_dict.get(tup, [])
                            )

                priority_actual = 5
                update_false = False
                resource_tuple = tuple(intersection_of_resources)

                if resource_tuple in self.scheduled_dict:

                    for n in self.scheduled_dict[resource_tuple]:
                        if not (
                            n["end"] < interval_start_embed
                            or n["start"] > interval_end_embed
                        ):
                            start_end_union = set(
                                range(n["start"], n["end"] + 1)
                            ).union(range(interval_start_embed, interval_end_embed + 1))
                            if start_end_union and intersection(
                                self.var_data["objectiveactivity"], info["resourceIds"]
                            ):
                                if self.var_data["lunch_id"] not in info["resourceIds"]:
                                    interval_start_embed = min(start_end_union)
                                    interval_end_embed = max(start_end_union)
                                    update_false = True
                                    priority_actual = n["priority"]
                                    self.model.Add(n["bol_appointment"] == 0)
                                self.resources1.slots.pop(n["key"], None)
                                break

                if not update_false:
                    self.not_updated_count += 1

                start_int = self.model.NewIntVar(
                    interval_start_embed, interval_end_embed, f"start-{id_for_bool}"
                )
                duration_int = self.model.NewIntVar(
                    0,
                    interval_end_embed - interval_start_embed,
                    f"duration-{id_for_bool}",
                )
                end_int = self.model.NewIntVar(
                    interval_start_embed, interval_end_embed, f"end-{id_for_bool}"
                )
                event_interval = self.model.NewOptionalIntervalVar(
                    start_int, duration_int, end_int, del_bol, f"interval-{id_for_bool}"
                )

                self.model.Add(start_int == interval_start).OnlyEnforceIf(start_int_bol)
                self.model.Add(end_int == interval_end).OnlyEnforceIf(end_int_bol)
                self.model.Add(start_int != interval_start).OnlyEnforceIf(
                    start_int_bol.Not()
                )
                self.model.Add(end_int != interval_end).OnlyEnforceIf(end_int_bol.Not())

                self.model.Add(start_int_bol + end_int_bol < 2).OnlyEnforceIf(
                    update_bol.Not()
                )
                self.model.Add(duration_int > 0).OnlyEnforceIf(update_bol.Not())
                self.model.Add(start_int_bol + end_int_bol == 2).OnlyEnforceIf(
                    update_bol
                )

                practice_bol = True
                self.model.AddHint(del_bol, 1)
                self.model.AddHint(update_bol, 1)

                if self.var_data["percentage"] == 0 or (
                    practice_bol
                    and not intersection(
                        self.var_data["objectiveactivity"], info["resourceIds"]
                    )
                ):
                    # self.model.Add(del_bol == 1)
                    self.model.Add(update_bol == 1)

                self.model.Add(duration_int > 0).OnlyEnforceIf(del_bol)
                self.model.Add(duration_int == 0).OnlyEnforceIf(del_bol.Not())

                weekday_index = interval_start // (
                    (24 * 60) // self.var_data["slot_length"]
                )

                resource_key = (
                    tuple([interval_start])
                    + tuple([interval_end])
                    + tuple(["scheduled"])
                    + tuple([str(weekday_index)])
                    + tuple(resource_list)
                )
                if info["id"] == "e139c6b3-7472-4632-af5d-839b8eeda688":
                    print("ladida4", info["resourceIds"], info)

                if info["id"] not in event_ids:
                    self.resources1.priorities[resource_key] = {
                        "priorities": priority_actual,
                        "faker": faker,
                        "info": info,
                    }
                    if info["id"] == "e139c6b3-7472-4632-af5d-839b8eeda688":
                        print("ladida3", info["resourceIds"], info)

                    self.resources1.slots[resource_key] = [
                        duration_int,
                        1,
                        event_interval,
                        start_int,
                        end_int,
                        True,
                        1,
                        address,
                        waitlist_count,
                        info["id"],
                        orange_sol,
                        del_bol,
                        loc_id,
                        yellow_sol,
                        weight,
                        loc_id2,
                        update_bol,
                        fake_bool,
                        con,
                        duration,
                    ]
                    resource_key_intersection = tuple(intersection_of_resources)

                    if info["title"] != "ByPass Activity":
                        if info["id"] == "e139c6b3-7472-4632-af5d-839b8eeda688":
                            print("ladida2", info["resourceIds"], info)

                        if (
                            resource_key_intersection
                            in self.bol_appointments_dict.keys()
                        ):
                            self.bol_appointments_dict[
                                resource_key_intersection
                            ].append(del_bol)
                        else:
                            self.bol_appointments_dict[resource_key_intersection] = [
                                del_bol
                            ]

                        for i in intersection_of_resources:
                            if i in self.persons_bol_appointments:
                                self.persons_bol_appointments[i].append(del_bol)

                    self.delete_bool.append(del_bol)
                    self.update_bool.append(update_bol)
                    if info["title"] != "ByPass Activity":
                        self.direct_events_sum += duration
                    client_intersections = intersection(clients_ids, resource_list)
                    self.deletable_events.append(info)
                    if len(client_intersections) >= 1:
                        if info["title"] != "ByPass Activity":
                            self.clients_durations[client_intersections[0]] += duration
                event_ids.append(info["id"])
                event_ids = list(set(event_ids))
        # for key in skip_these:  # iterate over the keys you want to remove
        #     self.resources1.slots.pop(key, None)
        # .pop(key, None) removes the entry if it exists;
        # the second arg (None) prevents KeyError if it’s missing

    # @measure_time
    def no_overlap(self, e_pair):
        supervision_activity_id = "1b1b9fe3-a96a-4074-97d4-1f5767a84428"
        direct_activity_id = "6adaecd0-ffb8-4011-8037-412569ca3dda"
        clinicDirector = set(self.find_ids_by_role(["Clinic Director"]))
        bcba = set(self.find_ids_by_role(["BCBA"]))
        bcaba = set(self.find_ids_by_role(["BCaBa"]))
        seniorintern = set(self.find_ids_by_role(["Senior Intern"]))
        seniortherapist = set(self.find_ids_by_role(["Senior Therapist"]))
        supervisory_staff = (
            bcba | bcaba | seniorintern | seniortherapist | clinicDirector
        )
        print("supervisory_staff", supervisory_staff)
        print("self.resources1.slots", self.resources1.slots)
        client_ids = set(self.find_ids_by_role(["Client"]))
        employee_ids = set(self.find_ids_by_role(["Employee"]))
        for index in range(0, 6):
            supervision_key_list = []
            direct_key_list = []
            for key, value in self.resources1.slots.items():
                if value[9] == "e139c6b3-7472-4632-af5d-839b8eeda688":
                    print("lookie here", key, value)
                tuple_list = list(key)
                print("tuple_list2", index, tuple_list)
                if str(index) in tuple_list:
                    print("tuple_list1", index, tuple_list)
                    if (
                        supervision_activity_id in tuple_list
                        or f"{supervision_activity_id}a" in tuple_list
                    ):
                        supervision_key_list.append(tuple_list)
                    if value[9] == "e139c6b3-7472-4632-af5d-839b8eeda688":
                        print(
                            "lookie here9",
                            key,
                            value,
                            direct_activity_id,
                            tuple_list,
                            direct_activity_id in tuple_list,
                        )
                    if (
                        direct_activity_id in tuple_list
                        or f"{direct_activity_id}a" in tuple_list
                    ):
                        direct_key_list.append(key)

            print("triplet", direct_key_list)
            print("self.resources1.slots5", self.resources1.slots)
            for s in supervision_key_list:
                s_resources = s[4:]
                # print('ruffer2',s_resources)
                s_ortool = self.resources1.slots[tuple(s)]
                is_found = False
                if s_ortool[9] == "f9d4f797-bd9a-4732-9385-03ca660d1cd1":
                    print("found you", s_ortool)
                for i, d in enumerate(direct_key_list):
                    # print("flicker3", self.resources1.slots[d][9])
                    # print("clivver", d)
                    # if (
                    #     self.resources1.slots[d][9]
                    #     == "e139c6b3-7472-4632-af5d-839b8eeda688"
                    # ):
                    #     print("found you45", d)

                    d_resources = list(d)[4:]
                    # print('ruffer1',s_resources,d_resources,list(intersection(s_resources,d_resources)))
                    intersected_resources = list(intersection(s_resources, d_resources))
                    if s_ortool[9] == "f9d4f797-bd9a-4732-9385-03ca660d1cd1":
                        print(
                            "found you maybe6",
                            intersected_resources,
                            d,
                            self.resources1.slots[d][9],
                        )
                        if (
                            self.resources1.slots[d][9]
                            == "e139c6b3-7472-4632-af5d-839b8eeda688"
                        ):
                            print("wower", d)
                    if (
                        s_ortool[9] == "f9d4f797-bd9a-4732-9385-03ca660d1cd1"
                        and len(intersected_resources) > 0
                    ):
                        print("found you maybe3", intersected_resources)
                        print("found you maybe4", s, d)

                    if (
                        len(intersected_resources) == 2
                        and len(
                            [
                                rid
                                for rid in intersected_resources
                                if rid not in supervisory_staff
                            ]
                        )
                        == 2
                    ):
                        print("starlit")
                        d_ortool = self.resources1.slots[d]
                        if hasattr(d_ortool[6], "Not"):
                            happening_or_not = d_ortool[6]
                        else:
                            happening_or_not = d_ortool[11]
                        if hasattr(s_ortool[6], "Not"):
                            happening_or_not_s = s_ortool[6]
                        else:
                            happening_or_not_s = s_ortool[11]
                        print("ruffer3", s_ortool)
                        self.model.Add(d_ortool[3] <= s_ortool[3]).OnlyEnforceIf(
                            happening_or_not_s
                        )
                        self.model.Add(d_ortool[4] >= s_ortool[4]).OnlyEnforceIf(
                            happening_or_not_s
                        )
                        if hasattr(s_ortool[6], "Not"):
                            self.model.Add(s_ortool[6] == 0).OnlyEnforceIf(
                                happening_or_not.Not()
                            )
                        else:
                            self.model.Add(s_ortool[11] == 0).OnlyEnforceIf(
                                happening_or_not.Not()
                            )
                        for inter in list(set(s_resources) | set(d_resources)):
                            if inter in self.resource_supervision_pair[index]:
                                self.resource_supervision_pair[index][inter].append(
                                    [tuple(s), d]
                                )
                            else:
                                self.resource_supervision_pair[index][inter] = [
                                    [tuple(s), d]
                                ]

                        # del direct_key_list[i]
                        is_found = True
                        if s_ortool[9] == "f9d4f797-bd9a-4732-9385-03ca660d1cd1":
                            print(
                                "found you timer",
                                self.resources1.slots[d][9],
                                d,
                                intersected_resources,
                                self.resources1.slots[tuple(s)],
                            )
                        if s_ortool[9] == "0c57ab2e-1c8a-438d-8f3a-c37645792f0c":
                            print(
                                "found you timer",
                                self.resources1.slots[d][9],
                                d,
                                intersected_resources,
                                self.resources1.slots[tuple(s)],
                            )
                        if s_ortool[9] == "ee114d55-6672-431a-982a-dcbb27576dbb":
                            print(
                                "found you timer",
                                self.resources1.slots[d][9],
                                d,
                                intersected_resources,
                                self.resources1.slots[tuple(s)],
                            )
                        break
                if not is_found:
                    print("not_found", self.resources1.slots[tuple(s)])
                    if s_ortool[9] == "f9d4f797-bd9a-4732-9385-03ca660d1cd1":
                        print("found you not found", s_ortool)
                    self.model.Add(self.resources1.slots[tuple(s)][0] == 0)

            for id in client_ids.union(employee_ids):
                # extra_arr = self.fake_whites.get(id, [])
                extra_arr = []
                if id in self.fake_whites:
                    for day, constraints in self.fake_whites[id].items():
                        extra_arr.extend(constraints)

                val = self.get_appointments([[id], [str(index)]])
                # val_super = self.get_appointments([[id], [supervision_activity_id]])

                if id in supervisory_staff:
                    arr = [value for key, value in val.items()]

                    flimp = [num[2] for num in arr] + extra_arr
                    self.model.AddNoOverlap(flimp)
                else:
                    if val:
                        arr = [
                            value
                            for key, value in val.items()
                            if supervision_activity_id not in key
                        ]

                        flimp = [num[2] for num in arr] + extra_arr
                        self.model.AddNoOverlap(flimp)

                    if val:
                        arr = [
                            value
                            for key, value in val.items()
                            if direct_activity_id not in key
                        ]
                        flip_super = [num[2] for num in arr]
                        self.model.AddNoOverlap(flip_super)

                    if val and id in self.resource_supervision_pair[index]:
                        for e in self.resource_supervision_pair[index][id]:

                            arr = []
                            counter = 5
                            for key, value in val.items():
                                # print('fooler3',e[0],e[1],key)
                                if direct_activity_id in key and not e[1] == key:
                                    arr.append(value)
                                # else:
                                #     print('fooler4',e[0],e[1],key)
                            arr.append(self.resources1.slots[e[0]])
                            flip_pair = [num[2] for num in arr]
                            self.model.AddNoOverlap(flip_pair)

        # for id in self.find_ids_by_role(["Roomy"]):
        #     val = self.get_appointments([[id]])

        #     if val:
        #         flimp = [value[2] for value in val.values()]
        #         self.model.AddNoOverlap(flimp)

        # for id in list(set(self.find_ids_by_role(["Employee"]))):
        #     # extra_arr = self.fake_whites[id] if id in self.fake_whites else []
        #     extra_arr = []
        #     if id in self.fake_whites:
        #         for day, constraints in self.fake_whites[id].items():
        #             extra_arr.extend(constraints)
        #     val = self.get_appointments(
        #         [
        #             [id],
        #             #  self.var_data["objectiveactivity"]
        #         ]
        #     )
        #     if len(val) > 0:
        #         arr = val.values()
        #         over_yellow = []
        #         over_normal = []
        #         for i in arr:
        #             if i[13]:
        #                 over_yellow.append(i)
        #             else:
        #                 over_normal.append(i)
        #         flimp1 = list((map(lambda num: num[2], over_yellow)))
        #         flimp2 = (
        #             list((map(lambda num: num[2], over_normal))) + extra_arr
        #         )  # +fake_interval_array
        #         self.model.AddNoOverlap(flimp1)
        #         self.model.AddNoOverlap(flimp2)

    from datetime import datetime

    def sum_other_days_durations(self, constraint):
        today_index = self.var_data[
            "today_index"
        ]  # 0 = Sunday, 1 = Monday, ..., 6 = Saturday
        total_duration = 0

        for entry in constraint.get("all", {}).get("dates", []):
            date_obj = datetime.datetime.fromisoformat(entry["date"])
            date_index = (
                date_obj.weekday() + 1
            ) % 7  # convert Monday=0 to Sunday=0 system

            if date_index != today_index:
                total_duration += entry.get("duration", 0)

        return total_duration

    # @measure_time
    def constraint_drive(self):
        constraint_drive_data = self.constraint_drive_data
        count_applied = 0
        max_time_for_drive = 60
        max_time_slots_array = list(
            range(max_time_for_drive // self.var_data["slot_length"] + 1)
        )
        boost_cof = 1
        is_high_traffic = False
        days_arrays = days_arr(self.var_data["slot_length"])
        all_act = [
            i
            for i in self.find_ids_by_role(["Activity"])
            if i not in self.var_data["notWorking"]
        ]
        for index, x in enumerate(days_arrays):
            print("ligger1", self.var_data["today_index"])
            if index == self.var_data["today_index"]:
                for id in self.find_ids_by_role(["Employee"]):
                    val = self.get_appointments(
                        [[id], ["1", "2", "3", "4", "5", "6", "7"], all_act]
                    )
                    val_not = self.get_appointments(
                        [
                            [id],
                            ["1", "2", "3", "4", "5", "6", "7"],
                            self.var_data["notWorking"],
                        ]
                    )
                    val_values = list(val.values())
                    val_not_values = list(val_not.values())
                    print("ligger2")
                    combs = list(combinations(val_values, 2))

                    all_combs = combs + [
                        (r11, r22) for r11 in val_values for r22 in val_not_values
                    ]
                    for r in all_combs:
                        res1, res2 = r

                        if res1[12] is None or res2[12] is None:
                            continue

                        # Get address and location indexes
                        address1, address2 = res1[7], res2[7]
                        loc1 = self.solutions1["user_uuid_to_index"][res1[12]]
                        loc2 = self.solutions1["user_uuid_to_index"][res2[12]]
                        print("ligger3")
                        if not address1 or not address2 or address1 == address2:
                            continue
                        print("ligger4")
                        users = self.solutions1["users"]
                        user1_data = users[loc1]
                        user2_data = users[loc2]
                        print("ligger5")
                        if address1 is None or address2 is None:
                            continue
                        print("ligger7")
                        if address1 == address2:
                            continue
                        print("ligger6")

                        # Determine branch IDs
                        branchId1 = (
                            user1_data["branches"][0]
                            if loc1 and user1_data["branches"]
                            else "d"
                        )
                        branchId2 = (
                            user2_data["branches"][0]
                            if loc2 and user2_data["branches"]
                            else "s"
                        )

                        if len(branchId1) > 1 and len(branchId2) > 1 and (loc1 or loc2):
                            company_id = self.var_data["companyId"]
                            slot_length = self.var_data["slot_length"]
                            branch_data = self.solutions1["branches"][branchId1]
                            drive_time = branch_data.get("drivetime")
                            print("ligger8")
                            tuple_ids = (address1, address2)
                            tuple_ids_reverse = (address2, address1)
                            print("drive-lime")
                            if (
                                tuple_ids in constraint_drive_data.keys()
                                and company_id != "090121f7-8598-463e-92c4-f501c2576e60"
                            ):
                                d_data_duration = constraint_drive_data[tuple_ids][
                                    "mid"
                                ]
                                drive_time_data = round_to_nearest_interval(
                                    d_data_duration // 60, slot_length
                                )

                                if is_high_traffic:
                                    drive_time_data *= boost_cof

                                for i in max_time_slots_array:
                                    if (
                                        i
                                        > drive_time_data / self.var_data["slot_length"]
                                    ):
                                        drive_time = i
                                        break

                            elif company_id != "090121f7-8598-463e-92c4-f501c2576e60":
                                result_distance_dur_early = return_interval_drive_time(
                                    address1, address2, 11, 30
                                )
                                # Just makes 15 minute hardcode
                                # result_distance_dur_early = [900, 900]
                                # Just makes 15 minute hardcode
                                if result_distance_dur_early != [0, 0]:
                                    result_distance_dur_mid = result_distance_dur_early
                                    result_distance_dur_late = result_distance_dur_early

                                    drive_data = [
                                        {
                                            "address1": address1,
                                            "address2": address2,
                                            "duration": result_distance_dur_mid[1],
                                            "duration_early": result_distance_dur_early[
                                                1
                                            ],
                                            "duration_late": result_distance_dur_late[
                                                1
                                            ],
                                            "distance": result_distance_dur_early[0],
                                        },
                                        {
                                            "address1": address2,
                                            "address2": address1,
                                            "duration": result_distance_dur_mid[1],
                                            "duration_early": result_distance_dur_early[
                                                1
                                            ],
                                            "duration_late": result_distance_dur_late[
                                                1
                                            ],
                                            "distance": result_distance_dur_early[0],
                                        },
                                    ]
                                    # dont post drive time to db yet
                                    for data in drive_data:
                                        post_drive_time_data(
                                            self.var_data["header"],
                                            {"data": data},
                                            self.var_data["host"],
                                        )
                                    # dont post drive time to db yet

                                    for ids in [
                                        (tuple_ids, result_distance_dur_early),
                                        (tuple_ids_reverse, result_distance_dur_early),
                                    ]:
                                        constraint_drive_data[ids[0]] = {
                                            "early": ids[1][1],
                                            "mid": result_distance_dur_mid[1],
                                            "late": result_distance_dur_late[1],
                                        }

                                    drive_time_data = round_to_nearest_interval(
                                        result_distance_dur_mid[1] // 60,
                                        self.var_data["slot_length"],
                                    )
                                    if is_high_traffic:
                                        drive_time_data *= boost_cof

                                    for i in max_time_slots_array:
                                        if (
                                            i
                                            > drive_time_data
                                            / self.var_data["slot_length"]
                                        ):
                                            drive_time = i
                                            break
                            if drive_time == 0 or not drive_time:
                                drive_time = 0
                                constraint_drive_data[tuple_ids] = {
                                    "early": 0,
                                    "mid": 0,
                                    "late": 0,
                                }
                                constraint_drive_data[tuple_ids_reverse] = {
                                    "early": 0,
                                    "mid": 0,
                                    "late": 0,
                                }
                                drive_time = 0 // self.var_data["slot_length"]
                            else:
                                pass
                            drive_time_slot = int(drive_time)

                            if (
                                self.var_data["companyId"]
                                == "090121f7-8598-463e-92c4-f501c2576e60"
                            ):
                                drive_time_slot = 15 // self.var_data["slot_length"]

                            start1, end1 = res1[3], res1[4]
                            start2, end2 = res2[3], res2[4]

                            if address1 != address2:
                                is_left = self.model.NewBoolVar("is_left")
                                is_drive = self.model.NewBoolVar("is_drive")
                                self.model.Add(start1 <= start2).OnlyEnforceIf(is_left)
                                self.model.Add(start2 < start1).OnlyEnforceIf(
                                    is_left.Not()
                                )
                                self.model.Add(
                                    start2 - end1 >= drive_time_slot
                                ).OnlyEnforceIf(is_left).OnlyEnforceIf(is_drive)
                                self.model.Add(
                                    start1 - end2 >= drive_time_slot
                                ).OnlyEnforceIf(is_left.Not()).OnlyEnforceIf(is_drive)

                                self.model.AddMinEquality(is_drive, [res1[6], res2[6]])

                                count_applied += 1
        self.drive_time_data = constraint_drive_data

    # @measure_time
    def supervision_constraint(self):
        clients = self.find_ids_by_role(["Client"])
        direct_activity_id = "2faf27ca-9120-486c-9738-83714f0ee50d"
        supervision_activity_id = "f39d479c-ea0f-4dcf-86e1-3e47c19328c7"

        for client_id in clients:
            direct_appointments = list(
                self.get_appointments([[client_id], [direct_activity_id]]).values()
            )
            supervision_appointments = list(
                self.get_appointments([[client_id], [supervision_activity_id]]).values()
            )

            for super_appointment in supervision_appointments:
                super_bol = self.model.NewBoolVar(f"super_bol-{client_id}")
                constraints = []

                for direct_appointment in direct_appointments:
                    direct_super_bol = self.model.NewBoolVar(
                        f"direct_super_bol-{client_id}"
                    )
                    self.model.Add(
                        direct_appointment[3] <= super_appointment[3]
                    ).OnlyEnforceIf(direct_super_bol)
                    self.model.Add(
                        direct_appointment[4] >= super_appointment[4]
                    ).OnlyEnforceIf(direct_super_bol)
                    self.model.Add(
                        direct_appointment[0] >= super_appointment[0]
                    ).OnlyEnforceIf(direct_super_bol)
                    constraints.append(direct_super_bol)

                self.model.Add(sum(constraints) == 1).OnlyEnforceIf(super_bol)
                self.model.Add(sum(constraints) == 0).OnlyEnforceIf(super_bol.Not())

                self.model.Add(super_appointment[0] > 0).OnlyEnforceIf(super_bol)
                self.model.Add(super_appointment[0] == 0).OnlyEnforceIf(super_bol.Not())

    # @measure_time
    def matches_frequency(self):
        start_time = time.time()

        hour_slot_ratio = 60 // self.var_data["slot_length"]
        max_total_hours = max(
            int(get_number_per_slot_2(self.solutions1) // hour_slot_ratio), 1
        )

        employees = self.find_ids_by_role(["Employee"])
        persons = self.find_ids_by_role(["Person"])
        clients = self.find_ids_by_role(["Client"])
        clinicDirector = set(self.find_ids_by_role(["Clinic Director"]))
        bcba = set(self.find_ids_by_role(["BCBA"]))
        bcaba = set(self.find_ids_by_role(["BCaBa"]))
        seniorintern = set(self.find_ids_by_role(["Senior Intern"]))
        seniortherapist = set(self.find_ids_by_role(["Senior Therapist"]))
        supervisory_staff = (
            bcba | bcaba | seniorintern | seniortherapist | clinicDirector
        )
        people = employees + clients

        av_arr_for_fake = {
            person_id: {day: [] for day in range(8)} for person_id in people
        }

        weekly_data = self.var_data["weekly_events_data"]
        days_arrays = days_arr(self.var_data["slot_length"])
        gaps_ids_arr = []
        av_arr_for_fake_raw = self.solutions1["user_availabilities_general"]
        for some_id in people:
            for i in av_arr_for_fake_raw[some_id]:
                i_new1 = i[0] + (96 * (15 // self.var_data["slot_length"]))
                i_new2 = i[1] + (96 * (15 // self.var_data["slot_length"]))
                i_new = (i_new1, i_new2)
                some_index = i[0] // ((24 * 60) // self.var_data["slot_length"])
                av_arr_for_fake[some_id][some_index].append(i_new)

        if self.solutions1["resources1"]["frequency_constraints"] != []:
            counts_of_vars = {}
            rank_of_vars = {}
            for constraint in self.solutions1["resources1"]["frequency_constraints"]:
                counts_of_vars[constraint["id"]] = 0
                rank_of_vars[constraint["id"]] = 0

            rank_count = 2
            for item_id in self.var_data["highPriority"]:
                rank_of_vars[item_id] = rank_count
                rank_count += 1

            for item_id in self.var_data["hard"]:
                rank_of_vars[item_id] = 1

            for constraint in self.solutions1["resources1"]["frequency_constraints"]:
                constraint_id = constraint["id"]
                if (
                    constraint_id not in self.var_data["hard"]
                    and constraint_id not in self.var_data["highPriority"]
                ):
                    rank_of_vars[constraint_id] = rank_count + 1
                    rank_count += 1

            inte_vars = {
                constraint["id"]: self.model.NewIntVar(1, 1000_0000, constraint["id"])
                for constraint in self.solutions1["resources1"]["frequency_constraints"]
            }

            pair_vars = {
                constraint["id"]: constraint["id"]
                for constraint in self.solutions1["resources1"]["frequency_constraints"]
            }

            counts_of_vars["max_total_durations"] = max_total_hours
            rank_of_vars["max_total_durations"] = 2 + len(self.var_data["highPriority"])
            pair_vars["max_total_durations"] = "max_total_durations"
            inte_vars["max_total_durations"] = self.model.NewIntVar(
                0, 1000_0000, "mx_total"
            )
            print(
                'self.solutions1["resources1"]["frequency_constraints"]',
                self.solutions1["resources1"]["frequency_constraints"],
            )

            for c in self.solutions1["resources1"]["frequency_constraints"]:
                constraint_start_time = time.time()

                c_min = int(c["minSeconds"]) // (60 * self.var_data["slot_length"])
                c_max = int(c["maxSeconds"]) // (60 * self.var_data["slot_length"])
                if c["id"] not in self.var_data["highPriority"]:
                    continue

                elif c["type"] == "frequency":
                    print("safety1")
                    for user_a in c["users_antecedent"]:
                        user_a_id = self.solutions1["resources1"]["resources"][
                            user_a
                        ].id

                        if c["frequency"] == "day":
                            print("safety2")
                            arr = []
                            for index, x in enumerate(days_arrays):
                                if index == 0:
                                    continue
                                for user_c in c["users_consequence"]:
                                    user_c_id = self.solutions1["resources1"][
                                        "resources"
                                    ][user_c].id
                                    val = self.get_appointments(
                                        [[user_c_id], [user_a_id], [str(index)]]
                                    )
                                    if not val:
                                        continue
                                    print("safety4")
                                    target1 = self.model.NewBoolVar(
                                        f"freq_bool-{user_c_id}"
                                    )
                                    self.model.AddMaxEquality(
                                        target1, [num[6] for num in val.values()]
                                    )
                                    arr.append(target1)
                                if not arr:
                                    continue
                                ##
                                usertouser_analyzer_bool = self.model.NewBoolVar(
                                    f"session_analyzer_{c['id']}"
                                )

                                if c["id"] in self.var_data["highPriority"]:
                                    self.constraint_booleans_hard.append(
                                        usertouser_analyzer_bool
                                    )
                                else:
                                    self.constraint_booleans_soft.append(
                                        usertouser_analyzer_bool
                                    )
                                self.model.Add(sum(arr) <= int(c["max"])).OnlyEnforceIf(
                                    usertouser_analyzer_bool
                                )
                                if c["min"] > 0:
                                    self.model.Add(sum(arr) >= c["min"]).OnlyEnforceIf(
                                        usertouser_analyzer_bool
                                    )

                        elif c["frequency"] == "week":
                            arr = []
                            for user_c in c["users_consequence"]:
                                user_c_id = self.solutions1["resources1"]["resources"][
                                    user_c
                                ].id
                                val = self.get_appointments([[user_c_id], [user_a_id]])
                                if not val:
                                    continue
                                arr.extend([num[6] for num in val.values()])

                            if not arr:
                                continue

                            usertouser_analyzer_bool = self.model.NewBoolVar(
                                f"session_analyzer_{c['id']}"
                            )

                            if c["id"] in self.var_data["highPriority"]:
                                self.constraint_booleans_hard.append(
                                    session_analyzer_bool
                                )
                            else:
                                self.constraint_booleans_soft.append(
                                    session_analyzer_bool
                                )
                            self.model.Add(sum(arr) <= c["max"]).OnlyEnforceIf(
                                usertouser_analyzer_bool
                            )
                            if c["min"] > 0:
                                self.model.Add(sum(arr) >= c["min"]).OnlyEnforceIf(
                                    usertouser_analyzer_bool
                                )

                elif c["type"] == "time":

                    print("gooba5", c)
                    # self.constraint_booleans[c["id"]] = time_analyzer_bool

                    for user_a in c["users_antecedent"]:
                        user_a_id = self.solutions1["resources1"]["resources"][
                            user_a
                        ].id

                        if user_a_id not in self.soft_time_constraint_vars:
                            self.soft_time_constraint_vars[user_a_id] = []

                        if c["frequency"] == "session":
                            for index, x in enumerate(days_arrays):
                                for user_c in c["users_consequence"]:
                                    user_c_id = self.solutions1["resources1"][
                                        "resources"
                                    ][user_c].id
                                    val = self.get_appointments(
                                        [[user_c_id], [user_a_id], [str(index)]]
                                    )
                                    if len(val) == 0:
                                        continue
                                    durations = list(
                                        map(lambda num: num[0], val.values())
                                    )
                                    for dur in durations:
                                        if c["id"] in self.var_data["highPriority"]:
                                            self.model.Add(dur <= c_max).OnlyEnforceIf(
                                                time_analyzer_bool
                                            )
                                            if c_min != 0:
                                                inc = 1
                                                while inc < c_min:
                                                    self.model.Add(
                                                        dur != inc
                                                    ).OnlyEnforceIf(time_analyzer_bool)
                                                    inc += 1
                                            counts_of_vars[c["id"]] += 1
                                        else:
                                            bol = self.model.NewBoolVar("y")
                                            inte = self.model.NewIntVar(
                                                0, 10000000000, "snip1"
                                            )
                                            self.model.Add(inte == 1).OnlyEnforceIf(
                                                bol
                                            ).OnlyEnforceIf(time_analyzer_bool)
                                            counts_of_vars[c["id"]] += 1
                                            self.model.Add(inte == 0).OnlyEnforceIf(
                                                bol.Not()
                                            ).OnlyEnforceIf(time_analyzer_bool)
                                            self.constraint_bols.append(inte)
                                            self.model.Add(dur <= c_max).OnlyEnforceIf(
                                                bol
                                            ).OnlyEnforceIf(time_analyzer_bool)
                                            self.model.Add(dur >= c_max).OnlyEnforceIf(
                                                bol
                                            ).OnlyEnforceIf(time_analyzer_bool)

                        if False and c["each_or_all_users"] == "each":
                            pass
                            # if c["frequency"] == "day":
                            #     for index, day in enumerate(days_arrays):
                            #         for user_c in c["users_consequence"]:
                            #             user_c_id = self.solutions1["resources1"][
                            #                 "resources"
                            #             ][user_c].id
                            #             appointments = self.get_appointments(
                            #                 [[user_c_id], [user_a_id], [str(index)]]
                            #             ).values()
                            #             arr = [num[0] for num in appointments]

                            #             if not arr:
                            #                 continue

                            #             bol = self.model.NewBoolVar("y")
                            #             inte = self.model.NewIntVar(
                            #                 0, 10000000000, "snip1"
                            #             )

                            #             self.model.Add(inte == 1).OnlyEnforceIf(
                            #                 bol
                            #             ).OnlyEnforceIf(time_analyzer_bool)
                            #             self.model.Add(inte == 0).OnlyEnforceIf(
                            #                 bol.Not()
                            #             ).OnlyEnforceIf(time_analyzer_bool)

                            #             counts_of_vars[c["id"]] += 1
                            #             self.constraint_bols.extend([bol, inte])

                            #             self.model.Add(sum(arr) <= c_max).OnlyEnforceIf(
                            #                 bol
                            #             ).OnlyEnforceIf(time_analyzer_bool)
                            #             self.model.Add(sum(arr) >= c_min).OnlyEnforceIf(
                            #                 bol
                            #             ).OnlyEnforceIf(time_analyzer_bool)

                            # elif c["frequency"] == "week":
                            #     for user_c in c["users_consequence"]:
                            #         user_c_id = self.solutions1["resources1"][
                            #             "resources"
                            #         ][user_c].id
                            #         appointments = self.get_appointments(
                            #             [[user_c_id], [user_a_id]]
                            #         ).values()
                            #         arr = [num[0] for num in appointments]

                            #         if not arr:
                            #             continue

                            #         total_slots = sum(arr)
                            #         slots_per_hour = 60 // self.var_data["slot_length"]
                            #         print(f"appointments data:::::: {appointments}")
                            #         print(f"total slots data ----- : {total_slots}")

                            #         if c["id"] in self.var_data["highPriority"]:
                            #             self.model.Add(
                            #                 total_slots <= c_max * slots_per_hour
                            #             ).OnlyEnforceIf(time_analyzer_bool)
                            #             counts_of_vars[c["id"]] += 1
                            #         else:
                            #             bol = self.model.NewBoolVar("y")
                            #             inte = self.model.NewIntVar(
                            #                 0, 10000000000, "snip1"
                            #             )

                            #             self.model.Add(inte == 1).OnlyEnforceIf(
                            #                 bol
                            #             ).OnlyEnforceIf(time_analyzer_bool)
                            #             self.model.Add(inte == 0).OnlyEnforceIf(
                            #                 bol.Not()
                            #             ).OnlyEnforceIf(time_analyzer_bool)

                            #             counts_of_vars[c["id"]] += 1
                            #             self.constraint_bols.extend([bol, inte])

                            #             self.model.Add(
                            #                 total_slots <= c_max
                            #             ).OnlyEnforceIf(bol).OnlyEnforceIf(
                            #                 time_analyzer_bool
                            #             )
                        else:
                            if not c["users_consequence"]:
                                continue

                            user_cons = c["users_consequence"]
                            hour_slot_ratio = 60 // self.var_data["slot_length"]

                            if c["frequency"] == "day":
                                for index, _ in enumerate(days_arrays):
                                    user_c_ids = [
                                        self.solutions1["resources1"]["resources"][
                                            user_cc
                                        ].id
                                        for user_cc in user_cons
                                    ]
                                    appointments = self.get_appointments(
                                        [user_c_ids, [user_a_id]]
                                    ).values()
                                    arr = [num[0] for num in appointments]

                                    if not arr:
                                        continue
                                    ##NEW ANALYZE
                                    time_analyzer_bool = self.model.NewBoolVar(
                                        f"time_analyzer_{c['id']}"
                                    )
                                    ##NEW ANALYZE

                                    if c["id"] in self.var_data["highPriority"]:
                                        self.constraint_booleans_hard.append(
                                            time_analyzer_bool
                                        )
                                        self.model.Add(sum(arr) <= c_max).OnlyEnforceIf(
                                            time_analyzer_bool
                                        )
                                        if c["min"] > 0:
                                            self.model.Add(
                                                sum(arr) >= c_min
                                            ).OnlyEnforceIf(time_analyzer_bool)
                                        counts_of_vars[c["id"]] += 1
                                    else:
                                        self.constraint_booleans_soft.append(
                                            time_analyzer_bool
                                        )
                                        self.model.Add(sum(arr) <= c_max)
                                        self.model.Add(sum(arr) <= c_max).OnlyEnforceIf(
                                            bol
                                        ).OnlyEnforceIf(time_analyzer_bool)
                                        self.model.Add(sum(arr) >= c_min).OnlyEnforceIf(
                                            bol
                                        ).OnlyEnforceIf(time_analyzer_bool)
                            elif c["frequency"] == "week":
                                # for all!
                                print("gooba1", c["users_consequence"], [user_a_id])
                                # user_c_id = self.solutions1["resources1"]["resources"][
                                #     user_c
                                # ].id
                                for user_c in c["users_consequence"]:
                                    user_c_id = self.solutions1["resources1"][
                                        "resources"
                                    ][user_c].id
                                appointments = self.get_appointments(
                                    [
                                        [user_a_id],
                                        [
                                            self.solutions1["resources1"]["resources"][
                                                user_c
                                            ].id
                                            for user_c in c["users_consequence"]
                                        ],
                                    ]
                                ).values()

                                # ###FOR PERCENTAGE not in c
                                # if not c["antecedentTypeActivityId"] is None:
                                #     print(
                                #         'c["antecedentTypeActivityId"]',
                                #         c["antecedentTypeActivityId"],
                                #     )

                                # ###FOR PERCENTAGE

                                print(
                                    "gommer",
                                    self.var_data["today_index"],
                                    c["id"],
                                    user_a_id,
                                    self.flags,
                                )
                                total = 0
                                if (
                                    not self.is_week
                                    and c["id"] in self.flags
                                    and user_a_id in self.flags[c["id"]]
                                    and "dates" in self.flags[c["id"]][user_a_id]["all"]
                                ):
                                    print("seeweed", self.flags[c["id"]][user_a_id])
                                    total = (
                                        self.sum_other_days_durations(
                                            self.flags[c["id"]][user_a_id]
                                        )
                                        * hour_slot_ratio
                                    )
                                    print("seeweed2", total)
                                    if (
                                        self.flags[c["id"]][user_a_id]["unit"]
                                        == "minutes"
                                    ):
                                        total = total / 60 * hour_slot_ratio
                                        print("seeweed3", total)

                                arr = [num[0] for num in appointments]
                                print("gooba2", arr)
                                if not arr:
                                    continue
                                time_analyzer_bool = self.model.NewBoolVar(
                                    f"time_analyzer_{c['id']}"
                                )
                                self.constraint_booleans_hard.append(
                                    time_analyzer_bool * 100
                                )
                                max_real = int(math.ceil(max((c_max - total), 0)))
                                min_real = int(math.ceil(max((c_min - total), 0)))
                                print("max_real", max_real, min_real)
                                self.model.Add(sum(arr) <= max_real)
                                self.model.Add(sum(arr) <= max_real).OnlyEnforceIf(
                                    time_analyzer_bool
                                )
                                if c["min"] > 0:
                                    self.model.Add(sum(arr) >= min_real).OnlyEnforceIf(
                                        time_analyzer_bool
                                    )

                elif c["type"] == "gaps":
                    supervision_activity_id = "1b1b9fe3-a96a-4074-97d4-1f5767a84428"

                    gaps_analyzer_bool = self.model.NewBoolVar(
                        f"gaps_analyzer_{c['id']}"
                    )
                    # self.constraint_booleans[c["id"]] = gaps_analyzer_bool
                    counter = 0
                    for user_a in c["users_antecedent"]:
                        user_a_id = self.solutions1["resources1"]["resources"][
                            user_a
                        ].id

                        counter = counter + 1
                        for index, x in enumerate(days_arrays):
                            if c["each_or_all_users"] == "each" or True:
                                print("here gap", c_min, c_max)
                                if True or (c_min == 0 and c_max == 0):
                                    val_gaps = self.get_appointments(
                                        [[user_a_id], [str(index)]]
                                    )
                                    if not val_gaps:
                                        continue

                                    if index <= 0:
                                        new_index = 7
                                    else:
                                        new_index = index - 1
                                    av_data = av_arr_for_fake[user_a_id][new_index]

                                    if not av_data or not any(av_data):
                                        continue

                                    if user_a_id not in self.fake_whites:
                                        self.fake_whites[user_a_id] = {}

                                    if index not in self.fake_whites[user_a_id]:
                                        self.fake_whites[user_a_id][index] = []

                                    clients_gaps_interval = []
                                    clients_gaps_duration = []
                                    is_supervisor = user_a_id in supervisory_staff
                                    print(
                                        "is_supervisor",
                                        is_supervisor,
                                        user_a_id,
                                        supervisory_staff,
                                    )
                                    durations = [
                                        val_data[0]
                                        for val_key, val_data in val_gaps.items()
                                        if supervision_activity_id not in val_key
                                        or is_supervisor
                                    ]
                                    appointments_new = [
                                        [val_key, val_data]
                                        for val_key, val_data in val_gaps.items()
                                        if supervision_activity_id not in val_key
                                        or is_supervisor
                                    ]

                                    print("limmert1", av_data)
                                    print("limmert2", self.fake_whites)
                                    try:
                                        if len(av_data) > 1:
                                            fake_start_actual = min(
                                                i[0] for i in av_data
                                            )
                                            fake_end_actual = max(i[1] for i in av_data)
                                            count_gaps_fake = 3

                                            for gap in find_gaps(av_data)[
                                                "gap_intervals"
                                            ]:
                                                print("found gap", gap)
                                                fake_start, fake_end = gap
                                                fake_gaps_bool = self.model.NewBoolVar(
                                                    f"fake_gaps_bool-{user_a_id}-{index}-{count_gaps_fake}"
                                                )
                                                fake_gaps_start_int = self.model.NewIntVar(
                                                    fake_start_actual,
                                                    fake_end_actual,
                                                    f"fake_gaps_start-{user_a_id}-{index}-{count_gaps_fake}",
                                                )
                                                fake_gaps_end_int = self.model.NewIntVar(
                                                    fake_start_actual,
                                                    fake_end_actual,
                                                    f"fake_gaps_end-{user_a_id}-{index}-{count_gaps_fake}",
                                                )
                                                fake_gaps_duration_int = self.model.NewIntVar(
                                                    0,
                                                    fake_end_actual - fake_start_actual,
                                                    f"dur-{user_a_id}-{index}-{count_gaps_fake}",
                                                )

                                                fake_interval = self.model.NewOptionalIntervalVar(
                                                    fake_gaps_start_int,
                                                    fake_gaps_duration_int,
                                                    fake_gaps_end_int,
                                                    fake_gaps_bool,
                                                    f"fake-{user_a_id}-{index}-{count_gaps_fake}",
                                                )

                                                self.model.Add(
                                                    fake_gaps_duration_int > 0
                                                ).OnlyEnforceIf(fake_gaps_bool)
                                                self.model.Add(
                                                    fake_gaps_duration_int == 0
                                                ).OnlyEnforceIf(fake_gaps_bool.Not())
                                                self.model.Add(
                                                    fake_gaps_start_int <= fake_start
                                                )
                                                self.model.Add(
                                                    fake_gaps_end_int >= fake_end
                                                )

                                                clients_gaps_interval.append(
                                                    fake_interval
                                                )
                                                clients_gaps_duration.append(
                                                    fake_gaps_duration_int
                                                )

                                                count_gaps_fake += 1
                                    except Exception as e:
                                        print("Error processing gaps:", e)

                                    fake_bol1 = self.model.NewBoolVar(
                                        f"fake1_{user_a_id}_{index}"
                                    )
                                    fake_bol2 = self.model.NewBoolVar(
                                        f"fake2_{user_a_id}_{index}"
                                    )

                                    if not av_data or not any(av_data):
                                        continue

                                    fake_start = min(i[0] for i in av_data)
                                    fake_end = max(i[1] for i in av_data)
                                    gap_length = find_gaps(av_data)["gap_length"]
                                    print("gap_length", gap_length)
                                    # fake_start_int_1 = self.model.NewIntVar(
                                    #     fake_start,
                                    #     fake_start,
                                    #     f"fake_start1_{user_a_id}_{index}",
                                    # )
                                    fake_end_int_1 = self.model.NewIntVar(
                                        0,
                                        10000,
                                        # fake_start,
                                        # fake_end,
                                        f"fake_end1_{user_a_id}_{index}",
                                    )
                                    # fake_duration_int_1 = self.model.NewIntVar(
                                    #     0,
                                    #     fake_end - fake_start,
                                    #     f"dur1_{user_a_id}_{index}",
                                    # )

                                    fake_start_int_2 = self.model.NewIntVar(
                                        0,
                                        10000,
                                        # fake_start,
                                        # fake_end,
                                        f"fake_start2_{user_a_id}_{index}",
                                    )
                                    # fake_end_int_2 = self.model.NewIntVar(
                                    #     fake_end,
                                    #     fake_end,
                                    #     f"fake_end2_{user_a_id}_{index}",
                                    # )
                                    # fake_duration_int_2 = self.model.NewIntVar(
                                    #     0,
                                    #     fake_end - fake_start,
                                    #     f"dur2_{user_a_id}_{index}",
                                    # )
                                    print("fake_start", fake_start)
                                    print("fake_end", fake_end)

                                    # fake1 = self.model.NewOptionalIntervalVar(
                                    #     fake_start,
                                    #     fake_end_int_1 - fake_start,
                                    #     # fake_duration_int_1,
                                    #     fake_end_int_1,
                                    #     fake_bol1,
                                    #     f"fake1_{user_a_id}_{index}",
                                    # )
                                    # fake2 = self.model.NewOptionalIntervalVar(
                                    #     fake_start_int_2,
                                    #     fake_end - fake_start_int_2,
                                    #     fake_end,
                                    #     fake_bol2,
                                    #     f"fake2_{user_a_id}_{index}",
                                    # )

                                    # self.fake_whites[user_a_id][index].extend(
                                    #     [fake1, fake2] + clients_gaps_interval
                                    # )

                                    # self.model.Add(
                                    #     fake_end_int_1 - fake_start > 0
                                    # ).OnlyEnforceIf(fake_bol1)
                                    # self.model.Add(
                                    #     fake_end_int_1 - fake_start == 0
                                    # ).OnlyEnforceIf(fake_bol1.Not())

                                    # self.model.Add(
                                    #     fake_end - fake_start_int_2 > 0
                                    # ).OnlyEnforceIf(fake_bol2)
                                    # self.model.Add(
                                    #     fake_end - fake_start_int_2 == 0
                                    # ).OnlyEnforceIf(fake_bol2.Not())
                                    # self.model.Add(fake_start_int_2 >= fake_end_int_1)
                                    # self.model.Add(fake_start_int_1 == fake_start)
                                    # self.model.Add(fake_end_int_2 == fake_end)
                                    print("c_max gap", c_max, c_min)
                                    print("c_max gap1", c["minSeconds"])
                                    print("c_max ga2", c["maxSeconds"])
                                    inner_gap_calculated = self.model.NewIntVar(
                                        0, 100000, "g"
                                    )

                                    # self.model.Add(
                                    #     sum(durations)
                                    #     + (fake_end_int_1 - fake_start)
                                    #     + (fake_end - fake_start_int_2)
                                    #    # + sum(clients_gaps_duration)
                                    #     == fake_end - fake_start
                                    # ).OnlyEnforceIf(gaps_analyzer_bool)

                                    # Caravel

                                    bol_has_duration = self.model.NewBoolVar(
                                        f"bol_has_duration"
                                    )
                                    self.model.Add(sum(durations) > 0).OnlyEnforceIf(
                                        bol_has_duration
                                    )
                                    self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                                        bol_has_duration.Not()
                                    )
                                    # self.model.Add(sum(durations) == 0)
                                    min_start = self.model.NewIntVar(
                                        0, 100000, f"{fake_start}"
                                    )
                                    max_end = self.model.NewIntVar(
                                        0, 100000, f"{fake_end}"
                                    )
                                    gap_amount = self.model.NewIntVar(0, 100000, "s")
                                    self.gap_list.append(gap_amount)
                                    self.model.Add(
                                        gap_amount
                                        >= fake_end
                                        - fake_start
                                        - (
                                            sum(durations)
                                            + (fake_end_int_1 - fake_start)
                                            + (fake_end - fake_start_int_2)
                                            # + gap_length
                                            + sum(clients_gaps_duration)
                                        )
                                    ).OnlyEnforceIf(bol_has_duration)
                                    self.model.Add(gap_amount == 0).OnlyEnforceIf(
                                        bol_has_duration.Not()
                                    )

                                    self.resource_gaps[index][user_a_id] = gap_amount
                                    self.resource_first_appointment_start[index][
                                        user_a_id
                                    ] = min_start
                                    self.resource_last_appointment_end[index][
                                        user_a_id
                                    ] = max_end
                                    self.model.Add(fake_end_int_1 == min_start)
                                    self.model.Add(fake_start_int_2 == max_end)
                                    min_array = []
                                    max_array = []
                                    for a in appointments_new:
                                        key = a[0]
                                        value = a[1]
                                        print("second1", value)
                                        if key in self.min_max_amounts:
                                            max_amount = self.min_max_amounts[key][1]
                                            min_amount = self.min_max_amounts[key][0]
                                        else:
                                            max_amount = self.model.NewIntVar(
                                                0, 10000, "s"
                                            )
                                            min_amount = self.model.NewIntVar(
                                                0, 10000, "s"
                                            )
                                            self.min_max_amounts[key] = [
                                                min_amount,
                                                max_amount,
                                            ]
                                            if not hasattr(value[6], "Not"):
                                                print("googly1")
                                                self.model.Add(
                                                    min_amount == value[3]
                                                ).OnlyEnforceIf(value[11])
                                                self.model.Add(
                                                    max_amount == value[4]
                                                ).OnlyEnforceIf(value[11])
                                                self.model.Add(
                                                    min_amount == 10000
                                                ).OnlyEnforceIf(value[11].Not())
                                                self.model.Add(
                                                    max_amount == 0
                                                ).OnlyEnforceIf(value[11].Not())
                                            else:
                                                print("googly2")
                                                self.model.Add(
                                                    min_amount == 10000
                                                ).OnlyEnforceIf(value[6].Not())
                                                self.model.Add(
                                                    max_amount == 0
                                                ).OnlyEnforceIf(value[6].Not())
                                                self.model.Add(
                                                    min_amount == value[3]
                                                ).OnlyEnforceIf(value[6])
                                                self.model.Add(
                                                    max_amount == value[4]
                                                ).OnlyEnforceIf(value[6])
                                        min_array.append(min_amount)
                                        max_array.append(max_amount)

                                    # self.model.AddMinEquality(min_start, [a[3] for a in appointments_new])
                                    # self.model.AddMaxEquality(max_end, [a[4] for a in appointments_new])
                                    if True or counter == 3:

                                        print(
                                            "trying3",
                                            self.resources1.resources[
                                                user_a_id
                                            ].firstName,
                                            min_array,
                                            max_array,
                                            min_start,
                                            max_end,
                                        )
                                        if len(min_array) > 0:
                                            self.model.AddMinEquality(
                                                min_start, min_array
                                            )
                                        if len(max_array) > 0:
                                            self.model.AddMaxEquality(
                                                max_end, max_array
                                            )
                                    # for a in appointments_new:
                                    #     self.model.Add(min_start < a[3]).OnlyEnforceIf(a[6].Not()).OnlyEnforceIf(bol_has_duration)
                                    #     self.model.Add(max_end > a[4]).OnlyEnforceIf(a[6].Not()).OnlyEnforceIf(bol_has_duration)

                                    # Caravel

                                    if (
                                        self.var_data.get("companyId")
                                        == "b51dfb8f-a6c4-41be-913c-19fe0d911062"
                                    ):
                                        pass
                                    #     self.model.Add(gap_amount == fake_end - fake_start - sum(durations))
                                    #     self.model.AddMinEquality(min_start, [a[3] for a in appointments_new])
                                    #     self.model.AddMaxEquality(max_end, [a[4] for a in appointments_new])

                                    # if c_min != 0:
                                    #     print("hojy")
                                    #     self.model.Add(
                                    #         sum(durations)
                                    #         + (fake_end_int_1 - fake_start)
                                    #         + (fake_end - fake_start_int_2)
                                    #         + sum(clients_gaps_duration)
                                    #         + c_min
                                    #         <= fake_end - fake_start
                                    #     ).OnlyEnforceIf(gaps_analyzer_bool)

                                    # if clients_gaps_duration:
                                    #     self.model.Add(
                                    #         sum(clients_gaps_duration) >= gap_length
                                    #     ).OnlyEnforceIf(gaps_analyzer_bool)

                                    # self.individual_fake_boolean.setdefault(
                                    #     user_a_id, {}
                                    # ).setdefault(index, []).extend(
                                    #     [fake_bol1, fake_bol2]
                                    # )
                                else:
                                    gaps_ids_arr.append(user_a_id)
                                    max_gap = c_max

                                    val_gaps = self.get_appointments(
                                        [[user_a_id], [str(index)]]
                                    )
                                    if not val_gaps:
                                        continue

                                    if index <= 0:
                                        new_index = 6
                                    else:
                                        new_index = index - 1
                                    av_data = av_arr_for_fake[user_a_id][new_index]
                                    if not av_data:
                                        continue

                                    fake_start = min(i[0] for i in av_data)
                                    fake_end = max(i[1] for i in av_data)

                                    durations = [x[0] for x in val_gaps.values()]

                                    var_dict = {
                                        "bools": {},
                                        "starts": {},
                                        "ends": {},
                                        "durations": {},
                                        "intervals": {},
                                    }

                                    for n in range(4):
                                        var_dict["bools"][n] = self.model.NewBoolVar(
                                            f"fake_bool-{n}-{user_a_id}"
                                        )
                                        var_dict["starts"][n] = self.model.NewIntVar(
                                            fake_start,
                                            fake_end,
                                            f"fake_start-{n}-{user_a_id}",
                                        )
                                        var_dict["ends"][n] = self.model.NewIntVar(
                                            fake_start,
                                            fake_end,
                                            f"fake_end-{n}-{user_a_id}",
                                        )
                                        var_dict["durations"][n] = self.model.NewIntVar(
                                            0,
                                            fake_end - fake_start,
                                            f"fake_dur-{n}-{user_a_id}",
                                        )
                                        var_dict["intervals"][n] = (
                                            self.model.NewOptionalIntervalVar(
                                                var_dict["starts"][n],
                                                var_dict["durations"][n],
                                                var_dict["ends"][n],
                                                var_dict["bools"][n],
                                                f"fake_interval-{n}-{user_a_id}",
                                            )
                                        )

                                    self.model.Add(fake_start == var_dict["starts"][0])
                                    self.model.Add(fake_end == var_dict["ends"][1])
                                    self.model.Add(
                                        sum(var_dict["durations"].values())
                                        + sum(durations)
                                        == fake_end - fake_start
                                    )

                                    for n in range(4):
                                        self.model.Add(
                                            var_dict["durations"][n] > 0
                                        ).OnlyEnforceIf(var_dict["bools"][n])
                                        self.model.Add(
                                            var_dict["durations"][n] == 0
                                        ).OnlyEnforceIf(var_dict["bools"][n].Not())

                                    self.model.Add(
                                        var_dict["durations"][2]
                                        + var_dict["durations"][3]
                                        <= max_gap
                                    )
                                    self.model.Add(
                                        var_dict["starts"][3] >= var_dict["ends"][2]
                                    )

                                    self.fake_whites.setdefault(user_a_id, []).extend(
                                        var_dict["intervals"].values()
                                    )

                elif c["type"] == "authorization":
                    authorization_analyzer_bool = self.model.NewBoolVar(
                        f"authorization_analyzer_{c['id']}"
                    )
                    # self.constraint_booleans[c["id"]] = authorization_analyzer_bool

                    poss_hours = {}

                    user_anti_arr = [
                        self.solutions1["resources1"]["resources"][user_a].id
                        for user_a in c["users_antecedent"]
                    ]
                    user_cons_arr = [
                        self.solutions1["resources1"]["resources"][user_c].id
                        for user_c in c["users_consequence"]
                    ]
                    for d in range(7):
                        poss_hours[d] = {}
                    for d in range(7):
                        for u in user_anti_arr:
                            poss_hours[d][u] = 0
                    for u in user_anti_arr:
                        for d in range(7):
                            if d in self.var_data["weekdays_av_data"].keys():
                                if u in self.var_data["weekdays_av_data"][d].keys():
                                    poss_hours[d][u] += self.var_data[
                                        "weekdays_av_data"
                                    ][d][u]

                    for ev in self.var_data["auth_week"][0]:
                        if (
                            len(intersection(ev["resourceIds"], user_anti_arr)) > 0
                            and len(intersection(ev["resourceIds"], user_cons_arr)) > 0
                        ):
                            total_hours, weekday_index = calculate_duration_hours(
                                {"start": ev["start"], "end": ev["end"]}
                            )
                            for x in intersection(ev["resourceIds"], user_anti_arr):
                                poss_hours[weekday_index][x] -= total_hours

                    for u in user_anti_arr:
                        sum_hours = 0
                        for d in range(7):
                            if u in poss_hours[d].keys():
                                sum_hours += poss_hours[d][u]
                        for d in range(7):
                            if u in poss_hours[d].keys():
                                if sum_hours == 0:
                                    poss_hours[d][u] = 0
                                else:
                                    poss_hours[d][u] = poss_hours[d][u] / sum_hours

                    try:
                        arr_act_loc = []
                        if not c["antecedentTypeActivityId"] is None:
                            arr_act_loc.append(c["antecedentTypeActivityId"])
                        for d in range(7):
                            for user_a in c["users_antecedent"]:
                                user_a_id = self.solutions1["resources1"]["resources"][
                                    user_a
                                ].id
                                for user_c in c["users_consequence"]:
                                    user_c_id = self.solutions1["resources1"][
                                        "resources"
                                    ][user_c].id
                                    val_auth = self.get_appointments(
                                        [[user_c_id], [user_a_id], str(d)]
                                    )
                                    if d in poss_hours.keys():
                                        if user_a_id in poss_hours[d].keys():
                                            max_poss = int(
                                                c["maxSeconds"]
                                                * poss_hours[d][user_a_id]
                                                / 60
                                                / self.var_data["slot_length"]
                                            )
                                            sum_val = sum(
                                                map(lambda x: x[0], val_auth.values())
                                            )
                                            self.model.Add(
                                                sum_val <= max_poss
                                            ).OnlyEnforceIf(authorization_analyzer_bool)
                    except Exception as e:
                        traceback.print_exc()
                    pass

                elif c["type"] == "sessionlength":
                    # sessionlength_analyzer_bool = self.model.NewBoolVar(
                    #     f"sessionlength_analyzer_{c['id']}"
                    # )
                    # self.constraint_booleans[c["id"]] = sessionlength_analyzer_bool
                    try:
                        for user_a in c["users_antecedent"]:

                            user_a_id = self.solutions1["resources1"]["resources"][
                                user_a
                            ].id
                            for index, x in enumerate(days_arrays):
                                if index == self.var_data["today_index"] or True:
                                    for user_c in c["users_consequence"]:
                                        user_c_id = self.solutions1["resources1"][
                                            "resources"
                                        ][user_c].id
                                        val = self.get_appointments(
                                            [[user_c_id], [user_a_id], [str(index)]]
                                        )
                                        if len(val) == 0:
                                            continue
                                        durations = list(
                                            map(lambda num: num, val.values())
                                        )
                                        for dur in durations:
                                            c_min2 = None
                                            if dur[18]:
                                                c_min2 = dur[19]
                                            if c_min2 is None:
                                                c_min2 = c_min
                                            if c["id"] in self.var_data["highPriority"]:
                                                if (
                                                    dur[9]
                                                    in self.events_break_session_length_long.keys()
                                                ):
                                                    self.model.Add(
                                                        dur[0]
                                                        <= self.events_break_session_length_long[
                                                            dur[9]
                                                        ]
                                                    )
                                                    # .OnlyEnforceIf(
                                                    #     sessionlength_analyzer_bool
                                                    # )
                                                else:
                                                    self.model.Add(dur[0] <= c_max)
                                                    # .OnlyEnforceIf(
                                                    #     sessionlength_analyzer_bool
                                                    # )
                                                if c_min != 0:
                                                    inc = 1
                                                    if (
                                                        dur[9]
                                                        in self.events_break_session_length_short.keys()
                                                    ):
                                                        c_min2 = self.events_break_session_length_short[
                                                            dur[9]
                                                        ]
                                                    while inc < c_min2:
                                                        self.model.Add(dur[0] != inc)
                                                        # .OnlyEnforceIf(
                                                        #     sessionlength_analyzer_bool
                                                        # )
                                                        inc += 1
                    except Exception as e:
                        traceback.print_exc()

                elif c["type"] == "backToBack":
                    back_to_back_analyzer_bool = self.model.NewBoolVar(
                        f"back_to_back_analyzer_{c['id']}"
                    )
                    # self.model.Add(back_to_back_analyzer_bool == 1)
                    self.constraint_booleans_hard.append(back_to_back_analyzer_bool)
                    # self.constraint_booleans[c["id"]] = back_to_back_analyzer_bool
                    people_type = set(self.find_ids_by_role(["Person"]))
                    is_person_and_activity = False

                    all_user_anti = [
                        self.solutions1["resources1"]["resources"][user_a].id
                        for user_a in c["users_antecedent"]
                    ]
                    all_user_cons = [
                        self.solutions1["resources1"]["resources"][user_c].id
                        for user_c in c["users_consequence"]
                    ]

                    if set(all_user_anti).intersection(people_type) or set(
                        all_user_cons
                    ).intersection(people_type):
                        is_person_and_activity = True

                    if is_person_and_activity:
                        for user_a in c["users_antecedent"]:
                            user_a_id = self.solutions1["resources1"]["resources"][
                                user_a
                            ].id

                            for index in range(1, 6):
                                some_array = {}

                                for user_c in c["users_consequence"]:
                                    user_c_id = self.solutions1["resources1"][
                                        "resources"
                                    ][user_c].id
                                    val_back_to_back = self.get_appointments(
                                        [[user_c_id], [user_a_id], [str(index)]]
                                    )
                                    some_array.update(val_back_to_back)

                                back_to_back_values = list(some_array.values())
                                len_back = len(back_to_back_values)

                                for i1 in range(len_back):
                                    for i2 in range(i1 + 1, len_back):
                                        bool_left = self.model.NewBoolVar(
                                            f"left-{index}-{user_a_id}-{i1}-{i2}"
                                        )

                                        # Add constraints
                                        self.model.Add(
                                            back_to_back_values[i1][4]
                                            <= back_to_back_values[i2][3]
                                        ).OnlyEnforceIf(bool_left).OnlyEnforceIf(
                                            back_to_back_analyzer_bool
                                        )
                                        self.model.Add(
                                            back_to_back_values[i2][4]
                                            <= back_to_back_values[i1][3]
                                        ).OnlyEnforceIf(bool_left.Not()).OnlyEnforceIf(
                                            back_to_back_analyzer_bool
                                        )
                                        self.model.Add(
                                            back_to_back_values[i2][3]
                                            - back_to_back_values[i1][4]
                                            > 0 // self.var_data["slot_length"]
                                        ).OnlyEnforceIf(bool_left).OnlyEnforceIf(
                                            back_to_back_analyzer_bool
                                        )
                                        self.model.Add(
                                            back_to_back_values[i1][3]
                                            - back_to_back_values[i2][4]
                                            > 0 // self.var_data["slot_length"]
                                        ).OnlyEnforceIf(bool_left.Not()).OnlyEnforceIf(
                                            back_to_back_analyzer_bool
                                        )
                                        # self.model.Add(
                                        #     back_to_back_values[i2][3]
                                        #     - back_to_back_values[i1][4]
                                        #     <= 240 // self.var_data["slot_length"]
                                        # ).OnlyEnforceIf(bool_left).OnlyEnforceIf(
                                        #     back_to_back_analyzer_bool
                                        # )
                                        # self.model.Add(
                                        #     back_to_back_values[i1][3]
                                        #     - back_to_back_values[i2][4]
                                        #     <= 240 // self.var_data["slot_length"]
                                        # ).OnlyEnforceIf(bool_left.Not()).OnlyEnforceIf(
                                        #     back_to_back_analyzer_bool
                                        # )
                    else:
                        for index in range(1, 6):
                            some_array_anti = []
                            some_array_cons = []
                            for user_a in c["users_antecedent"]:
                                user_a_id = self.solutions1["resources1"]["resources"][
                                    user_a
                                ].id
                                val_back_to_back_anti = self.get_appointments(
                                    [[user_a_id], [str(index)]]
                                )
                                some_array_anti = some_array_anti + list(
                                    val_back_to_back_anti.values()
                                )
                            for user_c in c["users_consequence"]:
                                user_c_id = self.solutions1["resources1"]["resources"][
                                    user_c
                                ].id
                                val_back_to_back_cons = self.get_appointments(
                                    [[user_c_id], [str(index)]]
                                )
                                some_array_cons = some_array_cons + list(
                                    val_back_to_back_cons.values()
                                )
                            for i1 in some_array_anti:
                                inc = 0
                                for i2 in some_array_cons:
                                    bool_left = self.model.NewBoolVar(f"left")
                                    self.model.Add(i1[3] <= i2[3]).OnlyEnforceIf(
                                        bool_left
                                    ).OnlyEnforceIf(back_to_back_analyzer_bool)
                                    self.model.Add(i2[3] < i1[3]).OnlyEnforceIf(
                                        bool_left.Not()
                                    ).OnlyEnforceIf(back_to_back_analyzer_bool)
                                    self.model.Add(
                                        i2[3] - i1[4]
                                        > 0 // self.var_data["slot_length"]
                                    ).OnlyEnforceIf(bool_left).OnlyEnforceIf(
                                        back_to_back_analyzer_bool
                                    )
                                    self.model.Add(
                                        i1[3] - i2[4]
                                        > 0 // self.var_data["slot_length"]
                                    ).OnlyEnforceIf(bool_left.Not()).OnlyEnforceIf(
                                        back_to_back_analyzer_bool
                                    )

                                    # self.model.Add(
                                    #     i2[3] - i1[4]
                                    #     <= 240 // self.var_data["slot_length"]
                                    # ).OnlyEnforceIf(bool_left).OnlyEnforceIf(
                                    #     back_to_back_analyzer_bool
                                    # )
                                    # self.model.Add(
                                    #     i1[3] - i2[4]
                                    #     <= 240 // self.var_data["slot_length"]
                                    # ).OnlyEnforceIf(bool_left.Not()).OnlyEnforceIf(
                                    #     back_to_back_analyzer_bool
                                    # )
                elif c["type"] == "breakQuantity":

                    counter = 0
                    # self.constraint_booleans[c["id"]] = break_quantity_analyzer_bool
                    # self.break_booleans[c["id"]] = break_quantity_analyzer_bool

                    for user_a in c["users_antecedent"]:
                        user_a_id = self.solutions1["resources1"]["resources"][
                            user_a
                        ].id

                        work_ids = set(self.var_data["objectiveactivity"]) - set(
                            self.var_data["notWorking"]
                        )
                        print("notWorking", self.var_data["notWorking"])
                        print("work_ids", work_ids)
                        for index in range(0, 6):
                            for user_c in c["users_consequence"]:
                                user_c_id = self.solutions1["resources1"]["resources"][
                                    user_c
                                ].id
                                app_time = time.time()

                                therapy_val = self.get_appointments(
                                    [
                                        [user_a_id],
                                        [str(index)],
                                        self.var_data["objectiveactivity"],
                                    ]
                                )
                                working = self.get_appointments(
                                    [[user_a_id], [str(index)], work_ids]
                                )
                                break_val = self.get_appointments(
                                    [[user_a_id], [user_c_id], [str(index)]]
                                )

                                if not break_val or not therapy_val or not working:
                                    continue
                                print(
                                    "self.resource_first_appointment_start",
                                    self.resource_first_appointment_start,
                                )
                                bol_break = sum(num[6] for num in break_val.values())
                                break_appointments = [num for num in break_val.values()]
                                caravel_minutes_start = (
                                    120 // self.var_data["slot_length"]
                                )
                                nova_minutes_start = 60 // self.var_data["slot_length"]
                                caravel_minutes_end = (
                                    120 // self.var_data["slot_length"]
                                )
                                nova_minutes_end = 60 // self.var_data["slot_length"]
                                actual_minutes_start = 0
                                actual_minutes_end = 0
                                ##caravel
                                if (
                                    self.var_data["companyId"]
                                    == "b51dfb8f-a6c4-41be-913c-19fe0d911062"
                                ):
                                    actual_minutes_start = caravel_minutes_start
                                    actual_minutes_end = caravel_minutes_end
                                elif (
                                    self.var_data["companyId"]
                                    == "a7769d5a-8363-4fc1-94ac-a8d82c9c0c34"
                                ):
                                    actual_minutes_start = nova_minutes_start
                                    actual_minutes_end = nova_minutes_end
                                print("actual_minutes_start", actual_minutes_start)
                                print("actual_minutes_end", actual_minutes_end)
                                if (
                                    user_a_id
                                    in self.resource_first_appointment_start[index]
                                ):
                                    for b in break_appointments:
                                        self.see_here.append(
                                            [
                                                [index],
                                                b[3],
                                                b[4],
                                                self.resource_first_appointment_start[
                                                    index
                                                ][user_a_id],
                                                self.resource_last_appointment_end[
                                                    index
                                                ][user_a_id],
                                                b[6],
                                                self.resources1.resources[
                                                    user_a_id
                                                ].firstName,
                                            ]
                                        )
                                        print(
                                            "gotter1",
                                            b[3],
                                            b[4],
                                            self.resource_first_appointment_start[
                                                index
                                            ][user_a_id],
                                        )
                                        # self.model.Add(b[6]==0)
                                        self.model.Add(
                                            self.resource_first_appointment_start[
                                                index
                                            ][user_a_id]
                                            + actual_minutes_start
                                            < b[3]
                                        ).OnlyEnforceIf(b[6])
                                        self.model.Add(
                                            self.resource_last_appointment_end[index][
                                                user_a_id
                                            ]
                                            - actual_minutes_end
                                            > b[4]
                                        ).OnlyEnforceIf(b[6])
                                # self.model.Add(
                                #     bol_break <= int(c["min"])
                                # ).OnlyEnforceIf(break_quantity_analyzer_bool)

                                dur_working = sum(num[0] for num in working.values())

                                break_on_bol = self.model.NewBoolVar("break_on_bol")
                                ##NEW ANALYZE
                                # time_analyzer_bool = self.model.NewBoolVar(
                                #     f"time_analyzer_{c['id']}"
                                #         )
                                ##NEW ANALYZE
                                break_quantity_analyzer_bool = self.model.NewBoolVar(
                                    f"break_quantity_analyzer_{c['id']}"
                                )
                                if c["id"] in self.var_data["highPriority"]:
                                    self.constraint_booleans_hard.append(
                                        break_quantity_analyzer_bool * 100
                                    )
                                else:
                                    self.constraint_booleans_soft.append(
                                        break_quantity_analyzer_bool
                                    )

                                self.model.Add(bol_break == 1).OnlyEnforceIf(
                                    break_on_bol
                                ).OnlyEnforceIf(break_quantity_analyzer_bool)
                                self.model.Add(bol_break == 0).OnlyEnforceIf(
                                    break_on_bol.Not()
                                ).OnlyEnforceIf(break_quantity_analyzer_bool)

                                self.model.Add(dur_working >= c_max).OnlyEnforceIf(
                                    break_on_bol
                                ).OnlyEnforceIf(break_quantity_analyzer_bool)
                                self.model.Add(dur_working < c_max).OnlyEnforceIf(
                                    break_on_bol.Not()
                                )

                                # if break_val:
                                #     all_lunches_bol = []
                                #     i_break_count = 0

                                #     num_scheduled = [
                                #         1
                                #         for break_d in break_val.values()
                                #         if break_d[5]
                                #     ]
                                #     sum_scheduled = sum(num_scheduled)

                                # val_time = time.time()

                                # for break_d in break_val.values():
                                #     if not break_d[5] and sum_scheduled >= 1:
                                #         self.model.Add(
                                #             break_d[6] == 0
                                #         ).OnlyEnforceIf(
                                #             break_quantity_analyzer_bool
                                #         )
                                #         continue
                                #     break_exists = self.model.NewBoolVar(
                                #         f"break_exists-{i_break_count}"
                                #     )
                                #     i_break_count += 1

                                #     self.model.Add(break_d[0] > 0).OnlyEnforceIf(
                                #         break_exists
                                #     ).OnlyEnforceIf(break_quantity_analyzer_bool)
                                #     self.model.Add(break_d[0] == 0).OnlyEnforceIf(
                                #         break_exists.Not()
                                #     ).OnlyEnforceIf(break_quantity_analyzer_bool)

                                #     all_lunches_bol.append(break_exists)

                                # final_lunch_bol = self.model.NewBoolVar(
                                #     "final_lunch_bol"
                                # )

                                # self.model.Add(dur_working >= c_max).OnlyEnforceIf(
                                #     final_lunch_bol
                                # ).OnlyEnforceIf(break_quantity_analyzer_bool)
                                # self.model.Add(dur_working < c_max).OnlyEnforceIf(
                                #     final_lunch_bol.Not()
                                # ).OnlyEnforceIf(break_quantity_analyzer_bool)
                                # self.model.Add(
                                #     sum(all_lunches_bol) == 1
                                # ).OnlyEnforceIf(final_lunch_bol).OnlyEnforceIf(
                                #     break_quantity_analyzer_bool
                                # )
                                # self.model.Add(
                                #     sum(all_lunches_bol) == 0
                                # ).OnlyEnforceIf(
                                #     final_lunch_bol.Not()
                                # ).OnlyEnforceIf(
                                #     break_quantity_analyzer_bool
                                # )

                elif c["type"] == "session":
                    # session_analyzer_bool = self.model.NewBoolVar(
                    #     f"session_analyzer_{c['id']}"
                    # )
                    # self.constraint_booleans[c["id"]] = session_analyzer_bool
                    for user_a in c["users_antecedent"]:
                        user_a_id = self.solutions1["resources1"]["resources"][
                            user_a
                        ].id
                        if c["frequency"] == "day":
                            for index, x in enumerate(days_arrays):
                                if index == 0:
                                    continue
                                if c["each_or_all_users"] == "each":
                                    for user_c in c["users_consequence"]:
                                        arr = []
                                        user_c_id = self.solutions1["resources1"][
                                            "resources"
                                        ][user_c].id
                                        arr = list(
                                            map(
                                                lambda num: num[6],
                                                self.get_appointments(
                                                    [
                                                        [user_c_id],
                                                        [user_a_id],
                                                        [str(index)],
                                                    ]
                                                ).values(),
                                            )
                                        )
                                        if len(arr) == 0:
                                            continue
                                        session_analyzer_bool = self.model.NewBoolVar(
                                            f"session_analyzer_{c['id']}"
                                        )
                                        if c["id"] in self.var_data["highPriority"]:
                                            self.constraint_booleans_hard.append(
                                                session_analyzer_bool
                                            )
                                        else:
                                            self.constraint_booleans_soft.append(
                                                session_analyzer_bool
                                            )

                                        self.model.Add(
                                            sum(arr) <= c["max"]
                                        ).OnlyEnforceIf(session_analyzer_bool)
                                        self.model.Add(
                                            sum(arr) >= c["min"]
                                        ).OnlyEnforceIf(session_analyzer_bool)
                                else:
                                    arr = []
                                    for user_c in c["users_consequence"]:
                                        user_c_id = self.solutions1["resources1"][
                                            "resources"
                                        ][user_c].id
                                        val = self.get_appointments(
                                            [[user_c_id], [user_a_id], [str(index)]]
                                        )
                                        if len(val) == 0:
                                            continue
                                        arr = arr + list(
                                            map(lambda num: num[6], val.values())
                                        )
                                    if len(arr) == 0:
                                        continue
                                    session_analyzer_bool = self.model.NewBoolVar(
                                        f"session_analyzer_{c['id']}"
                                    )
                                    if c["id"] in self.var_data["highPriority"]:
                                        self.constraint_booleans_hard.append(
                                            session_analyzer_bool
                                        )
                                    else:
                                        self.constraint_booleans_soft.append(
                                            session_analyzer_bool
                                        )
                                    self.model.Add(sum(arr) <= c["max"]).OnlyEnforceIf(
                                        session_analyzer_bool
                                    )
                                    if c["min"] != 0:
                                        self.model.Add(
                                            sum(arr) >= c["min"]
                                        ).OnlyEnforceIf(session_analyzer_bool)

                        elif c["frequency"] == "week":
                            if c["each_or_all_users"] == "each":
                                for user_c in c["users_consequence"]:
                                    arr = []
                                    user_c_id = self.solutions1["resources1"][
                                        "resources"
                                    ][user_c].id
                                    val = self.get_appointments(
                                        [[user_c_id], [user_a_id]]
                                    )
                                    if len(val) == 0:
                                        continue
                                    arr = arr + list(
                                        map(lambda num: num[0], val.values())
                                    )
                                    if len(arr) == 0:
                                        continue
                                    print(
                                        "session_analyzer_bool", session_analyzer_bool
                                    )
                                    session_analyzer_bool = self.model.NewBoolVar(
                                        f"session_analyzer_{c['id']}"
                                    )
                                    if c["id"] in self.var_data["highPriority"]:
                                        self.constraint_booleans_hard.append(
                                            session_analyzer_bool
                                        )
                                    else:
                                        self.constraint_booleans_soft.append(
                                            session_analyzer_bool
                                        )
                                    self.model.Add(sum(arr) <= c["max"]).OnlyEnforceIf(
                                        session_analyzer_bool
                                    )
                                    if c["min"] > 1:
                                        total = sum(
                                            arr
                                        )  # create it once so we don't rebuild the expression
                                        for i in range(1, c["min"]):
                                            # Disallow totals of 1, 2, …, min-1
                                            self.model.Add(total != i).OnlyEnforceIf(
                                                session_analyzer_bool
                                            )

                            else:
                                arr = []
                                for user_c in c["users_consequence"]:
                                    user_c_id = self.solutions1["resources1"][
                                        "resources"
                                    ][user_c].id
                                    val = self.get_appointments(
                                        [[user_c_id], [user_a_id]]
                                    )
                                    if len(val) == 0:
                                        continue
                                    arr = arr + list(
                                        map(lambda num: num[0], val.values())
                                    )
                                    if len(arr) == 0:
                                        continue
                                    session_analyzer_bool = self.model.NewBoolVar(
                                        f"session_analyzer_{c['id']}"
                                    )
                                    if c["id"] in self.var_data["highPriority"]:
                                        self.constraint_booleans_hard.append(
                                            session_analyzer_bool
                                        )
                                    else:
                                        self.constraint_booleans_soft.append(
                                            session_analyzer_bool
                                        )
                                    self.model.Add(sum(arr) <= c["max"]).OnlyEnforceIf(
                                        session_analyzer_bool
                                    )
                                    if c["min"] != 0:
                                        self.model.Add(
                                            sum(arr) >= c["min"]
                                        ).OnlyEnforceIf(session_analyzer_bool)

                constraint_execution_time = time.time() - constraint_start_time
                self.matches_frequency_timings[f"constraint_{c['type']}"] = (
                    constraint_execution_time
                )

            for k, v in counts_of_vars.items():
                if v == 0:
                    counts_of_vars[k] = 1
            for k, v in inte_vars.items():
                self.model.Add(v == 1)

        print("\nConstraint Processing Time (Benchmarking Results):")
        for key, value in sorted(
            self.matches_frequency_timings.items(), key=lambda x: x[1], reverse=True
        ):
            print(f"{key}: {value:.6f} seconds")

    def flag(self, row):
        return row[6] if hasattr(row[6], "Not") else row[11]

    def solve_model(self, data, timeconstraints, e_pair):
        data_insert_time = time.time()
        self.data_insert(data)
        self.timings["Data_insert"] = time.time() - data_insert_time
        try:
            frequency_time = time.time()
            self.matches_frequency()
            self.timings["Matches_frequency"] = time.time() - frequency_time
        except Exception as e:
            traceback.print_exc()
        try:
            self.prefered_session_lengths()
            self.add_a_b_schedule()
            if self.var_data["settings"]["driveTime"]:
                self.constraint_drive()
                # self.timings["Constraint_drive"], _ = self.constraint_drive()
        except Exception as e:
            traceback.print_exc()
        if self.var_data["is_overlap_constraint"]:
            # pass
            self.no_overlap(e_pair)
        # self.timings["No_overlap"], _ = self.no_overlap(e_pair)
        try:
            objective_time = time.time()
            self.optimize_schedule_objective(self.var_data["objectiveactivity"])
            self.timings["Optimize_schedule_objective"] = time.time() - objective_time
        except Exception as e:
            traceback.print_exc()
        solve_time = time.time()
        self.solve_with_analyzer()
        self.timings["Solve"] = time.time() - solve_time

        print("Automate Benchmarking:", json.dumps(self.timings, indent=4))
