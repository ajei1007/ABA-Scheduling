import os
import datetime
import time
import copy
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.shared.utils import (
    get_week_start_end,
    get_weekday_index,
    availabilities,
    get_number_per_slot,
    max_possible_total_hours,
)
from api.utils import convert_events
from core.shared.event_schedular.main import EventScheduler
from core.shared.data_gatherer import Data_Gatherer
from core.shared.event_solver.main import Solver
from core.optimizer.event_matcher import is_matching_event, events_overlap, parse_dt


class Optimizer:
    def __init__(self, data):
        self.data = data
        self.start_date = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d")
        self.end_date = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d")
        self.total_days = (self.end_date - self.start_date).days + 1
        self.weekly_availability = None
        self.resource_availability_map = None
        self.availability = {}
        self.efficiency = []
        self.efficiency_data = {}
        self.deleted_appointments_list = []
        self.status_name = ""
        self.created_hours = 0
        self.deleted_hours = 0
        self.max_total_hours = None
        self.solution = None
        self.timings = {}
        self.part1_results = {}
        self.converted_events = []
        self.public_ip = "host.docker.internal:4000"
        self.time_since_server_started = None
        self.instance_id = ""
        self.data_gatherer = None

    def serialize_solution(self, solution):
        if isinstance(solution, EventScheduler):
            return solution.to_dict()
        elif isinstance(solution, list):
            return [self.serialize_solution(item) for item in solution]
        elif isinstance(solution, dict):
            return {
                key: self.serialize_solution(value) for key, value in solution.items()
            }
        else:
            return solution

    def assign_colors(self, events, color_type="orange"):
        """Assign color codes to events based on matching criteria."""
        colored_events = []
        for event in events:
            type = color_type
            if "ov" in event and event["ov"] == "t":
                type = "yellow"
            colored_events.append(
                {**event, "colorType": type, "backgroundColor_real": type}
            )
        return colored_events

    def categorize_events(self, unmatch_poss_events):
        """Categorize events into matched and unmatched lists based on constraints."""
        section_timings = {}
        constraint_types_to_include = {"grouping", "matching", "unmatching"}
        start_time = time.time()
        highPriority = [*self.data.get("highPriority", []), *self.data.get("soft", [])]
        filtered_constraint_ids = [
            c["id"]
            for c in self.data_gatherer.custom_constraints
            if c["constraint"] in constraint_types_to_include
            and c["id"] in highPriority
        ]
        high_priority_str = "|".join(filtered_constraint_ids)
        future_events = self.data_gatherer.some_data.get_event_future(
            unmatch_poss_events, high_priority_str
        )
        print("filtered_constraint_ids", filtered_constraint_ids)
        section_timings["fetch_future_events"] = time.time() - start_time

        new_events = []

        start_time = time.time()
        for event in unmatch_poss_events:
            color = "orange"
            if len(future_events.get(event["id"], {}).get("constraints", [])) == 0:
                event.pop("reasons", None)
                color = "yellow" if "ov" in event else "white"
                new_events.append(
                    {**event, "backgroundColor_real": color, "colorType": color}
                )
            else:
                reasons = []
                for c in future_events[event["id"]]["constraints"]:
                    description = c.get("description", "")
                    color = "yellow" if "ov" in event else "orange"
                    if description not in reasons:
                        reasons.append(
                            {"reason": re.sub(r"</?strong>", "", description)}
                        )
                new_events.append(
                    {
                        **event,
                        "orange_sol": True,
                        "constraint": future_events[event["id"]]["constraints"],
                        "reasons": reasons,
                    }
                )

        section_timings["iterate_events"] = time.time() - start_time
        section_timings["total_time"] = sum(section_timings.values())

        return new_events

    def optimize_workflow(self):
        self.data["has_blocks"] = False
        self.data["is_optimized"] = True
        start_time = time.time()

        # The 'default' EC2MakeStart function has url https://ihwpbnj2... 
        # Ultimately, this should be configured 'properly', but allow this to default for
        # now to avoid breakage when migrating to a new split setup
        initInstanceUrl = os.getenv("EC2_START_FUNCTION_URL") or "https://ihwpbnjt2syrzqtvlgrndo5qpi0sxeqa.lambda-url.us-east-1.on.aws"

        ##production
        response = requests.get(initInstanceUrl)
        data = response.json()
        print("ip_address", data)
        self.public_ip = data["public_ip"]
        self.instance_id = data["instance_id"]
        self.time_since_server_started = datetime.datetime.now()
        ##production
        print("sushi1")
        if self.data.get("part1"):
            self.data.update(
                {
                    "percentage": 0,
                    "part1": True,
                    "part2_in_part1": False,
                    "is_orange": True,
                    "max_time_in_seconds": 60.0,
                }
            )

            self.efficiency_data = {}
            self.part1_results = {}
            self.part1_results = self.run_optimization_phase()
            print("sushi2")
            print(f"part1 result---: {self.part1_results}")

            # self.data.update(
            #     {
            #         "percentage": 10,
            #         "part1": False,
            #         "part2_in_part1": False,
            #         "is_orange": True,
            #         "max_time_in_seconds": 120.0,
            #     }
            # )
            # part2_results = self.run_optimization_phase()
            # print(f"part2 result----: {part2_results}")

            combined_result = {
                "creatingEvents": [],
                "deletingEvents": [],
                "updatingEvents": [],
                "obj_value": 0,
                "disabled_constraints": [],
                "statistics": {},
            }
            part2_results = False

            if (
                self.part1_results
                and self.part1_results.get("creatingEvents")
                and part2_results
                and part2_results.get("deletingEvents")
            ):
                filtered_creates = []
                part2_event_pool = part2_results.get("creatingEvents", []) + [
                    u_evt["newEvent"]
                    for u_evt in part2_results.get("updatingEvents", [])
                    if "newEvent" in u_evt
                ]

                print(f"created part2 event pool: {part2_event_pool}")

                for c_evt in self.part1_results["creatingEvents"]:
                    try:
                        match_index = next(
                            (
                                i
                                for i, d_evt in enumerate(
                                    part2_results["deletingEvents"]
                                )
                                if is_matching_event(d_evt, c_evt)
                            ),
                            None,
                        )

                        overlaps = False
                        overlaps = any(
                            events_overlap(c_evt, part2_evt)
                            for part2_evt in part2_event_pool
                        )

                        if overlaps:
                            print(f"Removed due to overlap with part2: {c_evt}")

                        if not overlaps and match_index is None:
                            filtered_creates.append(c_evt)
                    except Exception as e:
                        print(f"[WARN] Failed processing event: {c_evt} — Reason: {e}")
                        continue

                for evt in part2_event_pool:
                    evt = evt.copy()
                    if evt.get("type") == "update":
                        evt["type"] = "create"
                    filtered_creates.append(evt)
                self.part1_results["creatingEvents"] = filtered_creates

            combined_result["creatingEvents"] = self.part1_results["creatingEvents"]
            combined_result["deletingEvents"] = self.part1_results["deletingEvents"]
            if part2_results:
                combined_result["obj_value"] = part2_results.get(
                    "obj_value", combined_result.get("obj_value", 0)
                )

                if part2_results.get("disabled_constraints"):
                    combined_result["disabled_constraints"].extend(
                        part2_results["disabled_constraints"]
                    )

            efficiency_data = self.calculate_efficiency()
            combined_result["statistics"] = efficiency_data
            execution_time = round(time.time() - start_time)
            combined_result["statistics"]["run_time"] = execution_time
            print(f"total optimizer execution time: {execution_time}")
            return [combined_result]

        self.data.update(
            {
                "percentage": 10,
                "part2_in_part1": False,
                "is_orange": True,
                "max_time_in_seconds": 60.0,
            }
        )

        # # self.timings["Run_Optimization_Phase"], results = self.run_optimization_phase()
        results = self.run_optimization_phase()
        execution_time = round(time.time() - start_time)

        efficiency_data = self.calculate_efficiency()

        results["statistics"] = efficiency_data
        results["statistics"]["run_time"] = execution_time
        print(f"execution time: {execution_time}")
        # self.timings["total_time"] = sum(self.timings.values())
        # if False and os.getenv("ENV") == "development":
        #     visualize_timings(
        #         self.timings,
        #         title="Optimizer",
        #         save_path="/var/task/benchmarking/Optimizer_excution_time.png",
        #     )
        return [results]

    # #@measure_time
    def run_optimization_phase(self):
        self.data["is_events"] = False
        self.data["is_session_for_part2"] = False
        primary_data = self.data
        secondary_data = copy.deepcopy(self.data)
        solutions_primary = {}
        solutions_secondary = {}
        solutions_array = []
        current_date_str = self.start_date.strftime("%Y-%m-%d")

        start_time = time.time()
        with ThreadPoolExecutor() as executor:
            generated_solutions = executor.map(self.get_solutions, [primary_data])
            for solution in generated_solutions:
                solutions_array.append(solution)

        self.timings["Getting_Solutions"] = time.time() - start_time
        solutions_primary = solutions_array[0]
        self.solution = solutions_primary[0][0]

        week_dates = get_week_start_end(self.data["start_date"])
        self.weekly_availability = {i: {} for i in range(len(week_dates["week_dates"]))}

        for i in range(len(self.weekly_availability) - 1):
            start = week_dates["week_dates"][i]
            end = week_dates["week_dates"][i + 1]
            availability = availabilities(
                self.data["host"], self.data["header"], start, end, self.data["branch"]
            )
            self.weekly_availability[i].update(availability[4])

        def run_optimize_team(idx=0):
            with ThreadPoolExecutor() as executor:
                futures = [
                    executor.submit(
                        self.optimize_team,
                        team_idx,
                        team,
                        [
                            solutions_primary[0][team_idx],
                            solutions_primary[1][team_idx],
                            solutions_primary[2][team_idx],
                            solutions_primary[3][team_idx],
                        ],
                        [
                            # solutions_secondary[0][team_idx],
                            # solutions_secondary[1][team_idx],
                            # solutions_secondary[2][team_idx],
                            # solutions_secondary[3][team_idx],
                        ],
                        idx,
                    )
                    for team_idx, team in enumerate(self.data["teams_ids"])
                ]

                all_team_results = [future.result() for future in futures]

            final_results = self.aggregate_team_results(all_team_results)
            return final_results

        start_time = time.time()
        if self.data.get("part1"):
            results = run_optimize_team()
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                futures = {
                    executor.submit(run_optimize_team, 5): 5
                    for i in range(1)
                    # executor.submit(run_optimize_team, i + 1): i + 1 for i in range(5)
                }
                allResult = {
                    futures[future]: future.result() for future in as_completed(futures)
                }

            try:
                best_result = min(
                    allResult.items(),
                    key=lambda x: (
                        (-x[1]["obj_value"], x[0])
                        if isinstance(x[1], dict) and "obj_value" in x[1]
                        else float("inf")
                    ),
                )

                results_index, results = best_result
                print(
                    f"Best result number and results: {results_index} ----- {results}"
                )

            except ValueError:
                print("Error: No valid results found in allResult.")

        self.timings["run optimizer with team"] = time.time() - start_time
        print(f"Time for the run optimizer:", self.timings)

        return results

    def optimize_team(
        self, team_idx, team, solutions_primary, solutions_secondary=[], idx=0
    ):
        print("solutions_primary[0].events2", solutions_primary[0].events2)
        team_results = []
        team_admin_filler = []

        # for day_idx in range(self.total_days):
        # end_date = self.start_date + datetime.timedelta(days=4 + 1)
        end_date = self.end_date
        daily_data = self.data.copy()
        daily_data.update(
            {
                "team": team,
                "team_index": team_idx,
                "start_date": self.start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "today_index": get_weekday_index(self.start_date.strftime("%Y-%m-%d")),
                "weekdays_av_data": self.weekly_availability,
                "sol_1": solutions_primary[0],
                "sol_2": solutions_primary[1],
                "sol_3": solutions_primary[2],
                "public_ip": self.public_ip,
                "time_since_server_started": self.time_since_server_started,
                "instance_id": self.instance_id,
            }
        )

        task_data_copy = copy.deepcopy(daily_data)
        if daily_data.get("analyzeMode"):
            # Analyze mode logic
            print("Running analyzeMode")
            daily_data.update(
                {
                    "run_with_teams": False,
                    "workers": os.cpu_count() * 2,
                    "sols_with_events": [],
                    "new_created_events": [],
                }
            )
            # task_data_copy.update(
            #     {
            #         "run_with_teams": False,
            #         "sols_with_events": [],
            #         "new_created_events": [],
            #     }
            # )
            # (
            #     task_data_copy["sol_1"],
            #     task_data_copy["sol_2"],
            #     task_data_copy["sol_3"],
            # ) = (
            #     solutions_secondary[0],
            #     solutions_secondary[1],
            #     solutions_secondary[2],
            # )

            solver = Solver(daily_data)
            analyze_results = solver.part_two()
            team_admin_filler.extend(solver.admin_filler)
            analyze_results.update(
                {
                    "analyzerMessage": "Issue detected",
                    "issueArray": daily_data["ignoredConstrainTypes"],
                }
            )
            if len(analyze_results["creatingEvents"]) == 0:
                analyze_results["statistics"]["status"] = "INFEASIBLE"
            team_results.append(analyze_results)
        elif daily_data.get("part1") and not daily_data.get("analyzeMode"):
            print("Running Part1 optimizer")
            daily_data.update(
                {
                    "run_with_teams": False,
                    "workers": os.cpu_count() * 2,
                    "sol_1": solutions_primary[0],
                    "sol_2": solutions_primary[1],
                    "sol_3": solutions_primary[2],
                    "sols_with_events": [],
                    "new_created_events": [],
                    "percentage": 0,
                }
            )
            solver = Solver(daily_data)
            part1_results = solver.part_one()
            print("folly", part1_results)
            team_results.append(part1_results)
            solutions_primary[0].created_events += solver.created_events
        else:
            print("Running Part2 optimizer")
            if daily_data["percentage"] == 0:
                workers_count = os.cpu_count() * 2
                # if len(daily_data["teams"]) > 5:
                #     workers_count = 128 // len(daily_data["teams"]) * 2

                daily_data.update(
                    {
                        "run_with_teams": False,
                        "workers": workers_count,
                        "sol_1": solutions_primary[0],
                        "sol_2": solutions_primary[1],
                        "sol_3": solutions_primary[2],
                        "sols_with_events": [],
                        "new_created_events": [],
                    }
                )

                # task_data_copy.update(
                #     {
                #         "run_with_teams": False,
                #         "workers": os.cpu_count()*2,
                #         "sol_1": solutions_secondary[0],
                #         "sol_2": solutions_secondary[1],
                #         "sol_3": solutions_secondary[2],
                #         "sols_with_events": [],
                #         "new_created_events": [],
                #         "percentage": 0,
                #     }
                # )

                solver = Solver(daily_data)
                optimization_result = solver.part_two()
                team_admin_filler.extend(solver.admin_filler)

                new_creating_events = []
                new_deleting_events = []
                lunch_id = "ab0bc43a-b680-4642-88e1-2c2f4236dd5e"

                for event in optimization_result["creatingEvents"]:
                    if lunch_id != event["activity0Id"]:
                        new_creating_events.append(event)
                    else:
                        print("Skipping lunch event during creation.")

                for event in optimization_result["deletingEvents"]:
                    if lunch_id not in event["resourceIds"]:
                        new_deleting_events.append(event)
                    else:
                        print("Skipping lunch event during deletion.")

                optimization_result["creatingEvents"] = new_creating_events
                optimization_result["deletingEvents"] = new_deleting_events

                daily_data["new_created_events"] += copy.deepcopy(
                    optimization_result["creatingEvents"]
                ) + copy.deepcopy(optimization_result["updatingEvents"])

                # task_data_copy["new_created_events"] += copy.deepcopy(
                #     optimization_result["creatingEvents"]
                # ) + copy.deepcopy(optimization_result["updatingEvents"])

                lunch_ids = []
                fake_uuids = []
                # if len(task_data_copy["new_created_events"]) > 0:
                #     for i in task_data_copy["new_created_events"]:
                #         temp_uuid = str(uuid.uuid4())
                #         i["id"] = temp_uuid
                #         timestamp = datetime.datetime.strptime(
                #             i["end"], "%Y-%m-%dT%H:%M:%S.%fZ"
                #         )
                #         formatted_timestamp = timestamp.strftime(
                #             "%Y-%m-%dT%H:%M:%S.%fZ"
                #         )
                #         i["end"] = formatted_timestamp
                #         i["resourceIds"] = list(filter(lambda x: x != "1", i["users"]))
                #         i["title"] = ""
                #         fake_uuids.append(temp_uuid)
                # for i in task_data_copy["new_created_events"]:
                #     if i["activity"] == "Lunch":
                #         lunch_ids.append(i["id"])

                if (
                    False
                    and optimization_result["statistics"]["total_clients_efficiency"]
                    != "100.0%"
                ):
                    solver2 = Solver(task_data_copy)
                    additional_results = solver2.part_two()
                    team_admin_filler.extend(solver2.admin_filler)

                    dont_send = []
                    additional_creating_events = [
                        i
                        for i in task_data_copy["new_created_events"]
                        if i["id"] not in dont_send
                    ]
                    additional_results["creatingEvents"] = [
                        *additional_results["creatingEvents"],
                        *additional_creating_events,
                    ]

                    filtered_create_events = []
                    event_types = {
                        "create": "creatingEvents",
                        "update": "updatingEvents",
                        "delete": "deletingEvents",
                    }

                    for event in additional_results["creatingEvents"]:
                        event_type = event.get("type")

                        if event_type in event_types:
                            if event_type == "create":
                                filtered_create_events.append(event)
                            elif event_type == "update" | event_type == "delete":
                                additional_results[event_types[event_type]].append(
                                    event
                                )
                        else:
                            print("outside of the event type")

                    additional_results["creatingEvents"] = filtered_create_events

                    real_event_ids = {
                        event["id"] for event in solutions_secondary[1].events2
                    }

                    additional_results["deletingEvents"] = list(
                        filter(
                            lambda x: x["id"] in real_event_ids,
                            additional_results["deletingEvents"],
                        )
                    )

                    updating_to_creating = list(
                        filter(
                            lambda x: x["id"] not in real_event_ids,
                            additional_results["updatingEvents"],
                        )
                    )
                    for event in updating_to_creating:
                        event["type"] = "create"

                    additional_results["creatingEvents"] = [
                        event
                        for event in additional_results["creatingEvents"]
                        if "id" not in event
                        or event["id"] not in {e["id"] for e in updating_to_creating}
                    ]

                    additional_results["creatingEvents"].extend(updating_to_creating)

                    additional_results["updatingEvents"] = [
                        event
                        for event in additional_results["updatingEvents"]
                        if event["id"] in real_event_ids
                    ]

                    additional_results["statistics"]["deleted_appointments"] = [
                        event["id"] for event in additional_results["deletingEvents"]
                    ]

                    team_results.append(additional_results)
                else:
                    team_results.append(optimization_result)
            else:
                daily_data["run_with_teams"] = False
                daily_data["workers"] = os.cpu_count() * 2
                daily_data["sol_1"] = solutions_primary[0]
                daily_data["sol_2"] = solutions_primary[1]
                daily_data["sol_3"] = solutions_primary[2]
                daily_data["sols_with_events"] = []
                daily_data["new_created_events"] = []
                daily_data["percentage"] = idx * 2
                print("limmers", daily_data["sol_1"].events2)

                solver = Solver(daily_data)
                print("limmers3", solver.solution1.events2)
                optimization_result = solver.part_two()
                print("limmers4", solver.solution1.events2)
                team_admin_filler.extend(solver.admin_filler)
                team_results.append(optimization_result)
        return {"results": team_results, "admin_filler": team_admin_filler}

    def calculate_efficiency(self):
        adam_max_total_hours = (
            get_number_per_slot(self.solution)
            / (60 // self.data["slot_length"])
            / (self.data["slot_length"] / 15)
        )

        start = self.start_date.strftime("%Y-%m-%d")
        end = (self.start_date + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        # end = self.end_date.strftime("%Y-%m-%d")
        print("self.end_date2", self.start_date, self.end_date)
        host, branch, header = (
            self.data["host"],
            self.data["branch"],
            self.data["header"],
        )
        stat = availabilities(host, header, start, end, branch)

        self.availability.update(stat[0])
        efficiency = {}
        for team_idx, team_ids in enumerate(self.data["teams_ids"]):
            team_efficiency = self.efficiency[team_idx]
            for resource_id in team_ids:
                if resource_id in team_efficiency:
                    efficiency[resource_id] = team_efficiency[resource_id]
        efficiency_data = {
            "total_efficiency": 0.0,
            "total_employees_efficiency": 0.0,
            "total_clients_efficiency": 0.0,
            "employees_efficiency": {},
            "clients_efficiency": {},
            "adam__possible_max_hours": adam_max_total_hours,
            "total_max_possible_hours": self.max_total_hours,
            "total_deleted_hours": self.deleted_hours,
            "total_created_hours": self.created_hours,
            "status": "",
            "orange_solution_ratio": 0.0,
            "deleted_appointments": [],
            "deleted_appointments_number": 0,
        }
        total_availability = 0
        employees_total_availability = 0
        clients_total_availability = 0
        for value in self.solution.user_availabilities_general_clients.values():
            for tup in value:
                tup_list = list(tup)
                start = tup_list[0]
                end = tup_list[1]
                clients_total_availability += (end - start) / (
                    60 / self.solution.slot_length
                )
        for value in self.solution.user_availabilities_general_employees.values():
            for tup in value:
                tup_list = list(tup)
                start = tup_list[0]
                end = tup_list[1]
                employees_total_availability += (end - start) / (
                    60 / self.solution.slot_length
                )

        total_availability = clients_total_availability + employees_total_availability

        total_appointments_duration = sum([i for i in self.efficiency_data.values()])
        efficiency_data["total_efficiency"] = round(
            total_appointments_duration / total_availability, 2
        )
        employees_id = list(self.availability["employees"].keys())
        clients_id = list(self.availability["clients"].keys())
        employees_total_duration = sum(
            [v for i, v in self.efficiency_data.items() if i in employees_id]
        )
        clients_total_duration = sum(
            [v for i, v in self.efficiency_data.items() if i in clients_id]
        )
        efficiency_data["total_employees_efficiency"] = (
            employees_total_duration / employees_total_availability
            if employees_total_availability
            else 0
        )

        efficiency_data["total_clients_efficiency"] = (
            clients_total_duration / clients_total_availability
            if clients_total_availability
            else 0
        )

        for k, v in self.efficiency_data.items():
            if k in employees_id:
                eff = round((v / self.availability["employees"][k]) * 100, 2)
                efficiency_data["employees_efficiency"].update({k: eff})
            elif k in clients_id:
                eff = round((v / self.availability["clients"][k]) * 100, 2)
                efficiency_data["clients_efficiency"].update({k: eff})
        efficiency_data["status"] = self.status_name
        efficiency_data["deleted_appointments"] = self.deleted_appointments_list
        efficiency_data["deleted_appointments_number"] = len(
            self.deleted_appointments_list
        )
        efficiency_data["total_clients_efficiency"] = (
            f"{round(efficiency_data['total_clients_efficiency'] * 100, 2)}%"
        )
        efficiency_data["total_employees_efficiency"] = (
            f"{round(efficiency_data['total_employees_efficiency'] * 100, 2)}%"
        )
        efficiency_data["total_efficiency"] = (
            f"{round(efficiency_data['total_efficiency'] * 100, 2)}%"
        )

        self.response = efficiency_data
        return efficiency_data

    def aggregate_team_results(self, all_team_results):

        final_result = {
            "creatingEvents": [],
            "deletingEvents": [],
            "updatingEvents": [],
            "obj_value": 0,
            "disabled_constraints": [],
            "statistics": {},
        }
        total_obj_value = 0
        count = len(all_team_results)

        if count == 0:
            return final_result

        print("first_team_result", all_team_results)
        first_team_result = all_team_results[0]["results"][0]
        final_result["deletingEvents"] = first_team_result["deletingEvents"]
        final_result["updatingEvents"] = first_team_result["updatingEvents"]
        self.deleted_appointments_list = first_team_result["deleted_appointments_list"]
        self.status_name = first_team_result["status_name"]
        self.max_total_hours = first_team_result["max_total_hours"]
        self.efficiency = []
        for team_result in all_team_results:
            team_data = team_result["results"][0]
            final_result["creatingEvents"].extend(team_data["creatingEvents"])
            final_result["disabled_constraints"].extend(
                team_data["disabled_constraints"]
            )
            self.efficiency.append(team_data["efficiency"])
            self.created_hours += team_data["created_hours"]
            self.deleted_hours += team_data["deleted_hours"]
            total_obj_value += team_data["obj_value"]

        final_result["obj_value"] = total_obj_value / count
        print('self.data["teams_ids"]', self.data["teams_ids"])
        for team_idx, team_ids in enumerate(self.data["teams_ids"]):
            team_efficiency = self.efficiency[team_idx]
            for resource_id in team_ids:
                if resource_id not in self.efficiency_data:
                    self.efficiency_data[resource_id] = 0
                if resource_id in team_efficiency and team_efficiency[resource_id] != 0:
                    self.efficiency_data[resource_id] = team_efficiency[resource_id]
        print("this_print", self.efficiency_data)
        # final_result["statistics"] = efficiency_data

        return final_result

    def get_solutions(self, a):
        events_poss = []
        d1 = datetime.datetime.strptime(a["end_date"], "%Y-%m-%d")
        d2 = datetime.datetime.strptime(a["start_date"], "%Y-%m-%d")
        print("date1 here", d1, d2)
        delta = d1 - d2
        start_date_original = datetime.datetime.strptime(a["start_date"], "%Y-%m-%d")
        end_date_original = datetime.datetime.strptime(a["end_date"], "%Y-%m-%d")
        # real_end_date = datetime.datetime.strftime(
        #     end_date_original + datetime.timedelta(days=int(delta.days) + 1),
        #     "%Y-%m-%d",
        # )
        real_end_date = a["end_date"]
        print('a["start_date"]', a["start_date"], a["end_date"])

        start_time = time.time()
        print("date1 here", real_end_date)
        self.data_gatherer = Data_Gatherer(
            {**a, "end_date": real_end_date, "is_events": True, "optimizer_sol": True}
        )
        print(f"fetching data time: {time.time() - start_time}")

        if self.part1_results:
            self.converted_events = convert_events(self.part1_results["creatingEvents"])
            if hasattr(self.data_gatherer, "events2") and isinstance(
                self.data_gatherer.events2, list
            ):
                self.data_gatherer.events2.extend(self.converted_events)
            else:
                self.data_gatherer.events2 = list(self.converted_events)

        print("pholy1", self.data_gatherer.events)
        print("pholy2", self.data_gatherer.events2)
        is_session = False
        if "is_session_for_part2" in a.keys():
            is_session = a["is_session_for_part2"]

        solutions1 = EventScheduler(
            self.data_gatherer,
            {
                "is_orange": True,
                "is_session": is_session,
                "investigate": [],
                "ignoreConstraintArray": a["uncheckWhiteSolutionConstraints"],
                "soft": True,
            },
        )
        # print("solutions1.events24", solutions1.events2)

        events_poss = solutions1.generate_scheduling_events()

        colored_events = self.assign_colors(events_poss)

        events_poss = self.categorize_events(colored_events)
        print("gommer3", events_poss)
        result = []
        for item in solutions1.events_poss:
            modified_resource_ids = [
                resource_id[:-1] for resource_id in item["resourceIds"]
            ]
            result.append(modified_resource_ids)
        self.data_gatherer.resourceCombinationsExclude = result
        print("solutions1.events25", solutions1.events2)

        solutions2 = EventScheduler(
            self.data_gatherer,
            {
                "is_orange": True,
                "is_session": False,
                "ignoreConstraintArray": a["uncheckOrangeSolutionConstraints"],
                "soft": True,
            },
        )

        unmatch_poss_events = []
        unmatch_poss_events = solutions2.generate_scheduling_events()

        # running_team_creator = solutions1.part1 and not a.get("teams")
        running_team_creator = False

        teams = solutions1.team_creator(
            events_poss + unmatch_poss_events, running_team_creator
        )
        self.data["teams_ids"] = teams["team_ids"]

        def filter_events_by_team(events_list, users_map, teams):
            team_solutions = []
            for team_resources in teams:
                team_events = []
                for event in events_list:
                    persons = [
                        users_map[res]["id"]
                        for res in event["resourceIds_r"]
                        if "Person" in users_map[res]["roles"]
                    ]
                    if all(res in team_resources for res in persons):
                        team_events.append(event)
                solution_copy = copy.deepcopy(solutions1)
                solution_copy.events_poss = team_events
                team_solutions.append(solution_copy)
            return team_solutions

        team_solutions_primary = filter_events_by_team(
            events_poss, solutions1.users, self.data["teams_ids"]
        )
        events_poss = [ts.events_poss for ts in team_solutions_primary]

        team_solutions_secondary = filter_events_by_team(
            unmatch_poss_events, solutions2.users, self.data["teams_ids"]
        )
        team_orange = []

        for i, team_resources in enumerate(self.data["teams_ids"]):
            team_events = []
            for event in unmatch_poss_events:
                persons = [
                    solutions2.users[res]["id"]
                    for res in event["resourceIds_r"]
                    if "Person" in solutions2.users[res]["roles"]
                ]
                if all(res in team_resources for res in persons):
                    event_with_flag = event.copy()
                    event_with_flag["orange_sol"] = True
                    team_events.append(event_with_flag)
            team_orange.append(team_events)

        return [
            team_solutions_primary,
            team_solutions_secondary,
            team_orange,
            events_poss,
        ]


def runOptimizer(data):
    optimizer = Optimizer(data)
    return optimizer.optimize_workflow()
