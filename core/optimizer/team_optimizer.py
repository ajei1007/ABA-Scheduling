import datetime
import copy
import uuid
import json
import pickle
import base64
import traceback
from core.shared.event_schedular.main import EventScheduler
from core.shared.event_solver.main import Solver
from core.shared.utils import get_week_start_end, get_weekday_index, availabilities


def serialize_instance(instance):
    binary_data = pickle.dumps(instance)
    return base64.b64encode(binary_data).decode("utf-8")


def deserialize_instance(serialized_data):
    binary_data = base64.b64decode(serialized_data)
    return pickle.loads(binary_data)


def lambda_handler(event, context):
    try:
        print("howdy")

        body = json.loads(event["body"])
        print("howdy", body)
        data = body.get("data")
        team_idx = body.get("team_idx")
        team = body.get("team")
        solutions_primary_serialized = body.get("solutions_primary")
        solutions_secondary_serialized = body.get("solutions_secondary")

        # if not all([data, team_idx, team, solutions_primary_serialized, solutions_secondary_serialized]):
        #     return {
        #         "statusCode": 400,
        #         "body": json.dumps({"error": "Missing required fields in the payload"})
        #     }

        solutions_primary = deserialize_instance(solutions_primary_serialized)
        solutions_secondary = deserialize_instance(solutions_secondary_serialized)

        print(f"Optimizing for team_idx: {team_idx}, team: {team}")
        print(f"Primary Solutions: {solutions_primary}")
        print(f"Secondary Solutions: {solutions_secondary}")

        solver_results = optimize_team(
            data, team_idx, team, solutions_primary, solutions_secondary
        )
        print("generated result----------:", solver_results)

        return {"body": json.dumps(serialize_instance(solver_results))}

    except Exception as e:
        print(f"Error in Lambda function: {e}")
        traceback.print_exc()
        return json.dumps({"error": "Something went wrong!"})


def optimize_team(data, team_idx, team, solutions_primary, solutions_secondary):
    try:
        # solutions_primary = deserialize_instance(solutions_primary_serialized)
        # solutions_secondary = deserialize_instance(solutions_secondary_serialized)
        print(f"Optimizing for team_idx: {team_idx}, team: {team}")
        print(f"Primary Solutions: {solutions_primary}")
        print(f"Secondary Solutions: {solutions_secondary}")
        team_results = []
        team_admin_filler = []
        start_date = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d")
        end_date = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d")
        total_days = (end_date - start_date).days + 1

        week_dates = get_week_start_end(data["start_date"])
        weekly_availability = {i: {} for i in range(len(week_dates["week_dates"]))}

        for i in range(len(weekly_availability) - 1):
            start = week_dates["week_dates"][i]
            end = week_dates["week_dates"][i + 1]
            availability = availabilities(
                data["host"], data["header"], start, end, data["branch"]
            )
            weekly_availability[i].update(availability[4])

        print("solutions_primary data:", solutions_primary)
        print("solutions_secondary data:", solutions_secondary)

        for day_idx in range(total_days):
            current_date = start_date + datetime.timedelta(days=day_idx + 1)
            daily_data = data.copy()
            daily_data.update(
                {
                    "team": team,
                    "team_index": team_idx,
                    "start_date": current_date.strftime("%Y-%m-%d"),
                    "end_date": current_date.strftime("%Y-%m-%d"),
                    "today_index": get_weekday_index(current_date.strftime("%Y-%m-%d")),
                    "weekdays_av_data": weekly_availability,
                    "sol_1": solutions_primary[0],
                    "sol_2": solutions_primary[1],
                    "sol_3": solutions_primary[2],
                }
            )

            task_data_copy = copy.deepcopy(daily_data)

            if daily_data.get("analyzeMode"):
                # Analyze mode logic
                daily_data.update(
                    {
                        "run_with_teams": False,
                        "workers": 12,
                        "sols_with_events": [],
                        "new_created_events": [],
                    }
                )
                task_data_copy.update(
                    {
                        "run_with_teams": False,
                        "sols_with_events": [],
                        "new_created_events": [],
                    }
                )
                (
                    task_data_copy["sol_1"],
                    task_data_copy["sol_2"],
                    task_data_copy["sol_3"],
                ) = (
                    solutions_secondary[0],
                    solutions_secondary[1],
                    solutions_secondary[2],
                )

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
                # Part 1 logic
                daily_data["percentage"] = 0
                solver = Solver(daily_data)
                part1_results = solver.part_one()
                team_results.append(part1_results)
                solutions_primary[0].created_events += solver.created_events
            else:
                if daily_data["percentage"] == 0:
                    workers_count = 12
                    # if len(daily_data["teams"]) > 5:
                    #     workers_count = 128 // len(daily_data["teams"]) * 2

                    daily_data.update(
                        {
                            "run_with_teams": True,
                            "workers": workers_count,
                            "sol_1": solutions_primary[0],
                            "sol_2": solutions_primary[1],
                            "sol_3": solutions_primary[2],
                            "sols_with_events": [],
                            "new_created_events": [],
                        }
                    )

                    task_data_copy.update(
                        {
                            "run_with_teams": False,
                            "workers": 12,
                            "sol_1": solutions_secondary[0],
                            "sol_2": solutions_secondary[1],
                            "sol_3": solutions_secondary[2],
                            "sols_with_events": [],
                            "new_created_events": [],
                            "percentage": 0,
                        }
                    )

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

                    task_data_copy["new_created_events"] += copy.deepcopy(
                        optimization_result["creatingEvents"]
                    ) + copy.deepcopy(optimization_result["updatingEvents"])

                    lunch_ids = []
                    fake_uuids = []
                    if len(task_data_copy["new_created_events"]) > 0:
                        for i in task_data_copy["new_created_events"]:
                            temp_uuid = str(uuid.uuid4())
                            i["id"] = temp_uuid
                            timestamp = datetime.datetime.strptime(
                                i["end"], "%Y-%m-%dT%H:%M:%S.%fZ"
                            )
                            formatted_timestamp = timestamp.strftime(
                                "%Y-%m-%dT%H:%M:%S.%fZ"
                            )
                            i["end"] = formatted_timestamp
                            print("filly", formatted_timestamp)
                            i["resourceIds"] = list(
                                filter(lambda x: x != "1", i["users"])
                            )
                            i["title"] = ""
                            fake_uuids.append(temp_uuid)
                            print("footy", i["resourceIds"])
                    for i in task_data_copy["new_created_events"]:
                        if i["activity"] == "Lunch":
                            print(
                                "lunch_here",
                                i["activity0Id"],
                                task_data_copy["lunch_id"],
                            )
                            lunch_ids.append(i["id"])

                    if (
                        optimization_result["statistics"]["total_clients_efficiency"]
                        != "100.0%"
                    ):
                        print("Re-running optimization for better efficiency.")

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
                                print(f"seemer{event_types[event_type]}", event)
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
                            or event["id"]
                            not in {e["id"] for e in updating_to_creating}
                        ]

                        additional_results["creatingEvents"].extend(
                            updating_to_creating
                        )

                        additional_results["updatingEvents"] = [
                            event
                            for event in additional_results["updatingEvents"]
                            if event["id"] in real_event_ids
                        ]

                        additional_results["statistics"]["deleted_appointments"] = [
                            event["id"]
                            for event in additional_results["deletingEvents"]
                        ]

                        team_results.append(additional_results)
                    else:
                        team_results.append(optimization_result)
                else:
                    daily_data["run_with_teams"] = False
                    daily_data["workers"] = 12
                    daily_data["sol_1"] = solutions_primary[0]
                    daily_data["sol_2"] = solutions_primary[1]
                    daily_data["sol_3"] = solutions_primary[2]
                    daily_data["sols_with_events"] = []
                    daily_data["new_created_events"] = []

                    solver = Solver(daily_data)
                    optimization_result = solver.part_two()
                    team_admin_filler.extend(solver.admin_filler)
                    team_results.append(optimization_result)
        print("team_result:", team_results)
        return {"results": team_results, "admin_filler": team_admin_filler}

    except Exception as e:
        print(f"Error in optimize_team: {e}")
        return {"results": [], "admin_filler": []}
