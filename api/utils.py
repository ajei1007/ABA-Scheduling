import uuid
from datetime import datetime
from dateutil import parser
import os


def data_converter(data):

    # backend_url = f'{data["host"]}/api'
    # backend_url = "production-api.abaschedules.com/api"
    backend_url = os.getenv("BACKEND_URL")

    if not backend_url.startswith("http"):
        backend_url = f"https://{backend_url}"

    converted_data = {
        "start_date": data["startdate"],
        "end_date": data["enddate"],
        "branch": data["branches"][0],
        "teams": data["teams"],
        "daily": False,
        "blocks": False,
        "is_Multi": True,
        "is_lunch": False,
        "is_break": data.get("breaktime", False),
        "is_orange": True,
        "onCall": data.get("onCall", False),
        "is_events": True,
        "isolatedResources": data.get("isolatedResources", []),
        "objective_role": data["objectiveRolesRanking"],
        "insert_data_role": "Person",
        "slot_length": max(5, min(data["settings"].get("timeInterval", 15), 15)),
        "max_time_in_seconds": 180.0,
        "num_search_workers": data["workers"],
        "min_session_dur": data["minsession"],
        "max_session_length": float(data["maxsession"]),
        "no_gap_role": "Person",
        "overlap_role": "Person",
        "team_bounds": {
            "num_of_teams": 5,
            "r": 4,
            "min_people_per_team": 5,
        },
        "lunch_role": "Employee",
        "lunch_length": 2,
        "maxClientHoursPerDay": data["maxClientHoursPerDay"],
        "maxEmployeeHoursPerDay": data["maxEmployeeHoursPerDay"],
        "maxGapClientSchedule": data["maxGapClientSchedule"],
        "maxGapEmployeeSchedule": data["maxGapEmployeeSchedule"],
        "clientsMaxAppointmentsPerDay": data["clientsMaxAppointmentsPerDay"],
        "employeesMaxAppointmentsPerDay": data["employeesMaxAppointmentsPerDay"],
        "break_role": "Employee",
        "break_length": 1,
        "part1": data.get("part1", False),
        "is_time_constraint": False,
        "is_drive_constraint": data.get("constraintdrive", True),
        "is_lunch_constraint": data["constraintlunch"],
        "is_break_constraint": data["breaktime"],
        "is_team_constraint": False,
        "is_overlap_constraint": True,
        "is_minSession_constraint": True,
        "is_noGap_constraint": True,
        "is_delete": False,
        "optimizer_sol": True,
        "host": backend_url,
        "all_or_nothing": data.get("all_or_nothing", False),
        "hard": data["hard"],
        "highPriority": data.get("highPriority", []),
        "soft": data.get("soft", []),
        "disabled": data.get("disabled", []),
        "break_id": data["break_id"],
        "drive_id": data["drive_id"],
        "home_id": data.get("home_id", ""),
        "lunch_id": data["lunch_id"],
        "objectiveactivity": data["activitiesRanking"],
        "billable": data["billable"],
        "nonbillable": data["nonbillable"],
        "investigate": data.get("investigate", []),
        "expanded_resources": data["activitiesRanking"] or [],
        "uncheckWhiteSolutionConstraints": data["uncheckWhiteSolutionConstraints"],
        "uncheckOrangeSolutionConstraints": data["uncheckOrangeSolutionConstraints"],
        "settings": data["settings"],
        "companyId": data["companyId"],
        "header": data["header"],
        "limit_coefficient": 10,
        "activitiesRanking": data.get("activitiesRanking", []),
        "mode": data.get("mode", "fast"),
        "notWorking": data.get("notWorking", []),
        "analyzeMode": False,
        "runAnalyzer": False,
        "ignoredConstrainTypes": [],
    }

    if converted_data["is_lunch"]:
        converted_data["expanded_resources"].append(converted_data["lunch_id"])
    if converted_data["is_break"]:
        converted_data["expanded_resources"].append(converted_data["break_id"])

    return converted_data


def convert_events(event_list):
    converted = []

    for event in event_list:
        new_event = {}

        new_event["id"] = str(uuid.uuid4())

        new_event["resourceIds"] = list(
            set(
                event.get("resourceIds", [])
                + [
                    event.get("activity0Id", ""),
                    event.get("location0Id", ""),
                    event.get("loc_id", ""),
                ]
            )
        )

        location = event.get("location", "")
        client = event.get("client", "")
        employee = event.get("employee", "")
        activity = event.get("activity", "")
        new_event["location"] = location
        new_event["client"] = client
        new_event["employee"] = employee
        new_event["activity"] = activity
        title_parts = [client, employee, location, location, activity, activity]
        title = " - ".join(filter(None, title_parts))
        new_event["title"] = title

        new_event["canceledId"] = False

        address = event.get("address")
        new_event["address"] = address if address else None
        new_event["reasons"] = []
        new_event["people_drive_times"] = {"start": {}, "end": {}}
        new_event["distances_all"] = []
        new_event["times_all"] = []
        new_event["reasons_l"] = ""
        new_event["loc_id"] = event.get("loc_id") if event.get("loc_id") else None
        new_event["priority"] = ""

        try:
            start_time = parser.isoparse(event["start"])
        except Exception:
            start_time = datetime.strptime(event["start"], "%Y-%m-%dT%H:%M:%S.000Z")

        try:
            end_time = parser.isoparse(event["end"])
        except Exception:
            end_time = datetime.strptime(event["end"], "%Y-%m-%dT%H:%M:%S.000Z")
        duration = (end_time - start_time).seconds
        new_event["duration"] = int(duration)

        new_event["start"] = start_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        end_fixed = end_time.strftime("%Y-%m-%dT%H:%M:%S.000000Z")
        new_event["end_real_time"] = end_fixed
        new_event["end"] = end_fixed

        new_event["scheduled"] = event.get("scheduled", True)
        new_event["orange_sol"] = event.get("orange_sol", False)

        converted.append(new_event)

    return converted
