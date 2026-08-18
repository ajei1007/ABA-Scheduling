import datetime
import time
import itertools
import copy
import math
import uuid
from ortools.sat.python import cp_model
from itertools import combinations, product
from datetime import timezone
from external import haversine, round_to_nearest_interval, detect_range, debug_mode
from core.shared.utils import intersection, time_to_slot, slot_to_time
from calculate_drive_time import *
from models.scheduling_models import Resources
from test_capacity import run_interval_scheduler_with_global_caps
from team_creator import run_team_creator
from core.shared.event_schedular.helpers import (
    VarArraySolutionPrinter,
    VarArraySolutionPrinter2,
)


class EventScheduler:
    def __init__(self, dict_data, more_data):
        # Initialization of basic parameters
        self.optimizer_or_not = dict_data.dd_data["optimizer_sol"]
        self.highPriority = [
            *dict_data.dd_data["highPriority"],
            *dict_data.dd_data["soft"],
        ]
        # self.softConstraints = dict_data.dd_data["soft"]
        self.header = dict_data.dd_data["header"]  #
        self.drive_time_on = dict_data.dd_data["settings"]["driveTime"]
        self.host = dict_data.dd_data["host"]
        self.part1 = dict_data.dd_data.get("part1", True)
        self.start_date = dict_data.start_date
        self.end_date = dict_data.end_date
        self.onCall = dict_data.onCall
        self.branch_id = dict_data.branch_id
        self.isolatedResources = dict_data.isolatedResources
        self.slot_length = max(5, min(dict_data.settings.get("timeInterval", 15), 15))
        self.settings = dict_data.settings
        self.expanded_resources = dict_data.expanded_resources
        self.expanded_resources_filter = dict_data.expanded_resources_filter
        self.resourceCombinationsExclude = dict_data.resourceCombinationsExclude
        self.distance_matrix = dict_data.distance_matrix
        self.num_of_days = (
            datetime.datetime.strptime(self.end_date, "%Y-%m-%d")
            - datetime.datetime.strptime(self.start_date, "%Y-%m-%d")
        ).days
        self.soft = more_data["soft"]
        self.is_session = more_data.get("is_session", True)
        self.is_orange = more_data["is_orange"]
        self.investigate = more_data.get("investigate", [])
        self.is_investigate = len(self.investigate) > 0
        self.user_availabilities_general = {}
        self.user_solutions_array_unit = {}
        self.user_solutions_array_total = {}
        self.availabilities = dict_data.availabilities
        self.activity_table = dict_data.activity_table
        self.users = dict_data.users
        self.capacities = dict_data.capacities
        self.branches = dict_data.branches
        self.e_pair = dict_data.e_pair
        self.subgroups = dict_data.subgroups
        self.location_raw_data = dict_data.location_raw_data
        self.home_id = dict_data.home_id
        self.flags = dict_data.flags_data
        self.created_events = []
        self.limit_coefficient = 10
        self.conflicted_constraints = {}
        self.debug_booleans = debug_mode()

        self.custom_constraints = self._filter_constraints(dict_data.custom_constraints)
        # self.custom_constraints = dict_data.custom_constraints

        self.branch_structure = dict_data.branch_structure
        self.events = dict_data.events
        self.events2 = dict_data.events2
        self.events_billable = []
        self.events_nonbillable = []
        self.resources1 = Resources(self.users)

        self.events_poss = []
        self.events_poss_raw = []
        self.relevant_users = set()
        self.user_uuid_to_index = {}
        self.time_to_slot = time_to_slot
        self.slot_to_time = slot_to_time

    def _filter_constraints(self, custom_constraints):
        """Filter custom constraints based on soft and highPriority flags."""
        # if not self.is_investigate:
        # Only keep non-soft constraints if `soft` is True
        # if self.soft:
        #     custom_constraints = [
        #         c for c in custom_constraints if not c.get("soft")
        #     ]
        # Retain only high-priority constraints
        return [c for c in custom_constraints if c["id"] in self.highPriority]

    def calc_availabilities(self, start_time, end_time, format, timezone_bol=True):
        start = datetime.datetime.strptime(start_time, format)
        end = datetime.datetime.strptime(end_time, format)

        if timezone_bol:
            start = start.astimezone(timezone.utc)
            end = end.astimezone(timezone.utc)

        interval_start = self.time_to_slot(
            start.strftime("%H:%M:%S"),
            (start.weekday()),
            15 // (15 // self.slot_length),
        )
        interval_end = self.time_to_slot(
            end.strftime("%H:%M:%S"), (end.weekday()), 15 // (15 // self.slot_length)
        )

        if interval_end < interval_start:
            interval_end = 672
        return [i for i in range(interval_start, interval_end)]

    def get_user_ids(self, role_name, type_str="roles"):
        return {i for i, user in enumerate(self.users) if role_name in user[type_str]}

    def get_index_of_id(self, user_id):
        return next(
            (i for i, user in enumerate(self.users) if user["id"] == user_id), None
        )

    def detect_range(self, l):
        l.sort()  # Ensure the list is sorted
        for _, group in itertools.groupby(enumerate(l), lambda x: x[1] - x[0]):
            group = list(group)
            yield group[0][1], group[-1][1] + 1

    def convert_index_to_slot(self, lst):
        return [i for i, n in enumerate(lst) if n == 1]

    def find_users_from_roles_subgroups(self, t):
        t_set = set(t)
        users = []
        for i, user in enumerate(self.users):
            roles = (
                user["roles"] if isinstance(user["roles"], set) else set(user["roles"])
            )
            subgroups = (
                user["subgroups_real"]
                if isinstance(user["subgroups_real"], set)
                else set(user["subgroups_real"])
            )
            branches = (
                user["branches_real"]
                if isinstance(user["branches_real"], set)
                else set(user["branches_real"])
            )
            if t_set.issubset(roles | subgroups | branches):
                users.append(i)
        return users

    def handle_general_constraint_type(self, roles, subgroups, branches):
        p = list(product(*roles))
        t = list(product(*subgroups))
        o = list(product(*branches))  # This is unused right now
        users = []
        for i in list(product(*p, *t)):
            users = [*users, *self.find_users_from_roles_subgroups(i)]
        return list(set(users))

    def handle_general_constraint_specific(self, users1):
        return list(product(*users1))

    def handle_general_constraint_specific_index(self, users1):
        return np.array(
            [
                self.user_uuid_to_index[y]
                for x in product(*users1)
                for y in x
                if y in self.user_uuid_to_index_keys
            ]
        ).flatten()

    def get_resources_from_role(self, roles):
        return list(
            set(
                resource_id
                for resource_id, resource in self.resources1.resources.items()
                if any(role in resource.roles for role in roles)
            )
        )

    def get_appointments(self, arr, slots_bol=True, slots=None):
        if slots_bol:
            slots = self.resources1.slots  # Use default slots if `slots_bol` is True

        obj = {
            tup: event
            for tup, event in slots.items()
            if all(any(res in tup for res in resources) for resources in arr)
        }
        return obj

    def get_id_from_role_array(self, role, resource_ids_r):
        return next(
            (res for res in resource_ids_r if role in self.users[res]["roles"]), -1
        )

    def turn_uuid_array_into_index(self, resource_ids):
        return [
            self.user_uuid_to_index[res]
            for res in resource_ids
            if res in self.user_uuid_to_index_keys
        ]

    def main_drive_time(self):
        constraint_drive_data = get_drive_time_data(self.header, self.host)
        debug_drive_time = self.debug_booleans.get("main_drive_time", True)
        updated_events_poss = []

        for i, event in enumerate(self.events):
            for res in event["resourceIds"]:
                if res in self.user_uuid_to_index_keys:
                    index = self.user_uuid_to_index[res]
                    self.resources1.resources[index].events.append(i)

        for ev in self.events_poss:
            start_drive, end_drive = 0, 0
            person_drive = {}
            resource_ids = ev["resourceIds_r"]
            event_start = datetime.datetime.strptime(
                ev["start"], "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            event_end = datetime.datetime.strptime(ev["end"], "%Y-%m-%dT%H:%M:%S.%fZ")
            updated_event = copy.deepcopy(ev)

            # Get location details
            location_id = self.get_id_from_role_array("Location", resource_ids)
            location_ids = {
                user["id"] for user in self.users if "Location" in user.get("roles", [])
            }

            if location_id >= 0:
                location_address = self.users[location_id]["address"]
                for res in resource_ids:
                    if "Person" in self.users[res]["roles"]:
                        # Process person-related resources
                        relevant_events = self.resources1.resources[res].events
                        if relevant_events:
                            for e in relevant_events:
                                prior_event = self.events[e]
                                prior_loc_id = prior_event["loc_id"]
                                combined_resource_ids = set(
                                    prior_event["resourceIds"]
                                    + [i[:-1] for i in ev["resourceIds"]]
                                )

                                client_ids = [
                                    ii
                                    for ii in combined_resource_ids
                                    if ii in self.user_uuid_to_index_keys
                                    and "Client"
                                    in self.users[self.user_uuid_to_index[ii]]["roles"]
                                ]

                                client_ids = sorted(set(client_ids))
                                if not client_ids or prior_loc_id in {
                                    i[:-1] for i in ev["resourceIds"]
                                }:
                                    continue

                                prior_start = datetime.datetime.strptime(
                                    prior_event["start"], "%Y-%m-%dT%H:%M:%S.%fZ"
                                )
                                prior_end = datetime.datetime.strptime(
                                    prior_event["end"], "%Y-%m-%dT%H:%M:%S.%fZ"
                                )

                                if prior_start > event_end or prior_end < event_start:
                                    continue

                                delta_start = (event_start - prior_end).total_seconds()
                                delta_end = (prior_start - event_end).total_seconds()

                                prior_address = prior_event["address"]
                                current_address = ev["address"]

                                if (
                                    current_address
                                    and prior_address
                                    and current_address != prior_address
                                ):
                                    addresses_pair = tuple(
                                        sorted([current_address, prior_address])
                                    )
                                    drive_time_data = constraint_drive_data.get(
                                        addresses_pair
                                    )

                                    if not drive_time_data:
                                        drive_time_data = return_interval_drive_time(
                                            current_address, prior_address, 11, 30
                                        )
                                        if drive_time_data != [0, 0]:
                                            post_drive_time_data(
                                                self.header,
                                                {
                                                    "data": {
                                                        "address1": current_address,
                                                        "address2": prior_address,
                                                        "duration": drive_time_data[1],
                                                        "distance": drive_time_data[0],
                                                    }
                                                },
                                                self.host,
                                            )
                                            constraint_drive_data[addresses_pair] = {
                                                "mid": drive_time_data[1]
                                            }

                                    if drive_time_data:
                                        if delta_start >= 0:
                                            start_drive = round_to_nearest_interval(
                                                drive_time_data["mid"] // 60,
                                                self.slot_length,
                                            )
                                        if delta_end >= 0:
                                            end_drive = round_to_nearest_interval(
                                                drive_time_data["mid"] // 60,
                                                self.slot_length,
                                            )

                                    person_drive[self.users[res]["id"]] = {
                                        "start": start_drive,
                                        "end": end_drive,
                                        "beginningDrive": [
                                            ev["start"],
                                            updated_event["start"],
                                        ],
                                        "endDrive": [updated_event["end"], ev["end"]],
                                    }

            updated_event["person_drive"] = person_drive
            updated_event["start"] = datetime.datetime.strftime(
                event_start + datetime.timedelta(minutes=start_drive),
                "%Y-%m-%dT%H:%M:%S.%fZ",
            )
            updated_event["end"] = datetime.datetime.strftime(
                event_end - datetime.timedelta(minutes=end_drive),
                "%Y-%m-%dT%H:%M:%S.%fZ",
            )

            if (
                "fake" not in updated_event
                and (event_end - event_start).total_seconds() > 0
            ):
                updated_events_poss.append(updated_event)

        for event in self.resources1.drive_constraints:
            for index, event_poss in enumerate(updated_events_poss):
                common_users = set(event_poss["resourceIds_r"]) & set(
                    event["users_antecedent_set"]
                )
                event_address = event_poss["address"]

                if event_address and len(event_address) >= 5:
                    for user_id in common_users:
                        user_address = self.users[user_id]["address"]
                        if user_address and user_address != event_address:
                            address_pair = tuple(sorted([event_address, user_address]))
                            drive_time = constraint_drive_data.get(
                                address_pair, {}
                            ).get("mid", 0)

                            if drive_time // 60 > event["max"]:
                                updated_events_poss.pop(index)
                                break

        self.events_poss = updated_events_poss
        return updated_events_poss

    def refine_scheduling_constraints(self):
        model = cp_model.CpModel()

        default_arr = [0] * 7
        work_together_obj = {}
        time_together_obj = {}
        sessions_together_obj = {}

        for event in self.events:
            duration = event["duration"]
            event_availabilities = self.calc_availabilities(
                event["start"], event["end_real_time"], "%Y-%m-%dT%H:%M:%S.%fZ", False
            )

            if not event_availabilities:
                continue

            time_index = math.floor(
                event_availabilities[0] / (96 * (15 // self.slot_length))
            )

            for res1_id, res2_id in combinations(event["resourceIds"], 2):
                if (
                    res1_id not in self.user_uuid_to_index_keys
                    or res2_id not in self.user_uuid_to_index_keys
                ):
                    continue

                res1 = self.user_uuid_to_index[res1_id]
                res2 = self.user_uuid_to_index[res2_id]

                if res1 == res2:
                    continue

                pair_key = (res1, res2) if res1 < res2 else (res2, res1)

                if pair_key not in work_together_obj:
                    work_together_obj[pair_key] = default_arr.copy()
                    time_together_obj[pair_key] = default_arr.copy()
                    sessions_together_obj[pair_key] = default_arr.copy()

                    for resource in (res1, res2):
                        other_res = res2 if resource == res1 else res1
                        self.resources1.resources[resource].work_together_arr[
                            other_res
                        ] = default_arr.copy()
                        self.resources1.resources[resource].sessions_together_arr[
                            other_res
                        ] = default_arr.copy()
                        self.resources1.resources[resource].time_with_users[
                            other_res
                        ] = default_arr.copy()

                work_together_obj[pair_key][time_index] = 1
                sessions_together_obj[pair_key][time_index] += 1
                time_together_obj[pair_key][time_index] += duration

                for resource in (res1, res2):
                    other_res = res2 if resource == res1 else res1
                    self.resources1.resources[resource].work_together_arr[other_res][
                        time_index
                    ] = 1
                    self.resources1.resources[resource].sessions_together_arr[
                        other_res
                    ][time_index] += 1
                    self.resources1.resources[resource].time_with_users[other_res][
                        time_index
                    ] += duration

        for event_info in self.events_poss_raw:
            start_time = event_info["start"]
            end_time = event_info["end"]
            resource_ids = event_info["resourceIds"]
            duration = end_time - start_time
            appointment_var = model.NewBoolVar("appointment_var")
            event_interval = model.NewOptionalIntervalVar(
                start_time, duration, end_time, appointment_var, "interval"
            )
            self.resources1.slots[tuple([start_time]) + tuple(resource_ids)] = [
                duration,
                event_interval,
                start_time,
                end_time,
                False,
                appointment_var,
                resource_ids,
                [],
            ]

        constraint_ids = {}
        users_antecedents = {}

        def operate_constraint(users_consequence, together_arr_type):
            if not together_arr_type:
                return

            for user_a in users_antecedents:
                aggregated_values = work_together_obj.copy()
                total_count = 0

                for user_c in users_consequence:
                    user_constraints = getattr(
                        self.resources1.resources[user_a], together_arr_type
                    ).get(user_c, [])
                    for index, value in enumerate(user_constraints):
                        aggregated_values[index] += value

                    if (
                        c.get("type_or_specific_consequence") == "specific"
                        or c.get("constraint") == "usertosession"
                    ):
                        total_count += sum(user_constraints)
                    else:
                        total_count += max(user_constraints, default=0)

                appointments = self.get_appointments([[user_a], users_consequence])

                for appointment in appointments.values():
                    time_index = math.floor(
                        appointment[2] / (96 * (15 // self.slot_length))
                    )
                    intersecting_users = intersection(appointment[6], users_consequence)
                    appointment_var = appointment[5]

                    if time_index == 7:
                        continue

                    if intersecting_users:
                        sub_count = 0
                        for user in intersecting_users:
                            user_constraints = getattr(
                                self.resources1.resources[user_a], together_arr_type
                            ).get(user, [])
                            if c["frequency"] == "day":
                                sub_count += user_constraints[time_index] > 0
                            elif c["frequency"] == "week":
                                sub_count += max(user_constraints, default=0) > 0

        for index, constraint in enumerate(self.custom_constraints):
            if (
                constraint["id"]
                not in self.highPriority
                # and constraint["id"] not in self.softConstraints
            ):
                continue

            supported_constraints = {
                "matching",
                "unmatching",
                "grouping",
                "usertouser",
                "usertosession",
            }
            if constraint["constraint"] not in supported_constraints:
                constraint_ids[index] = {
                    "min": constraint["min"],
                    "max": constraint["max"],
                    "frequency": constraint["frequency"],
                    "constraint": constraint["constraint"],
                    "days": (
                        list(range(7))
                        if not constraint.get("days")
                        else constraint["days"]
                    ),
                }

                users_antecedent = (
                    self.handle_general_constraint_type(
                        constraint["apply_constraint_to_this_role"],
                        constraint["apply_constraint_to_this_subgroup"],
                        constraint["apply_constraint_to_this_branch"],
                    )
                    if constraint["type_or_specific"] == "type"
                    else self.handle_general_constraint_specific_index(
                        constraint["apply_constraint_to_this_user"]
                    )
                )
                users_consequence = (
                    self.handle_general_constraint_type(
                        constraint["consequence_constraint_to_this_role"],
                        constraint["consequence_constraint_to_this_subgroup"],
                        constraint["consequence_constraint_to_this_branch"],
                    )
                    if constraint["type_or_specific_consequence"] == "type"
                    else self.handle_general_constraint_specific_index(
                        constraint["consequence_constraint_to_this_user"]
                    )
                )

                if constraint["constraint"] == "drive":
                    self.resources1.drive_constraints.append(
                        {
                            "each_or_all_users": constraint["each_or_all_users"],
                            "frequency": constraint["frequency"],
                            "weight": constraint["weight"],
                            "type": "time",
                            "users_antecedent": users_antecedent,
                            "users_consequence": users_consequence,
                            "users_antecedent_set": set(users_antecedent),
                            "users_consequence_set": set(users_consequence),
                            "max": constraint["max"],
                            "min": constraint["min"],
                            "id": constraint["id"],
                            "rank": index,
                        }
                    )

                elif constraint["constraint"] == "time":
                    frequency = constraint["frequency"]
                    self.resources1.frequency_constraints.append(
                        {
                            "each_or_all_users": constraint["each_or_all_users"],
                            "frequency": frequency,
                            "weight": constraint["weight"],
                            "type": "time",
                            "soft": constraint["soft"],
                            "users_antecedent": users_antecedent,
                            "users_consequence": users_consequence,
                            "max": constraint["max"],
                            "min": constraint["min"],
                            "id": constraint["id"],
                            "rank": index,
                        }
                    )

                    for user_antecedent in users_antecedent:
                        user_time_constraints = self.resources1.resources[
                            user_antecedent
                        ].time_constraints[frequency]
                        constraint_obj = {
                            "min": constraint["min"],
                            "max": constraint["max"],
                            "each_or_all_users": constraint["each_or_all_users"],
                            "weight": constraint["weight"],
                            "users_consequence": users_consequence,
                            "users_antecedent": users_antecedent,
                        }
                        for user_consequence in users_consequence:
                            if user_consequence not in user_time_constraints:
                                user_time_constraints[user_consequence] = constraint_obj
                                self.resources1.resources[
                                    user_consequence
                                ].time_constraints[frequency][
                                    user_antecedent
                                ] = constraint_obj

                else:
                    constraint_type_mapping = {
                        "usertouser": ("work_together_arr", "frequency"),
                        "usertosession": ("sessions_together_arr", "session"),
                    }
                    together_arr_type, type_label = constraint_type_mapping.get(
                        constraint["constraint"], (None, "nothing")
                    )

                    self.resources1.frequency_constraints.append(
                        {
                            "each_or_all_users": constraint["each_or_all_users"],
                            "frequency": constraint["frequency"],
                            "weight": constraint["weight"],
                            "type": type_label,
                            "soft": constraint["soft"],
                            "users_antecedent": users_antecedent,
                            "users_consequence": users_consequence,
                            "max": constraint["max"],
                            "min": constraint["min"],
                            "id": constraint["id"],
                            "rank": index,
                        }
                    )

                    if (
                        constraint["constraint"] == "usertosession"
                        and constraint["each_or_all_users"] == "each"
                    ):
                        for user_consequence in users_consequence:
                            operate_constraint([user_consequence], together_arr_type)
                    else:
                        operate_constraint(users_consequence, together_arr_type)

        appointments = self.get_appointments(
            [self.get_resources_from_role(["Resource"])]
        )
        model.Maximize(sum(appointment[5] for appointment in appointments.values()))

        solver = cp_model.CpSolver()
        solution_printer = VarArraySolutionPrinter2(
            self.resources1.slots.values(),
            self.events_poss,
            self.events_poss_raw,
            self.resources1,
            self.is_investigate,
        )
        solver.parameters.log_search_progress = True

        status = solver.Solve(model, solution_printer)

        new_all_solutions = []

        for solution in solution_printer.all_solutions:
            session_max = 36000000
            pass_solution = False

            for cus_constraint in self.resources1.frequency_constraints:
                if cus_constraint["id"] not in self.highPriority:
                    continue

                if cus_constraint["type"] == "sessionlength":
                    antecedent_resources = intersection(
                        solution["resourceIds_r"], cus_constraint["users_antecedent"]
                    )
                    consequence_resources = intersection(
                        solution["resourceIds_r"], cus_constraint["users_consequence"]
                    )

                    if antecedent_resources and consequence_resources:
                        session_length = (
                            int(solution["end_r"] - solution["start_r"])
                            * 15
                            // (15 // self.slot_length)
                        )
                        min_session_length = cus_constraint["minSeconds"] // 60

                        if min_session_length > session_length:
                            pass_solution = True
                            break

            for res1, res2 in list(combinations(solution["resourceIds_r"], 2)):
                time_constraints = self.resources1.resources[res1].time_constraints
                time_constraints2 = self.resources1.resources[res2].time_constraints
                time_with_users = self.resources1.resources[res1].time_with_users
                time_with_users2 = self.resources1.resources[res2].time_with_users
                time_with_users_keys = time_with_users.keys()
                time_with_users_keys2 = time_with_users2.keys()
                if self.is_session and res2 in time_constraints["session"].keys():
                    remaining = time_constraints["session"][res2]["max"] * 3600
                    if remaining < session_max:
                        session_max = remaining
                if res2 in time_constraints["day"].keys():
                    total = 0
                    if res1 == 0 or res2 == 0:
                        pass
                    ind = math.floor(
                        solution["start_r"] / (96 * (15 // self.slot_length))
                    )
                    if time_constraints["day"][res2]["each_or_all_users"] == "each":
                        if res2 in time_with_users_keys:
                            total = time_with_users[res2][ind]
                    else:
                        for us in (
                            time_constraints["day"][res2]["users_consequence"]
                            + time_constraints2["day"][res1]["users_antecedent"]
                        ):
                            if us in time_with_users_keys:
                                total += time_with_users[us][ind]
                            if us in time_with_users_keys2:
                                total += time_with_users2[us][ind]
                    if res1 == 11 or res2 == 11:
                        pass
                    if False:
                        remaining = total
                    else:
                        remaining = time_constraints["day"][res2]["max"] * 3600
                        if (
                            "units" in time_constraints["day"][res2].keys()
                            and time_constraints["day"][res2]["units"] == "minutes"
                        ):
                            remaining = remaining // 60

                    if remaining < session_max:
                        session_max = remaining
                if res2 in time_constraints["week"].keys():
                    total = 0
                    if time_constraints["week"][res2]["each_or_all_users"] == "each":
                        if res2 in time_with_users_keys:
                            total = sum(time_with_users[res2])
                    else:
                        for us in (
                            time_constraints["week"][res2]["users_consequence"]
                            + time_constraints2["week"][res1]["users_antecedent"]
                        ):
                            if us in time_with_users_keys:
                                total += sum(time_with_users[us])
                            if us in time_with_users_keys2:
                                total += sum(time_with_users2[us])
                    if False:
                        remaining = total
                    else:
                        remaining = time_constraints["week"][res2]["max"] * 3600 - total
                    if remaining < session_max:
                        session_max = remaining

            slot_duration = int(solution["end_r"] - solution["start_r"])
            session_max_slot_duration = int(
                session_max / 3600.0 * (4 * (15 // self.slot_length))
            )
            current_start = solution["start_r"]
            new_start = solution["new_start"]

            if session_max_slot_duration < slot_duration:
                start_time = None
                end_time = None
                while (
                    (session_max_slot_duration) > 0
                    and slot_duration > 0
                    and current_start + (session_max_slot_duration) < solution["end_r"]
                ):

                    new_end = current_start + (session_max_slot_duration)
                    start = self.slot_to_time(
                        current_start, 15 // (15 // self.slot_length)
                    )
                    end = self.slot_to_time(new_end, 15 // (15 // self.slot_length))
                    new_solution_start = f"{new_start}T{start}.000Z"
                    new_solution_end = f"{new_start}T{end}.000Z"
                    start_time = datetime.datetime.strptime(
                        new_solution_start, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    end_time = datetime.datetime.strptime(
                        new_solution_end, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    if end_time < start_time:
                        end_time += datetime.timedelta(days=1)
                        new_solution_end = (
                            end_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
                        )
                    new_solution = {
                        **solution,
                        "start": new_solution_start,
                        "end": new_solution_end,
                    }
                    if not pass_solution:
                        new_all_solutions.append(new_solution)
                    else:
                        print("real_pass1", new_solution)
                    current_start = new_end
                start = self.slot_to_time(current_start, 15 // (15 // self.slot_length))

                new_solution_start = f"{new_start}T{start}.000Z"
                start_time = datetime.datetime.strptime(
                    new_solution_start, "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                if end_time is not None and start_time < end_time:
                    start_time += datetime.timedelta(days=1)
                    new_solution_start = (
                        start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
                    )
                new_solution = {**solution, "start": new_solution_start}
                if session_max_slot_duration > 0:
                    if not pass_solution:
                        new_all_solutions.append(new_solution)
                    else:
                        print("real_pass2", new_solution)
            else:
                if True or not pass_solution:
                    new_all_solutions.append(solution)
                else:
                    print("real_pass3", solution)
            session_max / 3600 * 4
        self.events_poss = new_all_solutions
        return new_all_solutions

    def calculate_flexibility(self):
        for sol in self.events_poss_raw:
            pass

    def calculate_solution_totals(self):
        start_time = time.time()
        user_totals = {}
        user_flexibility = {}
        original_length = len(self.events_poss)
        for sol in self.events_poss:
            for i in range(sol["start_r"], sol["end_r"]):
                for id in sol["resourceIds_r"]:
                    self.user_solutions_array_unit[id][i] = 1
                    self.user_solutions_array_total[id][i] += 1
        for id in self.user_solutions_array_total.keys():
            user_totals[id] = sum(self.user_solutions_array_total[id])

        for t in range(original_length // 2):
            max_num = -1
            max_index = -1
            for index, sol in enumerate(self.events_poss):
                total_count = 1
                total_flex_person = 1
                for id in sol["resourceIds_r"]:
                    if "Person" in self.users[id]["roles"]:
                        total_flex_person *= user_totals[id]
                        total_count_person = 0
                        for i in range(sol["start_r"], sol["end_r"]):
                            total_count_person += self.user_solutions_array_total[id][i]
                        total_count + total_count_person / (
                            sol["end_r"] - sol["start_r"]
                        )
                total_count *= total_flex_person
                if max_num < total_count:
                    max_num = total_count
                    max_index = index

            event = self.events_poss[max_index]

            for id in sol["resourceIds_r"]:
                user_totals[id] -= sol["end_r"] - sol["start_r"]
                for i in range(sol["start_r"], sol["end_r"]):
                    self.user_solutions_array_total[id][i] -= 1
            del self.events_poss[max_index]
        self.events_poss = self.events_poss
        return self.events_poss

    # def team_creator(self, events_poss=[], events_real=[], part1=True):
    #     teams = run_team_creator(
    #         num_of_teams=-1,
    #         events_poss=events_poss,
    #         users=self.users,
    #         usersPerTeam=15,
    #         events_real=events_real,
    #         part1=part1,
    #     )
    #     return teams

    def team_creator(self, events_poss=[], part1=True):
        teams = run_team_creator(
            num_of_teams=-1,
            events_poss=events_poss,
            users=self.users,
            usersPerTeam=15000,
            part1=part1,
        )
        return teams

    def generate_scheduling_events(self):
        model = cp_model.CpModel()

        total_slots = (672 + 96) * (15 // self.slot_length)
        zero_slots = [0] * total_slots
        one_slots = [1] * total_slots
        slot_interval = 15 // (15 // self.slot_length)
        solution_limit = 100000 if self.optimizer_or_not else 100000

        resource_bool_vars = {}
        user_availability = {}
        constraint_list = []
        paired_roles_primary = {}
        paired_roles_secondary = {}
        paired_role_slots = {}
        user_capacity_constraints = {}

        # Block status variable
        is_block_active = model.NewBoolVar("is_block")
        model.Add(is_block_active == (1 if self.settings.get("blocks") else 0))

        # Orange status variable
        is_orange_active = model.NewBoolVar("is_orange")
        model.Add(is_orange_active == (1 if self.is_orange else 0))

        # Gather all relevant IDs for resources, locations, and roles
        resource_ids = self.get_user_ids("Resource")
        location_ids_full = self.get_user_ids("Location")
        block_ids = self.get_user_ids("Block")
        room_ids = self.get_user_ids("Room")
        seat_ids = self.get_user_ids("Seat")
        location_ids = location_ids_full.difference(room_ids).difference(seat_ids)

        # Define priority and slot constraints
        priority_constraint = model.NewIntVar(0, 6000, "priority_constraint")
        slot_ortools_int = model.NewIntVar(0, 7, "slot_constraint")

        # Define allowed days within the week
        allowed_days = list(range(5, 6))
        for day in range(7):
            if day not in allowed_days:
                model.Add(slot_ortools_int != day)

        # Calculate start and end numeric weekdays
        start_day = datetime.datetime.strptime(self.start_date, "%Y-%m-%d").weekday()
        end_day = datetime.datetime.strptime(self.end_date, "%Y-%m-%d").weekday()

        min_day, max_day = (
            (end_day + 1, start_day + 1)
            if start_day < end_day
            else (start_day + 1, end_day + 1)
        )

        # Assign resource boolean vars and initialize capacity constraints
        for res_id in resource_ids:
            resource_var = model.NewBoolVar(f"resource_{res_id}")
            resource_bool_vars[res_id] = resource_var
            user_availability[res_id] = {}

            # Add missing parts
            self.user_solutions_array_unit[res_id] = zero_slots.copy()
            self.user_solutions_array_total[res_id] = zero_slots.copy()
            capacity = self.users[res_id]["capacity"]  # Only if this is necessary

            if "Location" in self.users[res_id].get("roles", []):
                user_capacity_constraints[res_id] = zero_slots.copy()

            for loc in location_ids:
                user_availability[res_id][loc] = zero_slots.copy()

        # Check if drive distance constraints are set and a valid maximum quantity is specified
        if (
            self.settings.get("driveDistanceMax")
            and self.settings.get("driveDistanceMaxQuantity", 0) > 0
        ):
            locations_distance_ids = [
                loc_id
                for loc_id in self.get_user_ids("Location")
                if loc_id not in self.get_user_ids("Home")
                and self.users[loc_id].get("latitude") not in (None, 0)
                and self.users[loc_id].get("longitude") not in (None, 0)
            ]

            employee_ids = [
                emp_id
                for emp_id in self.get_user_ids("Employee")
                if self.users[emp_id].get("latitude") not in (None, 0)
                and self.users[emp_id].get("longitude") not in (None, 0)
            ]

            client_ids = [
                client_id
                for client_id in self.get_user_ids("Client")
                if self.users[client_id].get("latitude") not in (None, 0)
                and self.users[client_id].get("longitude") not in (None, 0)
            ]

            # Constraint for employee-location pairs exceeding the maximum drive distance
            for emp_id, loc_id in (
                (emp, loc) for emp in employee_ids for loc in locations_distance_ids
            ):
                emp_coords = (
                    self.users[emp_id]["latitude"],
                    self.users[emp_id]["longitude"],
                )
                loc_coords = (
                    self.users[loc_id]["latitude"],
                    self.users[loc_id]["longitude"],
                )

                # Calculate distance using the haversine formula
                distance = haversine(
                    emp_coords[0],
                    emp_coords[1],
                    loc_coords[0],
                    loc_coords[1],
                    unit="miles",
                )

                # Add constraint if the distance exceeds the specified maximum
                if distance > self.settings["driveDistanceMaxQuantity"]:
                    model.Add(
                        resource_bool_vars[emp_id] + resource_bool_vars[loc_id] != 2
                    )

            # Additional constraints for employee-client pairs based on home proximity
            home_ids = list(self.get_user_ids("Home"))
            if home_ids:
                home_id = home_ids[0]

                # Generate constraints for each employee-client pair with a home distance constraint
                for emp_id, client_id in (
                    (emp, client) for emp in employee_ids for client in client_ids
                ):
                    emp_coords = (
                        self.users[emp_id]["latitude"],
                        self.users[emp_id]["longitude"],
                    )
                    client_coords = (
                        self.users[client_id]["latitude"],
                        self.users[client_id]["longitude"],
                    )

                    # Calculate the distance
                    distance = haversine(
                        emp_coords[0],
                        emp_coords[1],
                        client_coords[0],
                        client_coords[1],
                        unit="miles",
                    )

                    # Add constraint with an OnlyEnforceIf clause based on home proximity
                    if distance > self.settings["driveDistanceMaxQuantity"]:
                        model.Add(
                            resource_bool_vars[emp_id] + resource_bool_vars[client_id]
                            != 2
                        ).OnlyEnforceIf(resource_bool_vars[home_id])

        user_availability_yellow_blank = copy.deepcopy(user_availability)
        user_availability_yellow = copy.deepcopy(user_availability)

        # Set up UUID-to-index mappings for users and branches
        for idx, user in enumerate(self.users):
            user["subgroups_real"] = user.get("actual_subgroups", [])
            self.user_uuid_to_index[user["id"]] = idx

        # Extract the keys directly from the dictionary
        self.user_uuid_to_index_keys = set(self.user_uuid_to_index)

        for pair in self.e_pair:
            roles1 = {role["name"] for role in pair["roles1"]}
            roles2 = {role["name"] for role in pair["roles2"]}

            activity1, activity2 = pair["activity1Id"], pair["activity2Id"]
            if (
                activity1 in self.user_uuid_to_index_keys
                and activity2 in self.user_uuid_to_index_keys
            ):
                index1 = self.user_uuid_to_index[activity1]
                index2 = self.user_uuid_to_index[activity2]

                paired_roles_primary.setdefault(index1, []).append(roles1)
                paired_roles_secondary.setdefault(index2, {}).setdefault(
                    index1, []
                ).append(roles1 | roles2)

        # TODO: need to investigate
        if self.is_investigate:
            arr = []
            list_arr = []
            for id in self.investigate:
                if id in resource_bool_vars.keys():
                    arr.append(resource_bool_vars[self.user_uuid_to_index[id]])
                    list_arr.append(1)
            model.AddAllowedAssignments(arr, [tuple(list_arr)])

        # Constraint for 'BoolOr' on expanded resources
        expanded_resource_vars = [
            resource_bool_vars[self.user_uuid_to_index[res]]
            for res in self.expanded_resources
            if res in self.user_uuid_to_index
        ]
        model.AddBoolOr(expanded_resource_vars)

        # Apply constraints to exclude specified resource combinations, if defined
        if self.resourceCombinationsExclude:
            excluded_combinations = [
                [
                    resource_bool_vars[self.user_uuid_to_index[user_id]]
                    for user_id in combination
                ]
                for combination in self.resourceCombinationsExclude
            ]

            for excluded_vars in excluded_combinations:
                model.Add(sum(excluded_vars) != len(excluded_vars))

        # Apply 'BoolAnd' constraint if expanded_resources_filter is defined
        if self.expanded_resources_filter:
            filter_vars = [
                resource_bool_vars[self.user_uuid_to_index[res]]
                for res in self.expanded_resources_filter
            ]
            model.AddBoolAnd(filter_vars)

        for user in self.users:
            branches_set = set()
            for branch in user["branches"]:
                if branch in self.branch_structure:
                    branches_set.update(self.branch_structure[branch])
            user["branches_real"] = list(branches_set)

        # TODO-refactoring to calculate with current data
        for p in self.activity_table:
            userId = p["user"]["id"]
            if userId in self.user_uuid_to_index_keys:
                userIndex = self.user_uuid_to_index[userId]
                if "Person" in self.users[userIndex]["roles"]:
                    self.users[userIndex]["efficiency"] = round(p["efficiency"])

        # Filter and sort users by efficiency
        valid_indices = [i for i, user in enumerate(self.users) if "efficiency" in user]
        sorted_indices = sorted(
            valid_indices, key=lambda x: self.users[x]["efficiency"]
        )
        sorted_ortools_efficiency = [
            resource_bool_vars[index]
            for index in sorted_indices
            if index in resource_bool_vars
        ]

        # Define boolean variables for room, seat, and location
        is_room = model.NewBoolVar("is_room")
        is_seat = model.NewBoolVar("is_seat")
        is_location = model.NewBoolVar("is_location")

        # Retrieve and classify IDs by type
        all_room_ids = self.get_user_ids("Room")
        all_seat_ids = self.get_user_ids("Seat")
        all_location_ids = (
            self.get_user_ids("Location")
            .difference(all_room_ids)
            .difference(all_seat_ids)
        )

        # Create lists of ortools variables for rooms, seats, and locations
        room_ortool_ids = [resource_bool_vars[id] for id in all_room_ids]
        seat_ortool_ids = [resource_bool_vars[id] for id in all_seat_ids]
        location_ortool_ids = [resource_bool_vars[id] for id in all_location_ids]

        # Add constraints for exactly one room, seat, and location based on boolean conditions
        model.Add(sum(room_ortool_ids) == 1).OnlyEnforceIf(is_room)
        model.Add(sum(room_ortool_ids) == 0).OnlyEnforceIf(is_room.Not())
        model.Add(sum(seat_ortool_ids) == 1).OnlyEnforceIf(is_seat)
        model.Add(sum(seat_ortool_ids) == 0).OnlyEnforceIf(is_seat.Not())
        model.Add(sum(location_ortool_ids) == 1).OnlyEnforceIf(is_location)
        model.Add(sum(location_ortool_ids) == 0).OnlyEnforceIf(is_location.Not())

        # Enforce relationships between room, seat, and location variables
        model.Add(is_room == 1).OnlyEnforceIf(is_seat)
        model.Add(is_location == 1).OnlyEnforceIf(is_room)

        # Add conditional constraints based on user attributes
        for id in all_location_ids:
            model.Add(is_room == int(self.users[id]["needroom"])).OnlyEnforceIf(
                resource_bool_vars[id]
            )

        for id in all_room_ids:
            if self.users[id]["needseat"]:
                model.Add(is_seat == 1).OnlyEnforceIf(resource_bool_vars[id])

        def add_capacity_constraint(constraint, enforce_flag):
            user = constraint["user1"]
            activity_id = self.user_uuid_to_index[user["id"]]
            location_disabled = constraint["locationDisabled"]

            model.Add(resource_bool_vars[activity_id] == 1).OnlyEnforceIf(enforce_flag)
            resource_exclusion_set = resource_ids - {activity_id} - location_ids_full

            # Apply min/max constraints based on roles and subgroups
            def apply_role_subgroup_constraints(role, subgroup, min_val, max_val):
                if role and subgroup:
                    user_ids = self.get_user_ids(
                        role["name"], "roles"
                    ) & self.get_user_ids(subgroup["name"], "subgroups_real")
                elif role:
                    user_ids = self.get_user_ids(role["name"], "roles")
                elif subgroup:
                    user_ids = self.get_user_ids(subgroup["name"], "subgroups_real")
                else:
                    return 0

                resource_exclusion_set.difference_update(user_ids)
                apply_min_max(user_ids, min_val, max_val)
                return min_val if min_val is not None else 0

            # Helper function to apply min/max constraints
            def apply_min_max(user_ids, min_val, max_val):
                bool_vars = [resource_bool_vars[uid] for uid in user_ids]
                if min_val is not None:
                    model.Add(sum(bool_vars) >= min_val).OnlyEnforceIf(enforce_flag)
                if max_val is not None:
                    model.Add(sum(bool_vars) <= max_val).OnlyEnforceIf(enforce_flag)

            min_required = 2

            # Roles and subgroups are applied in sequence
            min_required += apply_role_subgroup_constraints(
                constraint["role1"],
                constraint["subgroup1"],
                constraint["min1"],
                constraint["max1"],
            )
            min_required += apply_role_subgroup_constraints(
                constraint["role2"],
                constraint["subgroup2"],
                constraint["min2"],
                constraint["max2"],
            )
            min_required += apply_role_subgroup_constraints(
                constraint["role3"],
                constraint["subgroup3"],
                constraint["min3"],
                constraint["max3"],
            )
            min_required += apply_role_subgroup_constraints(
                constraint["role4"],
                constraint["subgroup4"],
                constraint["min4"],
                constraint["max4"],
            )
            min_required += apply_role_subgroup_constraints(
                constraint["role5"],
                constraint["subgroup5"],
                constraint["min5"],
                constraint["max5"],
            )

            # Apply room and seat constraints if available
            if all_room_ids:
                apply_min_max(all_room_ids, 0, 1)
            if all_seat_ids:
                apply_min_max(all_seat_ids, 0, 1)

            # Block settings
            if self.settings["blocks"]:
                resource_exclusion_set.difference_update(block_ids)
                apply_min_max(block_ids, 1, 1)

            # Location constraints
            apply_min_max(
                location_ids,
                0 if location_disabled else 1,
                0 if location_disabled else 1,
            )

            # Enforce exclusion on remaining resources
            for res_id in resource_exclusion_set:
                model.Add(resource_bool_vars[res_id] == 0).OnlyEnforceIf(enforce_flag)

        active_constraints = []

        for capacity in self.capacities:
            user = capacity.get("user1")
            if (
                capacity.get("disabled")
                or not user
                or user["id"] not in self.user_uuid_to_index_keys
            ):
                continue

            constraint_active = model.NewBoolVar(f'capacity_active_{user["id"]}')
            add_capacity_constraint(capacity, constraint_active)
            active_constraints.append(constraint_active)

        # Ensure only one capacity constraint is active
        model.Add(sum(active_constraints) == 1)

        def add_forbidden_groups(
            role1_ids,
            role2_ids,
            subgroup_set,
            min_val,
            max_val,
            enforce_all,
            is_soft,
            antecedentTypeActivityId=None,
        ):
            if is_soft:
                print("hello softy!")
                return
            for user1 in role1_ids:
                user1_subgroups = set(self.users[user1]["subgroups_real"]).intersection(
                    subgroup_set
                )

                if enforce_all:
                    min_val = max_val = len(user1_subgroups)

                for user2 in role2_ids:
                    if user1 == user2:
                        continue

                    user2_subgroups = set(
                        self.users[user2]["subgroups_real"]
                    ).intersection(subgroup_set)
                    common_subgroups = user1_subgroups.intersection(user2_subgroups)

                    if not (min_val <= len(common_subgroups) <= max_val):
                        if False and is_soft:
                            constraint_var = model.NewBoolVar(
                                f'Group_{self.users[user1]["firstName"]}_{self.users[user2]["firstName"]}'
                            )
                            constraint_list.append(constraint_var)
                            if antecedentTypeActivityId is None:
                                model.Add(
                                    resource_bool_vars[user1]
                                    + resource_bool_vars[user2]
                                    == 2
                                ).OnlyEnforceIf(constraint_var)
                                model.Add(
                                    resource_bool_vars[user1]
                                    + resource_bool_vars[user2]
                                    != 2
                                ).OnlyEnforceIf(constraint_var.Not())
                            else:
                                model.Add(
                                    resource_bool_vars[user1]
                                    + resource_bool_vars[user2]
                                    + resource_bool_vars[antecedentTypeActivityId]
                                    == 3
                                ).OnlyEnforceIf(constraint_var)
                                model.Add(
                                    resource_bool_vars[user1]
                                    + resource_bool_vars[user2]
                                    + resource_bool_vars[antecedentTypeActivityId]
                                    != 3
                                ).OnlyEnforceIf(constraint_var.Not())

                        else:
                            if antecedentTypeActivityId is None:
                                model.Add(
                                    resource_bool_vars[user1]
                                    + resource_bool_vars[user2]
                                    != 2
                                )
                            else:
                                model.Add(
                                    resource_bool_vars[user1]
                                    + resource_bool_vars[user2]
                                    + resource_bool_vars[antecedentTypeActivityId]
                                    != 3
                                )

        for av in filter(lambda a: a["av"], self.availabilities):
            user_id = self.user_uuid_to_index.get(av["resourceIds"][0])

            if user_id in user_availability:
                loc_ids = [
                    self.user_uuid_to_index.get(loc)
                    for loc in av["location"]
                    if loc in self.user_uuid_to_index_keys
                ] or location_ids
                time_slots = self.calc_availabilities(
                    av["start"].replace(":", ""),
                    av["end"].replace(":", ""),
                    "%Y-%m-%dT%H%M%S%z",
                )

                for time_slot in time_slots:
                    for loc_id in loc_ids:
                        user_a = user_availability.setdefault(user_id, {})
                        if loc_id not in user_a:
                            user_a[loc_id] = [0] * total_slots
                        user_a[loc_id][time_slot] = 1
                        if not (
                            "Activity" in self.users[user_id]["roles"]
                            and not self.users[user_id]["billable"]
                        ):
                            ua_y = user_availability_yellow.setdefault(user_id, {})
                            if loc_id not in ua_y:
                                ua_y[loc_id] = [0] * total_slots
                            ua_y[loc_id][time_slot] = 1

        condition = filter(
            lambda a: not a["av"] or (self.onCall and a["onCall"]), self.availabilities
        )
        for av in condition:
            user_id = self.user_uuid_to_index.get(av["resourceIds"][0])
            if user_id in user_availability:
                time_slots = self.calc_availabilities(
                    av["start"].replace(":", ""),
                    av["end"].replace(":", ""),
                    "%Y-%m-%dT%H%M%S%z",
                )
                for time_slot in time_slots:
                    for loc_id in location_ids:
                        user_availability[user_id][loc_id][time_slot] = 0
                        user_availability_yellow[user_id][loc_id][time_slot] = 0

        # Manage roomy constraints
        roomy_ids = list(self.get_user_ids("Roomy"))
        roomy_availability = {}
        for client_id in self.get_user_ids("Client"):
            for location, slots in user_availability.get(client_id, {}).items():
                if location in roomy_ids:
                    roomy_availability.setdefault(location, zero_slots.copy())
                    roomy_availability[location] = [
                        x + y for x, y in zip(slots, roomy_availability[location])
                    ]

        for location, slot_arr in roomy_availability.items():
            client_ratio = self.users[location]["clientratio"]
            employee_ratio = self.users[location].get("employeeratio", 1)
            max_clients = max(slot_arr)
            non_zero_slots = [x for x in slot_arr if x]

            if client_ratio == 0 or not non_zero_slots:
                model.Add(resource_bool_vars[location] == 0)
            else:
                min_clients = min(non_zero_slots)
                min_employees_needed = math.ceil(
                    max_clients / client_ratio * employee_ratio
                )
                min_employees_alternate = math.ceil(
                    min_clients / client_ratio * employee_ratio
                )
                employee_vars = [
                    resource_bool_vars[emp_id]
                    for emp_id in self.get_user_ids("Employee")
                ]

                model.Add(sum(employee_vars) == min_employees_needed).OnlyEnforceIf(
                    resource_bool_vars[location]
                )
                model.Add(sum(employee_vars) >= min_employees_alternate).OnlyEnforceIf(
                    resource_bool_vars[location]
                )

        for user_id in resource_ids:
            if "Person" in self.users[user_id]["roles"]:
                for location_id in location_ids:
                    if 1 not in user_availability[user_id][location_id]:
                        model.Add(
                            resource_bool_vars[user_id]
                            + resource_bool_vars[location_id]
                            != 2
                        )

        for event in self.events2:
            resource_vars = [
                self.user_uuid_to_index.get(res)
                for res in event["resourceIds"]
                if res in self.user_uuid_to_index_keys
            ]
            event["resourceIds_r"] = resource_vars

            event_time_slots = self.calc_availabilities(
                event["start"], event["end_real_time"], "%Y-%m-%dT%H:%M:%S.%fZ", False
            )
            if event_time_slots:
                event["start_r"] = event_time_slots[0]
                event["end_r"] = event_time_slots[-1] + 1
            else:
                event["start_r"] = None
                event["end_r"] = None

        for event in self.events:
            resource_vars = [
                self.user_uuid_to_index.get(res)
                for res in event["resourceIds"]
                if res in self.user_uuid_to_index_keys
            ]
            # event["resourceIds_r"] = resource_vars

            # event_time_slots = self.calc_availabilities(
            #     event["start"], event["end_real_time"], "%Y-%m-%dT%H:%M:%S.%fZ", False
            # )
            event_is_billable = any(
                self.users[res]["billable"] for res in resource_vars
            )

            if event_is_billable:
                self.events_billable.append(event)
            else:
                self.events_nonbillable.append(event)

        work_together_arr = [0] * 7
        work_together_obj = {}

        for event in self.events:
            event_slots = self.calc_availabilities(
                event["start"], event["end_real_time"], "%Y-%m-%dT%H:%M:%S.%fZ", False
            )
            event_slot_index = (
                math.floor(event_slots[0] / (96 * (15 // self.slot_length)))
                if event_slots
                else None
            )

            event_resource_ids = [
                self.user_uuid_to_index[res]
                for res in event["resourceIds"]
                if res in self.user_uuid_to_index_keys
            ]
            locations_in_event = []
            roles_in_event = set()
            person_count = 0
            activity_id = -1

            for res1, res2 in combinations(event_resource_ids, 2):
                pair = (
                    (res1, res2) if (res1, res2) in work_together_obj else (res2, res1)
                )

                if event_slot_index is not None:
                    work_together_obj.setdefault(pair, work_together_arr.copy())[
                        event_slot_index
                    ] = 1

            for res_id in event_resource_ids:
                roles_in_event.update(self.users[res_id]["roles"])
                if "Activity" in self.users[res_id]["roles"]:
                    activity_id = res_id
                if "Location" in self.users[res_id]["roles"]:
                    locations_in_event.append(res_id)
                if (
                    "Person" in self.users[res_id]["roles"]
                    or "Seat" in self.users[res_id]["roles"]
                ):
                    person_count += 1
                    for slot in event_slots:
                        for location_id in location_ids:
                            user_availability[res_id][location_id][slot] = 0

            if activity_id >= 0 and activity_id in paired_roles_primary:
                resource_set = sorted([activity_id, *event_resource_ids])
                resource_tuple = tuple(resource_set)
                if resource_tuple not in paired_role_slots:
                    paired_role_slots[resource_tuple] = zero_slots.copy()
                for slot in event_slots:
                    paired_role_slots[resource_tuple][slot] = 1

            for location_id in locations_in_event:
                if location_id in user_capacity_constraints:
                    for slot in event_slots:
                        user_capacity_constraints[location_id][slot] += person_count

        for user_id in user_capacity_constraints:
            capacity = self.users[user_id].get("capacity")
            if not capacity:
                continue

            exceeded_indices = [
                i
                for i, value in enumerate(user_capacity_constraints[user_id])
                if value >= capacity
            ]

            for loc_id in location_ids:
                for i in exceeded_indices:
                    user_availability[user_id][loc_id][i] = 0

        def update_billable_and_nonbillable_availability(events, is_billable):
            availability_flag = 0 if is_billable else 1

            for event in events:
                event_slots = self.calc_availabilities(
                    event["start"],
                    event["end_real_time"],
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                    False,
                )

                for res_id in event["resourceIds"]:
                    if res_id not in self.user_uuid_to_index_keys:
                        continue

                    user_index = self.user_uuid_to_index[res_id]
                    if "Person" in self.users[user_index]["roles"]:
                        for loc_id in location_ids:
                            for slot in event_slots:
                                user_availability_yellow_blank[user_index][loc_id][
                                    slot
                                ] = availability_flag

                                if "Client" in self.users[user_index]["roles"]:
                                    user_availability_yellow[user_index][loc_id][
                                        slot
                                    ] = 0

        update_billable_and_nonbillable_availability(self.events_nonbillable, False)
        update_billable_and_nonbillable_availability(self.events_billable, True)

        for user_index in user_availability_yellow:
            if "Employee" in self.users[user_index]["roles"]:
                for loc_id in location_ids:
                    yellow_blank = user_availability_yellow_blank[user_index][loc_id]
                    yellow = user_availability_yellow[user_index][loc_id]

                    user_availability_yellow[user_index][loc_id] = [
                        1 if blank == 1 and current else 0
                        for blank, current in zip(yellow_blank, yellow)
                    ]

        # NOT MATCHING
        constraint_ids_dict = {}

        for index, constraint in enumerate(self.custom_constraints):
            constraint_type = constraint["constraint"]

            if constraint_type in {"matching", "unmatching", "grouping"}:
                continue

            constraint_ids_dict[index] = {
                "min": constraint["min"],
                "max": constraint["max"],
                "frequency": constraint["frequency"],
                "constraint": constraint_type,
            }

            if constraint["type_or_specific"] == "type":
                users_antecedent = self.handle_general_constraint_type(
                    constraint["apply_constraint_to_this_role"],
                    constraint["apply_constraint_to_this_subgroup"],
                    constraint["apply_constraint_to_this_branch"],
                )
            else:
                users_antecedent = self.handle_general_constraint_specific_index(
                    constraint["apply_constraint_to_this_user"]
                )

            if constraint["type_or_specific_consequence"] == "type":
                users_consequence = self.handle_general_constraint_type(
                    constraint["consequence_constraint_to_this_role"],
                    constraint["consequence_constraint_to_this_subgroup"],
                    constraint["consequence_constraint_to_this_branch"],
                )
            else:
                users_consequence = self.handle_general_constraint_specific_index(
                    constraint["consequence_constraint_to_this_user"]
                )

            if constraint_type in {"time", "sessionlength"}:
                frequency_constraint = {
                    "each_or_all_users": constraint["each_or_all_users"],
                    "frequency": constraint["frequency"],
                    "weight": constraint["weight"],
                    "type": constraint_type,
                    "soft": constraint["soft"],
                    "users_antecedent": users_antecedent,
                    "users_consequence": list(users_consequence),
                    "max": constraint["max"],
                    "min": constraint["min"],
                    "minSeconds": constraint["minSeconds"],
                    "maxSeconds": constraint["maxSeconds"],
                    "id": constraint["id"],
                    "rank": index,
                }
                self.resources1.frequency_constraints.append(frequency_constraint)

                for antecedent_user in users_antecedent:
                    user_time_constraints = self.resources1.resources[
                        antecedent_user
                    ].time_constraints[constraint["frequency"]]
                    time_constraint_obj = {
                        "min": constraint["min"],
                        "max": constraint["max"],
                        "units": constraint["units"],
                        "each_or_all_users": constraint["each_or_all_users"],
                        "weight": constraint["weight"],
                        "users_consequence": users_consequence,
                        "users_antecedent": users_antecedent,
                    }
                    for consequence_user in users_consequence:
                        if consequence_user not in user_time_constraints:
                            user_time_constraints[consequence_user] = (
                                time_constraint_obj
                            )
                            self.resources1.resources[
                                consequence_user
                            ].time_constraints[constraint["frequency"]][
                                antecedent_user
                            ] = time_constraint_obj
            else:
                freq_obj = {
                    "each_or_all_users": constraint["each_or_all_users"],
                    "frequency": constraint["frequency"],
                    "weight": constraint["weight"],
                    "users_antecedent": users_antecedent,
                    "users_consequence": list(users_consequence),
                    "max": constraint["max"],
                    "min": constraint["min"],
                    "minSeconds": constraint["minSeconds"],
                    "maxSeconds": constraint["maxSeconds"],
                    "description": constraint.get("description", ""),
                    "soft": constraint["soft"],
                    "id": constraint["id"],
                    "rank": index,
                    "antecedentTypeActivityId": constraint.get(
                        "antecedentTypeActivityId"
                    ),
                    "antecedentLocationId": constraint.get("antecedentLocationId"),
                    "rollover": constraint.get("rollover"),
                }

                type_label = constraint_type
                if constraint_type == "usertouser":
                    type_label = "frequency"
                    for antecedent_user in users_antecedent:
                        self.resources1.resources[antecedent_user].onlyUserToUser[
                            constraint["id"]
                        ] = -1
                    self.resources1.onlyUserToUser.update({constraint["id"]: freq_obj})

                elif constraint_type == "usertosession":
                    type_label = "session"
                    for antecedent_user in users_antecedent:
                        self.resources1.resources[antecedent_user].onlyUserToSession[
                            constraint["id"]
                        ] = -1
                    self.resources1.onlyUserToSession.update(
                        {constraint["id"]: freq_obj}
                    )

                if constraint_type == "priority":
                    freq_obj["rank"] = constraint["max"]

                freq_obj["type"] = type_label
                self.resources1.frequency_constraints.append(freq_obj)

        # # Matching && Unmatching
        user_ids_for_constraint = sorted([user["id"] for user in self.users])

        self.conflicted_constraints = {
            tuple(user_pair): {"match": set(), "unmatch": set()}
            for user_pair in combinations(user_ids_for_constraint, 2)
        }

        for index, constraint in enumerate(self.custom_constraints):
            constraint_id = constraint["id"]
            constraint_type = constraint["constraint"]

            if constraint_id not in self.highPriority or constraint_type not in {
                "matching",
                "unmatching",
                "grouping",
            }:
                continue
            if constraint["soft"]:
                continue

            if constraint["type_or_specific"] == "type":
                antecedent_users = self.handle_general_constraint_type(
                    constraint["apply_constraint_to_this_role"],
                    constraint["apply_constraint_to_this_subgroup"],
                    [],
                )
                antecedent_users = list(
                    map(lambda x: tuple([self.users[x]["id"]]), antecedent_users)
                )
            else:
                antecedent_users = self.handle_general_constraint_specific(
                    constraint["apply_constraint_to_this_user"]
                )

            if constraint["type_or_specific_consequence"] == "type":
                users_consequence = self.handle_general_constraint_type(
                    constraint["consequence_constraint_to_this_role"],
                    constraint["consequence_constraint_to_this_subgroup"],
                    [],
                )
                users_consequence = list(
                    map(lambda x: tuple([self.users[x]["id"]]), users_consequence)
                )

            else:
                users_consequence = self.handle_general_constraint_specific(
                    constraint["consequence_constraint_to_this_user"]
                )

            antecedent_ids = []
            consequence_ids = []
            for u_t in users_consequence:
                for i in u_t:
                    consequence_ids.append(i)
            for u_t in antecedent_users:
                for i in u_t:
                    antecedent_ids.append(i)
            consequence_ids = list(set(consequence_ids))
            antecedent_ids = list(set(antecedent_ids))

            if constraint_type == "unmatching":
                for ant_id in antecedent_ids:
                    for cons_id in consequence_ids:
                        sorted_pair = tuple(sorted([ant_id, cons_id]))
                        if sorted_pair in self.conflicted_constraints:
                            self.conflicted_constraints[sorted_pair]["unmatch"].add(
                                constraint_id
                            )

                antecedent_bools = [
                    resource_bool_vars[self.user_uuid_to_index[ant]]
                    for ant in antecedent_ids
                    if ant in user_ids_for_constraint
                ]
                consequence_bools = [
                    resource_bool_vars[self.user_uuid_to_index[cons]]
                    for cons in consequence_ids
                    if cons in user_ids_for_constraint
                ]

                if antecedent_bools and consequence_bools:
                    location_activity_bools = [
                        resource_bool_vars[self.user_uuid_to_index[constraint[key]]]
                        for key in ["antecedentLocationId", "antecedentTypeActivityId"]
                        if constraint.get(key) in user_ids_for_constraint
                    ]

                    if location_activity_bools:
                        for ant_bool in antecedent_bools:
                            match_bool2 = model.NewBoolVar("match_bool2")
                            model.AddMinEquality(
                                match_bool2, [ant_bool, *location_activity_bools]
                            )
                            model.Add(sum(consequence_bools) == 0).OnlyEnforceIf(
                                match_bool2
                            )
                    else:
                        match_bool = model.NewBoolVar("match_bool")
                        model.Add(sum(antecedent_bools) == 1).OnlyEnforceIf(match_bool)
                        model.Add(sum(consequence_bools) == 0).OnlyEnforceIf(match_bool)
                        model.Add(sum(antecedent_bools) == 0).OnlyEnforceIf(
                            match_bool.Not()
                        )

            elif constraint_type == "matching":
                person_ids = self.get_user_ids("Person")

                for ant_id in antecedent_ids:
                    for cons_id in consequence_ids:
                        sorted_pair = tuple(sorted([ant_id, cons_id]))
                        if sorted_pair in self.conflicted_constraints:
                            self.conflicted_constraints[sorted_pair]["match"].add(
                                constraint_id
                            )

                antecedent_bools = [
                    resource_bool_vars[self.user_uuid_to_index[ant]]
                    for ant in antecedent_ids
                    if ant in user_ids_for_constraint
                ]

                antecedent_bools_idx = [
                    self.user_uuid_to_index[ant]
                    for ant in antecedent_ids
                    if ant in user_ids_for_constraint
                ]

                consequence_bools = [
                    resource_bool_vars[self.user_uuid_to_index[cons]]
                    for cons in consequence_ids
                    if cons in user_ids_for_constraint
                ]
                role_consequence_bools = [
                    resource_bool_vars[idx]
                    for idx in person_ids
                    if idx not in antecedent_bools_idx
                ]

                if antecedent_bools and consequence_bools:
                    location_activity_bools = [
                        resource_bool_vars[self.user_uuid_to_index[constraint[key]]]
                        for key in ["antecedentLocationId", "antecedentTypeActivityId"]
                        if constraint.get(key) in user_ids_for_constraint
                    ]

                    if location_activity_bools:
                        for ant_bool in antecedent_bools:
                            match_bool2 = model.NewBoolVar("match_bool2")
                            model.AddMinEquality(
                                match_bool2,
                                [
                                    ant_bool,
                                    *location_activity_bools,
                                    *role_consequence_bools,
                                ],
                            )
                            model.Add(sum(consequence_bools) == 1).OnlyEnforceIf(
                                match_bool2
                            )
                    else:
                        match_bool = model.NewBoolVar("match_bool")
                        match_bool_ortools = model.NewBoolVar("match_bool_ortools")
                        model.Add(sum(role_consequence_bools) >= 1).OnlyEnforceIf(
                            match_bool_ortools
                        )
                        model.Add(sum(role_consequence_bools) == 0).OnlyEnforceIf(
                            match_bool_ortools.Not()
                        )
                        model.Add(sum(antecedent_bools) == 1).OnlyEnforceIf(match_bool)
                        model.Add(sum(consequence_bools) >= 1).OnlyEnforceIf(
                            match_bool
                        ).OnlyEnforceIf(match_bool_ortools)
                        model.Add(sum(antecedent_bools) != 1).OnlyEnforceIf(
                            match_bool.Not()
                        )

        if "conflicts" not in self.conflicted_constraints:
            self.conflicted_constraints["conflicts"] = []

        conflicts = self.conflicted_constraints["conflicts"]
        for key, value in self.conflicted_constraints.items():
            if key == "conflicts":
                continue

            matches, unmatches = value.get("match", []), value.get("unmatch", [])
            if matches and unmatches:
                conflicts.extend(
                    [[match, unmatch] for match in matches for unmatch in unmatches]
                )

        for ind, constraint in enumerate(self.custom_constraints):
            if constraint["constraint"] != "grouping":
                continue
            print(f"grouping constraints2: {constraint}")
            is_soft = constraint["soft"]

            if constraint["type_or_specific"] == "type":
                users_antecedent = self.handle_general_constraint_type(
                    constraint["apply_constraint_to_this_role"],
                    constraint["apply_constraint_to_this_subgroup"],
                    [],
                )
                users_antecedent = [
                    (self.users[user]["id"],) for user in users_antecedent
                ]
            else:
                users_antecedent = self.handle_general_constraint_specific(
                    constraint["apply_constraint_to_this_user"]
                )

            # Determine consequence users
            if constraint["type_or_specific_consequence"] == "type":
                users_consequence = self.handle_general_constraint_type(
                    constraint["consequence_constraint_to_this_role"],
                    constraint["consequence_constraint_to_this_subgroup"],
                    [],
                )
                users_consequence = [
                    (self.users[user]["id"],) for user in users_consequence
                ]
            else:
                users_consequence = self.handle_general_constraint_specific(
                    constraint["consequence_constraint_to_this_user"]
                )

            if not users_antecedent or not users_consequence:
                continue

            group_name = constraint["grouping"]
            all_bol = constraint["all"]
            subgroup_set = set(self.subgroups[group_name])
            antecedentTypeActivityId = None
            if constraint["antecedentTypeActivityId"] in self.user_uuid_to_index:
                antecedentTypeActivityId = self.user_uuid_to_index[
                    constraint["antecedentTypeActivityId"]
                ]
            users1 = {
                self.user_uuid_to_index[user_id]
                for user_tuple in users_antecedent
                for user_id in user_tuple
                if user_id in self.user_uuid_to_index_keys
            }
            users2 = {
                self.user_uuid_to_index[user_id]
                for user_tuple in users_consequence
                for user_id in user_tuple
                if user_id in self.user_uuid_to_index_keys
            }

            users1 &= resource_ids
            users2 &= resource_ids

            if not constraint["limit"]:
                min_limit = 1
            else:
                min_limit = constraint["min"]
            max_limit = (
                constraint.get("max", float("inf"))
                if constraint.get("limit")
                else float("inf")
            )

            add_forbidden_groups(
                users1,
                users2,
                subgroup_set,
                min_limit,
                max_limit,
                all_bol,
                is_soft,
                antecedentTypeActivityId,
            )

        self.user_availabilities_general_employees = {}
        self.user_availabilities_general_clients = {}

        for resource_id in resource_ids:
            max_values = np.array(list(user_availability[resource_id].values())).max(
                axis=0
            )
            detected_ranges = self.detect_range(
                sorted(set(self.convert_index_to_slot(list(max_values))))
            )
            availability_list = list(detected_ranges)

            user_id = self.users[resource_id]["id"]
            self.user_availabilities_general[user_id] = availability_list

            user_roles = self.users[resource_id]["roles"]
            if "Employee" in user_roles:
                self.user_availabilities_general_employees[user_id] = availability_list
            elif "Client" in user_roles:
                self.user_availabilities_general_clients[user_id] = availability_list

        solution_printer = VarArraySolutionPrinter(
            [
                resource_bool_vars,
                slot_ortools_int,
                constraint_list,
                priority_constraint,
                is_block_active,
                self.users,
            ],
            solution_limit,
        )

        solver = cp_model.CpSolver()

        # Prepare priority constraints
        priority_arr = []
        for constraint in self.resources1.frequency_constraints:
            if constraint["type"] != "priority":
                continue

            rank = constraint["rank"]
            antecedent_list = constraint["users_antecedent"]
            consequence_list = constraint["users_consequence"]

            if not antecedent_list or not consequence_list:
                continue

            priority_bool = model.NewBoolVar("priority_active")
            priority_value = model.NewIntVar(0, 100, "priority_value")
            model.Add(priority_value == rank).OnlyEnforceIf(priority_bool)
            model.Add(priority_value == 100).OnlyEnforceIf(priority_bool.Not())
            priority_arr.append(priority_value)

            antecedent_vars = [resource_bool_vars[a] for a in antecedent_list]
            consequence_vars = [resource_bool_vars[c] for c in consequence_list]

            antecedent_combined = (
                antecedent_vars[0]
                if len(antecedent_vars) == 1
                else model.NewBoolVar("antecedent_combined")
            )
            if len(antecedent_vars) > 1:
                model.AddMaxEquality(antecedent_combined, antecedent_vars)

            consequence_combined = (
                consequence_vars[0]
                if len(consequence_vars) == 1
                else model.NewBoolVar("consequence_combined")
            )
            if len(consequence_vars) > 1:
                model.AddMaxEquality(consequence_combined, consequence_vars)

            model.Add(antecedent_combined + consequence_combined == 2).OnlyEnforceIf(
                priority_bool
            )
            model.Add(antecedent_combined + consequence_combined != 2).OnlyEnforceIf(
                priority_bool.Not()
            )

        efficiency_arr = []
        for person_id in self.get_user_ids("Person"):
            efficiency = self.users[person_id].get("efficiency", 0)
            efficiency = max(0, min(efficiency, 100))  # Clamp efficiency to [0, 100]

            efficiency_bool = resource_bool_vars[person_id]
            efficiency_value = model.NewIntVar(0, 10000, "efficiency_value")
            model.Add((100 - efficiency) == efficiency_value).OnlyEnforceIf(
                efficiency_bool
            )
            model.Add(efficiency_value == 0).OnlyEnforceIf(efficiency_bool.Not())
            efficiency_arr.append(efficiency_value)

        if priority_arr:
            model.AddMinEquality(priority_constraint, priority_arr)
        else:
            model.Add(priority_constraint == 0)

        solver.parameters.enumerate_all_solutions = True
        solver.parameters.log_search_progress = True

        # model.AddDecisionStrategy(
        #     [priority_constraint, *sorted_ortools_efficiency],
        #     cp_model.CHOOSE_FIRST,
        #     cp_model.SELECT_MAX_VALUE,
        # )
        # solver.parameters.search_branching = cp_model.FIXED_SEARCH

        status = solver.Solve(model, solution_printer)
        all_solutions_clean = []
        events_poss = []
        events_poss_raw = []

        def get_slots_from_days(excluded_days):
            excluded_slots = {
                day * (96 * (15 // self.slot_length)) + slot
                for day in set(range(7)) - set(excluded_days)
                for slot in range(96 * (15 // self.slot_length))
            }
            return excluded_slots

        def calculate_solutions(user_availability, yellow=False):

            for solution, slots in solution_printer.all_solutions.items():
                loc_id = next(iter(location_ids.intersection(solution)), -1)
                address = self.users[loc_id]["address"] if loc_id != -1 else ""
                branch_id = self.users[loc_id]["branches"][0] if loc_id != -1 else ""
                block = solution_printer.all_blocks[solution]
                priority = 0

                arr = []
                person_count = 0
                locaition_arr = []

                forbidden_slots = get_slots_from_days(slots)
                forbidden_slots = set()
                client_arr = []
                for n in solution:
                    if "Person" in self.users[n]["roles"]:
                        person_count = person_count + 1
                    if "Location" in self.users[n]["roles"]:
                        locaition_arr.append(n)
                    if "Client" in self.users[n]["roles"]:
                        client_arr.append(n)

                    intersecting_roles = set(solution).intersection(
                        paired_roles_secondary.keys()
                    )
                    excluded_roles = set()

                    if intersecting_roles:
                        remaining_solution = set(solution) - intersecting_roles
                        primary_role = next(iter(intersecting_roles))
                        combined_slot_arrays = [np.array(zero_slots)]

                        for secondary_role in paired_roles_secondary[primary_role]:
                            updated_solution = remaining_solution | {secondary_role}
                            for role_pair, slot_data in paired_role_slots.items():
                                if (
                                    len(set(role_pair).intersection(solution))
                                    >= len(role_pair) - 2
                                ):
                                    excluded_roles.update(role_pair)
                                    combined_slot_arrays.append(np.array(slot_data))

                        if len(combined_slot_arrays) > 1:
                            aggregated_slots = np.sum(
                                np.vstack(combined_slot_arrays), axis=0
                            )
                            arr.append(aggregated_slots)

                availability_arrays = []

                for user_id in solution:
                    if loc_id == -1:
                        max_availability = np.array(
                            list(user_availability[user_id].values())
                        ).max(axis=0)
                        availability_arrays.append(max_availability)
                    else:
                        if user_id not in excluded_roles:
                            location_availability = np.array(
                                user_availability[user_id][loc_id]
                            )
                            availability_arrays.append(location_availability)

                if availability_arrays:
                    combined_availability = np.prod(
                        np.vstack(availability_arrays), axis=0
                    )
                    if np.any(combined_availability):
                        available_slots = self.convert_index_to_slot(
                            combined_availability
                        )

                        detected_ranges = detect_range(
                            sorted(set(available_slots) - forbidden_slots)
                        )

                try:
                    for time_range in [tuple(i) for i in list(detected_ranges)]:
                        start = self.slot_to_time(time_range[0], slot_interval)
                        end = self.slot_to_time(time_range[1], slot_interval)
                        start_date_original = datetime.datetime.strptime(
                            self.start_date, "%Y-%m-%d"
                        )

                        start_day_offset = (
                            time_range[0] // (24 * 60 // slot_interval)
                            - start_date_original.weekday()
                            + 7
                        ) % 7
                        end_day_offset = (
                            time_range[1] // (24 * 60 // slot_interval)
                            - start_date_original.weekday()
                            + 7
                        ) % 7

                        new_start_date = start_date_original + datetime.timedelta(
                            days=start_day_offset
                        )
                        new_end_date1 = start_date_original + datetime.timedelta(
                            days=start_day_offset + 1
                        )
                        new_end_date2 = start_date_original + datetime.timedelta(
                            days=end_day_offset
                        )

                        new_start = new_start_date.strftime("%Y-%m-%d")
                        new_end1 = new_end_date1.strftime("%Y-%m-%d")
                        new_end2 = new_end_date2.strftime("%Y-%m-%d")
                        full_start = f"{new_start}T{start}.000Z"
                        full_end = f"{new_end2}T{end}.000Z"

                        resource_ids = []
                        resource_names = []
                        categorized_resources = {
                            "Person": [],
                            "Activity": [],
                            "Location": [],
                            "Other": [],
                        }

                        for user_index in solution:
                            roles = self.users[user_index]["roles"]
                            for category in ["Person", "Activity", "Location"]:
                                if category in roles:
                                    categorized_resources[category].append(user_index)
                                    break
                            else:
                                categorized_resources["Other"].append(user_index)

                        sol_ordered = (
                            categorized_resources["Person"]
                            + categorized_resources["Activity"]
                            + categorized_resources["Location"]
                            + categorized_resources["Other"]
                        )

                        for user_index in sol_ordered:
                            user = self.users[user_index]
                            user_id = user["id"]
                            user_name = user["firstName"]

                            if user.get("lastName"):
                                user_name += f" {user['lastName'][0]}"

                            if user.get("efficiency"):
                                user_name += f" ({user['efficiency']}%)"

                            if user_id not in self.expanded_resources:
                                resource_names.append(user_name)
                            resource_ids.append(f"{user_id}a")

                        if loc_id == -1:
                            loc_real = loc_real2 = None
                        else:
                            loc_real = loc_real2 = self.users[loc_id]["id"]
                            home_id = self.get_id_from_role_array("Home", [loc_id])
                            if home_id != -1:
                                client_id = self.get_id_from_role_array(
                                    "Client", solution
                                )
                                if client_id != -1:
                                    address = self.users[client_id]["address"]

                        priority = solution_printer.all_priorities[solution]
                        if priority == 0:
                            priority = 100

                        roomy_intersection = set(solution).intersection(roomy_ids)
                        if roomy_intersection:
                            roomy_id = next(iter(roomy_intersection))
                            if roomy_id in roomy_availability:
                                client_ratio = self.users[roomy_id]["clientratio"]
                                employee_ratio = self.users[roomy_id]["employeeratio"]
                                slot_array = roomy_availability[roomy_id][
                                    time_range[0] : time_range[1]
                                ]
                                non_zero_slots = [
                                    slot for slot in slot_array if slot != 0
                                ]
                                max_clients = max(slot_array, default=0)
                                min_employees_needed = math.ceil(
                                    max_clients / client_ratio * employee_ratio
                                )

                                if (
                                    not non_zero_slots
                                    or len(
                                        set(solution).intersection(
                                            self.get_user_ids("Employee")
                                        )
                                    )
                                    != min_employees_needed
                                ):
                                    continue

                        obj = {
                            "title": " - ".join(resource_names),
                            "resourceIds": resource_ids,
                            "resourceIds_r": solution,
                            "new_start": new_start,
                            "loc_id2": loc_real2,
                            "start": full_start,
                            "end": full_end,
                            "priority": priority,
                            "block": block,
                            "start_r": time_range[0],
                            "end_r": time_range[1],
                            "scheduled": False,
                            "address": address,
                            "branch_id": branch_id,
                            "loc_id": loc_real,
                            "id": str(uuid.uuid4()),
                            "orange_sol": False,
                        }
                        priority = 0
                        if yellow:
                            obj["ov"] = "t"

                        self.relevant_users.update(solution)

                        obj2 = {
                            "title": resource_names,
                            "resourceIds": solution,
                            "start": time_range[0],
                            "end": time_range[1],
                            "reasons": [],
                        }

                        if self.is_orange:
                            obj["reasons"] = [[]]

                        if self.is_investigate:
                            obj["reasons"] = list(
                                solution_printer.all_solutions_constraints.get(
                                    solution, {}
                                ).values()
                            )[0]

                        events_poss.append(obj)
                        events_poss_raw.append({**obj, **obj2})
                except Exception as e:
                    print("Exception:", e)

                all_solutions_clean.append(solution)

        calculate_solutions(user_availability)

        calculate_solutions(user_availability_yellow, True)

        self.events_poss = events_poss
        self.events_poss_raw = events_poss_raw

        return events_poss

    def main(self):
        self.generate_scheduling_events()
