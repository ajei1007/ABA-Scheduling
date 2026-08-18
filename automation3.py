import gc
import math
import random
import time
import datetime
from random import randrange
import itertools
from get_data import Get_Data
from itertools import combinations
from ortools.sat.python import cp_model
import requests
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor
from abstract_inputs import header
import json
import cProfile
from events_durations_calc import Time_Constraint_Handler
from helper_functions import *
import faulthandler

start_time = time.time()

my_new_events = []

faulthandler.enable()

branch = '1ca63c9a-4926-40e4-a2e5-16c580fa82de'  # Southlake
# branch = 'a5fe9f20-8494-4e85-995d-c09c385d98d2'  # Hannah

session = requests.Session()
day_ids = {
    0: '20770718-a98e-499f-ae8b-c395f0f743bb',
    1: '2d0599e7-2729-49ee-acbe-ede6de8ad9b7',
    2: '3260c7e7-c57b-4144-803f-7db9cf88393c',
    3: '56cbe76a-0cf6-4647-8a49-2ef9fd102079',
    4: '6d92706c-9bb1-447e-bf74-572609066663',
    5: 'ecd70b60-3fef-4d43-9181-2f9db60e19fe',
    6: 'fa2adb44-e5ba-4586-ae19-5f1e1767228d',
}
teams_now = [
    "3eb8aaef-b471-4ee0-9e5c-bf48b76fa929",  # "Amy Miller's Team"
    "f57102de-7aa6-49ed-a0de-237d7310a85f",  # "Clarisvel Carranco's Team":
    "a5fe9f20-8494-4e85-995d-c09c385d98d2",  # "Hannah Murray's Team":
    "664e188e-9bf6-4a24-a45b-c2c08a06e9f6",  # "Jason Vinocur Team":
    "aa8e83cb-e7f7-4a46-9639-4b8d802b8b86"  # "Jenna Courtney's Team":
]

resource_ids = {}


def days_arr(minute_interval):
    array = [1]
    ii = 60 // minute_interval
    for i in range(7):
        array.append((i + 1) * 24 * ii)
    return array


# def delete_multiple_events(arr, host):
#     for j in range(len(arr)):
#         response = requests.post(f'{host}/events/remove/multiple',
#                                  headers=input_data['header'],
#                                  json=[arr[j]['id']])


def remove_randomly(arr, act_id, lunch_id, percent):
    target = [d for d in arr if act_id in d.get('resourceIds')]
    lunches = [d for d in arr if lunch_id in d.get('resourceIds')]
    random_numbers = random.sample(range(1, len(target)),
                                   int(len(target) * percent // 100))
    deleted = []
    for i in random_numbers:
        x = target[i]
        arr.remove(x)
        deleted.append(x)
    for i in lunches:
        arr.remove(i)
        deleted.append(i)
    # print("ak74 : ", deleted)
    return [arr, deleted]


def min_session_array(minute_interval, min_minute):
    return [i for i in range(1, 60) if i * minute_interval < min_minute]


def ceil_to_multiple(number, multiple):
    return multiple * math.ceil(number / multiple)


def calculate_duration_hours(data):
    total = 0
    for i in data:
        start_recur = datetime.datetime.fromisoformat(i["start"].replace(
            'Z', '+00:00'))
        end_recur = datetime.datetime.fromisoformat(i["end"].replace(
            'Z', '+00:00'))

        duration_hours = (end_recur - start_recur).total_seconds() / 3600
        total += duration_hours

    return total


# This function converts slots to the normal day time
def slot_to_time(slot, slot_interval):
    # slot : int , 0 < slot_interval : int <= 60
    slots_per_day = 24 * 60 // slot_interval
    slots_per_hour = 60 // slot_interval
    hours = str((slot % slots_per_day) // slots_per_hour).zfill(2)
    minutes = str(
        (slot % slots_per_day % slots_per_hour) * slot_interval).zfill(2)
    seconds = '00'
    return hours + ':' + minutes + ':' + seconds


def time_to_slot(t, day, minutes, s):
    x = time.strptime(t, '%H:%M:%S')
    output = datetime.timedelta(
        hours=x.tm_hour, minutes=x.tm_min,
        seconds=x.tm_sec).total_seconds() / 60 / minutes
    if s == "start":
        if int(output) < output:
            output = int(output) + 1
    if s == "end":
        output = int(output)
    output = int(day * 24 * 60 / minutes + output)
    return output


class Resource:
    def __init__(self, info):
        self.name = info['name']
        self.id = info['id']
        self.roles = info['roles']
        self.waitlisted = info['waitlisted']
        self.matches = {}
        self.matches2 = {}
        self.matches2_durations = {}
        self.matches2_sessions = {}
        self.events = []
        self.total_time = 0
        self.time_so_far = 0
        self.rec_time = 0
        self.max_time_obj = {}
        self.max_time = randrange(60, 80)
        self.slots = {}
        self.activities = {}


class Resources:
    def __init__(self, resources):
        self.resources = {}
        self.roles = {}
        self.events = []
        self.appointments = []
        self.slots = {}
        for resource in resources:
            new_resource = Resource(resource)
            self.resources[resource['id']] = new_resource


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""
    def __init__(self, variables):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0

    def OnSolutionCallback(self):
        self.__solution_count += 1
        for v in self.__variables:
            print('%s = %i' % (v, self.Value(v)), end=' ')
        print()

    def solution_count(self):
        return self.__solution_count


def detect_range(l):
    l.sort()
    for i, j in itertools.groupby(enumerate(l), lambda x: x[1] - x[0]):
        j = list(j)
        yield j[0][1], j[-1][1] + 1


def intersection(lst1, lst2):  # gets intersection of two lists
    return [value for value in lst1 if value in lst2]


class Automate_Schedules:
    def __init__(self, resources, roles_hierarchy, given_data, resources_not,
                 distance_matrix, solutions1):
        self.model = cp_model.CpModel()
        self.model_actual = cp_model
        self.shift_hour = 1
        self.table = [['name'] + list(range(int(672 / self.shift_hour)))]
        self.solver = cp_model.CpSolver()
        self.resources1 = Resources(resources)
        # self.resources1 = solutions1.resources1
        self.roles_hierarchy = roles_hierarchy
        self.printer = []
        self.resources_yes = []
        self.resources_no = []
        self.distance_matrix = distance_matrix
        self.var_data = given_data
        self.team_vals = {}
        self.status_name = ""
        self.no_gap_priority = []
        self.events_bol = []
        self.max_possible = 0
        self.direct_events_sum = 0
        self.min_obj = 0
        self.orange_sum = 0
        self.solutions1 = solutions1

    def get_team_vals(self):
        return self.team_vals

    def get_status_name(self):
        return self.status_name

    def get_resources_from_role(self, roles):  # got it
        resources_ids = []
        # print('snifter',self.resources1.resources)
        for id, resource in self.resources1.resources.items():
            bol = False
            for resource_role in resource.roles:
                if resource_role in self.roles_hierarchy.keys():
                    # print('hefty', resource_role, self.roles_hierarchy)
                    if len(
                            intersection(
                                roles,
                                self.roles_hierarchy[resource_role])) > 0:
                        bol = True
                if bol:
                    resources_ids.append(id)
        return resources_ids

    def get_appointments(self, arr, slots_bol=True, slots={}):
        obj = {}
        if slots_bol:
            slots = self.resources1.slots
        for tup, event in slots.items():
            resources_ids = list(tup)
            bol = True
            for resources in arr:
                if len(intersection(resources, resources_ids)) == 0:
                    bol = False
                    break
            if bol:
                obj[tup] = event
        return obj

    def objective_resource(self, id):
        val = self.get_appointments([
            self.get_resources_from_role([self.var_data['objective_role']]),
            [self.var_data["objectiveactivity"]]
        ])
        val2 = self.get_appointments(
            [self.var_data["objectiveactivity"], self.var_data["lunch_id"]])
        del_bol_arr = []
        del_app = []

        regen_arr = []
        for i in val.values():
            if i[5]:
                del_app.append(i[0])
                del_bol_arr.append(i[11])
            if not i[5]:
                regen_arr.append(i[0])
        max_delete = self.direct_events_sum * (
            100 - self.var_data["percentage"]) // 100
        if self.var_data["percentage"] > 0:
            self.model.Add(sum(del_app) >= 0)

        else:
            self.model.Add(sum(del_bol_arr) >= int(len(del_bol_arr)))

        arr = []
        for i in map(lambda num: num[0], val.values()):
            b = self.model.NewBoolVar("so")
            self.model.Add(i == 0).OnlyEnforceIf(b)
            arr.append(b.Not())
        white_weighted_array = []
        orange_weighted_array = []
        for i in val.values():
            if not i[10]:
                white_weighted_array.append(i[0])
            else:
                orange_weighted_array.append(i[0])
        # self.model.Maximize(
        #     sum(white_weighted_array)
        #     * 2 + sum(orange_weighted_array)
        # )
        self.model.Maximize(
            sum(map(lambda num: num[0], val.values())) + sum(del_bol_arr)
            # - sum(arr)
        )
        # self.orange_sum = sum(orange_weighted_array)
        # self.model.Maximize(
        #     sum(map(lambda num: num[0], val.values()))
        #     # - sum(arr)
        # )
        # self.model.Minimize(self.min_obj -
        #                     sum(map(lambda num: num[0], val.values())))

    def data_insert(self, data):
        print('garry : ', data)
        waitlist_count = 1
        event_ids = []
        people = self.get_resources_from_role(
            [self.var_data['insert_data_role']])
        for j in list(range(1)):
            for info in data:
                if info['scheduled'] == False:
                    start = datetime.datetime.strptime(
                        info['start'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    end = datetime.datetime.strptime(info['end'],
                                                     '%Y-%m-%dT%H:%M:%S.%fZ')
                    duration = int((end - start).total_seconds() / 3600 *
                                   (60 // self.var_data['slot_length']))
                    interval_start = time_to_slot(start.strftime('%H:%M:%S'),
                                                  (start.weekday() + 1) % 7,
                                                  self.var_data['slot_length'],
                                                  "start")
                    interval_end = time_to_slot(end.strftime('%H:%M:%S'),
                                                (start.weekday() + 1) % 7,
                                                self.var_data['slot_length'],
                                                "end")
                    # interval_end = interval_start + int(
                    #     duration * 60 // self.var_data['slot_length'])
                    # interval_range = list(range(interval_start, interval_end))
                    resource_list = []
                    address = info['address']

                    for res in sorted(info['resourceIds']):

                        # All of the users in white bubble
                        resource_list.append(
                            res[:-1])  # Puts users in resource_list
                    resource_list_all = resource_list
                    resource_list_people = intersection(resource_list, people)
                    # print('blabla: ', resource_list)
                    for r in list(combinations(resource_list_all, 2)):
                        res1 = r[0]
                        res2 = r[1]
                        if res2 not in self.resources1.resources[res1].matches:
                            bol_match = self.model.NewBoolVar('hi')
                            self.resources1.resources[res1].matches[
                                res2] = bol_match
                            self.resources1.resources[res2].matches[
                                res1] = bol_match
                        if res2 not in self.resources1.resources[
                                res1].matches2:
                            self.resources1.resources[res1].matches2[res2] = {}
                            self.resources1.resources[res2].matches2[res1] = {}
                            self.resources1.resources[res1].matches2_durations[
                                res2] = {}
                            self.resources1.resources[res2].matches2_durations[
                                res1] = {}
                            self.resources1.resources[res1].matches2_sessions[
                                res2] = {}
                            self.resources1.resources[res2].matches2_sessions[
                                res1] = {}
                            for i in range(7):
                                bol_match = self.model.NewBoolVar('hi')
                                int_duration = self.model.NewIntVar(
                                    0, 100000000, 'hi')
                                int_session = self.model.NewIntVar(
                                    0, 100000000, 'hi')
                                self.resources1.resources[res1].matches2[res2][
                                    i] = bol_match
                                self.resources1.resources[res2].matches2[res1][
                                    i] = bol_match
                                self.resources1.resources[
                                    res1].matches2_durations[res2][
                                        i] = int_duration
                                self.resources1.resources[
                                    res2].matches2_durations[res1][
                                        i] = int_duration
                                self.resources1.resources[
                                    res1].matches2_sessions[res2][
                                        i] = int_session
                                self.resources1.resources[
                                    res2].matches2_sessions[res1][
                                        i] = int_session

                    duration_int = self.model.NewIntVar(
                        0, duration, 'session length')
                    start_int = self.model.NewIntVar(interval_start,
                                                     interval_end, 'start')
                    end_int = self.model.NewIntVar(interval_start,
                                                   interval_end, 'end')
                    bol_appointment = self.model.NewBoolVar('hi')
                    event_interval = self.model.NewOptionalIntervalVar(
                        start_int, duration_int, end_int, bol_appointment,
                        'interval')
                    self.model.Add(0 == duration_int).OnlyEnforceIf(
                        bol_appointment.Not())
                    # All in one feature
                    # if (True and self.var_data["all_or_nothing"]
                    #         and self.var_data["blocks"]
                    #         and (not ("Lunch" in info["title"]))
                    #         and (not ("Break" in info["title"]))):
                    #     self.model.Add(duration_int == duration).OnlyEnforceIf(
                    #         bol_appointment)
                    # else:
                    #     self.model.Add(duration_int >= bol_appointment
                    #                    ).OnlyEnforceIf(bol_appointment)

                    if len(resource_list_people) > 1:
                        for r in list(combinations(resource_list_people, 2)):
                            res1 = r[0]
                            res2 = r[1]
                            if self.resources1.resources[res1].waitlisted:
                                waitlist_count = waitlist_count - 1
                            if self.resources1.resources[res2].waitlisted:
                                waitlist_count = waitlist_count - 1
                                # print('yes printed')
                            self.model.Add(duration_int == 0).OnlyEnforceIf(
                                self.resources1.resources[res1].matches[res2].
                                Not())
                            self.resources1.slots[
                                tuple([interval_start]) +
                                tuple(resource_list) + tuple([j])] = [
                                    duration_int, self.resources1.
                                    resources[res1].matches[res2].Not(),
                                    event_interval, start_int, end_int, False,
                                    bol_appointment, address, waitlist_count,
                                    info["id"], info["orange_sol"], 2
                                ]

                    else:
                        self.resources1.slots[tuple([interval_start]) +
                                              tuple(resource_list) +
                                              tuple([j])] = [
                                                  duration_int, 1,
                                                  event_interval, start_int,
                                                  end_int, False,
                                                  bol_appointment, address,
                                                  waitlist_count, info["id"],
                                                  info["orange_sol"], 2
                                              ]

                if info['scheduled']:
                    orange_sol = False
                    if "orange_sol" in info.keys():
                        orange_sol = info["orange_sol"]
                    start = datetime.datetime.strptime(
                        info['start'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    end = datetime.datetime.strptime(info['end'],
                                                     '%Y-%m-%dT%H:%M:%S.%fZ')
                    duration = int((end - start).total_seconds() / 3600 *
                                   (60 // self.var_data['slot_length']))
                    interval_start = time_to_slot(start.strftime('%H:%M:%S'),
                                                  (start.weekday() + 1) % 7,
                                                  self.var_data['slot_length'],
                                                  "start")
                    interval_end = time_to_slot(end.strftime('%H:%M:%S'),
                                                (start.weekday() + 1) % 7,
                                                self.var_data['slot_length'],
                                                "end")
                    address = ""

                    del_bol = self.model.NewBoolVar("del_bol")
                    resource_list = list(set(info['resourceIds']))
                    resource_list = [res for res in sorted(resource_list)]
                    duration_int = self.model.NewIntVar(
                        0, duration, "some_dur")
                    start_int = self.model.NewConstant(interval_start)
                    end_int = self.model.NewConstant(interval_start + duration)
                    event_interval = self.model.NewOptionalIntervalVar(
                        start_int, duration_int, end_int, del_bol, 'interval')
                    self.model.Add(
                        duration_int == duration).OnlyEnforceIf(del_bol)
                    self.model.Add(duration_int == 0).OnlyEnforceIf(
                        del_bol.Not())

                    # if self.var_data["objectiveactivity"] in resource_list:
                    self.direct_events_sum += duration

                    # if info["id"] in event_ids:
                    #     continue
                    # else:

                    self.resources1.slots[tuple([interval_start]) +
                                          tuple(resource_list) +
                                          tuple([j])] = [
                                              duration_int, 1, event_interval,
                                              start_int, end_int, True, 1,
                                              address, waitlist_count,
                                              info["id"], orange_sol, del_bol
                                          ]

                    event_ids.append(info["id"])
                    event_ids = list(set(event_ids))

        print("OK_WITH_DATA : DATA_INSERT")
        gc.collect()

    def solve(self):
        self.solver = cp_model.CpSolver()

        self.solver.parameters.max_time_in_seconds = self.var_data[
            'max_time_in_seconds']
        self.solver.parameters.log_search_progress = True
        # self.solver.parameters.use_pb_resolution = True
        # self.solver.parameters.presolve_use_bva = True
        # # self.solver.parameters.use_dual_scheduling_heuristics = True
        # self.solver.parameters.share_objective_bounds = True
        # self.solver.parameters.cover_optimization = True
        self.solver.parameters.optimize_with_core = False
        self.solver.parameters.num_search_workers = 2
        self.solver.log_callback = print
        solution_printer = VarArraySolutionPrinter([])
        self.printer = solution_printer
        status = self.solver.Solve(self.model, solution_printer)
        print('Status = %s' % self.solver.StatusName(status))
        print('Number of solutions found: %i' %
              solution_printer.solution_count())
        self.status_name = self.solver.StatusName(status)
        if status == cp_model.INFEASIBLE:
            print(
                f'WHY_INFEASIBLE: {self.solver.SufficientAssumptionsForInfeasibility()}'
            )
        return self.solver.StatusName(status)

    def time_constraints_insert(self, timeconstraints):

        for constraint in timeconstraints:
            if constraint["activity_id"] == "":
                val = self.get_appointments(
                    [[constraint['user_id']],
                     [self.get_resources_from_role(["Activity"])]]).values()
                if len(val) > 0:

                    self.model.Add(
                        sum(map(lambda num: num[0], val)) <= math.floor(
                            float(constraint['max']) * 4))
            else:
                val = self.get_appointments([[constraint['user_id']],
                                             [constraint['activity_id']]
                                             ]).values()
                if len(val) > 0:
                    val = [i for i in val if i[5] == False]

                    self.model.Add(
                        sum(map(lambda num: num[0], val)) <= math.floor(
                            float(constraint['max']) * 4))
        print("OK_WITH : TIME_CONS")

        # if constraint['frequency'] == 'Total' and 'id' in constraint.keys(
        # ):

        #     val = self.get_appointments([[constraint['id']],
        #                                  [constraint['activity_id']]
        #                                  ]).values()
        #     if len(val) > 0:
        #         self.model.Add(
        #             sum(map(lambda num: num[0], val)) < math.floor(
        #                 int(constraint['rec'])))
        #         self.resources1.resources[constraint['id']].max_time_obj = {
        #             **self.resources1.resources[constraint['id']].max_time_obj, constraint['activity_id']:
        #             math.floor(int(constraint['rec']))
        #         }

    def minSession(self):
        val = self.get_appointments([[self.var_data["objectiveactivity"]]])
        durations = list(map(lambda num: num[0], val.values()))
        min_session_arr = min_session_array(self.var_data['slot_length'],
                                            self.var_data['min_session_dur'])
        max_slot = self.var_data["max_session_length"] // self.var_data[
            "slot_length"]
        for dur in durations:
            for i in min_session_arr:
                self.model.Add(dur != i)
            self.model.Add(dur <= max_slot)
        print("OK_WITH : MIN_SESSION")

    def matches_frequency(self):
        print('hello1')
        people = self.get_resources_from_role(["Person"])
        days_arrays = days_arr(self.var_data['slot_length'])
        for person_id in people:
            val = self.get_appointments([[person_id]])
            for person_id2 in self.resources1.resources[
                    person_id].matches2.keys():
                val2 = self.get_appointments([[person_id2]], False, val)
                for index, x in enumerate(days_arrays):
                    if index != 0:
                        # print('hello2', index, x)
                        val3 = self.get_appointments(
                            [list(range(days_arrays[index - 1], x))], False,
                            val2)
                        durations = list(map(lambda num: num[0],
                                             val3.values()))
                        sessions = list(map(lambda num: num[6], val3.values()))
                        matching_bol = self.resources1.resources[
                            person_id].matches2[person_id2][index - 1]
                        int_duration = self.resources1.resources[
                            person_id].matches2_durations[person_id2][index -
                                                                      1]
                        int_session = self.resources1.resources[
                            person_id].matches2_sessions[person_id2][index - 1]

                        if len(val3) == 0:
                            self.model.Add(matching_bol == 0)
                            self.model.Add(int_duration == 0)
                            self.model.Add(int_session == 0)
                        else:
                            self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                                matching_bol.Not())
                            self.model.Add(
                                sum(durations) > 0).OnlyEnforceIf(matching_bol)
                            self.model.Add(sum(durations) == int_duration)
                            self.model.Add(sum(sessions) == int_session)

        # for person_id in people:
        #     for index, x in enumerate(days_arrays):
        #         if index != 0:
        #             arr = []
        #             for person_id2 in self.resources1.resources[
        #                     person_id].matches2.keys():
        #                 print('hello3')
        #                 matching_bol = self.resources1.resources[
        #                     person_id].matches2[person_id2][index - 1]
        #                 arr.append(matching_bol)
        #             self.model.Add(sum(arr) <= 1)
        for c in self.solutions1.resources1.frequency_constraints:
            if c['type'] == 'frequency':
                for user_a in c['users_antecedent']:
                    user_a_id = self.solutions1.resources1.resources[user_a].id
                    if c['frequency'] == 'day':
                        for index, x in enumerate(days_arrays):
                            if index != 0:
                                arr = []
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[
                                        user_c].id
                                    if user_a_id in self.resources1.resources.keys(
                                    ) and user_c_id in self.resources1.resources[
                                            user_a_id].matches2.keys():
                                        matching_bol = self.resources1.resources[
                                            user_a_id].matches2[user_c_id][
                                                index - 1]
                                        arr.append(matching_bol)
                                self.model.Add(sum(arr) <= c['max'])
                                self.model.Add(sum(arr) >= c['min'])
                    elif c['frequency'] == 'week':
                        arr = []
                        for index, x in enumerate(days_arrays):
                            if index != 0:
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[
                                        user_c].id
                                    if user_a_id in self.resources1.resources.keys(
                                    ) and user_c_id in self.resources1.resources[
                                            user_a_id].matches2.keys():
                                        matching_bol = self.resources1.resources[
                                            user_a_id].matches2[user_c_id][
                                                index - 1]
                                        arr.append(matching_bol)
                        self.model.Add(sum(arr) <= c['max'])
                        self.model.Add(sum(arr) >= c['min'])
            elif c['type'] == 'time':
                for user_a in c['users_antecedent']:
                    user_a_id = self.solutions1.resources1.resources[user_a].id
                    if c["each_or_all_users"] == 'each':
                        if c['frequency'] == 'day':
                            for index, x in enumerate(days_arrays):
                                if index != 0:
                                    for user_c in c['users_consequence']:
                                        arr = []
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_durations.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_durations[
                                                    user_c_id][index - 1]
                                            arr.append(int_duration)
                                            self.model.Add(
                                                sum(arr) <= c['max'] * 4)
                                            self.model.Add(
                                                sum(arr) >= c['min'] * 4)
                        elif c['frequency'] == 'week':
                            for user_c in c['users_consequence']:
                                arr = []
                                for index, x in enumerate(days_arrays):
                                    if index != 0:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_durations.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_durations[
                                                    user_c_id][index - 1]
                                            arr.append(int_duration)
                                self.model.Add(sum(arr) <= c['max'] * 4)
                                self.model.Add(sum(arr) >= c['min'] * 4)
                    else:
                        if c['frequency'] == 'day':
                            for index, x in enumerate(days_arrays):
                                if index != 0:
                                    arr = []
                                    for user_c in c['users_consequence']:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_durations.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_durations[
                                                    user_c_id][index - 1]
                                            arr.append(int_duration)
                                    self.model.Add(sum(arr) <= c['max'] * 4)
                                    self.model.Add(sum(arr) >= c['min'] * 4)
                        elif c['frequency'] == 'week':
                            arr = []
                            for user_c in c['users_consequence']:
                                for index, x in enumerate(days_arrays):
                                    if index != 0:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_durations.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_durations[
                                                    user_c_id][index - 1]
                                            arr.append(int_duration)
                            self.model.Add(sum(arr) <= c['max'] * 4)
                            self.model.Add(sum(arr) >= c['min'] * 4)

            elif c['type'] == 'session':
                print('soothy1')
                for user_a in c['users_antecedent']:
                    user_a_id = self.solutions1.resources1.resources[user_a].id
                    if c['frequency'] == 'day':
                        print('soothy2')
                        for index, x in enumerate(days_arrays):
                            if index != 0:
                                if c["each_or_all_users"] == 'each':
                                    for user_c in c['users_consequence']:
                                        arr = []
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_durations.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_sessions[
                                                    user_c_id][index - 1]
                                            arr.append(int_duration)
                                            self.model.Add(
                                                sum(arr) <= c['max'])
                                            self.model.Add(
                                                sum(arr) >= c['min'])
                                else:
                                    arr = []
                                    print('smilly')
                                    for user_c in c['users_consequence']:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        print(
                                            'smooshie', user_c_id, user_a_id,
                                            self.resources1.
                                            resources[user_a_id].
                                            matches2_sessions.keys())
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_sessions.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_sessions[
                                                    user_c_id][index - 1]
                                            print('ookie', c['max'], c['min'])
                                            arr.append(int_duration)
                                    self.model.Add(sum(arr) <= c['max'])
                                    self.model.Add(sum(arr) >= c['min'])

                    elif c['frequency'] == 'week':
                        if c["each_or_all_users"] == 'each':
                            for user_c in c['users_consequence']:
                                arr = []
                                for index, x in enumerate(days_arrays):
                                    if index != 0:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_durations.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_sessions[
                                                    user_c_id][index - 1]
                                            arr.append(int_duration)
                                self.model.Add(sum(arr) <= c['max'])
                                self.model.Add(sum(arr) >= c['min'])
                        else:
                            arr = []
                            for user_c in c['users_consequence']:
                                for index, x in enumerate(days_arrays):
                                    if index != 0:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_durations.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_sessions[
                                                    user_c_id][index - 1]
                                            arr.append(int_duration)
                            self.model.Add(sum(arr) <= c['max'])
                            self.model.Add(sum(arr) >= c['min'])

    def noGapsEquation(self):  # No gap equation

        employees = self.get_resources_from_role(['Employee'])
        days_arrays = days_arr(self.var_data['slot_length'])
        for index, x in enumerate(days_arrays):
            if index != 0:
                for person_id in self.get_resources_from_role(
                    [self.var_data['no_gap_role']]):
                    # for person_id in self.get_resources_from_role(['ABA']):
                    val = self.get_appointments(
                        [[person_id],
                         list(range(days_arrays[index - 1], x)),
                         self.get_resources_from_role(['Activity'])])
                    if len(val) > 0:
                        min = self.model.NewIntVar(0, 10000000000, 'snip1')
                        max = self.model.NewIntVar(0, 1000000000, 'snip2')
                        min_array = list(map(lambda num: num[3], val.values()))
                        max_array = list(map(lambda num: num[4], val.values()))
                        durations = list(map(lambda num: num[0], val.values()))
                        self.model.AddMinEquality(min, min_array)
                        self.model.AddMaxEquality(max, max_array)
                        self.model.Add(sum(durations) <=
                                       max - min)  # reducing search space

                        bol = self.model.NewBoolVar(f'{person_id}')
                        if person_id in employees:
                            # self.min_obj += max - min - sum(durations)
                            self.model.Add(sum(durations) >= max - min -
                                           6).OnlyEnforceIf(bol)
                            self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                                bol.Not())
                        else:
                            self.model.Add(sum(durations) == max -
                                           min).OnlyEnforceIf(bol)
                            self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                                bol.Not())
                            self.min_obj += sum(durations)
        print("OK_WITH : NO_GAP")

    def overlap(self, event_pair):  # got it

        for id in list(
                set(
                    self.get_resources_from_role(
                        [self.var_data['overlap_role']]))):
            val = self.get_appointments([[id],
                                         self.get_resources_from_role(
                                             ['Activity'])])
            if len(val) > 0:
                arr = val.values()
                # arr = []
                # event_id = []
                # for i in val.values():
                #     if not i[5]:
                #         arr.append(i)
                #     elif not (i[9] in event_id):
                #         arr.append(i)
                #         event_id.append(i[9])

                flimp = list((map(lambda num: num[2], arr)))
                self.model.AddNoOverlap(flimp)
        print("OK_WITH : OVERLAP")

    def constraint_drive(self):
        constraint_drive = self.distance_matrix
        drive_keys = constraint_drive.keys()
        days_arrays = days_arr(self.var_data['slot_length'])
        for index, x in enumerate(days_arrays):
            if index != 0:

                for id in self.get_resources_from_role(['Employee']):
                    val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         self.get_resources_from_role(['Activity'])])
                    for r in list(
                            combinations(map(lambda num: num, val.values()),
                                         2)):
                        res1 = r[0]
                        res2 = r[1]
                        address1 = res1[7]
                        address2 = res2[7]

                        if address1 and address2 and len(address1) > 1 and len(
                                address2
                        ) > 1 and address2 != address1 and address1 in drive_keys:
                            if address2 in constraint_drive[address1].keys(
                            ) and constraint_drive[address1][address2][1]:
                                # print('snoofy5',constraint_drive[address1][address2],address1,address2)
                                drive_time = ceil_to_multiple(
                                    constraint_drive[address1][address2][1] /
                                    60.0, self.var_data['slot_length'])
                                drive_time_slot = int(
                                    drive_time // self.var_data['slot_length'])
                                # print('sloofy',drive_time,drive_time_slot)
                                end2 = res2[4]
                                start2 = res2[3]
                                end1 = res1[4]
                                start1 = res1[3]
                                duration2 = res2[0]
                                duration1 = res1[0]
                                newBol = self.model.NewBoolVar('yo')
                                self.model.AddMultiplicationEquality(
                                    newBol, [res1[6], res2[6]])
                                newInt1 = self.model.NewIntVar(
                                    -100000, 100000, 'h')
                                newInt3 = self.model.NewIntVar(
                                    -100000, 100000, 'h')
                                max_end = self.model.NewIntVar(
                                    -100000, 100000, 'h')
                                min_end = self.model.NewIntVar(
                                    -100000, 100000, 'h')
                                self.model.AddMaxEquality(
                                    max_end, [end1, end2])
                                self.model.AddMinEquality(
                                    min_end, [start1, start2])

                                self.model.Add(newInt1 == max_end - min_end -
                                               duration2 - duration1)
                                self.model.Add(newInt1 >= drive_time_slot
                                               ).OnlyEnforceIf(newBol)
        print("OK_WITH : DRIVE_CONS")

    def constraint_team(self, team_bounds):
        people = self.get_resources_from_role(['Person'])
        some_val = {}
        for id in people:
            ab = self.model.NewIntVar(0, team_bounds['num_of_teams'] - 1, id)
            some_val[id] = ab
        self.team_vals = some_val
        some_dic = {}
        teams_arr = []
        for t in range(team_bounds['num_of_teams']):
            arr = []
            for id in people:
                bol = self.model.NewBoolVar(f'{t} {id}')
                some_dic[(id, t)] = bol
                arr.append(bol)
                self.model.Add(t == some_val[id]).OnlyEnforceIf(bol)
                self.model.Add(t != some_val[id]).OnlyEnforceIf(bol.Not())
            teams_arr.append(arr)
        for i in range(team_bounds['num_of_teams'] - 1):
            self.model.Add(
                sum(teams_arr[i]) - sum(teams_arr[i + 1]) <= team_bounds['r'])
        self.model.Add(
            sum(teams_arr[team_bounds['num_of_teams'] - 1]) -
            sum(teams_arr[0]) <= team_bounds['r'])
        for t in range(team_bounds['num_of_teams']):
            self.model.Add(
                sum(teams_arr[t]) >= team_bounds['min_people_per_team'])
        for tup, event in self.resources1.slots.items():
            peep = intersection(list(tup), people)
            if len(peep) == 2:
                per1 = peep[0]
                per2 = peep[1]

                self.model.Add(some_val[per1] == some_val[per2]).OnlyEnforceIf(
                    event[6])

    def constraint_lunch(self):  # got it
        days_arrays = days_arr(self.var_data['slot_length'])
        for index, x in enumerate(days_arrays):
            if index != 0:
                for id in self.get_resources_from_role(
                    [self.var_data['lunch_role']]):
                    val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         [self.var_data["lunch_id"]]])
                    therapy_val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         [self.var_data["objectiveactivity"]]])
                    xy = self.model.NewBoolVar('hello')
                    dur_lunch = sum(map(lambda num: num[0], val.values()))
                    dur_therapy = sum(
                        map(lambda num: num[0], therapy_val.values()))

                    if (len(val) > 0):
                        self.model.Add(
                            dur_lunch == 30 //
                            self.var_data["slot_length"]).OnlyEnforceIf(xy)
                        self.model.Add(
                            dur_lunch + dur_therapy >= (30 + 360) //
                            self.var_data["slot_length"]).OnlyEnforceIf(xy)
                        self.model.Add(dur_lunch == 0).OnlyEnforceIf(xy.Not())
                        self.model.Add(
                            dur_therapy < 360 //
                            self.var_data["slot_length"]).OnlyEnforceIf(
                                xy.Not())

                    # else:
                    #     self.model.Add(
                    #         sum(map(lambda num: num[0], val.values())) == 0)
        print("OK_WITH : LUNCH_CONS")

    def constraint_break(self):
        days_arrays = days_arr(self.var_data['slot_length'])
        for index, x in enumerate(days_arrays):
            if index != 0:
                for id in self.get_resources_from_role(
                    [self.var_data['break_role']]):
                    val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         [self.var_data["break_id"]]])
                    val_lunch = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         [self.var_data["lunch_id"]]])
                    therapy_val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         [self.var_data["objectiveactivity"]]])
                    xy = self.model.NewBoolVar('hello')

                    dur_therapy = sum(
                        map(lambda num: num[0], therapy_val.values()))
                    self.model.Add(xy == dur_therapy).OnlyEnforceIf(xy.Not())

                    if (len(val) > 0):
                        if len(val_lunch) > 0:
                            mn = self.model.NewIntVar(0, 10000000000, 'snip1')
                            mx = self.model.NewIntVar(0, 1000000000, 'snip2')
                            self.model.AddMaxEquality(
                                mx,
                                list(
                                    map(lambda num: num[4],
                                        val_lunch.values())))
                            self.model.AddMaxEquality(
                                mn, list(map(lambda num: num[3],
                                             val.values())))
                            self.model.Add(
                                mn - mx >= (180 //
                                            self.var_data['slot_length']))
                            self.model.Add(
                                sum(map(lambda num: num[0], val.values())) ==
                                1).OnlyEnforceIf(xy)
                        else:
                            self.model.Add(
                                sum(map(lambda num: num[0], val.values())) ==
                                1).OnlyEnforceIf(xy)

                    else:
                        self.model.Add(
                            sum(map(lambda num: num[0], val.values())) == 0)
        print("OK_WITH : BREAK_CONS")

    def solve_model(self, data, timeconstraints, aut_arr, act_id, e_pair):
        # self.data_insert(data)
        # print('lifty', self.solutions1.events, self.solutions1.events_poss)
        self.data_insert(
            [*self.solutions1.events_poss, *self.solutions1.events2])
        if self.var_data['is_minSession_constraint']:
            self.minSession()
        # # if self.var_data['is_time_constraint']:
        # #     self.time_constraints_insert(timeconstraints)
        # # if self.var_data['is_drive_constraint']:
        # #     self.constraint_drive()
        if self.var_data['is_lunch_constraint']:
            self.constraint_lunch()
        # # if self.var_data['is_break_constraint']:
        # #     self.constraint_break()
        # # if self.var_data['is_team_constraint']:
        # #     self.constraint_team(self.var_data['team_bounds'])
        if self.var_data['is_overlap_constraint']:
            self.overlap(e_pair)
        # # if True:
        # #     self.matches_frequency()
        if self.var_data['is_noGap_constraint']:
            self.noGapsEquation()
        self.objective_resource(self.var_data["objectiveactivity"])
        self.status_name = self.solve()


newDict = dict()
for (key, value) in resource_ids.items():
    if value['possible'] != 0:
        newDict[key] = value
resource_ids = {**newDict}
resource_ids = dict(
    sorted(resource_ids.items(), key=lambda item: item[1]['possible']))

input_data = {
    'start_date': '2022-10-13',
    'end_date': '2022-10-14',
    'branch': branch,
    'teams': teams_now,
    'daily': False,
    'blocks': False,
    'is_Multi': False,
    'is_lunch': False,
    'is_break': False,
    'is_orange': False,
    'is_events': True,
    'percentage': 10,  # percentage
    'objective_role': 'R/BT',
    'insert_data_role': 'Person',
    'slot_length': 15,
    'max_time_in_seconds': 60.0,
    'num_search_workers': 8,
    'min_session_dur': 30,  # [1]
    'max_session_length': 16,
    'no_gap_role': 'Person',
    'overlap_role': 'Person',
    'team_bounds': {
        'num_of_teams': 5,
        'r': 4,
        'min_people_per_team': 6
    },
    'lunch_role': 'Employee',
    'lunch_length': 2,
    'break_role': 'Employee',
    'break_length': 1,
    'part1': False,
    'is_time_constraint': False,
    'is_drive_constraint': False,
    'is_lunch_constraint': False,
    'is_break_constraint': False,
    'is_team_constraint': False,
    'is_overlap_constraint': True,
    'is_minSession_constraint': True,
    'is_noGap_constraint': True,
    'is_delete': False,
    'optimize_curret': True,
    'header': header,
    'host': 'http://localhost:8080/api'
}


class Rocket:
    def __init__(self, data, solutions1):
        self.data = data
        self.solutions1 = solutions1

    def test_insert(self, d):
        start_date_original = d['start_date_original']
        resources_team = d['resources_team']
        data = d['data']
        date_original = d['date_original']
        data2_team = d['data2_team']
        aut_arr = d['aut_arr']
        returned_arr = []
        objective_value = 0
        host = data["host"]
        for act_id in [d["objectiveactivity"]]:
            for j in list(range(1)):
                for day in range(1):
                    resources_used = []
                    start_date = datetime.datetime.strftime(
                        start_date_original + datetime.timedelta(days=day),
                        "%Y-%m-%d")
                    end_date = datetime.datetime.strftime(
                        start_date_original +
                        datetime.timedelta(days=day + data['day_increment']),
                        "%Y-%m-%d")
                    aut2 = Automate_Schedules(resources_team,
                                              data['roles_hierarchy'], data,
                                              resources_used,
                                              data['distance_matrix'],
                                              self.solutions1)
                    aut2.solve_model(data2_team, data['time_cons'], aut_arr,
                                     act_id, data["e_pair"])
                    resources_used += aut2.resources_yes
                    activity_list = aut2.get_resources_from_role(['Activity'])
                    people_list = aut2.get_resources_from_role(['Person'])
                    people_appointments = {}
                    for id in people_list:
                        people_appointments[id] = []
                    event_obj = {}
                    teams_dict = {}
                    if len(aut2.get_team_vals()) > 0:
                        for k, v in aut2.get_team_vals().items():
                            teams_dict[k] = aut2.solver.Value(v)

                    objective_value = aut2.solver.ObjectiveValue()
                    status = aut2.get_status_name()
                    # print("Total orange solution in slots : ", aut2.orange_sum)

                    if aut2.printer.solution_count() != 0:

                        for tup, event in aut2.resources1.slots.items():
                            if (aut2.solver.Value(event[0]) > 0
                                    or (event[5] == True)):
                                resources_ids = tuple(list(tup)[1:])
                                slot = list(tup)[0]
                                if resources_ids in event_obj.keys():
                                    event_obj[resources_ids].append(slot)
                                else:
                                    event_obj[resources_ids] = [slot]
                        del_arr = []
                        for tup, slots in event_obj.items():

                            users = list(set(list(tup)))
                            for times in detect_range(list(sorted(
                                    set(slots)))):
                                inte = aut2.solver.Value(aut2.resources1.slots[
                                    tuple([int(times[0])]) + tup][0])
                                inte_start = aut2.solver.Value(
                                    aut2.resources1.slots[
                                        tuple([int(times[0])]) + tup][3])
                                inte_end = aut2.solver.Value(
                                    aut2.resources1.slots[
                                        tuple([int(times[0])]) + tup][4])
                                address = aut2.resources1.slots[
                                    tuple([int(times[0])]) + tup][7]
                                scheduled = aut2.resources1.slots[
                                    tuple([int(times[0])]) + tup][5]
                                delete_event = aut2.solver.Value(
                                    aut2.resources1.slots[
                                        tuple([int(times[0])]) + tup][11])

                                delete_event_id = aut2.resources1.slots[
                                    tuple([int(times[0])]) + tup][9]
                                if delete_event == 0:
                                    del_arr.append(delete_event_id)

                                start = slot_to_time(inte_start,
                                                     data['slot_length'])
                                end = slot_to_time(inte_end,
                                                   data['slot_length'])
                                start_date_original = datetime.datetime.strptime(
                                    date_original, "%Y-%m-%d")
                                start_day = math.floor(
                                    inte_start /
                                    (24 * 60 // data['slot_length'])
                                ) - datetime.datetime.strptime(
                                    date_original, '%Y-%m-%d').weekday() - 1
                                new_start = datetime.datetime.strftime(
                                    start_date_original +
                                    datetime.timedelta(days=start_day),
                                    "%Y-%m-%d")
                                new_end = datetime.datetime.strftime(
                                    start_date_original +
                                    datetime.timedelta(days=start_day + 1),
                                    "%Y-%m-%d")

                                for peep_id in intersection(
                                        users, people_list):
                                    people_appointments[peep_id].append({
                                        'start':
                                        f'{new_start}T{start}.000Z',
                                        'end':
                                        f'{new_start}T{end}.000Z',
                                        'startRecur':
                                        f'{new_start}T{start}.000Z',
                                        'endRecur':
                                        f'{new_end}T{end}.000Z',
                                        'address':
                                        address,
                                        'new_start':
                                        new_start
                                    })
                                if not scheduled:
                                    if (len(intersection(users, activity_list))
                                            > 0):
                                        activity = intersection(
                                            users, activity_list)[0]
                                        myobj = {
                                            'data': {
                                                'start':
                                                f'{new_start}T{start}.000Z',
                                                'end':
                                                f'{new_start}T{end}.000Z',
                                                'users':
                                                users,
                                                'activity0Id':
                                                activity,
                                                'notes':
                                                '',
                                                'frequency':
                                                'Weekly',
                                                'startRecur':
                                                f'{new_start}T{start}.000Z',
                                                'endRecur':
                                                f'{new_end}T{end}.000Z',
                                                'interval':
                                                1,
                                                'daysOfWeek': [
                                                    day_ids[(datetime.datetime.
                                                             strptime(
                                                                 new_start,
                                                                 '%Y-%m-%d').
                                                             weekday() + 1) %
                                                            7]
                                                ]
                                            }
                                        }
                                        returned_arr.append(myobj)
                                        if not data['optimize_curret']:
                                            host = data['host']
                                            response = requests.post(
                                                f'{host}/events',
                                                headers=data['header'],
                                                json=myobj)
                        response = requests.post(
                            f'{host}/events/remove/multiple',
                            headers=data['header'],
                            json={
                                "toBeDeletedIds": del_arr,
                                "pushNotification": {
                                    "send": False,
                                    "message": "",
                                    "to": []
                                }
                            })
                    # print('slifty',people_appointments)
                    distance_matrix_keys = aut2.distance_matrix.keys()
                    for id, arr in people_appointments.items():
                        arr_sorted = sorted(
                            arr,
                            key=lambda x: datetime.datetime.strptime(
                                x['start'], "%Y-%m-%dT%H:%M:%S.000Z"),
                            reverse=False)
                        for i in range(len(arr_sorted) - 1):
                            new_list = arr_sorted[i:i + 2]
                            address1 = new_list[0]['address']
                            address2 = new_list[1]['address']
                            if (address1 and address2 and len(address2) > 0
                                    and len(address1) > 0
                                    and address1 in distance_matrix_keys):
                                if (address2 in
                                        aut2.distance_matrix[address1].keys()
                                        and aut2.distance_matrix[address1]
                                    [address2][1]):
                                    drive_time = ceil_to_multiple(
                                        aut2.distance_matrix[address1]
                                        [address2][1] / 60.0,
                                        data['slot_length'])
                                    drive_time_slot = int(drive_time //
                                                          data['slot_length'])
                                    date_string = new_list[0]['end']
                                    date_object = datetime.datetime.strptime(
                                        date_string, '%Y-%m-%dT%H:%M:%S.%fZ')
                                    new_date = date_object + datetime.timedelta(
                                        minutes=drive_time)
                                    new_date_string = new_date.strftime(
                                        '%Y-%m-%dT%H:%M:%S.%fZ')
                                    # myobj = {
                                    #     'data': {
                                    #         'start':
                                    #         new_list[0]['end'],
                                    #         'end':
                                    #         new_date_string,
                                    #         'users': [id],
                                    #         'activity0Id':
                                    #         d["drive_id"],
                                    #         'notes':
                                    #         '',
                                    #         'frequency':
                                    #         'Weekly',
                                    #         'startRecur':
                                    #         new_list[0]['startRecur'],
                                    #         'endRecur':
                                    #         new_list[0]['endRecur'],
                                    #         'interval':
                                    #         1,
                                    #         'daysOfWeek': [
                                    #             day_ids[
                                    #                 (datetime.datetime.strptime(
                                    #                     new_list[0]['new_start'],
                                    #                     '%Y-%m-%d').weekday() + 1)
                                    #                 % 7]
                                    #         ]
                                    #     }
                                    # }
                                    # returned_arr.append(myobj)
                                    if not data['optimize_curret']:
                                        host = data['host']
                                        response = requests.post(
                                            f'{host}/events',
                                            headers=data['header'],
                                            json=myobj)
        # print('rett : ', returned_arr, objective_value)
        gc.collect()
        return {
            'returned_arr': returned_arr,
            'objective_value': objective_value,
            "status": status
        }

    def test_runner(self, data):
        aut_arr = []
        date_original = data['start_date']
        end_date_original = data['end_date']
        start_date_original = datetime.datetime.strptime(
            date_original, "%Y-%m-%d")
        r = []
        end_date = datetime.datetime.strftime(
            start_date_original +
            datetime.timedelta(days=data['day_increment']), "%Y-%m-%d")

        if data['part1']:
            some_arr_of_data = []
            for team in data['teams']:
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                for res in data['resource_array']:
                    if 'Person' not in res['roles'] or team in res['branches']:
                        resources_team.append(res)
                for res in data['resource_array']:
                    if 'Person' in res['roles'] and team in res['branches']:
                        resource_id_team.append(f'{res["id"]}a')
                    if 'Person' in res['roles'] and team not in res['branches']:
                        resource_id_team_not.append(f'{res["id"]}a')
                for dat in data['actual_data']:
                    if len(
                            intersection(dat['resourceIds'],
                                         resource_id_team_not)) == 0:
                        data2_team.append(dat)
                d = {
                    'objectiveactivity': data["objectiveactivity"],
                    'start_date_original': start_date_original,
                    'resources_team': resources_team,
                    'data': data,
                    'date_original': date_original,
                    'data2_team': data2_team,
                    'aut_arr': aut_arr
                }
                some_arr_of_data.append(d)

            with ThreadPoolExecutor() as executor:
                results = executor.map(self.test_insert, some_arr_of_data)
                for result in results:
                    print('multi_res : ', result)

            # results = []
            # for team in some_arr_of_data:
            #     results.append(test_insert(team))
            # # with ThreadPoolExecutor() as executor:
            # #     results = executor.map(test_insert, some_arr_of_data)
            #     for result in results:
            #         print('multi_res : ', result)

        else:
            for team in range(1):
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                scheduled_ids = []
                k = []
                for res in data['resource_array']:
                    if 'Person' not in res['roles'] or True:
                        resources_team.append(res)
                for res in data['resource_array']:
                    if 'Person' in res['roles'] and True:
                        resource_id_team.append(f'{res["id"]}a')
                    if 'Person' in res['roles'] and True:
                        resource_id_team_not.append(f'{res["id"]}a')
                for dat in data['actual_data']:
                    if len(
                            intersection(dat['resourceIds'],
                                         resource_id_team_not)) == 0 or True:
                        data2_team.append(dat)
                d = {
                    'objectiveactivity': data["objectiveactivity"],
                    'start_date_original': start_date_original,
                    'resources_team': resources_team,
                    'data': data,
                    'date_original': date_original,
                    'data2_team': data2_team,
                    'aut_arr': aut_arr
                }
                r.append(self.test_insert(d))
        return r

    def rocket(self, dict_data):
        d1 = datetime.datetime.strptime(dict_data['end_date'], "%Y-%m-%d")
        d2 = datetime.datetime.strptime(dict_data['start_date'], "%Y-%m-%d")

        delta = d1 - d2
        num_of_days = int(delta.days) + 1
        start = dict_data['start_date']
        end = dict_data['end_date']
        d = {
            'num_of_days': num_of_days,
        }
        d.update(dict_data)

        some_data = Get_Data(d)

        print()

        arr = []
        # print('snowman  :', some_data.get_resources())
        for i in some_data.get_resources():
            a = {
                "id": i['id'],
                "name": i['name'],
                "title": i['title'],
                "resourceTypeId": i['resourceTypeId'],
                "type": i['type'],
                "roles": i['roles'],
                "waitlisted": i['waitlisted'],
                "subgroups": i['subgroups'],
                "branches": i['branches'],
                "address": i['address'],
                "capacity": i['capacity'],
                "birthday": i['birthday'],
                "color": i['color'],
                "location_type": i['location_type']
            }
            arr.append(a)
        time_const = []
        if dict_data["is_time_constraint"]:
            time_const = Time_Constraint_Handler(d).get_time_cons_arr()
        roles_hierarchy = some_data.get_roles_hierarchy()
        distance_matrix = some_data.get_distance_matrix()
        e_pair = []  # some_data.get_event_pair()

        deleted_events = []
        regenerated_events = []
        if not dict_data['daily']:
            m_arr = some_data.get_direct_activities()
            ar = []

            events_arr = some_data.get_events()
            for i in m_arr:
                ar = ar + i
            n_arr = m_arr
            for i in range(len(events_arr)):
                n_arr[i] = n_arr[i] + events_arr[i]
            gap_fill = gap_filler_2(n_arr, some_data.get_resources(),
                                    dict_data["slot_length"])
            gapp_arr = []
            for i in gap_fill:
                ar = ar + i
                gapp_arr.append(i)

            for i in events_arr:
                ar = ar + i
            ar = [
                *self.solutions1.events_poss, *self.solutions1.events2,
                *gapp_arr
            ]
            aa = {
                'day_increment': num_of_days,
                'teams': dict_data['teams'],
                'resource_array': arr,
                'actual_data': ar,
                'roles_hierarchy': roles_hierarchy,
                'time_cons': time_const,
                'distance_matrix': distance_matrix,
                'header': dict_data['header'],
                "e_pair": e_pair
            }
            aa.update(dict_data)
            regenerated_events.append(self.test_runner(aa))
        else:
            arr_of_data = []
            sd = dict_data['start_date']

            for i in some_data.get_direct_activities():
                arr_of_data.append(i)

            x = len(arr_of_data)
            xyz = some_data.get_events()
            some_tuples = []
            for i in range(0, x):
                xy = remove_randomly(xyz[i], dict_data["objectiveactivity"],
                                     dict_data["lunch_id"], 0)
                data = arr_of_data[i] + xy[0]
                deleted_events.append(xy[1])
                a = {
                    'start_date': sd,
                    'day_increment': 1,
                    'teams': dict_data['teams'],
                    'resource_array': arr,
                    'actual_data': data,
                    'roles_hierarchy': roles_hierarchy,
                    'distance_matrix': distance_matrix,
                    'time_cons': time_const,
                    'header': dict_data['header'],
                    "e_pair": e_pair
                }
                a.update(dict_data)
                some_tuples.append(a)
                sd = datetime.datetime.strptime(sd, "%Y-%m-%d")
                sd = datetime.datetime.strftime(
                    sd + datetime.timedelta(days=1), "%Y-%m-%d")

            if dict_data['is_Multi']:
                with ThreadPoolExecutor() as executor:
                    results = executor.map(self.test_runner, some_tuples)
                    for result in results:
                        regenerated_events.append(result)

            else:
                for tup in some_tuples:
                    regenerated_events.append(self.test_runner(tup))
        # print("some_data : ", [regenerated_events, deleted_events])
        return [regenerated_events, deleted_events]

    def part1(self):
        dd = self.data
        sd = dd['start_date']
        ed = dd['end_date']
        ed = datetime.datetime.strptime(ed, "%Y-%m-%d")
        ed = datetime.datetime.strftime(ed + datetime.timedelta(days=1),
                                        "%Y-%m-%d")
        host = dd['host']
        dd['max_time_in_seconds'] = 90.0
        if len(dd["teams"]) == 0 or True:
            dd['part1'] = False
        dd["percentage"] = 0
        res = requests.delete(
            f'{host}/scheduler/eventDelete?start={sd}&end={ed}&password=e635dgndd88473g7d',
            headers=dd['header'])
        dd['is_events'] = True
        dd["optimize_curret"] = False
        dd["is_noGap_constraint"] = True
        dd["is_lunch_constraint"] = True
        dd['is_lunch'] = True
        dd['daily'] = False
        dd["is_orange"] = False
        self.rocket(dd)
        # if dd["objective_role"] == "R/BT":
        #     dd["is_orange"] = True
        #     dd['part1'] = False
        #     dd["percentage"] = 35
        #     dd['is_events'] = True
        #     rocket(dd)
        # a = dd
        # a['part1'] = False
        # a["percentage"] = 0
        # a['is_noGap_constraint'] = True
        # a['max_time_in_seconds'] = 55.0
        # a['is_team_constraint'] = False
        # a["is_lunch_constraint"] = True
        # a["is_break_constraint"] = False
        # a['is_lunch'] = True
        # a["is_minSession_constraint"] = True
        # a["is_orange"] = True
        # rocket(a)

    def part2(self, some_data):
        data = some_data
        data['is_noGap_constraint'] = True
        data['daily'] = False
        data['is_events'] = False
        host = data['host']
        sd = data['start_date']
        ed = data['end_date']
        data["slot_length"] = 15
        data["max_session_length"] = data["max_session_length"]
        data['part1'] = False
        data['min_session_dur'] = 60
        data["is_minSession_constraint"] = True
        data['max_time_in_seconds'] = 60.0
        data["optimize_curret"] = False
        data["is_orange"] = False
        data["is_lunch"] = True
        data["is_lunch_constraint"] = True
        self.rocket(data)
        return {
            "regen_data": "",
            "deleted_evets": "",
            "status": "",
            "hours_increment": ""
        }


def rocket_luncher(dd, solutions1):
    # d1 = datetime.datetime.strptime(dd['end_date'], "%Y-%m-%d")
    # d2 = datetime.datetime.strptime(dd['start_date'], "%Y-%m-%d")
    # delta = d1 - d2
    # num_of_days = int(delta.days) + 1
    # s_date = datetime.datetime.strptime(dd["start_date"], "%Y-%m-%d")
    # for i in range(num_of_days):
    #     aa = dd
    #     aa["end_date"] = datetime.datetime.strftime(
    #         s_date + datetime.timedelta(days=i), "%Y-%m-%d")
    #     aa["start_date"] = datetime.datetime.strftime(
    #         s_date + datetime.timedelta(days=i), "%Y-%m-%d")
    rock = Rocket(dd, solutions1)
    if dd['part1']:
        rock.part1()
    else:
        return rock.part2(dd)
    gc.collect()
