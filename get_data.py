import logging
import http.client
import requests
import datetime
import time
import urllib.parse
import re
import json
import pytz
from external import convert_date_to_timezone
from collections import defaultdict

http.client.HTTPConnection.debuglevel = 1

# You must initialize logging, otherwise you'll not see debug output.
logging.basicConfig()
logging.getLogger().setLevel(logging.WARNING)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.WARNING)
requests_log.propagate = False

# print(randrange(3,10))
# data = mock_data.poss_events["poss_events"]
# resources = mock_data.resources

day_ids = {
    0: "20770718-a98e-499f-ae8b-c395f0f743bb",
    1: "2d0599e7-2729-49ee-acbe-ede6de8ad9b7",
    2: "3260c7e7-c57b-4144-803f-7db9cf88393c",
    3: "56cbe76a-0cf6-4647-8a49-2ef9fd102079",
    4: "6d92706c-9bb1-447e-bf74-572609066663",
    5: "ecd70b60-3fef-4d43-9181-2f9db60e19fe",
    6: "fa2adb44-e5ba-4586-ae19-5f1e1767228d",
}

resource_ids = {}

# Action
# branch = '1ca63c9a-4926-40e4-a2e5-16c580fa82de'

session = requests.Session()


def convert_timezone(input_datetime_str, target_offset):
    # Parse input datetime string
    if input_datetime_str.endswith("Z"):
        return input_datetime_str
    dt = datetime.datetime.fromisoformat(input_datetime_str)

    # Extract original offset from the input string
    original_offset_hours = int(input_datetime_str[-6:-3])

    # Calculate the difference in offsets
    offset_diff = target_offset - original_offset_hours

    # Adjust the datetime with the offset difference
    dt += datetime.timedelta(hours=offset_diff)

    # Convert to ISO 8601 format with 'Z' at the end

    return dt.replace(tzinfo=None).isoformat() + ".000Z"


class Get_Data:
    def __init__(self, data):
        # print(data)
        self.header = data["header"]
        self.start_date = data["start_date"]
        self.end_date = data["end_date"]
        self.branches_id = data["branch"]
        self.sandboxMode = data["sandboxMode"] if "sandboxMode" in data else False
        self.direct_activity_id = data["objectiveactivity"]
        self.lunch_activity_id = data["lunch_id"]
        # self.supervision_activity_id = data['supervision_activity_id']
        self.break_activity_id = data["break_id"]
        self.num_of_days = data["num_of_days"]
        self.blocks = data["blocks"]
        self.isolatedResources = (
            data["isolatedResources"] if "isolatedResources" in data else []
        )
        self.is_lunch = data["is_lunch"]
        self.is_break = data["is_break"]
        self.settings = data["settings"]
        self.high_priority = data["highPriority"]
        self.orange = data["is_orange"]
        self.events = data["is_events"]
        self.host = data["host"]
        self.investigate = data["investigate"] if "investigate" in data else []
        self.notWorking = []

        self.resources = []
        self.activities = ""
        if "activities" in data.keys():
            self.activities = "|".join(data["activities"])

    def get_roles_hierarchy(self):
        response = requests.get(
            f"{self.host}/scheduler/roles_hierarchy", headers=self.header
        )
        return response.json()

    def get_distance_matrix(self):
        response = requests.get(
            f"{self.host}/scheduler/get_distance_matrix", headers=self.header
        )
        return response.json()

    def get_daysOfWeek(self):
        response = requests.get(
            f"{self.host}/scheduler/daysOfWeek", headers=self.header
        )
        res = {}
        data = response.json()
        for i in range(7):
            res[i] = data[i]["value"]
        return res

    def get_coordinates(self, userIds=""):
        response = requests.get(
            f"{self.host}/users/coordinates?userIds={userIds}", headers=self.header
        )
        res = {}
        data = response.json()
        return data

    def get_branches(self):
        time1 = time.time()
        response = requests.get(f"{self.host}/branches/optimizer", headers=self.header)
        obj = {}
        for b in response.json()["rows"]:
            obj[b["id"]] = b
        time2 = time.time()
        return obj

    def get_event_future(self, events, high_priority_str):
        time1 = time.time()
        response = []
        data = []
        if len(events) > 0:
            response = requests.post(
                f"{self.host}/events/eventfuture/constraints",
                headers=self.header,
                json={"events": events, "highPriority": high_priority_str},
            )
            data = response.json()
        time2 = time.time()
        print("get_event_future:", time2 - time1)

        return data

    def get_activity_table(self):
        time1 = time.time()
        timezone_str = self.settings["timezone"]
        start_date = datetime.datetime.strptime(self.start_date, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(self.end_date, "%Y-%m-%d")
        timezone = pytz.timezone(timezone_str)
        start_date = timezone.localize(start_date).isoformat()
        end_date = timezone.localize(end_date).isoformat()
        # print('sifter',timezone,start_date,end_date)
        response = requests.get(
            f"{self.host}/events/activity-table/statistics-activity-table?start={start_date}&end={end_date}&branches={self.branches_id}",
            headers=self.header,
        )
        obj = {}
        data = response.json()["rows"]
        time2 = time.time()
        # print('Timer get_activity_table_time: ',data, time2 - time1)
        return data

    def get_events_branch_activity(self):
        time1 = time.time()
        response = requests.post(
            f"{self.host}/scheduler/events/staff-track?start={self.start_date}&end={self.end_date}&branches={self.branches_id}&activities={self.activities}",
            headers=self.header,
        )
        time2 = time.time()

        # print('Timer events_branch_activity_time: ', time2 - time1)

        act_ar = []

        for item in response.json():
            date_string = item["start_real"]
            date_object = datetime.datetime.strptime(
                date_string, "%Y-%m-%dT%H:%M:%S.%fZ"
            )

            new_date = date_object + datetime.timedelta(
                seconds=item["duration"]["seconds"]
            )
            new_date_string = new_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            a = {
                "id": item["id"],
                "resourceIds": item["resourceIds"],
                "title": item["title"],
                # "canceledId": item["canceledId"],
                "address": item["address"],
                "reasons": [],
                "people_drive_times": {"start": {}, "end": {}},
                "distances_all": [],
                "times_all": [],
                "reasons_l": "",
                "priority": "",
                "duration": item["duration"]["seconds"],
                "start": item["start_real"],
                "end_real_time": item["end_real_time"],
                "end": new_date_string,
                "scheduled": True,
                "loc_id": item["location0Id"],
                "orange_sol": False,
            }
            # print('gap_2 : ', a)
            if True:
                act_ar.append(a)
        return act_ar

    def get_availability(self):
        time1 = time.time()
        date_obj = datetime.datetime.strptime(
            self.start_date, "%Y-%m-%d"
        )  # to datetime
        next_day_obj = date_obj + datetime.timedelta(days=1)  # add one day
        next_day_str = next_day_obj.strftime("%Y-%m-%d")  # back to string
        end_date = next_day_str if self.num_of_days <= 1 else self.end_date
        # end_date = self.end_date
        print("goobler", self.end_date)
        time1 = time.time()
        response = requests.get(
            f"{self.host}/scheduler/availabilities?start={self.start_date}&end={end_date}&branches={self.branches_id}",
            headers=self.header,
        )
        time2 = time.time()
        # print(
        #     'doofer',
        #     self.host,
        #     response.json(),
        # )
        # print('Timer availabilty_time: ', time2 - time1)
        res_json = response.json()
        # for i in res_json:
        #     i["start"] = i["start"][:19]+"-01:00"
        #     i["end"] = i["end"][:19]+"-01:00"
        # print("bazo_cool_bug : ",res_json)
        return res_json

    def get_event_pair(self):
        time1 = time.time()
        response = requests.get(f"{self.host}/eventpair", headers=self.header)
        time2 = time.time()
        # print('Timer get_event_pair_time: ', time2 - time1)
        # print("aa_bazo : ",response.json()["rows"])
        return response.json()["rows"]

    def get_events2(self):
        time1 = time.time()
        self.num_of_days
        is_week = False if self.num_of_days <= 1 else True
        print("simmer4", is_week, self.num_of_days)
        e = self.get_events(False, is_week)
        # print('foopy',e)
        time2 = time.time()
        print("Timer get_events2_time: ", time2 - time1)
        return e

    def get_events3(self):
        time1 = time.time()
        e = self.get_events(False, True)
        time2 = time.time()
        # print('Timer get_events2_time: ', time2 - time1)
        return e

    def get_notWorking(self):
        return self.notWorking

    def get_events(self, locations_bol=False, full_week=False):
        time1 = time.time()
        branch = self.branches_id
        people = []
        time1 = time.time()
        resources = self.get_resources()
        time2 = time.time()
        print("Actual_resources: ", time2 - time1)
        role_types = ["Person"]
        locations = []
        if locations_bol:
            for i in resources:
                if "Location" in i["roles"]:
                    locations.append(i["id"])
        locations = "|".join(locations)
        for i in resources:
            # print("bazo_res2 : ",i)
            if i["notWorking"]:
                self.notWorking.append(i["id"])
            for role in role_types:

                if role in i["roles"]:
                    people.append(i["id"])
                    break
        act_arr = []
        start_date_original = datetime.datetime.strptime(self.start_date, "%Y-%m-%d")
        num_of_days = self.num_of_days
        if full_week:
            start_date_original = start_date_original - datetime.timedelta(
                days=start_date_original.weekday() + 1
            )
            for i in range(1):
                end_date = datetime.datetime.strftime(
                    start_date_original + datetime.timedelta(days=i + 7), "%Y-%m-%d"
                )
                start_date = datetime.datetime.strftime(
                    start_date_original + datetime.timedelta(days=i), "%Y-%m-%d"
                )
                ab = []
                response = requests.post(
                    f'{self.host}/scheduler/events?locations={locations}&start={str(start_date)}&end={str(end_date)}&branches={branch}&sandboxMode={"true" if self.sandboxMode else "false"}',
                    headers=self.header,
                    json={"people": "|".join(people)},
                )
                for item in response.json():
                    item["start_real"] = convert_timezone(item["start_real"], 0)
                    date_string = item["start_real"]
                    date_object = datetime.datetime.strptime(
                        date_string, "%Y-%m-%dT%H:%M:%S.%fZ"
                    )

                    new_date = date_object + datetime.timedelta(
                        seconds=item["duration"]["seconds"]
                    )
                    new_date_string = new_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    if item["id"] == "8dd9ae2d-ca3c-4026-a71a-9b63046c30cc":
                        print("see this!", item["resourceIds"])
                    a = {
                        "id": item["id"],
                        "resourceIds": item["resourceIds"],
                        "title": item["title"],
                        "canceledId": item["canceled"],
                        "address": item["address"],
                        "reasons": [],
                        "people_drive_times": {"start": {}, "end": {}},
                        "distances_all": [],
                        "times_all": [],
                        "reasons_l": "",
                        "priority": "",
                        "duration": item["duration"]["seconds"],
                        "start": item["start_real"],
                        "startRecur": item["start_real"],
                        "end_real_time": new_date_string,
                        "end": new_date_string,
                        "scheduled": True,
                        "loc_id": item["location0Id"],
                        "orange_sol": False,
                    }
                    # print('gap_2 : ', a)
                    if not a["canceledId"]:
                        ab.append(a)
                act_arr.append(ab)
            print("act_arr2", act_arr)
            return [resources, act_arr]
        else:
            # for i in range(num_of_days):
            i = 0
            print("num_of_days", num_of_days)
            end_date = datetime.datetime.strftime(
                start_date_original + datetime.timedelta(days=1), "%Y-%m-%d"
            )
            start_date = datetime.datetime.strftime(
                start_date_original + datetime.timedelta(days=i), "%Y-%m-%d"
            )
            ab = []
            start_date = convert_date_to_timezone(self.settings["timezone"], start_date)
            end_date = convert_date_to_timezone(self.settings["timezone"], end_date)
            # print('letsee',start_date,end_date)
            time1 = time.time()
            response = requests.post(
                f'{self.host}/scheduler/events?locations={locations}&start={str(start_date)}&end={str(end_date)}&branches={branch}&sandboxMode={"true" if self.sandboxMode else "false"}',
                headers=self.header,
                json={"people": "|".join(people)},
            )
            time2 = time.time()
            print("Actual_events: ", time2 - time1)
            # print('baz_ar : ', response.json())

            for item in response.json():
                # print('itemmmm : ', item)
                item["start_real"] = convert_timezone(item["start_real"], 0)
                item["end_real"] = convert_timezone(item["end_real"], 0)
                date_string = item["start_real"]
                date_object = datetime.datetime.strptime(
                    date_string, "%Y-%m-%dT%H:%M:%S.%fZ"
                )

                new_date = date_object + datetime.timedelta(
                    seconds=item["duration"]["seconds"]
                )
                new_date_string = new_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                # print("bazo_evvv : ",item)
                a = {
                    "id": item["id"],
                    "resourceIds": item["resourceIds"],
                    "title": item["title"],
                    "canceledId": item["canceled"],
                    "address": item["address"],
                    "reasons": [],
                    "people_drive_times": {"start": {}, "end": {}},
                    "distances_all": [],
                    "times_all": [],
                    "reasons_l": "",
                    "loc_id": item["location0Id"],
                    "priority": "",
                    "duration": item["duration"]["seconds"],
                    "start": item["start_real"],
                    "end_real_time": new_date_string,
                    "end": new_date_string,
                    "scheduled": True,
                    "orange_sol": False,
                }
                # print('gap_2 : ', a)
                if not a["canceledId"]:
                    ab.append(a)
            act_arr.append(ab)
            # print('soovy3',resources, act_arr)
            print("act_arr", act_arr)
            return [resources, act_arr]

    # def get_direct_activities(self):
    #     block_situation = 'false'
    #     orange = 'false'
    #     events = 'false'
    #     if self.orange:
    #         orange = 'true'
    #     if self.events:
    #         events = 'true'
    #     if self.blocks:
    #         block_situation = 'true'
    #     people = []
    #     for i in self.get_resources():
    #         if 'Person' in i['roles']:
    #             people.append(i['id'])
    #     arr = []
    #     start_date_original = datetime.datetime.strptime(
    #         self.start_date, "%Y-%m-%d")
    #     for i in range(self.num_of_days):
    #         end_date = datetime.datetime.strftime(
    #             start_date_original + datetime.timedelta(days=i + 1),
    #             "%Y-%m-%d")
    #         start_date = datetime.datetime.strftime(
    #             start_date_original + datetime.timedelta(days=i), "%Y-%m-%d")
    #         act_arr = [self.direct_activity_id]
    #         if self.is_lunch:
    #             act_arr.append(self.lunch_activity_id)
    #         if self.is_break:
    #             act_arr.append(self.break_activity_id)
    #         x = []
    #         for id in act_arr:
    #             response = requests.post(
    #                 f'{self.host}/scheduler/events_possible?start={start_date}&end={end_date}&branches={self.branches_id}&expanded_resources='
    #                 + id + '&events5=' + events +
    #                 '&settings={%22subgroupsFilterLabels%22:null,%22resourceFilterLabels%22:null,%22hideCancelations%22:false,%22isolateCanceled%22:true,%22locationQuantity%22:2,%22rolesDefault%22:[],%22totalCustom%22:%22total%22,%22timeConstraintUpperBuffer%22:null,%22timeConstraintLowerBuffer%22:null,%22Time%20Constraints%22:false,%22defaultActivity%22:null,%22defaultLocation%22:null,%22Overbooking%22:true,%22No%20Gaps%22:false,%22Drive%20Time%22:false,%22Weekends%22:false,%22teamSeparation%22:1,%22Blocks%22:'
    #                 + block_situation + ',%22Orange%22:' + orange +
    #                 ',%22Drive%20Distance%22:false,%22driveDistanceMaxQuantity%22:30,%22driveDistanceMaxUnit%22:%22mi%22,%22driveTimeQuantity%22:30,%22driveTimeUnit%22:%22Minutes%22}&sliderCheckbox=1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1&sliderPriorityValue=1&sliderDistanceValue=1&sliderInput=1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1&groupings=Teams,Severity,RBT%20REQ,Allergies,Languages,Unmatch',
    #                 headers=self.header,
    #                 json={'people': '|'.join(people)})

    #             some_arr = []
    #             for item in (response.json()['poss_events']):
    #                 a = {
    #                     "id": item['id'],
    #                     "resourceIds": item['resourceIds'],
    #                     "title": item['title'],
    #                     "address": item['address'],
    #                     "reasons": [],
    #                     "people_drive_times": {
    #                         "start": {},
    #                         "end": {}
    #                     },
    #                     "distances_all": [],
    #                     "times_all": [],
    #                     "reasons_l": item['reasons_l'],
    #                     "priority": item['priority'],
    #                     "start": item['start'],
    #                     "end": item['end'],
    #                     'scheduled': False,
    #                     "orange_sol": False
    #                 }

    #                 some_arr.append(a)
    #             for item in (response.json()['unmatch_poss_events']):
    #                 a = {
    #                     "id": item['id'],
    #                     "resourceIds": item['resourceIds'],
    #                     "title": item['title'],
    #                     "address": item['address'],
    #                     "reasons": [],
    #                     "people_drive_times": {
    #                         "start": {},
    #                         "end": {}
    #                     },
    #                     "distances_all": [],
    #                     "times_all": [],
    #                     "reasons_l": item['reasons_l'],
    #                     "priority": item['priority'],
    #                     "start": item['start'],
    #                     "end": item['end'],
    #                     'scheduled': False,
    #                     "orange_sol": True
    #                 }

    #                 some_arr.append(a)
    #             x = x + some_arr
    #         arr.append(x)
    #     # print('howdy', arr)
    #     return arr

    def get_resources(self, staffTracker=False):
        time1 = time.time()
        # print('herewe',self.start_date,self.end_date)
        if self.start_date == self.end_date:
            # Convert self.end_date to a datetime object
            end_date_obj = datetime.datetime.strptime(self.end_date, "%Y-%m-%d")
            # Add one day
            end_date_obj += datetime.timedelta(days=1)
            # Update self.end_date as a string in the same format
            self.end_date = end_date_obj.strftime("%Y-%m-%d")
        # print('herewe2',self.start_date,self.end_date)
        if len(self.resources) == 0:
            request_str = f"{self.host}/scheduler/resources?branches={self.branches_id}&start={self.start_date}&end={self.end_date}"
            if self.investigate and len(self.investigate) > 0:
                request_str += "&userIds="
                request_str += "|".join(self.investigate)
            if staffTracker:
                request_str += "&staffTracker=true"
            # print('soofer', self.host, request_str)
            encoded_url = urllib.parse.quote(request_str, safe="|!:/?&=")
            response = requests.get(encoded_url, headers=self.header)
            time2 = time.time()
            self.resources = response.json()
            arr = []
            for res in self.resources:
                if not res["calendarhide"]:
                    arr.append(res)
            self.resources = arr
        time2 = time.time()
        # print('Timer get_resources: ', time2 - time1)
        filtered_resources = []
        if len(self.isolatedResources) > 0:
            for r in self.resources:
                if "Person" not in r["roles"]:
                    filtered_resources.append(r)
                else:
                    if r["id"] in self.isolatedResources:
                        filtered_resources.append(r)
            self.resources = filtered_resources
        return self.resources

    def get_branch_structure(self):
        time1 = time.time()
        response = requests.get(
            f"{self.host}/scheduler/branch_structure", headers=self.header
        )
        time2 = time.time()
        # print('Timer get_branch_structure_time: ', time2 - time1)
        return response.json()

    def get_custom_constraints(self):
        # print('fleever')
        time1 = time.time()
        # response = requests.get(f'{self.host}/tags?page=1&tags=',
        #                         headers=self.header)

        response = requests.get(
            f"{self.host}/newconstraintgenerator?branches={self.branches_id}",
            headers=self.header,
        )
        # print('frosty', response.json())
        response_json = response.json()["rows"]
        # print('simple', response_json)
        new_data = []
        for d in response_json:
            min = 0
            # print("Bazo_x : ", d)
            if d["min"]:
                min = d["min"]
            obj = {
                "id": d["id"],
                "constraint": d["constraintType"],
                "type_or_specific": d["antecedentType"],
                "apply_constraint_to_this_user": d["antecedentTypeUsers_filtered"],
                "apply_constraint_to_this_role": d["antecedentTypeRoles_filtered"],
                "apply_constraint_to_this_subgroup": d[
                    "antecedentTypeSubgroups_filtered"
                ],
                "apply_constraint_to_this_branch": d["antecedentTypeBranches_filtered"],
                "type_or_specific_consequence": d["consequenceType"],
                "consequence_constraint_to_this_user": d[
                    "consequenceTypeUsers_filtered"
                ],
                "consequence_constraint_to_this_role": d[
                    "consequenceTypeRoles_filtered"
                ],
                "consequence_constraint_to_this_subgroup": d[
                    "consequenceTypeSubgroups_filtered"
                ],
                "consequence_constraint_to_this_branch": d[
                    "consequenceTypeBranches_filtered"
                ],
                "every_day": d["consequenceTypeDaySelection"],
                # "days":
                # d["consequenceTypeWeekDays_filtered"],
                # "every_day_antecedent":
                # d["antecedentTypeDaySelection"],
                # "days_antecedent":
                # d["antecedentTypeWeekDays_filtered"],
                "min": min,
                "max": d["max"],
                "minSeconds": d["minSeconds"] if "minSeconds" in d else min,
                "maxSeconds": d["maxSeconds"],
                "all": d["all"],
                "weight": d["weight"],
                "description": re.sub(r"</?strong>", "", d["description"]),
                "startDate": d["start"],
                "endDate": d["end"],
                "frequency": d["frequency"],
                "each_or_all_users": d["consequenceTypeEachOrAll"],
                "grouping": d["grouping_filtered"],
                "limit": d["noLimit"],
                "disabled": d["disabled"],
                "soft": d["soft"],
                "units": d["units"],
                "each_or_all_users_antecedent": d["antecedentTypeEachOrAll"],
                "antecedentLocationId": d["antecedentLocationId"],
                "antecedentTypeActivityId": d["antecedentTypeActivityId"],
            }

            # print('flimper', obj)
            # if not d["antecedentLocationId"] is None:
            #     obj["apply_constraint_to_this_user"].append([d["antecedentLocationId"]])
            if not d["disabled"]:
                new_data.append(obj)
        # print("bazo_bug_custom_data", new_data)
        # mid_index = len(new_data) // 4
        # first_half = [new_data[:mid_index][1]]
        # print('softy',first_half)
        # time2 = time.time()
        # print('Timer get_custom_constraints_time: ', time2 - time1)
        # #return []
        return new_data
        # return response.json()["rows"]

    def get_funders_fake(self):
        return []

    def get_funders(self):
        response = requests.get(
            f"{self.host}/users/resources/Funder?limit=500&page=1&users=",
            headers=self.header,
        )
        arr = []
        for res in response.json()["rows"]:
            if not res["calendarhide"]:
                arr.append(res)
        return arr

    def get_capacities(self):
        time1 = time.time()
        response = requests.get(
            f"{self.host}/capacityconstraints?page=1&capacityconstraints=",
            headers=self.header,
        )
        time2 = time.time()
        return response.json()["rows"]

    def get_groupings(self):
        time1 = time.time()
        response = requests.get(
            f"{self.host}/groupings?page=1&groupings=", headers=self.header
        )
        time2 = time.time()
        return response.json()["rows"]

    def get_subgroups(self):
        time1 = time.time()
        response = requests.get(
            f"{self.host}/scheduler/subgroups?branches={self.branches_id}&all={True}",
            headers=self.header,
        )
        time2 = time.time()
        # print('Timer get_subgroups_time: ',response.json(), time2 - time1)
        return response.json()[0]

    def get_subgroups_raw_data(self):
        time1 = time.time()
        response = requests.get(
            f"{self.host}/subgroups?branches={self.branches_id}", headers=self.header
        )
        time2 = time.time()
        # print('Timer get_subgroup_raw_time: ', time2 - time1)
        # print("aa_bazo : ",response.json()["rows"])
        return response.json()["rows"]

    def get_person_raw_data(self):
        time1 = time.time()
        response = requests.get(
            f"{self.host}/users/resources/Person?bol2=true&branches={self.branches_id}",
            headers=self.header,
        )
        arr = []
        for res in response.json()["rows"]:
            if not res["calendarhide"]:
                arr.append(res)
        time2 = time.time()
        # print('Timer get_person_raw_time: ', time2 - time1)
        return arr

    def get_location_raw_data(self):
        time1 = time.time()
        response = requests.get(
            f"{self.host}/users/resources/Location?bol2=true&branches={self.branches_id}",
            headers=self.header,
        )
        arr = []
        for res in response.json()["rows"]:
            if not res["calendarhide"]:
                arr.append(res)
        time2 = time.time()
        # print('Timer get_location_raw_time: ', time2 - time1)
        return arr

    # def get_time_constraints(self):
    #     people = []
    #     for i in self.get_resources():
    #         if 'Person' in i['roles']:
    #             people.append(i['id'])
    #     # print('|'.join(people))

    #     stri = f'{self.host}/scheduler/time_constraints?start={self.start_date}&end={self.end_date}&branches={self.branches_id}'
    #     response = requests.post(stri,
    #                              headers=self.header,
    #                              json={'people': '|'.join(people)})

    #     return response.json()
    def get_flags(self):

        time1 = time.time()

        user_ids = [i["id"] for i in self.get_resources() if "Person" in i["roles"]]
        joined_users = "|".join(user_ids)

        # Define high priority list if available from context, else empty
        high_priority = (
            "|".join(self.get_high_priority_ids())
            if hasattr(self, "get_high_priority_ids")
            else ""
        )

        print("flag Here", self.start_date, self.end_date)
        payload = {
            "userIds": joined_users,
            "start": self.start_date,  # Ensure this is ISO format
            "end": self.end_date,  # You’ll need to define or adjust this
            "sandboxMode": False,
            "soft": "",
            "highPriority": "|".join(self.high_priority),
            "disabled": "",
            "hard": "",
            "timezone": "America/Chicago",
            "onlyOverbooking": False,
        }

        response = requests.post(
            f"{self.host}/users/constraint-gap/flags",
            headers={**self.header, "Content-Type": "application/json"},
            json=payload,
        )

        time2 = time.time()
        # print('Timer_get_flags: ', time2 - time1, response.json())

        user_data_list = response.json()

        constraint_map = defaultdict(dict)

        for user in user_data_list:
            user_id = user["userId"]
            for constraint in user.get("constraints", []):
                constraint_id = constraint["id"]
                constraint_map[constraint_id][user_id] = constraint
        return json.loads(json.dumps(constraint_map))

    def res(self):
        arr = []
        for i in self.get_resources():
            # print('howdy3',i['name'])
            a = {
                "id": i["id"],
                "name": i["name"],
                "title": i["title"],
                "resourceTypeId": i["resourceTypeId"],
                "type": i["type"],
                "roles": i["roles"],
                "waitlisted": i["waitlisted"],
                "subgroups": i["subgroups"],
                "branches": i["branches"],
                "address": i["address"],
                "capacity": i["capacity"],
                "birthday": i["birthday"],
                "color": i["color"] if not i["color"] is None else "30ff00",
                "location_type": i["location_type"],
            }
            # print("bazo_color",a["name"],a["color"])
            arr.append(a)
        return arr
