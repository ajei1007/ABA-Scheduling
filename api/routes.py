import os
import json
import time
import traceback
import random
import copy
import datetime
from analyzer import Analyzer
from api.utils import data_converter
from core.solution_generator.main import runSolutionGenerator
from staff_tracker import Data_Gatherer_Staff_Tracker
from testnewdetail2 import optimize_staff
from core.shared.event_solver.insert_handler import insert_handler
from core.optimizer.optimizer import runOptimizer


class RouteHandler:
    def __init__(self):
        self.backend_url = os.getenv("BACKEND_URL")

    def _success_response(self, data):
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            },
            "body": json.dumps(data),
        }

    def _error_response(self):
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            },
            "body": json.dumps("Something went wrong!"),
        }

    def staff_equilibrium(self, event):
        try:
            body = event["body"]
            body_dict = json.loads(body)
            formatted_data = body_dict["data"]
            result = optimize_staff(formatted_data)
            return self._success_response(result)
        except Exception as e:
            traceback.print_exc()
            return self._error_response()

    def staff_tracker(self, event):
        try:
            body = event["body"]
            body_dict = json.loads(body)
            formatted_data = body_dict["data"]
            formatted_data.update({"host": self.backend_url})

            data_gatherer = Data_Gatherer_Staff_Tracker(formatted_data)
            data_scrubbed = data_gatherer.main()
            data_scrubbed_oncall = data_gatherer.main(True)

            users_scrubbed, branches_scrubbed = self._process_data_gatherer(
                data_gatherer
            )

            count = 10
            data_range = {"min": 1, "max": 100}
            result = [
                {
                    "name": "Jan",
                    "data": self._generate_sample_data(20, {"min": -30, "max": 55}),
                },
                {
                    "name": "Feb",
                    "data": self._generate_sample_data(20, {"min": -30, "max": 55}),
                },
            ]

            return self._success_response(
                {
                    "data_before": data_scrubbed,
                    "data_after": data_scrubbed_oncall,
                    "branches": branches_scrubbed,
                    "users": users_scrubbed,
                    "startDate": formatted_data["start_date"],
                    "endDate": formatted_data["end_date"],
                }
            )
        except Exception as e:
            traceback.print_exc()
            return self._error_response()

    def _process_data_gatherer(self, data_gatherer):
        users_scrubbed = {
            x["id"]: {
                "name": x["name"],
                "branches": x["branches"],
                "latitude": x["latitude"],
                "longitude": x["longitude"],
            }
            for x in data_gatherer.users
        }

        branches_scrubbed = {
            key: {
                "name": value["name"],
                "locationId": value["userId"],
                "employees": [],
                "clients": [],
                "locations": [],
                "latitude": None,
                "longitude": None,
                "clientratio": None,
                "employeeratio": None,
            }
            for key, value in data_gatherer.branches.items()
        }

        location_ids = [
            value["userId"]
            for key, value in data_gatherer.branches.items()
            if value["userId"]
        ]
        location_coordinates = data_gatherer.some_data.get_coordinates(
            "|".join(location_ids)
        )

        for key, value in branches_scrubbed.items():
            location_id = value["locationId"]
            if location_id:
                location_info = location_coordinates.get(location_id, {})
                value.update(
                    {
                        "latitude": location_info.get("latitude"),
                        "longitude": location_info.get("longitude"),
                        "clientratio": location_info.get("clientratio"),
                        "employeeratio": location_info.get("employeeratio"),
                    }
                )

        for user in data_gatherer.users:
            for branch_actual in user["branches"]:
                for branch in data_gatherer.branch_structure[branch_actual]:
                    if branch in branches_scrubbed.keys():
                        for role in user["roles"]:
                            if role == "Employee":
                                branches_scrubbed[branch].setdefault(
                                    "employees", []
                                ).append(user["id"])
                            elif role == "Client":
                                branches_scrubbed[branch].setdefault(
                                    "clients", []
                                ).append(user["id"])
                            elif role == "Location":
                                branches_scrubbed[branch].setdefault(
                                    "locations", []
                                ).append(user["id"])

        return users_scrubbed, branches_scrubbed

    def _generate_sample_data(self, count: int, data_range):
        data = []
        min_val, max_val = data_range["min"], data_range["max"]
        for hour in range(8, 19):
            for minute in range(0, 46, 15):
                am_pm = "PM" if hour >= 12 else "AM"
                formatted_hour = hour - 12 if hour > 12 else hour
                time = f"{formatted_hour}:{str(minute).zfill(2)} {am_pm}"
                value = random.randint(min_val, max_val)
                data.append({"x": time, "y": random.randint(1, count), "value": value})
        return data

    def solution_generator(self, event):
        try:
            body = event["body"]
            body_dict = json.loads(body)
            data = body_dict.get("data", {})
            # tenant_id = event["headers"].get("X-Tenant-Id")
            tenant_id = event["headers"].get("x-tenant-id")
            print("fommer", tenant_id)
            data["header"]["X-Tenant-Id"] = tenant_id
            print("fommer2", data["header"])
            print("fommer3", event)
            res_body = runSolutionGenerator(data)
            return self._success_response(res_body)
        except Exception as e:
            traceback.print_exc()
            return self._error_response()

    def test_insert(self, event):
        try:
            print("gimmy!")
            body = json.loads(event["body"])
            # print('mybody',body)
            body = {**body, **body["data"]}
            # print("this_body",body)
            result = insert_handler(body, None)
            return result
        except Exception as e:
            return {"error": str(e)}, 500

    def optimzer(self, event):
        body = event["body"]
        parsed_data = json.loads(body)
        data = parsed_data.get("data", {})
        # tenant_id = event["headers"].get("X-Tenant-Id")
        tenant_id = event["headers"].get("x-tenant-id")
        data["header"]["X-Tenant-ID"] = tenant_id
        converted_data = data_converter(data)

        converted_data["part1_new"] = copy.copy(converted_data.get("part1", []))
        converted_data["objectiveactivity"] = converted_data.get(
            "activitiesRanking", []
        )
        converted_data["mode"] = converted_data.get("mode", "fast")
        converted_data["expanded_resources"] = converted_data.get(
            "activitiesRanking", []
        )

        try:
            start_date = datetime.datetime.strptime(
                converted_data["start_date"], "%Y-%m-%d"
            )
            end_date = datetime.datetime.strptime(
                converted_data["end_date"], "%Y-%m-%d"
            )
            if (end_date - start_date).days > 7:
                return {"status": "Day range should be less than or equal to 7 days"}
        except KeyError:
            return {"status": "Invalid date format or missing start_date/end_date"}

        if converted_data.get("is_lunch"):
            converted_data["expanded_resources"].append(converted_data.get("lunch_id"))
        if converted_data.get("is_break"):
            converted_data["expanded_resources"].append(converted_data.get("break_id"))

        if converted_data.get("analyzeMode"):
            analyzer = Analyzer(converted_data)
            final_data = analyzer.isNoGapRelatedIssues()
            result = runOptimizer(final_data)
        else:
            result = runOptimizer(converted_data)
        return json.dumps(result)

    def route_request(self, event):
        """Main routing function based on event path."""
        path = event["requestContext"]["http"]["path"]
        print("path_name5", path)
        print("event_name")

        if path == "/staff_equilibrium":
            return self.staff_equilibrium(event)
        elif path == "/staff_tracker":
            return self.staff_tracker(event)
        elif path == "/solution_generator":
            return self.solution_generator(event)
        elif path == "/optimzer":
            return self.optimzer(event)
        elif path == "/test_insert":
            print("event_name2")
            return self.test_insert(event)
        else:
            return self._success_response(
                {
                    "msg": f"Optimizer AWS Lambda Function is running successfully! backendURL: {self.backend_url}"
                }
            )
