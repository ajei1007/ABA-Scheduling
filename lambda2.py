import os
import json
import random
import sys
import datetime
import time
import re
import requests
from ortools.sat.python import cp_model
import copy

# Files
from controller import rocket_luncher
from solve import Solution_Generator, Data_Gatherer
from staff_tracker import Data_Gatherer_Staff_Tracker
import math
import traceback
from dotenv import load_dotenv
import uuid
import os
from external import *
from testnewdetail2 import optimize_staff
from analyzer import Analyzer

# import tes

# TODO move to the separate file


def data_converter(d):
    # backendURL = os.getenv("BACKEND_URL")
    backendURL = f'{d["host"]}/api'

    if backendURL[:4] != "http":
        backendURL = f"https://{backendURL}"
    # backendURL = 'https://beta.abaschedules.com/api'
    # backendURL = 'http://localhost:8080/api'
    print("************* backendURL", backendURL)
    print("sloogy2", d["companyId"], d)
    print("sloogy", d["header"])
    obj = {
        "start_date": d["startdate"],  #
        "end_date": d["enddate"],  #
        "branch": d["branches"][0],
        "teams": d["teams"],
        "daily": False,
        "blocks": False,  #
        "is_Multi": True,
        "is_lunch": False,
        # d["constraintlunch"] if "constraintlunch" in d else False,
        "is_break": d["breaktime"] if "breaktime" in d else False,
        "is_orange": True,
        "onCall": d["onCall"] if "onCall" in d else False,
        "is_events": True,
        "percentage": d["percentignore"],  # percentage
        # 'objective_role': 'R/BT',
        "isolatedResources": d.get("isolatedResources", []),
        "objective_role":
        # d["objectiverole"],
        d["objectiveRolesRanking"],
        "insert_data_role": "Person",
        "slot_length": max(5, min(d["settings"].get("timeInterval", 15), 15)),
        "max_time_in_seconds": 180.0,
        "num_search_workers": d["workers"],
        "min_session_dur": d["minsession"],  # [1]
        "max_session_length": float(d["maxsession"]),
        "no_gap_role": "Person",
        "overlap_role": "Person",
        "team_bounds": {"num_of_teams": 5, "r": 4, "min_people_per_team": 5},
        "lunch_role": "Employee",
        "lunch_length": 2,
        "maxClientHoursPerDay": d["maxClientHoursPerDay"],
        "maxEmployeeHoursPerDay": d["maxEmployeeHoursPerDay"],
        "maxGapClientSchedule": d["maxGapClientSchedule"],
        "maxGapEmployeeSchedule": d["maxGapEmployeeSchedule"],
        "clientsMaxAppointmentsPerDay": d["clientsMaxAppointmentsPerDay"],
        "employeesMaxAppointmentsPerDay": d["employeesMaxAppointmentsPerDay"],
        "break_role": "Employee",
        "break_length": 1,
        "part1": False,
        # d['part1'],
        "is_time_constraint": False,
        "is_drive_constraint": d["constraintdrive"] or True,
        "is_lunch_constraint": d["constraintlunch"],
        "is_break_constraint": d["breaktime"],
        "is_team_constraint": False,
        "is_overlap_constraint": True,
        "is_minSession_constraint": True,
        "is_noGap_constraint": True,
        "is_delete": False,
        "optimizer_sol": True,
        "host": backendURL,
        "all_or_nothing": d["all_or_nothing"] if "all_or_nothing" in d else False,
        "hard": d["hard"],
        "highPriority": d["highPriority"] if "highPriority" in d else [],
        "disabled": d["disabled"] if "disabled" in d else [],
        # "highPriority": [],
        "break_id": d["break_id"],
        "drive_id": d["drive_id"],
        "home_id": d["home_id"] if "home_id" in d else "",
        "lunch_id": d["lunch_id"],
        "objectiveactivity": d["activitiesRanking"],
        "mode": d["mode"] if "mode" in d else "fast",
        "billable": d["billable"],
        "nonbillable": d["nonbillable"],
        # For Solution_Generator:
        "investigate": d["investigate"] if "investigate" in d else [],
        "expanded_resources": (
            d["activitiesRanking"] if not d["activitiesRanking"] is None else []
        ),
        "uncheckWhiteSolutionConstraints": d["uncheckWhiteSolutionConstraints"],
        "uncheckOrangeSolutionConstraints": d["uncheckOrangeSolutionConstraints"],
        "settings": d["settings"],
        "companyId": d["companyId"],
        "header": d["header"],
        "limit_coefficient": 10,
        "activitiesRanking": d["activitiesRanking"] if "activitiesRanking" in d else [],
        "notWorking": d["notWorking"] if "notWorking" in d else [],
        "analyzeMode": False,
        "runAnalyzer": False,
        "ignoredConstrainTypes": [],
    }
    print("simily", d["companyId"])
    if obj["is_lunch"]:
        obj["expanded_resources"] = [*obj["expanded_resources"], obj["lunch_id"]]
    print("simily2", d["companyId"])
    if obj["is_break"]:
        obj["expanded_resources"] = [*obj["expanded_resources"], obj["break_id"]]
    print("simily3", d["companyId"])
    return obj


def runSolutionGenerator(data):
    backendURL = os.getenv("BACKEND_URL")

    formattedData = {
        "host": backendURL,
        "req_type": "solutionGenerator",
        "optimizer_sol": False,
        "isolatedResources": [],
    }

    formattedData.update(data["data"])
    data_gatherer = Data_Gatherer(formattedData)
    format = "%Y-%m-%d"

    data_gatherer.resourceCombinationsExclude = []
    solutions2 = Solution_Generator(
        data_gatherer,
        {
            "is_orange": True,
            "ignoreConstraintArray": formattedData["uncheckOrangeSolutionConstraints"],
            # TODO-remove
            "investigate": formattedData["investigate"],
            "soft": True,
        },
    )
    start3 = time.time()
    solutions1 = solutions2
    start = datetime.datetime.strptime(solutions1.start_date, format)
    end = datetime.datetime.strptime(solutions1.end_date, format)

    events_poss = []
    unmatch_poss_events = []

    unmatch_poss_events = solutions2.main2()

    unmatch_poss_events = solutions2.main3()

    if formattedData["settings"]["driveTime"]:
        print("bazo_triggered")
        events_poss = solutions1.main_drive_time()
        unmatch_poss_events = solutions2.main_drive_time()

    unmatch_poss_events_new = unmatch_poss_events

    unmatch_poss_events_new = unmatch_poss_events

    users_list = []
    names = []
    for event in unmatch_poss_events:
        for id in event["resourceIds_r"]:
            actual_id = solutions1.users[id]["id"]
            if id not in names:
                users_list.append(
                    {"label": solutions1.users[id]["name"], "value": actual_id}
                )
                names.append(id)
    users_list_sorted = sorted(users_list, key=lambda d: d["label"])
    events_poss_new2 = []
    for event in events_poss:
        type = "white"
        if "ov" in event.keys() and event["ov"] == "t":
            type = "yellow"
        events_poss_new2.append(
            {**event, "colorType": type, "backgroundColor_real": type}
        )

    unmatch_poss_events_new2 = []
    for event in unmatch_poss_events_new:
        type = "orange"
        if "ov" in event.keys() and event["ov"] == "t":
            type = "yellow"
        unmatch_poss_events_new2.append(
            {**event, "colorType": type, "backgroundColor_real": type}
        )

    all_slot = set()
    for event in unmatch_poss_events_new2:
        all_slot = all_slot.union(set(range(event["start_r"], event["end_r"] + 1)))

    all_slot_ranges = list(solutions1.detect_range(list(sorted(all_slot))))
    ev_dict = {}
    for slot_range in all_slot_ranges:
        ev_dict[slot_range] = []
    for event in unmatch_poss_events_new2:
        for slot_range in all_slot_ranges:
            start = list(slot_range)[0]
            end = list(slot_range)[1]
            if event["start_r"] >= start and event["end_r"] <= end:
                ev_dict[slot_range].append(event["id"])
                break

    lengths_had = []
    obj_return = {}
    for key, value in ev_dict.items():
        sample_event = value[0]
        actual_length = len(value)
        if actual_length in lengths_had:
            for i in range(105):
                if actual_length + i not in lengths_had:
                    actual_length = actual_length + i
        obj_return[actual_length] = {
            "start": list(key)[0],
            "end": list(key)[1],
            "ids": value,
            "index": 0,
            "index_groups": [],
        }
    start111 = time.time()

    new_match = []
    new_unmatch = []
    for event2 in unmatch_poss_events_new2:
        event2["id"] = str(uuid.uuid4())

    future_events = data_gatherer.some_data.get_event_future(unmatch_poss_events_new2)
    start113 = time.time()
    print("bazo_timer3 : ", start113 - start111)
    # print('All future events: ',future_events)
    for event in unmatch_poss_events_new2:
        # print('event-id:',event['id'])
        # print('future event data:',event['id'],future_events[event['id']])
        color = "orange"
        if len(future_events[event["id"]]["constraints"]) == 0:
            del event["reasons"]
            if "ov" in event.keys():
                color = "yellow"
            else:
                color = "white"
            new_match.append(
                {**event, "backgroundColor_real": color, "colorType": color}
            )
        else:
            reasons = []
            for c in future_events[event["id"]]["constraints"]:
                # print('liffy',c)
                description = c.get("description", "")
                if "ov" in event.keys():
                    color = "yellow"
                else:
                    color = "orange"
                if description not in reasons:
                    reasons.append({"reason": re.sub(r"</?strong>", "", description)})
            new_unmatch.append(
                {
                    **event,
                    "constraint": future_events[event["id"]]["constraints"],
                    "reasons": reasons,
                }
            )

    return {
        "intersections": [],
        "conflicts": solutions2.conflicted_constraints["conflicts"],
        # 'poss_events': events_poss_new2,
        # 'unmatch_poss_events': unmatch_poss_events_new2,
        "poss_events": new_match,
        "unmatch_poss_events": new_unmatch,
        "resources": users_list_sorted,
        "obj_return": obj_return,
        "num_of_obj": len(obj_return.values()),
        # 'unmatch_poss_events': events_poss_orange
    }


def routes(event):
    backendURL = os.getenv("BACKEND_URL")
    route = event["routeKey"]
    path = event["requestContext"]["http"]["path"]
    timer1 = time.time()
    # print('****** Path', path)
    # print('event5',event)

    if path == "/staff_equilibrium":
        try:
            body = event["body"]
            body_dict = json.loads(body)
            formattedData = body_dict["data"]
            print("formattedData", formattedData)
            result = optimize_staff(formattedData)
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                },
                "body": json.dumps(result),
            }
        except Exception as e:
            print("***** Automation Error", e)
            traceback.print_exc()  # Print to console
            return {
                "statusCode": 500,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                },
                "body": json.dumps("Something went wrong !"),
            }

    if path == "/staff_tracker":
        try:
            body = event["body"]
            backendURL = os.getenv("BACKEND_URL")
            body_dict = json.loads(body)
            formattedData = body_dict["data"]
            formattedData.update(
                {
                    "host": backendURL,
                }
            )
            print("floojy", formattedData)
            data_gatherer = Data_Gatherer_Staff_Tracker(formattedData)
            data_scrubbed = data_gatherer.main()
            data_scrubbed_oncall = data_gatherer.main(True)
            print("soomer2", data_gatherer.users)
            print("soomer3", data_gatherer.branches)
            users_scrubbed = {
                x["id"]: {
                    "name": x["name"],
                    "branches": x["branches"],
                    "latitude": x["latitude"],
                    "longitude": x["longitude"],
                }
                for x in data_gatherer.users
            }
            branches_scrubbed = {}

            # Loop through the original object
            location_ids = []
            for key, value in data_gatherer.branches.items():
                # Create the new value dictionary with the desired structure
                new_value = {
                    "name": value["name"],
                    "locationId": value["userId"],
                    "employees": [],
                    "clients": [],
                    "locations": [],
                }
                if value["userId"]:
                    location_ids.append(value["userId"])
                # Assign the new value to the corresponding key in the new object
                branches_scrubbed[key] = new_value

            location_coordinates = data_gatherer.some_data.get_coordinates(
                "|".join(location_ids)
            )
            for key, value in branches_scrubbed.items():
                location_id = branches_scrubbed[key]["locationId"]
                if location_id:
                    print("nonethe", location_coordinates[location_id]["clientratio"])
                    branches_scrubbed[key]["latitude"] = location_coordinates[
                        location_id
                    ]["latitude"]
                    branches_scrubbed[key]["longitude"] = location_coordinates[
                        location_id
                    ]["longitude"]
                    branches_scrubbed[key]["clientratio"] = location_coordinates[
                        location_id
                    ]["clientratio"]
                    branches_scrubbed[key]["employeeratio"] = location_coordinates[
                        location_id
                    ]["employeeratio"]

            for x in data_gatherer.users:
                for branch_actual in x["branches"]:
                    for branch in data_gatherer.branch_structure[branch_actual]:
                        if branch in branches_scrubbed.keys():
                            if "Employee" in x["roles"]:
                                branches_scrubbed[branch]["employees"].append(x["id"])
                            elif "Client" in x["roles"]:
                                branches_scrubbed[branch]["clients"].append(x["id"])
                            elif "Location" in x["roles"]:
                                branches_scrubbed[branch]["locations"].append(x["id"])

            def generate_data(count: int, data_range) -> list:
                data = []
                min_val, max_val = data_range["min"], data_range["max"]

                for hour in range(8, 19):
                    for minute in range(0, 46, 15):
                        am_pm = "PM" if hour >= 12 else "AM"
                        formatted_hour = hour - 12 if hour > 12 else hour
                        time = f"{formatted_hour}:{str(minute).zfill(2)} {am_pm}"
                        value = random.randint(min_val, max_val)
                        data.append(
                            {"x": time, "y": random.randint(1, count), "value": value}
                        )

                return data

            count = 10
            data_range = {"min": 1, "max": 100}
            result = [
                {
                    "name": "Jan",
                    "data": generate_data(
                        20,
                        {
                            "min": -30,
                            "max": 55,
                        },
                    ),
                },
                {
                    "name": "Feb",
                    "data": generate_data(
                        20,
                        {
                            "min": -30,
                            "max": 55,
                        },
                    ),
                },
            ]
            # result = generate_data(count, data_range)
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                },
                "body": json.dumps(
                    {
                        "data_before": data_scrubbed,
                        "data_after": data_scrubbed_oncall,
                        "branches": branches_scrubbed,
                        "users": users_scrubbed,
                        "startDate": formattedData["start_date"],
                        "endDate": formattedData["end_date"],
                    }
                ),
            }
        except Exception as e:
            print("***** Automation Error", e)
            traceback.print_exc()  # Print to console
            return {
                "statusCode": 500,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                },
                "body": json.dumps("Something went wrong !"),
            }

    # POST /solution_generator
    if path == "/solution_generator":
        try:
            print("Starting")
            body = event["body"]
            body_dict = json.loads(body)

            resBody = runSolutionGenerator(body_dict)

            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                },
                "body": json.dumps(resBody),
            }
        except Exception as e:
            print("***** Automation Error", e)
            traceback.print_exc()  # Print to console

    # POST /automation
    if path == "/automation":
        try:
            start_time = time.time()

            # headers = event['headers']
            # headers_dict = json.loads(headers)
            body = event["body"]
            body_dict = json.loads(body)
            print("no_bug", body_dict["data"])
            try:
                converted_data = data_converter(body_dict["data"])
            except Exception as e:
                print("bazo_find_bug : ", e)
            print("no_bug")

            converted_data["part1_new"] = copy.copy(converted_data["part1"])
            # converted_data["objectiveactivity"] = converted_data['billable']
            converted_data["expanded_resources"] = (
                converted_data["billable"] + converted_data["nonbillable"]
            )

            print("***** converted_data", converted_data)

            d1 = datetime.datetime.strptime(converted_data["end_date"], "%Y-%m-%d")
            d2 = datetime.datetime.strptime(converted_data["start_date"], "%Y-%m-%d")
            delta = d1 - d2

            if delta.days > 7:
                return {"status": "Day range should be less than or equal to 7 days"}
            if converted_data["is_lunch"]:
                converted_data["expanded_resources"] = [
                    *converted_data["expanded_resources"],
                    converted_data["lunch_id"],
                ]
            if converted_data["is_break"]:
                converted_data["expanded_resources"] = [
                    *converted_data["expanded_resources"],
                    converted_data["break_id"],
                ]
            print("no_problem_bazo")
            if converted_data["analyzeMode"]:
                someAnalyze = Analyzer(converted_data)
                final_data = someAnalyze.isNoGapRelatedIssues()
                print("bazo_final_data_print : ", final_data)
                result = rocket_luncher(final_data)
            else:
                pass
                # result = rocket_luncher(converted_data)
            print("***** result", result)
            end_time = time.time()

            print("***** TIME", end_time - start_time)
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                },
                "body": json.dumps(result),
            }
        except Exception as e:
            print("***** Automation Error", e)
            traceback.print_exc()
            return {
                "statusCode": 500,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                },
                "body": json.dumps("Something went wrong !"),
            }

    # Default
    return {
        "statusCode": 200,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        },
        "body": json.dumps(
            {
                "msg": f"Optimizer AWS Lambda Function is running successfully ! backendURL: {backendURL}",
            }
        ),
    }


def handler(event, context):
    backendURL = os.getenv("BACKEND_URL")
    print("***** Started! System version: " + sys.version + "!")
    print("***** Route Name: ", event["routeKey"])

    return routes(event)
