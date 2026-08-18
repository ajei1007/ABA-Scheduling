import os
import datetime
import traceback
import random
import uuid
import math
import gc
import base64
import json
import copy
from core.shared.utils import *
from get_data import Get_Data
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
from core.shared.event_solver.insert_handler import insert_handler
from core.shared.event_solver.automate import Automate
import sys
import boto3
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# from utils.timing_utils import measure_time, visualize_timings


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0

    def OnSolutionCallback(self):
        self.__solution_count += 1
        for v in self.__variables:
            print("%s = %i" % (v, self.Value(v)), end=" ")

    def solution_count(self):
        return self.__solution_count


class Solver:
    def __init__(self, data):
        self.data = data
        self.events = []
        self.gap_filler = []
        self.event_possibly = []
        self.time_constraints = []
        self.resources = []
        self.roles_hierarchy = []
        self.distance_matrix = []
        self.event_pair = []
        self.actual_data = []
        self.solution1 = data["sol_1"]
        self.solution2 = data["sol_2"]
        self.orange_data = data["sol_3"]
        self.public_ip = data["public_ip"]
        self.time_since_server_started = data["time_since_server_started"]
        self.instance_id = data["instance_id"]
        self.availability = {}
        self.efficiency = {}
        self.efficiency_data = {}
        self.status_name = ""
        self.deleted_appointments_list = []
        self.best_bound = 0
        self.founded = 0
        self.response = {"default": None}
        self.created_events = []
        self.all_appointments = []
        self.creatingEvents = []
        self.deletingEvents = []
        self.updatingEvents = []
        self.max_total_hours = None
        self.deleted_hours = 0
        self.created_hours = 0
        self.overlaped_ids = []
        self.employees_ids = []
        self.availability_person = {}
        self.date_original = None
        self.start_date_original = None
        self.loc_id_2 = None
        self.admin_id = None
        self.excluded_events = []
        self.auth_week = None
        self.admin_filler = []
        self.objective_value = 0
        self.disabled_constraints = []
        self.aws_region = "us-east-1"
        self.launch_template_id = "launchOptimizeContainerREAL"
        self.flask_port = 80  # Change if your Flask app runs on a different port

    def rocket(self, dd):
        self.data = dd
        data = self.data

        d1 = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d")
        d2 = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d")
        num_of_days = (d1 - d2).days + 1

        d = {"num_of_days": num_of_days}
        d.update(data)

        start = d2.strftime("%Y-%m-%d")
        end = (d2 + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        host, branch, header = data["host"], data["branch"], data["header"]

        stat = availabilities(host, header, start, end, branch)
        availabilities_for_fake_white_sol = {}
        for i_dict in stat[2]:
            res_id = i_dict["resourceIds"][0]
            avail_data = {"start": i_dict["start"], "end": i_dict["end"]}
            availabilities_for_fake_white_sol.setdefault(res_id, []).append(avail_data)

        self.availability.update(stat[0])
        self.data.update({"max_hours": stat[0]})
        self.efficiency = stat[1]

        some_data = Get_Data(d)
        self.resources = some_data.res()
        self.auth_week = some_data.get_events3()[1]
        self.data.update({"auth_week": self.auth_week})

        self.data["admin_id"] = "admin_id123"
        print("admin_now2")
        for ss_res in self.resources:
            if "Admin" in ss_res["name"] and "admin_id" in self.data:
                self.admin_id = ss_res["id"]
                self.data["admin_id"] = self.admin_id
                print("admin_now")

        self.data["notWorking"] = some_data.get_notWorking()

        employee_ids, persons_ids, client_ids = [], [], []
        print("lockerr6", self.solution1.events2)
        arr_of_overlap_allowed = [i["id"] for i in self.solution1.users if i["overlap"]]

        for resource in self.resources:
            roles = resource["roles"]
            if "Employee" in roles:
                employee_ids.append(resource["id"])
            if "Person" in roles:
                persons_ids.append(resource["id"])
            if "Client" in roles:
                client_ids.append(resource["id"])

        people_ids23 = {"employee_ids": employee_ids, "client_ids": client_ids}
        self.max_total_hours = max_possible_total_hours(stat[2], people_ids23, 15)

        scheduled_events = self.solution1.events2 + self.data["new_created_events"]
        print("lockerr5", self.solution1.events2)
        try:
            ev_dd = [
                e
                for e in scheduled_events
                if not intersection(e["resourceIds"], arr_of_overlap_allowed)
            ]

            ev_admin = [e for e in ev_dd if self.admin_id in e["resourceIds"]]
            # ev_dd = [e for e in ev_dd if self.admin_id not in e["resourceIds"]]
            # ev_dd = [e for e in ev_dd if self.admin_id not in e["resourceIds"]]

            # for event in ev_admin:
            #     event["type"] = "delete"
            #     self.deletingEvents.append(event)

            self.excluded_events.extend(
                [
                    e
                    for e in ev_dd
                    if not intersection(
                        self.data["objectiveactivity"], e["resourceIds"]
                    )
                ]
            )
            print("lockerr7", self.solution1.events2)

            # no_overlap_events = events_overlap(ev_dd, self.resources)
            print("lockerr8", self.solution1.events2)
            # self.events = no_overlap_events[0]
            self.events = self.solution1.events2
        except Exception as e:
            traceback.print_exc()
        print("lockerr4", self.solution1.events2)

        # fake_user_starts_ends = no_overlap_events[1]
        fake_user_starts_ends = {}
        self.data.update(
            {
                "fake_user_starts_ends": fake_user_starts_ends,
                # "clients_events_fake": no_overlap_events[2],
                "clients_events_fake": [],
                "weekly_events_data": weekly_events(scheduled_events, self.resources),
            }
        )

        # for person_id in persons_ids:
        #     self.excluded_events.extend(fake_user_starts_ends[person_id]["fakes"])

        self.gap_filler = []
        arr_poss = []
        combined_events = random.sample(
            self.solution1.events_poss, len(self.solution1.events_poss)
        ) + random.sample(self.orange_data, len(self.orange_data))

        for event in combined_events:
            arr_poss.append(event)

        self.event_possibly = arr_poss

        print("lockerr3", self.solution1.events2)
        if len(data["teams"]) <= 1:
            data["teams"] = get_groups_array(self.solution1, 20, persons_ids, arr_poss)

        # Gets rid of week events
        # event_arr = [
        #     i for i in self.events if str(data["start_date"]) == i["start"][:10]
        # ]
        # Gets rid of week events

        # Whole Week
        print("lockerr2", self.solution1.events2)
        event_arr = [i for i in self.events]
        # Whole Week
        print("event_arr", event_arr)

        arr_poss.extend(event_arr)

        self.data.update({"gg": []})
        self.roles_hierarchy = some_data.get_roles_hierarchy()
        self.distance_matrix = some_data.get_distance_matrix()
        self.event_pair = []  # Placeholder for event pair data

        self.actual_data = [self.event_possibly]
        if not data["daily"]:
            print(f"Not daily running")
            actual_data = sum(self.actual_data, [])
            self.actual_data = actual_data
            params = {
                "start_date": data["start_date"],
                "day_increment": num_of_days,
                "actual_data": actual_data,
            }
            cc = self.test_runner(params)
            if cc:
                self.solution1.created_events.extend(cc["created_events"])
            return cc
        else:
            print(f"Daily running")
            some_array = []
            sd = data["start_date"]
            for daily_data in self.actual_data:
                params = {
                    "start_date": sd,
                    "day_increment": 1,
                    "actual_data": daily_data,
                }
                some_array.append(params)
                sd = (
                    datetime.datetime.strptime(sd, "%Y-%m-%d")
                    + datetime.timedelta(days=1)
                ).strftime("%Y-%m-%d")

            if data["is_Multi"]:
                print(f"Running with multi-threading for test")
                with ThreadPoolExecutor() as executor:
                    results = list(executor.map(self.test_runner, some_array))
            else:
                for params in some_array:
                    cc = self.test_runner(params)
                    if cc:
                        self.solution1.created_events.extend(cc["created_events"])
                    return cc

    def prepare_test_insert_payload(self, data):
        try:
            required_data_keys = {
                "objective_role",
                "objectiveactivity",
                "mode",
                "run_with_teams",
                "is_lunch_constraint",
                "maxEmployeeHoursPerDay",
                "notWorking",
                "slot_length",
                "percentage",
                "companyId",
                "max_time_in_seconds",
                "workers",
                "fake_user_starts_ends",
                "gg",
                "start_date",
                "end_date",
                "drive_id",
                "part1",
                "nonbillable",
                "lunch_id",
                "settings",
                "admin_id",
                "host",
                "today_index",
                "header",
                "weekly_events_data",
                "highPriority",
                "hard",
                "weekdays_av_data",
                "auth_week",
                "is_overlap_constraint",
                "start_date",
                "end_date",
            }

            for user in self.solution1.users:
                user.pop("branches_real", None)

            filtered_data = {
                key: self.data[key] for key in required_data_keys if key in self.data
            }

            if "fake_user_starts_ends" in filtered_data:
                filtered_data["fake_user_starts_ends"] = serialize_instance(
                    filtered_data["fake_user_starts_ends"]
                )

            branches = {
                k: {"drivetime": v.get("drivetime", None)}
                for k, v in self.solution1.branches.items()
            }

            print("self.solution1.events2", self.solution1.events2)
            solution1_filtered = {
                "events2": self.solution1.events2,
                "users": self.solution1.users,
                "created_events": self.solution1.created_events,
                "user_availabilities_general": self.solution1.user_availabilities_general,
                "resources1": {
                    "frequency_constraints": serialize_instance(
                        self.solution1.resources1.frequency_constraints
                    ),
                    "resources": serialize_instance(
                        self.solution1.resources1.resources
                    ),
                },
                "user_uuid_to_index": self.solution1.user_uuid_to_index,
                "branches": branches,
                "flags": serialize_instance(self.solution1.flags),
                "events_poss": self.solution1.events_poss,
            }
            constraint_drive_data = get_drive_time_data(
                self.data["header"], self.data["host"]
            )

            constraint_drive_data = serialize_instance(constraint_drive_data)

            payload = {
                "start_date_original": serialize_instance(data["start_date_original"]),
                "resources_team": data["resources_team"],
                "data": filtered_data,
                "constraint_drive_data": constraint_drive_data,
                "date_original": data["date_original"],
                "data2_team": data["data2_team"],
                "aut_arr": data["aut_arr"],
                "overlaped_ids": self.overlaped_ids,
                "resources": self.resources,
                "roles_hierarchy": self.roles_hierarchy,
                "distance_matrix": self.distance_matrix,
                "solution1": solution1_filtered,
                "efficiency": copy.deepcopy(self.efficiency),
                "employees_ids": self.employees_ids,
                "availability_person": copy.deepcopy(self.availability_person),
                "creatingEvents": self.creatingEvents,
                "created_events": self.created_events,
                "deletingEvents": self.deletingEvents,
                "deleted_appointments_list": self.deleted_appointments_list,
                "created_hours": self.created_hours,
            }
            return payload
        except Exception as e:
            print(f"Unexpected error in prepare_test_insert_payload: {e}")

    def update_from_test_insert_response(self, response_data):
        self.employees_ids = response_data.get("employees_ids", [])
        self.availability_person = response_data.get("availability_person", [])

        if "efficiency" in response_data and response_data["efficiency"] is not None:
            for key, value in response_data["efficiency"].items():
                if key in self.efficiency_data:
                    if value != 0:
                        self.efficiency_data[key] = value
                else:
                    self.efficiency_data[key] = value

        deleting_events = response_data.get("deletingEvents", [])
        if deleting_events:
            self.deletingEvents.extend(deleting_events)

        all_appointments = response_data.get("all_appointments", [])
        if all_appointments:
            self.all_appointments.extend(all_appointments)

        updatingEvents = response_data.get("updatingEvents", [])
        if updatingEvents:
            self.updatingEvents.extend(updatingEvents)

        creatingEvents = response_data.get("creatingEvents", [])
        if creatingEvents:
            self.creatingEvents.extend(creatingEvents)

        created_events = response_data.get("created_events", [])
        if created_events:
            self.created_events.extend(created_events)

        disabled_constraints = response_data.get("disabled_constraints", [])
        if disabled_constraints:
            self.disabled_constraints.extend(disabled_constraints)

        deleted_appointments_list = response_data.get("deleted_appointments_list", [])
        if deleted_appointments_list:
            self.deleted_appointments_list.extend(deleted_appointments_list)

        self.loc_id_2 = response_data.get("loc_id_2", None)
        self.created_hours = response_data.get("created_hours", 0)
        self.objective_value = response_data.get("objective_value", 0)
        self.deleted_hours = response_data.get("deleted_hours", 0)
        self.best_bound = response_data.get("best_bound", 0)
        self.status_name = response_data.get("status_name", "")
        self.founded = response_data.get("founded", 0)

    def get_payload_size(self, payload):
        payload_json = json.dumps(payload)
        return sys.getsizeof(payload_json)

    def wait_for_instance_ready(self, instance_id):
        ec2 = boto3.client("ec2", region_name=self.aws_region)

        print("Waiting for instance to be in 'running' state...")
        waiter = ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])

        print("Instance is running. Fetching public IP...")
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        public_ip = desc["Reservations"][0]["Instances"][0]["PublicIpAddress"]
        print(f"Public IP: {public_ip}")
        return public_ip

    # def wait_for_flask_ready(self, url, timeout_seconds=120):
    #     elapsed = (
    #         datetime.datetime.now() - self.time_since_server_started
    #     ).total_seconds()
    #     time_seconds = math.floor(elapsed)

    #     print("time_seconds2", time_seconds)

    #     remaining = 45 - time_seconds
    #     if remaining > 0:
    #         print("time_seconds", remaining)
    #         time.sleep(remaining)
    #     session = requests.Session()
    #     retry = Retry(total=10, backoff_factor=2, status_forcelist=[502, 503, 504])
    #     session.mount("http://", HTTPAdapter(max_retries=retry))

    #     print(f"Waiting for Flask to be ready at {url}...")
    #     start = time.time()
    #     while True:
    #         try:
    #             resp = session.get(url, timeout=5)
    #             if resp.status_code == 200 or resp.status_code == 400:
    #                 print("Flask app is ready.")
    #                 return resp.text
    #         except requests.exceptions.RequestException:
    #             pass

    #         if time.time() - start > timeout_seconds:
    #             raise TimeoutError("Flask app did not become ready in time.")
    #         time.sleep(5)
    def wait_for_flask_ready(self, url, timeout_seconds=120):
        from datetime import datetime
        import time, math, requests

        # Optional: initial grace period (your existing 45-second logic)
        elapsed = (datetime.now() - self.time_since_server_started).total_seconds()
        remaining = 45 - math.floor(elapsed)
        if False and remaining > 0:
            time.sleep(remaining)

        session = requests.Session()
        retry_interval = 1  # ← one-second polling
        max_retries = timeout_seconds // retry_interval

        print(f"Waiting for Flask at {url} (retry every {retry_interval}s)…")
        start = time.time()

        for attempt in range(max_retries):
            try:
                resp = session.get(url, timeout=3)
                if resp.status_code in (200, 400):
                    print("Flask app is ready.")
                    return resp.text
            except requests.exceptions.RequestException as e:
                # Optional: log the exception for debugging
                # print(f"Attempt {attempt+1}: {e}")
                pass

            if time.time() - start > timeout_seconds:
                raise TimeoutError("Flask app did not become ready in time.")
            time.sleep(retry_interval)

    def terminate_instance(self, instance_id):
        ec2 = boto3.client("ec2", region_name=self.aws_region)
        print(f"Terminating instance {instance_id}...")
        ec2.terminate_instances(InstanceIds=[instance_id])

    # EC2 instance
    # production
    def run_test_insert(self, data):
        flask_url = f"http://{self.public_ip}/optimizer/test_insert"
        print("flask_url:", flask_url)
        # time.sleep(15)
        try:
            ##production
            response_body = self.wait_for_flask_ready(flask_url)
            print("Flask response:", response_body)
            ##production
            pass
        except Exception as e:
            print("Error waiting for Flask:", e)
        # finally:
        #     self.terminate_instance(self.instance_id)

        try:
            url = f"http://{self.public_ip}/optimizer/test_insert"
            payload = self.prepare_test_insert_payload(data)
            payload_size = self.get_payload_size(payload)
            print(f"Payload size: {payload_size} bytes")

            start_lambda = time.time()
            print("test ec2")
            print("payload load", payload)
            response = requests.post(url, json=payload)
            print("phony", response)
            print("response of the ec2:", response.json())
            ##production
            self.terminate_instance(self.instance_id)
            ##production
            print(f"Lambda running time: {time.time() - start_lambda:.2f}s")

            if response.status_code == 200:
                response_data = response.json()
                self.update_from_test_insert_response(response_data)
                return {
                    "returned_arr": response_data.get("returned_arr", []),
                    "objective_value": response_data.get("objective_value", 0),
                    "status": response_data.get("status", "status"),
                    "created_events": self.created_events,
                }
            else:
                print(f"Error: {response.status_code}, {response.text}")
        except requests.exceptions.RequestException as req_err:
            print("❌ Request failed:", req_err)
            traceback.print_exc()
        except Exception as e:
            print("❌ Unexpected error:", str(e))
            traceback.print_exc()

    # EC2 instance
    # production

    # def run_test_insert(self, data):
    #     url = f'http://{self.public_ip}/optimizer/test_insert'
    #     url_retry = "https://mdufhhkao3dzgj2byycz3sal7a0fzhfb.lambda-url.us-east-1.on.aws/"

    #     try:
    #         print("Trying Lambda warm-up URL...")
    #         response = requests.get(url_retry)
    #         print("Lambda warm-up response:", response.status_code)

    #         payload = self.prepare_test_insert_payload(data)
    #         payload_size = self.get_payload_size(payload)
    #         print(f"Payload size: {payload_size} bytes")

    #         print("Sending payload to EC2 Flask endpoint...")
    #         start_lambda = time.time()
    #         response = requests.post(url, json=payload)
    #         print(f"Lambda running time: {time.time() - start_lambda:.2f}s")

    #         response.raise_for_status()  # Raises HTTPError if status is 4xx or 5xx

    #         response_data = response.json()
    #         print("Response from Flask:", response_data)

    #         self.update_from_test_insert_response(response_data)
    #         return {
    #             "returned_arr": response_data.get("returned_arr", []),
    #             "objective_value": response_data.get("objective_value", 0),
    #             "status": response_data.get("status", "status"),
    #             "created_events": self.created_events,
    #         }

    #     except requests.exceptions.RequestException as req_err:
    #         print("❌ Request failed:", req_err)
    #         traceback.print_exc()
    #     except Exception as e:
    #         print("❌ Unexpected error:", str(e))
    #         traceback.print_exc()

    # #USES LAMBDA
    # def run_test_insert(self, data):
    #     url = "http://3.236.23.116/test_insert"
    #     url = "https://csfo3el5yrxkrrvdehxh4t2whu0uwwqo.lambda-url.us-east-1.on.aws/test_insert"
    #     payload = self.prepare_test_insert_payload(data)

    #     payload_size = self.get_payload_size(payload)
    #     print(f"Payload size: {payload_size} bytes")
    #     start_lambda = time.time()
    #     response = requests.post(url, json=payload)
    #     print("response of the lambda:", response.json())
    #     print(f"Lambda running time: {time.time() - start_lambda}")

    #     if response.status_code == 200:
    #         response_data = response.json()
    #         self.update_from_test_insert_response(response_data)
    #         return {
    #             "returned_arr": response_data.get("returned_arr", []),
    #             "objective_value": response_data.get("objective_value", 0),
    #             "status": response_data.get("status", "status"),
    #             "created_events": self.created_events,
    #         }
    #     else:
    #         print(f"Error: {response.status_code}, {response.text}")

    # #USES LAMBDA

    ##USES LOCAL
    # def run_test_insert(self, data):
    #     payload = self.prepare_test_insert_payload(data)

    #     payload_size = self.get_payload_size(payload)
    #     print(f"Payload size: {payload_size} bytes")
    #     start_time = time.time()
    #     response = insert_handler(payload, None)
    #     print(f"Test insert handler running time: {time.time() - start_time}")
    #     print("response of the lambda:", response)
    #     if response["statusCode"] == 200:
    #         print("something3")
    #         response_data = response["body"]
    #         self.update_from_test_insert_response(response_data)
    #         return {
    #             "returned_arr": response_data.get("returned_arr", []),
    #             "objective_value": response_data.get("objective_value", 0),
    #             "status": response_data.get("status", "status"),
    #             "created_events": self.created_events,
    #         }
    #     else:
    #         print(f"Error: {response['statusCode']}, {response['body']}")

    ##USES LOCAL

    def test_runner(self, testing_data):
        aut_arr = []
        date_original = testing_data["start_date"]
        print('testing_data["actual_data"]', testing_data["actual_data"])
        start_date_original = datetime.datetime.strptime(date_original, "%Y-%m-%d")
        self.date_original = date_original
        self.start_date_original = start_date_original
        print("googlew", self.solution1.events2)
        if self.data["run_with_teams"]:
            some_arr_of_data = []
            children_branches = []
            for b_id, value in self.solution1.branches.items():
                if value["parentId"] == self.solution1.branch_id:
                    children_branches.append(b_id)
            if len(children_branches) == 0:
                self.data["teams"] = [self.solution1.branch_id]
            else:
                self.data["teams"] = children_branches
            team_index = 0
            for team in self.data["teams"]:
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                true_team = [i[:-1] for i in team]
                for res in self.resources:
                    if "Person" not in res["roles"] or team in res["branches"]:
                        resources_team.append(res)
                for res in self.resources:
                    if "Person" in res["roles"] and team in res["branches"]:
                        resource_id_team.append(f'{res["id"]}a')
                        resource_id_team.append(f'{res["id"]}')
                    if "Person" in res["roles"] and team not in res["branches"]:
                        resource_id_team_not.append(f'{res["id"]}a')
                        resource_id_team_not.append(f'{res["id"]}')
                for dat in testing_data["actual_data"]:
                    if (
                        not dat["scheduled"]
                        and len(intersection(dat["resourceIds"], resource_id_team_not))
                        == 0
                    ):
                        data2_team.append(dat)
                    elif (
                        dat["scheduled"]
                        and len(intersection(dat["resourceIds"], resource_id_team)) > 0
                    ):
                        data2_team.append(dat)

                self.data.update({"true_team": true_team})
                d = {
                    "objectiveactivity": self.data["objectiveactivity"],
                    "mode": self.data["mode"],
                    "start_date_original": start_date_original,
                    "resources_team": resources_team,
                    "data": self.data,
                    "date_original": date_original,
                    "data2_team": data2_team,
                    "aut_arr": [team_index],
                }
                team_index += 1
                some_arr_of_data.append(d)
            with ThreadPoolExecutor() as executor:
                results = executor.map(self.run_test_insert, some_arr_of_data)
        else:
            print("Run without teams")
            for team in range(1):
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                scheduled_ids = []
                k = []
                for res in self.resources:
                    if "Person" not in res["roles"] or True:
                        resources_team.append(res)
                for res in self.resources:
                    if "Person" in res["roles"] and True:
                        resource_id_team.append(f'{res["id"]}a')
                        resource_id_team.append(f'{res["id"]}')
                    if "Person" in res["roles"] and True:
                        resource_id_team_not.append(f'{res["id"]}a')
                        resource_id_team_not.append(f'{res["id"]}')
                for dat in testing_data["actual_data"]:
                    # if dat["new_start"] == testing_data["start_date"]:
                    data2_team.append(dat)
                d = {
                    "objectiveactivity": self.data["objectiveactivity"],
                    "mode": self.data["mode"],
                    "start_date_original": start_date_original,
                    "resources_team": resources_team,
                    "data": self.data,
                    "date_original": date_original,
                    "data2_team": data2_team,
                    "aut_arr": aut_arr,
                }
                return self.run_test_insert(d)

    def add_admin(self):
        print("self.admin_id2", self.admin_id)
        if not self.admin_id is None and (
            self.admin_id == "661650b0-c24a-4234-a0ab-1e7c879dfc0c"
            or self.admin_id == "bfa0101d-5d9c-465b-905d-3bab7db276b9"
            or self.admin_id == "32ec7c49-bed9-4fee-b2e3-feeb1d21aa89"
        ):
            print("in here3")
            update_events_ids = [i["id"] for i in self.updatingEvents]
            not_include_ids = update_events_ids + self.deleted_appointments_list
            allEvents = (
                self.creatingEvents
                + self.updatingEvents
                + self.excluded_events
                + [i for i in self.events if not i["id"] in not_include_ids]
            )
            allEvents_dict = {}
            for _id in self.employees_ids:
                allEvents_dict[_id] = []
            weekday_all = 0
            for _event in allEvents:
                inter_emp = intersection(_event["resourceIds"], self.employees_ids)
                if len(inter_emp) > 0:
                    s_times = time_to_int(_event, self.data["slot_length"])
                    start_time = s_times[0]
                    end_time = s_times[2]
                    weekday = s_times[3]
                    weekday_all = weekday
                    for emp in inter_emp:
                        allEvents_dict[emp] += list(range(start_time, end_time))
            admin_filler_data = []
            weekday_all = int(weekday_all) - 1
            adjust = 24 * 60 // self.data["slot_length"]
            for i, v in allEvents_dict.items():
                all_int_av = []
                for x in self.availability_person[i].get(int(weekday_all), []):
                    all_int_av += list(range(x[0] + adjust, x[1] + adjust))
                set_v = set(v)
                print("geemer1", set_v)
                print("geemer2", all_int_av)
                print("geemer3")
                if not set_v:  # ← set is empty → skip to next iteration
                    continue
                lo, hi = min(set_v), max(set_v)
                ddd = [z for z in all_int_av if z not in set_v and lo <= z <= hi]
                ranges = detect_range2(ddd)
                for rang in ranges:
                    start = slot_to_time(rang[0], self.data["slot_length"])
                    end = slot_to_time(rang[1], self.data["slot_length"])
                    start_date_original = datetime.datetime.strptime(
                        self.date_original, "%Y-%m-%d"
                    )
                    start_day = (
                        math.floor(rang[0] / (24 * 60 // self.data["slot_length"]))
                        - datetime.datetime.strptime(
                            self.date_original, "%Y-%m-%d"
                        ).weekday()
                        - 1
                    )
                    new_start = datetime.datetime.strftime(
                        start_date_original + datetime.timedelta(days=start_day),
                        "%Y-%m-%d",
                    )
                    new_end = datetime.datetime.strftime(
                        start_date_original + datetime.timedelta(days=start_day + 1),
                        "%Y-%m-%d",
                    )
                    fake_admin = object_for_return(
                        new_start,
                        new_end,
                        start,
                        end,
                        [i],
                        self.admin_id,
                        self.loc_id_2,
                        "fake adress",
                        self.data["start_date"],
                        self.data["end_date"],
                    )
                    admin_filler_data.append(fake_admin["data"])

            self.admin_filler = admin_filler_data
            self.creatingEvents = [*self.creatingEvents, *self.admin_filler]

    def part_one(self):
        dd = self.data
        self.rocket(dd)
        # self.add_admin()
        c = {
            "creatingEvents": self.creatingEvents,
            "deletingEvents": self.deletingEvents,
            "updatingEvents": self.updatingEvents,
            "obj_value": self.objective_value,
            "max_total_hours": self.max_total_hours,
            "status_name": self.status_name,
            "created_hours": self.created_hours,
            "deleted_hours": self.deleted_hours,
            "efficiency": self.efficiency_data,
            "disabled_constraints": self.disabled_constraints,
            "deleted_appointments_list": self.deleted_appointments_list,
        }

        return c

    def part_two(self):
        dd = self.data
        self.rocket(dd)
        # self.add_admin()
        c = {
            "creatingEvents": self.creatingEvents,
            "deletingEvents": self.deletingEvents,
            "updatingEvents": self.updatingEvents,
            "obj_value": self.objective_value,
            "status_name": self.status_name,
            "created_hours": self.created_hours,
            "deleted_hours": self.deleted_hours,
            "efficiency": self.efficiency_data,
            "max_total_hours": self.max_total_hours,
            "disabled_constraints": self.disabled_constraints,
            "deleted_appointments_list": self.deleted_appointments_list,
        }
        return c

    def run(self):
        pass
