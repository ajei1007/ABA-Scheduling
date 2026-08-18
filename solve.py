# Adam Silver
from ortools.sat.python import cp_model
import itertools
import threading
from itertools import combinations, product
import time
import datetime
from datetime import timezone
import numpy as np
import math
from get_data import Get_Data
from itertools import zip_longest
import json
from concurrent.futures import ThreadPoolExecutor
import copy
import uuid
import builtins
from external import haversine, dict_priority, round_to_nearest_interval, detect_range,debug_mode
from calculate_drive_time import *


def intersection(lst1, lst2):  # gets intersection of two lists
    return [value for value in lst1 if value in lst2]


class Constraint:
    def __init__(self, info):
        self.max = info['max']
        self.min = info['min']
        self.frequency = info['frequency']
        self.constraint = info['constraint']
        self.days = info['days']
        pass


class Resource:
    def __init__(self, info, index):
        self.name = info['name']
        self.id = info['id']
        self.roles = info['roles']
        self.waitlisted = info['waitlisted']
        self.notWorking = info["notWorking"]
        self.matches = {}
        self.matches2 = {}
        self.onlyUserToUser = {}
        self.onlyUserToSession = {}
        self.work_together_arr = {}
        self.sessions_together_arr = {}
        self.time_with_users = {}
        self.events = []
        self.total_time = 0
        self.time_constraints = {'session': {}, 'day': {}, 'week': {}}
        self.time_so_far = 0
        self.rec_time = 0
        self.max_time_obj = {}
        self.slots = {}
        self.activities = {}
        self.index = index


class Resources:
    def __init__(self, resources):
        self.resources = {}
        self.roles = {}
        self.events = []
        self.appointments = []
        self.frequency_constraints = []
        self.drive_constraints = []
        self.onlyUserToUser = {}
        self.onlyUserToSession = {}
        self.slots = {}
        for index, resource in enumerate(resources):
            new_resource = Resource(resource, index)
            self.resources[index] = new_resource


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables, limit):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0
        self.all_solutions = {}
        self.all_priorities = {}
        self.all_blocks = {}
        self.all_solutions_constraints = {}
        self.__solution_limit = limit

    def on_solution_callback(self):
        self.__solution_count += 1
        arr = []
        assignments = self.__variables[0]
        slot = self.__variables[1]
        constraints = self.__variables[2]
        priority = self.__variables[3]
        block = self.__variables[4]
        users = self.__variables[5]
        constraints_values = []
        for key, v in assignments.items():
            pass
            value = self.Value(v)
            if value == 1:
                # print('%s=%i' % (v, value), end=' ')
                # print('%i' % (key), end=' ')
                # print(users[key]['name'])
                arr.append(key)

        tuple_arr = tuple(arr)
        slot_value = self.Value(slot)

        priority_value = self.Value(priority)
        block_value = self.Value(block)
        if self.__solution_count >= self.__solution_limit:
            print(f"Stop search after {self.__solution_limit} solutions")
            self.StopSearch()
        for c in constraints:
            value = self.Value(c)
            if (value) == 1:
                # print('soomy', str(c))
                constraints_values.append({"reason": str(c)})
        if (tuple_arr in self.all_solutions.keys()):
            self.all_solutions[tuple_arr].append(slot_value)
            if (slot_value
                    in self.all_solutions_constraints[tuple_arr].keys()):
                self.all_solutions_constraints[tuple_arr][
                    slot_value] = constraints_values
            else:
                self.all_solutions_constraints[tuple_arr][
                    slot_value] = constraints_values

        else:
            self.all_solutions[tuple_arr] = [slot_value]
            self.all_priorities[tuple_arr] = priority_value
            self.all_blocks[tuple_arr] = block_value
            self.all_solutions_constraints[tuple_arr] = {
                slot_value: constraints_values
            }
        print()

    def solution_count(self):
        return self.__solution_count


class VarArraySolutionPrinter2(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables, events_poss, events_poss_raw, resources1,
                 is_investigate):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__events_poss = events_poss
        self.__solution_count = 0
        self.all_solutions = []
        self.events_poss_raw = events_poss_raw
        self.resources1 = resources1
        self.is_investigate = is_investigate

    def on_solution_callback(self):
        self.__solution_count += 1
        for key, v in enumerate(self.__variables):
            value = self.Value(v[5])
            if value == 1:
                self.all_solutions.append(self.__events_poss[key])
            elif self.is_investigate:
                info = self.events_poss_raw[key]
                resource_list = info["resourceIds"]
                start_int = info['start']
                reasons = self.resources1.slots[tuple([start_int]) +
                                                tuple(resource_list)][7]
                self.all_solutions.append({
                    **self.__events_poss[key], 'reasons':
                    [*reasons, *self.__events_poss[key]['reasons']]
                })

    def solution_count(self):
        return self.__solution_count

class Data_Gatherer:
    def __init__(self, dict_data):
        self.dd_data = dict_data
        self.branch_id = dict_data['branch']
        self.start_date = dict_data["start_date"]
        self.end_date = dict_data["end_date"]
        self.settings = dict_data['settings']
        self.isolatedResources = dict_data.get('isolatedResources',[])
        self.home_id = dict_data["home_id"] if "home_id" in dict_data else ""
        self.expanded_resources = dict_data["expanded_resources"]
        self.resourceCombinationsExclude = dict_data.get("resourceCombinationsExclude", [])
        self.expanded_resources_filter = dict_data.get("expanded_resources_filter", [])
        self.onCall = dict_data.get("onCall", False)
        d1 = datetime.datetime.strptime(dict_data['end_date'], "%Y-%m-%d")
        d2 = datetime.datetime.strptime(dict_data['start_date'], "%Y-%m-%d")
        self.flags_data = {}
        self.distance_matrix = {}
        delta = d1 - d2
        time1 = time.time()
        d = {
            'objectiveactivity': '',
            'lunch_id': '',
            'break_id': '',
            'num_of_days': int(delta.days),
            'blocks': '',
            'is_lunch': '',
            'is_break': '',
            'is_orange': '',
            'is_events': '',
        }
        d.update(dict_data)
        some_data = Get_Data(d)
        self.some_data = some_data
        print("some data:", some_data)
        get_data_arr = []
        method_names = [
            'get_availability', 
            'get_capacities', 'get_subgroups',
            #'get_subgroups_raw_data', 
            'get_custom_constraints',
            'get_branch_structure', 'get_event_pair', 'get_events2',"get_branches","get_location_raw_data","get_activity_table"
                # 'get_flags'
        ]
        results = [True] * len(method_names)

        def call_method(method, index):
            result = method()
            results[index] = result

        threads = []
        # For Sync Results:
        for i, method_name in enumerate(method_names):
            method = getattr(some_data, method_name)
            t = threading.Thread(target=call_method, args=(method, i))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()


        # print("Gathering data from backend:", results[1])
            
        self.availabilities = results[0]
        # print("baza_availabilities_baz : ",self.availabilities)
        time2 = time.time()
        # print('Timer availabilty_time: ', time2-time1)
        # print("bazo__result: ",results)
        self.users = results[6][0]
        print("activity data table:", results[9])
        # print("bazo_admin2",self.users)
        time3 = time.time()
        # print('Timer resource_time: ', time3-time2)
        # print('soolies', self.users)
        # self.funders = results[2]
        time4 = time.time()
        # print('Timer funder_time: ', time4-time3)
        self.capacities = results[1]
        time5 = time.time()
        # print('Timer capacity_time: ', time5-time4)
        # self.groupings = results[4]
        time6 = time.time()
        # print('Timer groupings_time: ', time6-time5)
        self.subgroups = results[2]
        time7 = time.time()
        # print('Timer subgroups_time: ', time7-time6)
        # self.person_raw_data = results[6]
        # time8 = time.time()
        # # print('Timer person_raw_time: ', time8-time7)
        self.location_raw_data = results[8]
        # print("bb_raw_loc : ",self.location_raw_data)
        self.activity_table = results[9]
        # time9 = time.time()
        # print('Timer location_raw_time: ', time9-time8)
        #self.subgroups_raw_data = results[3]
        time10 = time.time()
        # print('Timer subgroups_time: ', time10-time9)
        self.custom_constraints = results[3]
        # print("custom_solve_py : ", results[3])
        time11 = time.time()
        # print('Timer custom_constraints_time: ', time11-time10)
        # self.branches = results[10]
        # time12 = time.time()
        # print('Timer branches_time: ', time12-time11)
        # print('gloophies', self.branches)
        self.branch_structure = results[4]
        self.e_pair = results[5]
        time13 = time.time()
        # print('Timer get_b_structure_time: ', time13-time12)
        self.events = []
        self.events2 = []
        ev = results[6][1]
        self.branches = results[7]
        print('gathering events:', results[6])
        # self.flags_data = results[14]
        # print('smooshie', ev)
        # print('bazo_flags : ', self.flags_data)
        if ev is None:
            ev = []
        time14 = time.time()
        # print('Timer events_time: ', time14 - time13)
        for sublist in ev:
            for element in sublist:
                self.events2.append(element)
        if 'is_events' not in dict_data.keys() or dict_data['is_events']:
            # print('seemlah')
            # ev = some_data.get_events(False, True)
            ev = results[6][1]
            for sublist in ev:
                for element in sublist:
                    if "part1" not in dict_data.keys():
                        self.events.append(element)
                    else:
                        if dict_data["part1"]:
                            self.events.append(element)
                    # self.events2.append(element)
        endtime = time.time()

        # print('here we go: ', time14 - time1)


class Solution_Generator:
    def __init__(self, dict_data, more_data):
        # print("bazo_dict_data : ", dict_data)
        # print("bazo_dict_data : ", dict_data.dd_data)
        # print("bazo_dict_data2 : ", more_data)
        self.optimizer_or_not = dict_data.dd_data["optimizer_sol"]
        self.highPriority = dict_data.dd_data["highPriority"]
        self.header = dict_data.dd_data["header"]
        self.drive_time_on = dict_data.dd_data["settings"]["driveTime"]
        self.host = dict_data.dd_data["host"]
        #self.notWorking = dict_data.dd_data["notWorking"]
        self.start_date = dict_data.start_date
        self.onCall = dict_data.onCall
        self.branch_id = dict_data.branch_id
        print('tupper',self.branch_id)
        self.isolatedResources = dict_data.isolatedResources
        print('soomer',self.isolatedResources)

        self.slot_length = max(5, min(dict_data.settings.get('timeInterval', 15),15))
        # print('sommer2',self.slot_length)
        self.end_date = dict_data.end_date
        self.settings = dict_data.settings
        self.expanded_resources = dict_data.expanded_resources
        self.expanded_resources_filter = dict_data.expanded_resources_filter
        self.resourceCombinationsExclude = dict_data.resourceCombinationsExclude
        self.distance_matrix = dict_data.distance_matrix
        d1 = datetime.datetime.strptime(dict_data.end_date, "%Y-%m-%d")
        d2 = datetime.datetime.strptime(dict_data.start_date, "%Y-%m-%d")
        delta = d1 - d2
        self.soft = more_data['soft']
        self.is_session = True
        if 'is_session' in more_data.keys():
            self.is_session = more_data['is_session']
        self.is_orange = more_data['is_orange']
        if 'investigate' in more_data.keys():
            self.investigate = more_data['investigate']
        else:
            self.investigate = []
        self.is_investigate = len(self.investigate) > 0

        d = {
            'objectiveactivity': '',
            'lunch_id': '',
            'break_id': '',
            'num_of_days': int(delta.days),
            'blocks': '',
            'is_lunch': '',
            'is_break': '',
            'is_orange': '',
            'is_events': '',
        }
        self.user_availabilities_general = {}
        self.user_solutions_array_unit = {}
        self.user_solutions_array_total = {}
        self.availabilities = dict_data.availabilities
        self.activity_table = dict_data.activity_table
        self.users = dict_data.users
        # self.funders = dict_data.funders
        self.capacities = dict_data.capacities
        self.branches = dict_data.branches
        self.e_pair = dict_data.e_pair
        # self.groupings = dict_data.groupings
        self.subgroups = dict_data.subgroups
        # self.person_raw_data = dict_data.person_raw_data
        #self.subgroups_raw_data = dict_data.subgroups_raw_data
        self.location_raw_data = dict_data.location_raw_data
        self.home_id = dict_data.home_id
        self.flags = dict_data.flags_data
        self.created_events = []
        self.limit_coefficient = 10
        self.conflicted_constraints = {}
        self.debug_booleans = debug_mode() # This is for printing things if debug mode is activated
        if not self.is_investigate:
            if self.soft and dict_data.custom_constraints:
                # print('cloovy', dict_data.custom_constraints)
                self.custom_constraints = list(
                    filter(lambda x: not x['soft'],
                           dict_data.custom_constraints))
            else:
                self.custom_constraints = dict_data.custom_constraints
        else:
            self.custom_constraints = dict_data.custom_constraints
        self.custom_constraints = [cus for cus in self.custom_constraints if cus["id"] in self.highPriority]
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

    def time_to_slot(self, t, day, minutes):
        x = time.strptime(t, '%H:%M:%S')
        output = datetime.timedelta(
            hours=x.tm_hour, minutes=x.tm_min,
            seconds=x.tm_sec).total_seconds() / 60 / minutes
        output = int(day * 24 * 60 / minutes + output)
        return output

    def slot_to_time(self, slot, slot_interval):
        # slot : int , 0 < slot_interval : int <= 60
        slots_per_day = 24 * 60 // slot_interval
        slots_per_hour = 60 // slot_interval
        hours = str((slot % slots_per_day) // slots_per_hour).zfill(2)
        minutes = str(
            (slot % slots_per_day % slots_per_hour) * slot_interval).zfill(2)
        seconds = '00'
        return hours + ':' + minutes + ':' + seconds

    def calc_availabilities(self,start_time,end_time,format,timezone_bol=True):
        
        start = datetime.datetime.strptime(start_time, format)
        end = datetime.datetime.strptime(end_time, format)
        # print("Calculating_bazo : ",start_time,end_time,start,end)

        if timezone_bol:
            start = start.astimezone(timezone.utc)
            end = end.astimezone(timezone.utc)

        interval_start = self.time_to_slot(start.strftime('%H:%M:%S'),
                                           (start.weekday()), 15//(15//self.slot_length))
        interval_end = self.time_to_slot(end.strftime('%H:%M:%S'),
                                         (end.weekday()), 15//(15//self.slot_length))
        # interval_start = interval_start - 32
        # interval_end = interval_end - 32
        
        if interval_end < interval_start:
            interval_end = 672
        # if interval_start > 672:
        #     interval_start = interval_start - 672
        # if interval_end > 672:
        #     interval_end = interval_end - 672
        # if interval_start > interval_end:
        #     interval_start = interval_start - 672 + 96
        
        # print("bazo_all_bugs : ",interval_start,interval_end)
        return [i for i in range(interval_start, interval_end)]

    def get_user_ids(self, role_name, type_str='roles'):
        indexes = set()
        for i, user in enumerate(self.users):
            if role_name in user[type_str]:
                indexes.add(i)
        return indexes

    def get_index_of_id(self, id):
        for i, user in enumerate(self.users):
            if id == user["id"]:
                return i
        return None

    def detect_range(self, l):
        l.sort()
        # print("bazo_lll  : ",l)
        for i, j in itertools.groupby(enumerate(l), lambda x: x[1] - x[0]):
            j = list(j)
            yield j[0][1], j[-1][1] + 1

    def convert_index_to_slot(self, l):
        arr = []
        for i, n in enumerate(l):
            if n == 1:
                arr.append(i)
        return arr

    def find_users_from_roles_subgroups(self, t):
        users = []
        for i, user in enumerate(self.users):
            bol = True
            for r in t:
                # print('lokky', r, user['name'], user['subgroups_real'],
                #       user['roles'], user['branches_real'])
                if not (r in user['roles'] or r in user['subgroups_real']
                        or r in user['branches_real']):
                    bol = False
                    break
            if bol:
                users.append(i)
        # print("bazo_dubb : ", len(users), len(set(users)))
        return users

    def handle_general_constraint_type(self, roles, subgroups, branches):
        arr = []
        # p = list(*product(*roles))
        # print('loogy', p)
        # if len(p) > 0:
        #     arr.append(p)
        # t = list(*product(*subgroups))
        # if len(t) > 0:
        #     arr.append(t)
        # o = list(*product(*branches))
        # if len(o) > 0:
        #     arr.append(o)

        p = list(product(*roles))
        # print('loogy', p)
        if len(p) > 0:
            arr.append(p)
        t = list(product(*subgroups))
        if len(t) > 0:
            arr.append(t)
        o = list(product(*branches))
        # print('sloopy', p, t, o)
        if len(o) > 0:
            arr.append(o)
        users = []
        # for i in list(product(*arr)):
        # print('siver1', list(product(*p, *t)), list(product(*p, *t, *o)))
        for i in list(product(*p, *t)):
            # print('siver2', i)
            users = [*users, *self.find_users_from_roles_subgroups(i)]
        return list(set(users))

    def handle_general_constraint_specific(self, users1):
        # print("bbb_d : ",list(product(*users1)))
        return list(product(*users1))

    def handle_general_constraint_specific_index(self, users1):
        arr = list(product(*users1))
        arr = np.array(
            list(
                map(
                    lambda x: list(
                        map(
                            lambda y: self.user_uuid_to_index[y],
                            filter(
                                lambda num: num in self.
                                user_uuid_to_index_keys, x))), arr)))
        # print('simmter', arr.flatten())
        return arr.flatten()

    def get_resources_from_role(self, roles):  # got it
        resources_ids = []
        # print('snifter',self.resources1.resources)
        for id, resource in self.resources1.resources.items():
            bol = False
            for resource_role in roles:
                # print('history', resource_role, resource.roles)
                if resource_role in resource.roles:
                    bol = True
            if bol:
                resources_ids.append(id)
        # print("bazo_dub : ", len(resources_ids), len(list(set(resources_ids))))
        return list(set(resources_ids))

    def get_appointments(self, arr, slots_bol=True, slots={}):
        obj = {}
        if slots_bol:
            slots = self.resources1.slots
        for tup, event in slots.items():
            resources_ids = list(tup)
            # print('leavy', resources_ids, arr)
            bol = True
            for resources in arr:
                if len(intersection(resources, resources_ids)) == 0:
                    bol = False
                    break
            if bol:
                obj[tup] = event
        return obj

    def get_id_from_role_array(self, role, resourceIds_r):
        loc_id = -1
        for res in resourceIds_r:
            if role in self.users[res]['roles']:
                loc_id = res
                break
        return loc_id

    def turn_uuid_array_into_index(self, resourceIds):
        arr = []
        for res in resourceIds:
            if res in self.user_uuid_to_index_keys:
                res_index = self.user_uuid_to_index[res]
                arr.append(res_index)
        # print("bazo_index : ",len(arr),len(set(arr)))
        return arr

    def main_drive_time(self):
        #gets distance matrix data
        constraint_drive_data_new = get_drive_time_data(self.header,self.host)
        # debug_main_drive_time = self.debug_booleans["main_drive_time"] if "main_drive_time" in self.debug_booleans.keys() else False
        debug_main_drive_time = True
        new_events_poss = []

        for i, event in enumerate(self.events):
            resourceIds = event['resourceIds']
            for res in resourceIds:
                if res in self.user_uuid_to_index_keys:
                    index = self.user_uuid_to_index[res]
                    self.resources1.resources[index].events.append(i)
                    # print('sivly')
        # print("bazo_drive_time_users: ",self.users) if debug_main_drive_time else None
        for ev in self.events_poss:
            start_drive = 0
            end_drive = 0
            person_drive = {}
            resourceIds_r = ev['resourceIds_r']
            start = datetime.datetime.strptime(ev['start'],
                                               '%Y-%m-%dT%H:%M:%S.%fZ')
            end = datetime.datetime.strptime(ev['end'],
                                             '%Y-%m-%dT%H:%M:%S.%fZ')
            newest_event = copy.copy(ev)
            loc_id = self.get_id_from_role_array('Location', resourceIds_r)
            loc_arr = []
            for user_k in self.users:
                # print("bb_bazo: ",user_k)
                if "roles" in user_k:
                    if "Location" in user_k["roles"]:
                        loc_arr.append(user_k["id"])
            # print("bazo_loc_loc_arr :",set(loc_arr))
            loc_arr = list(set(loc_arr))
            if loc_id >= 0:
                loc_address = self.users[loc_id]['address']
                loc_name = self.users[loc_id]['firstName']
                for res in resourceIds_r:
                    if 'Person' in self.users[res]['roles']:
                        if 'fake' in ev.keys():
                            print('loojy3',res,self.resources1.resources[res].events)
                        end_time = []
                        start_time = []
                        lower_delta = 100000000
                        upper_delta = 100000000
                        if self.resources1.resources[res].events:
                            for e in self.resources1.resources[res].events:
                                event = self.events[e]
                                event_loc_id = event["loc_id"]
                                #************************************************************************************************
                                all_resource_ids = event['resourceIds'] + [i[:-1] for i in ev["resourceIds"]]
                                my_client_ids = []
                                for ii in all_resource_ids:
                                    if ii in self.user_uuid_to_index_keys:
                                        index_c = self.user_uuid_to_index[ii]
                                        if 'Client' in self.users[index_c]['roles']:
                                            my_client_ids.append(ii)
                                #************************************************************************************************
                                arr_persons = sorted(list(set([i for i in my_client_ids if not i is None])))
                                if len(arr_persons) == 1:
                                    if arr_persons[0] in event["resourceIds"]:
                                        if event_loc_id in [i[:-1] for i in ev["resourceIds"]]:
                                            continue
                                        arr_persons = sorted(list(set(arr_persons + intersection([i[:-1] for i in ev["resourceIds"]], loc_arr))))
                                    else:
                                        if event_loc_id in [i[:-1] for i in ev["resourceIds"]]:
                                            continue
                                        arr_persons = sorted(list(set(arr_persons + intersection(event["resourceIds"], loc_arr))))
                                if len(arr_persons) == 0:
                                    continue
                                print("bazo_persons : ",arr_persons,self.users[res]["id"]) if debug_main_drive_time else None
                                start_here = datetime.datetime.strptime(
                                    event['start'], '%Y-%m-%dT%H:%M:%S.%fZ')
                                end_here = datetime.datetime.strptime(
                                    event['end'], '%Y-%m-%dT%H:%M:%S.%fZ')
                                if start_here > end or end_here < start:
                                    print("bazo_continued1")
                                    continue
                                delta1 = (start - end_here).total_seconds()
                                delta2 = (start_here - end).total_seconds()
                                loc_address2 = event['address']
                                loc_address = ev['address']
                                #loc_address = self.users[self.user_uuid_to_index[arr_persons[0]]]["address"]
                                #loc_address2 = self.users[self.user_uuid_to_index[arr_persons[1]]]["address"]
                                if loc_address is not None and loc_address2 is not None and len(loc_address)>0 and len(loc_address2)>0:
                                    arr_addresses = tuple(sorted([loc_address,loc_address2]))
                                    arr_addresses2 = tuple(sorted([loc_address,loc_address2],reverse=True))
                                    print('addresses',arr_addresses,arr_addresses2)
                                    if loc_address2:
                                        print('bazo_loc_ids : ', loc_address2,loc_address) if debug_main_drive_time else None
                                        pass
                                    print("bazo_ev_title : ",ev['title'])
                                    delta1_condition = delta1 >= 0 and delta1 < lower_delta
                                    delta2_condition = delta2 >= 0 and delta2 < upper_delta
                                    if loc_address != loc_address2:
                                        print("bazo_not_equal : ",arr_persons) if debug_main_drive_time else None
                                        if delta1 < 0:
                                            pass
                                        if delta1_condition or delta2_condition:
                                            print("bazo_delta1 : True") if debug_main_drive_time else None
                                            if delta1_condition:
                                                lower_delta = delta1
                                            if delta2_condition:
                                                upper_delta = delta2
                                            if arr_addresses in constraint_drive_data_new.keys():
                                                if not constraint_drive_data_new[arr_addresses] is None:
                                                    if delta1_condition:
                                                        start_drive = round_to_nearest_interval(constraint_drive_data_new[arr_addresses]['mid']//60,self.slot_length)
                                                        print('soomty',start_drive)
                                                    if delta2_condition:
                                                        end_drive = round_to_nearest_interval(constraint_drive_data_new[arr_addresses]['mid']//60,self.slot_length)

                                                else:
                                                    if delta1_condition:
                                                        start_drive = 0
                                                    if delta2_condition:
                                                        end_drive = 0
                                            else:
                                                #result_distance_dur_early = return_interval_drive_time(address1, address2,8,30)
                                                print('address9',loc_address)
                                                print('address11',loc_address2)
                                                result_distance_dur_early = return_interval_drive_time(loc_address, loc_address2,11,30)
                                                result_distance_dur_early_reverse = result_distance_dur_early
                                                #result_distance_dur_early_reverse = return_interval_drive_time(loc_address2, loc_address,8,30)
                                                if result_distance_dur_early != [0,0]:
                                                    result_distance_dur_mid = result_distance_dur_early
                                                    result_distance_dur_late = result_distance_dur_early
                                                    #result_distance_dur_mid = return_interval_drive_time(loc_address, loc_address2,11,30)
                                                    #result_distance_dur_late = return_interval_drive_time(loc_address, loc_address2,5,30)
                                                    result_distance_dur_mid_reverse = result_distance_dur_mid
                                                    result_distance_dur_late_reverse = result_distance_dur_late
                                                    #result_distance_dur_mid_reverse = return_interval_drive_time(loc_address, loc_address2,11,30)
                                                    #result_distance_dur_late_reverse = return_interval_drive_time(loc_address, loc_address2,5,30)
                                                    post_drive_time_data(self.header,{
                                                        "data" :{
                                                            "address1": loc_address,
                                                            "address2":loc_address2,
                                                            "duration": result_distance_dur_mid[1],
                                                            "duration_early": result_distance_dur_early[1],
                                                            "duration_late": result_distance_dur_late[1],
                                                            "distance": result_distance_dur_early[0],
                                                            }
                                                    },self.host)
                                                    post_drive_time_data(self.header,{
                                                        "data" :{
                                                            "address1": loc_address2,
                                                            "address2":loc_address,
                                                            "duration": result_distance_dur_mid_reverse[1],
                                                            "duration_early": result_distance_dur_early_reverse[1],
                                                            "duration_late": result_distance_dur_late_reverse[1],
                                                            "distance": result_distance_dur_early_reverse[0],
                                                            }
                                                    },self.host)
                                                if not result_distance_dur_mid[1] is None:
                                                    constraint_drive_data_new[arr_addresses] = {"early": result_distance_dur_early[1],"mid":result_distance_dur_mid[1],"late":result_distance_dur_late[1]}
                                                    constraint_drive_data_new[arr_addresses2] = {"early": result_distance_dur_early_reverse[1],"mid":result_distance_dur_mid_reverse[1],"late":result_distance_dur_late_reverse[1]}
                                                    if delta1_condition:
                                                        start_drive = round_to_nearest_interval(result_distance_dur_mid[1]//60,self.slot_length)
                                                    if delta2_condition:
                                                        end_drive = round_to_nearest_interval(result_distance_dur_mid[1]//60,self.slot_length)
                                                else:
                                                    if delta1_condition:
                                                        start_drive = 0
                                                    if delta2_condition:
                                                        end_drive = 0
                                            person_drive = {**person_drive, self.users[res]['id']:{'start':start_drive,'end':end_drive}}
                                                    
                                        # elif delta2 >= 0 and delta2 < upper_delta:
                                        #     print("bazo_delta2 : True") if debug_main_drive_time else None
                                        #     upper_delta = delta2
                                        #     if arr_addresses in constraint_drive_data_new.keys():
                                        #         if not constraint_drive_data_new[arr_addresses] is None:
                                        #             end_drive = constraint_drive_data_new[arr_addresses]["mid"]//60
                                        #         else:
                                        #             end_drive = 0
                                        #     else:
                                        #         result_distance_dur = return_interval_drive_time(self.users[self.user_uuid_to_index[arr_persons[0]]]['address'], self.users[self.user_uuid_to_index[arr_persons[1]]]['address'],return_ten_time())
                                        #         print("bazo_drive_result :" , result_distance_dur) if debug_main_drive_time else None
                                        #         if result_distance_dur != [0,0]:
                                        #             post_drive_time_data(self.header,{
                                        #                 "data" :{
                                        #                     "duration": result_distance_dur[1],
                                        #                     "distance": result_distance_dur[0],
                                        #                     "user1" : arr_persons[0],
                                        #                     "user2" : arr_persons[1],
                                        #                     }
                                        #             },self.host)
                                        #         if not result_distance_dur[1] is None:
                                        #             constraint_drive_data_new[arr_addresses] = result_distance_dur[1]
                                        #             end_drive = result_distance_dur[1]//60
                                        #         else:
                                        #             end_drive = 0

           
            new_start = newest_event['start']
            new_end = newest_event['end']
            # print("bazo_drive_dd : ",start_drive,end_drive)
            # start_drive = 15
            # end_drive = 17
            newest_event['person_drive'] = person_drive
            newest_event['start'] = datetime.datetime.strftime(
                start + datetime.timedelta(minutes=start_drive),
                '%Y-%m-%dT%H:%M:%S.%fZ')
            newest_event['end'] = datetime.datetime.strftime(
                end + datetime.timedelta(minutes=-1 * end_drive),
                '%Y-%m-%dT%H:%M:%S.%fZ')
            newest_event['start_initial'] = datetime.datetime.strftime(
                start,
                '%Y-%m-%dT%H:%M:%S.%fZ')
            newest_event['end_initial'] = datetime.datetime.strftime(
                end,
                '%Y-%m-%dT%H:%M:%S.%fZ')
            start_here2 = datetime.datetime.strptime(newest_event['start'],
                                                     '%Y-%m-%dT%H:%M:%S.%fZ')
            end_here2 = datetime.datetime.strptime(newest_event['end'],
                                                   '%Y-%m-%dT%H:%M:%S.%fZ')
            delta2 = (end_here2 - start_here2).total_seconds()
            
            for r in person_drive.keys():
                person_drive[r] = {**person_drive[r],'beginningDrive':[newest_event['start_initial'],newest_event['start']],'endDrive':[newest_event['end'],newest_event['end_initial']]}
            # print('person_drive', person_drive)
            if delta2 > 0:
                if 'fake' not in newest_event.keys():
                    new_events_poss.append(newest_event)
        self.events_poss = new_events_poss
        index_delete = []
        for event in self.resources1.drive_constraints:
            print('feeler',event)
            for index, event_poss in enumerate(new_events_poss):
                common = set(event_poss['resourceIds_r']) & set(event['users_antecedent_set'])
                address1 = event_poss['address']
                if address1 is None or len(address1) < 5:
                    continue
                for t in common:
                    address2 = self.users[t]['address']
                    if address2 is None or len(address2) < 5 or address1 == address2:
                        continue
                    arr_addresses = tuple(sorted([address1,address2]))
                    arr_addresses2 = tuple(sorted([address1,address2],reverse=True))
                    if arr_addresses in constraint_drive_data_new.keys():
                        time1 = constraint_drive_data_new[arr_addresses]['mid']
                        print('seahorse',time1)
                    else:
                        print('sivver2',address1, address2)
                        result_distance_dur_early = return_interval_drive_time(address1, address2,11,30)
                        print('lovely',result_distance_dur_early)
                        result_distance_dur_early_reverse = result_distance_dur_early
                        #result_distance_dur_early_reverse = return_interval_drive_time(loc_address2, loc_address,8,30)
                        if True or result_distance_dur_early != [0,0]:
                            result_distance_dur_mid = result_distance_dur_early
                            result_distance_dur_late = result_distance_dur_early
                            #result_distance_dur_mid = return_interval_drive_time(loc_address, loc_address2,11,30)
                            #result_distance_dur_late = return_interval_drive_time(loc_address, loc_address2,5,30)
                            result_distance_dur_mid_reverse = result_distance_dur_mid
                            result_distance_dur_late_reverse = result_distance_dur_late
                            #result_distance_dur_mid_reverse = return_interval_drive_time(loc_address, loc_address2,11,30)
                            #result_distance_dur_late_reverse = return_interval_drive_time(loc_address, loc_address2,5,30)
                            
                            post_drive_time_data(self.header,{
                                "data" :{
                                    "address1": address1,
                                    "address2":address2,
                                    "duration": result_distance_dur_mid[1],
                                    "duration_early": result_distance_dur_early[1],
                                    "duration_late": result_distance_dur_late[1],
                                    "distance": result_distance_dur_early[0],
                                    }
                            },self.host)
                            post_drive_time_data(self.header,{
                                "data" :{
                                    "address1": address2,
                                    "address2":address1,
                                    "duration": result_distance_dur_mid_reverse[1],
                                    "duration_early": result_distance_dur_early_reverse[1],
                                    "duration_late": result_distance_dur_late_reverse[1],
                                    "distance": result_distance_dur_early_reverse[0],
                                    }
                            },self.host)
                        constraint_drive_data_new[arr_addresses] = {"early": result_distance_dur_early[1],"mid":result_distance_dur_mid[1],"late":result_distance_dur_late[1]}
                        constraint_drive_data_new[arr_addresses2] = {"early": result_distance_dur_early_reverse[1],"mid":result_distance_dur_mid_reverse[1],"late":result_distance_dur_late_reverse[1]}
                        time1 = result_distance_dur_mid[1]
                    print('sivvty',event['max'],time1,time1//60)
                    if time1//60 > event['max']:
                        index_delete.append(index)
                        print('hover4',time1//60)
                    else:
                        print('hover5',time1//60)

                print('seemer3',address1,address2,common)
        index_delete.sort(reverse=True)
        for index in index_delete:
            del new_events_poss[index]    
        return new_events_poss

        # print('soomlier', self.events_poss)

    def main3(self):
        model = cp_model.CpModel()  # Creates the model
        # print('simmy4', self.relevant_users)
        work_together_arr = [0, 0, 0, 0, 0, 0, 0]
        work_together_obj = {}
        time_together_obj = {}
        sessions_together_obj = {}
        for event in self.events:
            # print('simmers', event)
            duration = event['duration']
            ev_now = self.calc_availabilities(event["start"],event["end_real_time"],'%Y-%m-%dT%H:%M:%S.%fZ', False)
            # print("bazo_ev_now",ev_now)
            person_count = 0
            locations_arr = []
            work_together_obj_keys = work_together_obj.keys()
            time_together_obj_keys = work_together_obj.keys()
            for r in list(combinations(event["resourceIds"], 2)):
                if r[0] in self.user_uuid_to_index_keys and r[1] in self.user_uuid_to_index_keys:
                    res1 = self.user_uuid_to_index[r[0]]
                    res2 = self.user_uuid_to_index[r[1]]
                    if res1 != res2:
                        if (res1 < res2):
                            res_tup1 = (res1, res2)
                        else:
                            res_tup1 = (res2, res1)
                        if len(ev_now) > 0:
                            ind = math.floor(ev_now[0] / (96*(15//self.slot_length)))
                            if res_tup1 in work_together_obj_keys:
                                work_together_obj[res_tup1][ind] = 1
                                sessions_together_obj[res_tup1][ind] += 1
                                time_together_obj[res_tup1][ind] = duration
                                self.resources1.resources[
                                    res1].work_together_arr[res2][ind] = 1
                                self.resources1.resources[
                                    res2].work_together_arr[res1][ind] = 1
                                self.resources1.resources[
                                    res2].sessions_together_arr[res1][ind] += 1
                                self.resources1.resources[
                                    res1].sessions_together_arr[res2][ind] += 1
                                self.resources1.resources[
                                    res1].time_with_users[res2][
                                        ind] += duration
                                self.resources1.resources[
                                    res2].time_with_users[res1][
                                        ind] += duration
                            else:
                                work_together_obj[
                                    res_tup1] = work_together_arr.copy()
                                time_together_obj[
                                    res_tup1] = work_together_arr.copy()
                                sessions_together_obj[
                                    res_tup1] = work_together_arr.copy()
                                self.resources1.resources[
                                    res1].work_together_arr[
                                        res2] = work_together_arr.copy()
                                self.resources1.resources[
                                    res2].work_together_arr[
                                        res1] = work_together_arr.copy()
                                self.resources1.resources[
                                    res1].sessions_together_arr[
                                        res2] = work_together_arr.copy()
                                self.resources1.resources[
                                    res2].sessions_together_arr[
                                        res1] = work_together_arr.copy()
                                self.resources1.resources[
                                    res1].time_with_users[
                                        res2] = work_together_arr.copy()
                                self.resources1.resources[
                                    res2].time_with_users[
                                        res1] = work_together_arr.copy()
                                self.resources1.resources[
                                    res1].time_with_users[res2][
                                        ind] += duration
                                self.resources1.resources[
                                    res2].time_with_users[res1][
                                        ind] += duration
                                self.resources1.resources[
                                    res1].work_together_arr[res2][ind] = 1
                                self.resources1.resources[
                                    res2].work_together_arr[res1][ind] = 1
                                self.resources1.resources[
                                    res1].sessions_together_arr[res2][ind] = 1
                                self.resources1.resources[
                                    res2].sessions_together_arr[res1][ind] = 1
                                work_together_obj[res_tup1][ind] = 1
                                sessions_together_obj[res_tup1][ind] += 1
                                time_together_obj[res_tup1][ind] += duration
        # print('simples', time_together_obj)
        for info in self.events_poss_raw:
            # print("one_info : ", info)
            start_int = info['start']
            end_int = info['end']
            resource_list = info["resourceIds"]
            duration_int = end_int - start_int
            bol_appointment = model.NewBoolVar('hi')
            event_interval = model.NewOptionalIntervalVar(
                start_int, duration_int, end_int, bol_appointment, 'interval')
            self.resources1.slots[tuple([start_int]) +
                                  tuple(resource_list)] = [
                                      duration_int, event_interval, start_int,
                                      end_int, False, bol_appointment,
                                      resource_list, []
            ]

        constraint_ids_dict = {}
        users_antecedent_dict = {}
        # print("bazo_knows :", self.custom_constraints)
        def operate_constraint(users_consequence,together_arr_type):
            if together_arr_type is None:
                return
            for user_a in users_antecedent:
                arr7 = work_together_arr.copy()
                arr_count = 0
                for user_c in users_consequence:
                    if user_c in getattr(self.resources1.resources[user_a],together_arr_type).keys():
                        for index, num in enumerate(getattr(self.resources1.resources[user_a],together_arr_type)[user_c]):
                            arr7[index] += num
                        if c['type_or_specific_consequence'] == 'specific' or c[
                                "constraint"] == 'usertosession':
                            arr_count += sum(getattr(self.resources1.resources[user_a],together_arr_type)[user_c])
                        else:
                            arr_count += max( getattr(self.resources1.resources[user_a],together_arr_type)[user_c])
                val = self.get_appointments([[user_a],users_consequence])
                for e in val.values():
                    ind = math.floor(e[2] / (96*(15//self.slot_length)))
                    inter = intersection(e[6], users_consequence)
                    bol = e[5]
                    if ind == 7:
                        pass
                        #model.Add(bol == 0)
                    else:
                        if len(inter) > 0:
                            sub_num = 0
                            for u in inter:
                                if u in getattr(self.resources1.resources[user_a],together_arr_type).keys():
                                    num_to_compare = 0
                                    if c['frequency'] == 'day':
                                        num_to_compare = getattr( self.resources1.resources[user_a],together_arr_type)[u][ind]
                                    elif c['frequency'] == 'week':
                                        num_to_compare = max(getattr(self.resources1.resources[user_a],together_arr_type)[u])
                                    if num_to_compare > 0:
                                        sub_num += 1
                            if True or sub_num == 0:
                                total = 0
                                if c['frequency'] == 'day':

                                    total = arr7[ind] + \
                                        len(inter)
                                    if c['constraint'] == 'usertouser':
                                        total = total - sub_num
                                elif c['frequency'] == 'week':
                                    total = arr_count + \
                                        len(inter)
                                    # print('smickers', arr_count)
                                    if c['type_or_specific_consequence'] != 'specific' and c[
                                            'constraint'] == 'usertouser':
                                        total = total - sub_num
                                    # print('gliffy', total)
                                # print("bazo_total : ", total)
                                if not (total <= c['max']
                                        and total >= c['min']):
                                    print(
                                        'dilly2',
                                        total,
                                    )
                                    e[7].append({
                                        "reason":
                                        'Theres a frequency conflict!'
                                    })
                                    #model.Add(bol == 0)
        
        # print('loofly',self.custom_constraints)
        for ind, cus in enumerate(self.custom_constraints):
            #print("bazo_constraint : ",cus)
            c = cus
            if cus["id"] not in self.highPriority:
                # print("bazo_invalid_id  :",cus['id'])
                continue 
            if not (c['constraint'] == 'matching' or c['constraint']
                    == 'unmatching' or c['constraint'] == 'grouping' or c['constraint'] == 'usertouser' or c['constraint'] == 'usertosession'):
                id = ind
                constraint_ids_dict[id] = {
                    "min": c['min'],
                    "max": c['max'],
                    "frequency": c["frequency"],
                    "constraint": c["constraint"]
                }
                if True : #len(c['days']) == 0:
                    constraint_ids_dict[id]['days'] = list(range(7))
                else:
                    constraint_ids_dict[id]['days'] = c['days']
                if c['type_or_specific'] == 'type':
                    users_antecedent = self.handle_general_constraint_type(
                        c["apply_constraint_to_this_role"],
                        c["apply_constraint_to_this_subgroup"],
                        c["apply_constraint_to_this_branch"])
                else:
                    users_antecedent = self.handle_general_constraint_specific_index(
                        c["apply_constraint_to_this_user"])
                if c['type_or_specific_consequence'] == 'type':
                    users_consequence = self.handle_general_constraint_type(
                        c["consequence_constraint_to_this_role"],
                        c["consequence_constraint_to_this_subgroup"],
                        c["consequence_constraint_to_this_branch"])
                else:
                    users_consequence = self.handle_general_constraint_specific_index(
                        c["consequence_constraint_to_this_user"])

                # print('lakky6',c['constraint'])
                if c['constraint'] == 'drive':
                    print('lakky7')
                    frequency = c['frequency']
                    self.resources1.drive_constraints.append({
                        "each_or_all_users":
                        c["each_or_all_users"],
                        "frequency":
                        c['frequency'],
                        "weight":
                        c["weight"],
                        "type":
                        "time",
                        "users_antecedent":
                        users_antecedent,
                        "users_consequence":
                        users_consequence,
                        "users_antecedent_set":
                        set(users_antecedent),
                        "users_consequence_set":
                        set(users_consequence),
                        "max":
                        c['max'],
                        "min":
                        c['min'],
                        "id":
                        c["id"],
                        "rank":
                        ind
                    })
                
                if c['constraint'] == 'time':
                    frequency = c['frequency']
                    self.resources1.frequency_constraints.append({
                        "each_or_all_users":
                        c["each_or_all_users"],
                        "frequency":
                        c['frequency'],
                        "weight":
                        c["weight"],
                        "type":
                        "time",
                        "users_antecedent":
                        users_antecedent,
                        "users_consequence":
                        users_consequence,
                        "max":
                        c['max'],
                        "min":
                        c['min'],
                        "id":
                        c["id"],
                        "rank":
                        ind
                    })
                    # for n in users_consequence:
                    #     print('seefee', n, self.users[n]['firstName'])
                    for user_a in users_antecedent:
                        user_time_constraints = self.resources1.resources[
                            user_a].time_constraints[frequency]
                        obj_h = {
                            "min": c['min'],
                            "max": c['max'],
                            "each_or_all_users": c["each_or_all_users"],
                            "weight": c["weight"],
                            "users_consequence": users_consequence,
                            "users_antecedent": users_antecedent
                        }
                        for user_c in users_consequence:
                            if user_c in user_time_constraints.keys():
                                pass
                            else:
                                # print('SLIVVER')
                                self.resources1.resources[
                                    user_a].time_constraints[frequency][
                                        user_c] = obj_h
                                self.resources1.resources[
                                    user_c].time_constraints[frequency][
                                        user_a] = obj_h
                                # print(
                                #     'iolys', self.resources1.resources[user_a].
                                #     time_constraints[frequency])

                    pass
                else:
                    type_label = 'nothing'
                    together_arr_type = None
                    if c['constraint'] == 'usertouser':
                        together_arr_type = "work_together_arr"
                        type_label = 'frequency'
                    elif c['constraint'] == 'usertosession':
                        together_arr_type = "sessions_together_arr"
                        type_label = 'session'
                    self.resources1.frequency_constraints.append({
                        "each_or_all_users":
                        c["each_or_all_users"],
                        "frequency":
                        c['frequency'],
                        "weight":
                        c["weight"],
                        "type":
                        type_label,
                        "users_antecedent":
                        users_antecedent,
                        "users_consequence":
                        users_consequence,
                        "max":
                        c['max'],
                        "min":
                        c['min'],
                        "id":
                        c["id"],
                        "rank":
                        ind
                    })

                    

                    if c["constraint"] == 'usertosession' and c["each_or_all_users"] == 'each':
                        for u_con in users_consequence:
                            operate_constraint([u_con],together_arr_type)
                    else:
                        operate_constraint(users_consequence,together_arr_type)

        val = self.get_appointments(
            [self.get_resources_from_role(['Resource'])])
        model.Maximize(sum(map(lambda num: num[5], val.values())))

        solver = cp_model.CpSolver()
        solution_printer2 = VarArraySolutionPrinter2(
            self.resources1.slots.values(), self.events_poss,
            self.events_poss_raw, self.resources1, self.is_investigate)
        solver.parameters.log_search_progress = True
        status = solver.Solve(model, solution_printer2)
        #print("bazo_all_const : ",self.resources1.frequency_constraints)
        # applying time constraints
        new_all_solutions = []
        #for solution in self.events_poss_raw:
        for solution in solution_printer2.all_solutions:
            session_max = 36000000
            session_min = 0
            pass_solution = False
            for cus_constraint in self.resources1.frequency_constraints:
                if cus_constraint["id"] not in self.highPriority:
                # print("bazo_invalid_id  :",cus['id'])
                    continue 
                if cus_constraint["type"] == "sessionlength":
                    # print('sotty1')
                    if len(intersection(solution["resourceIds_r"],cus_constraint["users_antecedent"])):
                        # print('sotty2')
                        if len(intersection(solution["resourceIds_r"],cus_constraint["users_consequence"])):
                            # print('sotty3',cus_constraint["minSeconds"],solution['end_r'],solution['start_r'],self.slot_length,cus_constraint["minSeconds"]//60,int(solution['end_r'] - solution['start_r'])*15//(15//self.slot_length))
                            if cus_constraint["minSeconds"]//60 > int(solution['end_r'] - solution['start_r'])*15//(15//self.slot_length):
                                # print('sotty4')
                                pass_solution = True
                                break
            
                        
            # print('likky', solution)
            for r in list(combinations(solution["resourceIds_r"], 2)):
                res1 = r[0]
                res2 = r[1]
                time_constraints = self.resources1.resources[res1].time_constraints
                time_constraints2 = self.resources1.resources[res2].time_constraints
                time_with_users = self.resources1.resources[res1].time_with_users
                time_with_users2 = self.resources1.resources[res2].time_with_users
                time_with_users_keys = time_with_users.keys()
                time_with_users_keys2 = time_with_users2.keys()
                # print('soogy',time_constraints,time_with_users2)
                if self.is_session and res2 in time_constraints['session'].keys():
                    # print('fimmer',time_constraints['session'][res2])
                    remaining = time_constraints['session'][res2]['max'] * 3600
                    # print('seamstress1')
                    if remaining < session_max:
                        session_max = remaining
                if res2 in time_constraints['day'].keys():
                    total = 0
                    if res1 == 0 or res2 == 0:
                        # print('steemer4', total)
                        pass
                    ind = math.floor(solution['start_r'] / (96*(15//self.slot_length)))
                    # print('seamstress2')
                    if time_constraints['day'][res2][
                            "each_or_all_users"] == 'each':
                        if res2 in time_with_users_keys:
                            total = time_with_users[res2][ind]
                    else:
                        for us in time_constraints['day'][res2][
                                "users_consequence"] + time_constraints2[
                                    'day'][res1]["users_antecedent"]:
                            if us in time_with_users_keys:
                                total += time_with_users[us][ind]
                            if us in time_with_users_keys2:
                                total += time_with_users2[us][ind]
                        # if res1 in time_constraints['day'].keys():
                        #     for us in time_constraints['day'][res1][
                        #             "users_consequence"]:
                        #         if us in time_with_users_keys:
                        #             print('slooby')
                        #             total += time_with_users[us][ind]
                    # if time_constraints['day'][res2]["each_or_all_users"] == 'each':
                    if res1 == 11 or res2 == 11:
                        # print('seemer', total)
                        pass
                    if False:
                        remaining = total
                    else:
                        remaining = time_constraints['day'][res2]['max'] * \
                            3600 
                        if 'units' in time_constraints['day'][res2].keys() and time_constraints['day'][res2]['units'] == 'minutes':
                            remaining = remaining // 60
                        #- total
                    
                    if remaining < session_max:
                        session_max = remaining
                    # print('lizzy1',remaining,session_max)
                    # print('gooby',time_constraints)
                if res2 in time_constraints['week'].keys():
                    total = 0
                    # print('seamstress3')
                    if time_constraints['week'][res2][
                            "each_or_all_users"] == 'each':
                        if res2 in time_with_users_keys:
                            total = sum(time_with_users[res2])
                    else:
                        for us in time_constraints['week'][res2][
                                "users_consequence"] + time_constraints2[
                                    'week'][res1]["users_antecedent"]:
                            if us in time_with_users_keys:
                                total += sum(time_with_users[us])
                            if us in time_with_users_keys2:
                                total += sum(time_with_users2[us])
                    # if time_constraints['day'][res2]["each_or_all_users"] == 'each':
                    if False:
                        remaining = total
                    else:
                        remaining = time_constraints['week'][res2]['max'] * \
                            3600 - total
                    if remaining < session_max:
                        session_max = remaining
                # print('sneefer', res1, self.users[res1]['firstName'],
                #       res2, self.users[res2]['firstName'], session_max)
            # print('lizzy2',remaining,session_max)
            slot_duration = int(solution['end_r'] - solution['start_r'])
            session_max_slot_duration = int(session_max / 3600.0 * (4*(15//self.slot_length)))
            # print('higgly', session_max_slot_duration)
            current_start = solution['start_r']
            new_start = solution['new_start']
            
            # print('lojjy',slot_duration,session_max_slot_duration)
            if session_max_slot_duration < slot_duration:
                # print('likky2', solution,session_max_slot_duration,slot_duration)
                start_time = None
                end_time = None
                while (session_max_slot_duration) > 0 and slot_duration > 0 and current_start + (session_max_slot_duration) < solution[
                        'end_r']:
                    # print('likky3', solution)
                    
                    new_end = current_start + (session_max_slot_duration)
                    start = self.slot_to_time(current_start, 15//(15//self.slot_length))
                    end = self.slot_to_time(new_end, 15//(15//self.slot_length))
                    new_solution_start = f'{new_start}T{start}.000Z'
                    new_solution_end = f'{new_start}T{end}.000Z'
                    start_time = datetime.datetime.strptime(new_solution_start, '%Y-%m-%dT%H:%M:%S.%fZ')
                    end_time = datetime.datetime.strptime(new_solution_end, '%Y-%m-%dT%H:%M:%S.%fZ')
                    if end_time < start_time:
                        end_time += datetime.timedelta(days=1)
                        new_solution_end = end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3] + 'Z'
                        # print('eddy2',new_solution_end)
                    # print('kimmy2',start,end,new_start,new_solution_start,new_solution_end)
                    new_solution = {
                        **solution, "start": new_solution_start,
                        "end": new_solution_end
                    }
                    if not pass_solution:
                        new_all_solutions.append(new_solution)
                    else:
                        print('real_pass1',new_solution)
                    current_start = new_end
                start = self.slot_to_time(current_start, 15//(15//self.slot_length))
                
                new_solution_start = f'{new_start}T{start}.000Z'
                start_time = datetime.datetime.strptime(new_solution_start, '%Y-%m-%dT%H:%M:%S.%fZ')
                if end_time is not None and start_time < end_time:
                    start_time += datetime.timedelta(days=1)
                    new_solution_start = start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3] + 'Z'
                new_solution = {**solution, "start": new_solution_start}
                if session_max_slot_duration > 0:
                    if not pass_solution:
                        # print("passing solution")
                        new_all_solutions.append(new_solution)
                    else:
                        print('real_pass2',new_solution)
            else:
                if True or not pass_solution:
                    # print("passing solution")
                    new_all_solutions.append(solution)
                else:
                    print('real_pass3',solution)
            session_max / 3600 * 4
        # print('snoofer', new_all_solutions)
        self.events_poss = new_all_solutions
        return new_all_solutions

    #     # for event in self.events_poss_raw

    def calculate_flexibility(self):
        for sol in self.events_poss_raw:
            pass

    def calculate_solution_totals(self):
        start_time = time.time()
        user_totals = {}
        user_flexibility = {}
        original_length = len(self.events_poss)
        # print('slifty3', original_length)
        # print('jokop', self.events_poss)
        for sol in self.events_poss:
            for i in range(sol['start_r'], sol['end_r']):
                # print('snoffy', sol['resourceIds'], sol,)
                for id in sol['resourceIds_r']:
                    self.user_solutions_array_unit[id][i] = 1
                    self.user_solutions_array_total[id][i] += 1
        # print('sugar2', self.user_solutions_array_total)
        for id in self.user_solutions_array_total.keys():
            #    # print('spooky3', sum(
            #         self.user_solutions_array_total[id]), id, self.user_solutions_array_total[id])
            user_totals[id] = sum(self.user_solutions_array_total[id])

        for t in range(original_length // 2):
            max_num = -1
            max_index = -1
            for index, sol in enumerate(self.events_poss):
                total_count = 1
                total_flex_person = 1
                for id in sol['resourceIds_r']:
                    if 'Person' in self.users[id]['roles']:
                        total_flex_person *= user_totals[id]
                        total_count_person = 0
                        for i in range(sol['start_r'], sol['end_r']):
                            total_count_person += self.user_solutions_array_total[
                                id][i]
                        total_count + total_count_person / \
                            (sol['end_r'] - sol['start_r'])
                total_count *= total_flex_person
                if (max_num < total_count):
                    max_num = total_count
                    max_index = index

            # print('footy2', max_index)
            event = self.events_poss[max_index]
            # print('footy3', event)

            for id in sol['resourceIds_r']:
                user_totals[id] -= sol['end_r'] - sol['start_r']
                for i in range(sol['start_r'], sol['end_r']):
                    self.user_solutions_array_total[id][i] -= 1
            del self.events_poss[max_index]
        self.events_poss = self.events_poss
        return self.events_poss
        # print('soofly3', len(self.events_poss), time.time() - start_time)

    def main2(self):
        model = cp_model.CpModel()  # Creates the model
        total_slots = (672+96)*(15//self.slot_length)
        zero_slots = []
        one_slots = []
        solution_limit_number = 0

        for i in range(total_slots):
            zero_slots.append(0)
            one_slots.append(1)
        user_length = len(self.users)
        slot_length = 15//(15//self.slot_length)
        all_possible_ids_ortools_obj = {}
        constraint_arr = []
        e_pair_organized1 = {}
        e_pair_organized2 = {}

        e_pair_slots = {}

        user_availabilities = {}
        user_availabilities_yellow_blank = {}
        user_capacities = {}
        # variable 1 - block
        is_block_bol = model.NewBoolVar('is_block')

        if self.settings['blocks']:
            # print('sitter')
            model.Add(is_block_bol == 1)
        else:
            model.Add(is_block_bol == 0)
        # variable 2 - orange
        is_orange_bol = model.NewBoolVar('is_orange')
        if (not self.is_orange):
            model.Add(is_orange_bol == 0)
        else:
            model.Add(is_orange_bol == 1)

        all_possible_ids = self.get_user_ids("Resource")

        full_location_ids = self.get_user_ids("Location")
        block_ids = self.get_user_ids("Block")
        room_ids = self.get_user_ids("Room")
        seat_ids = self.get_user_ids("Seat")

        location_ids = full_location_ids.difference(room_ids).difference(
            seat_ids)
        slot_ortools_int = model.NewIntVar(0, 7, 'h')
        slot_bol_obj = {}

        start_d = datetime.datetime.strptime(self.start_date, "%Y-%m-%d")
        end_d = datetime.datetime.strptime(self.end_date, "%Y-%m-%d")
        start_numeric = (start_d.weekday())
        end_numeric = (end_d.weekday())

        min_numeric = 0
        max_numeric = 0

        if start_numeric >= end_numeric:
            max_numeric = start_numeric+1
            min_numeric = end_numeric+1
        else:
            max_numeric = end_numeric+1
            min_numeric = start_numeric+1
            
        allowed_days = list(range(5, 6))
        
        for i in range(7):
            if i not in allowed_days:
                model.Add(slot_ortools_int != i)

        if solution_limit_number == 0:
            if self.optimizer_or_not:
                solution_limit_number = 100000

            else:
                solution_limit_number = 100000
            
        priority_ortools_int = model.NewIntVar(0, 6000, 'h')

        for id in all_possible_ids:
            # variable 5 - assigning each resource 0 or 1
            bol = model.NewBoolVar("bol") 
            all_possible_ids_ortools_obj[id] = bol
            user_availabilities[id] = {}
            self.user_solutions_array_unit[id] = zero_slots.copy()
            self.user_solutions_array_total[id] = zero_slots.copy()
            capacity = self.users[id]['capacity']
            if 'Location' in self.users[id]['roles']:
                user_capacities[id] = zero_slots.copy()
            for loc in location_ids:
                user_availabilities[id][loc] = zero_slots.copy()
        
        if self.settings['driveDistanceMax'] and self.settings['driveDistanceMaxQuantity'] and self.settings['driveDistanceMaxQuantity'] > 0:
            locations_distance_ids = list(self.get_user_ids("Location"))
            homes_distance_ids = list(self.get_user_ids("Home"))
            locations_distance_ids = [x for x in locations_distance_ids if x not in homes_distance_ids]
            employees_distance_ids = list(self.get_user_ids("Employee"))
            clients_distance_ids = list(self.get_user_ids("Client"))
            
            employees_distance_ids = [index for index in employees_distance_ids if self.users[index]['latitude'] is not None and self.users[index]['longitude'] is not None and self.users[index]['latitude'] != 0 and self.users[index]['longitude'] != 0]
            locations_distance_ids = [index for index in locations_distance_ids if self.users[index]['latitude'] is not None and self.users[index]['longitude'] is not None and self.users[index]['latitude'] != 0 and self.users[index]['longitude'] != 0]
            clients_distance_ids = [index for index in clients_distance_ids if self.users[index]['latitude'] is not None and self.users[index]['longitude'] is not None and self.users[index]['latitude'] != 0 and self.users[index]['longitude'] != 0]
            generator_of_tuples = ((x, y) for x in employees_distance_ids for y in locations_distance_ids)

            for tuple_item in generator_of_tuples:
                tuple_item_list = list(tuple_item)
                x = tuple_item_list[0]
                y = tuple_item_list[1]
                lon1 = self.users[x]['longitude']
                lon2 = self.users[y]['longitude']
                lat1 = self.users[x]['latitude']
                lat2 = self.users[y]['latitude']
                distance = haversine(lat1, lon1, lat2, lon2, unit='miles')
                if distance > self.settings['driveDistanceMaxQuantity']:
                    model.Add(all_possible_ids_ortools_obj[x] + all_possible_ids_ortools_obj[y] != 2)



            
            if len(homes_distance_ids) > 0:
                home_distance_id = homes_distance_ids[0]
                generator_of_tuples = ((x, y) for x in employees_distance_ids for y in clients_distance_ids)
                for tuple_item in generator_of_tuples:
                    tuple_item_list = list(tuple_item)
                    x = tuple_item_list[0]
                    y = tuple_item_list[1]
                    lon1 = self.users[x]['longitude']
                    lon2 = self.users[y]['longitude']
                    lat1 = self.users[x]['latitude']
                    lat2 = self.users[y]['latitude']
                    distance = haversine(lat1, lon1, lat2, lon2, unit='miles')
                    if distance > self.settings['driveDistanceMaxQuantity']:
                        model.Add(all_possible_ids_ortools_obj[x] + all_possible_ids_ortools_obj[y] != 2).OnlyEnforceIf(all_possible_ids_ortools_obj[home_distance_id])

        user_availabilities_yellow_blank = copy.deepcopy(user_availabilities)
        user_availabilities_yellow = copy.deepcopy(user_availabilities)

        for i, user in enumerate(self.users):
            self.users[i]['subgroups_real'] = self.users[i]['actual_subgroups']
            self.user_uuid_to_index[user["id"]] = i

        self.user_uuid_to_index_keys = self.user_uuid_to_index.keys()
        for e in self.e_pair:
            
            roles1 = list(map(lambda x: x['name'], e['roles1']))
            roles2 = list(map(lambda x: x['name'], e['roles2']))
            if e['activity1Id'] in self.user_uuid_to_index_keys and e[
                    'activity2Id'] in self.user_uuid_to_index_keys:
                activity1 = self.user_uuid_to_index[e['activity1Id']]
                activity2 = self.user_uuid_to_index[e['activity2Id']]
                if activity1 in e_pair_organized1.keys():
                    e_pair_organized1[activity1].append(set(roles1))
                else:
                    e_pair_organized1[activity1] = [set(roles1)]

                if activity2 in e_pair_organized2.keys():
                    if activity1 in e_pair_organized2[activity2].keys():
                        e_pair_organized2[activity2][activity1].append(
                            set(roles2 + roles1))
                    else:
                        e_pair_organized2[activity2][activity1] = [
                            set(roles2 + roles1)
                        ]
                else:
                    e_pair_organized2[activity2] = {
                        activity1: [set(roles2 + roles1)]
                    }

        # TODO: need to investigate
        if self.is_investigate:
            arr = []
            list_arr = []
            for id in self.investigate:
                if id in all_possible_ids_ortools_obj.keys():
                    arr.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[id]])
                    list_arr.append(1)
            model.AddAllowedAssignments(arr, [tuple(list_arr)])

        neededUsersForBoolOr = intersection(list(self.user_uuid_to_index.keys()),self.expanded_resources)
        model.AddBoolOr(
            list(
                map(
                    lambda x: all_possible_ids_ortools_obj[
                        self.user_uuid_to_index[x]], neededUsersForBoolOr)))
    
        
        if self.resourceCombinationsExclude:
            excludedIds = list(
                map(
                    lambda x: list(
                map(lambda y:all_possible_ids_ortools_obj[
                        self.user_uuid_to_index[y]], x)), self.resourceCombinationsExclude))
            list(map(lambda x: model.Add(sum(x) != len(x)),excludedIds))
        
        if self.expanded_resources_filter:
            model.AddBoolAnd(
            list(
                map(
                    lambda x: all_possible_ids_ortools_obj[
                        self.user_uuid_to_index[x]], self.expanded_resources_filter)))

        for user in self.users:
            branches_list = []
            for branch in user['branches']:
                if branch in self.branch_structure.keys():
                    branches_list = [
                        *branches_list, *self.branch_structure[branch]
                    ]
            user['branches_real'] = list(set(branches_list))
        
        #TODO-refactoring to calculate with current data
        for p in self.activity_table:
            userId = p['user']['id']
            if userId in self.user_uuid_to_index_keys:
                userIndex = self.user_uuid_to_index[userId]
                if 'Person' in self.users[userIndex]['roles']:
                    self.users[userIndex]['efficiency'] = round(p['efficiency'])

        valid_indices = [i for i in range(len(self.users)) if 'efficiency' in self.users[i]]

        sorted_indices = sorted(valid_indices, key=lambda x: self.users[x]['efficiency'])
        sorted_ortools_efficiency = [all_possible_ids_ortools_obj[index] for index in sorted_indices if index in all_possible_ids_ortools_obj]
        
        is_room = model.NewBoolVar('is_room')
        is_seat = model.NewBoolVar('is_seat')
        is_location = model.NewBoolVar('is_location')
        
        all_room_ids = self.get_user_ids("Room")
        all_seat_ids = self.get_user_ids("Seat")
        all_location_ids2 = self.get_user_ids("Location").difference(all_room_ids).difference(all_seat_ids)
        room_ortool_ids = []
        for id in all_room_ids:
            room_ortool_ids.append(all_possible_ids_ortools_obj[id])
        seat_ortool_ids = []
        for id in all_seat_ids:
            seat_ortool_ids.append(all_possible_ids_ortools_obj[id])
        location_ortool_ids = []
        for id in all_location_ids2:
            location_ortool_ids.append(all_possible_ids_ortools_obj[id])
        
        model.Add(sum(room_ortool_ids) == 1).OnlyEnforceIf(is_room)
        model.Add(sum(room_ortool_ids) == 0).OnlyEnforceIf(is_room.Not())
        model.Add(sum(seat_ortool_ids) == 1).OnlyEnforceIf(is_seat)
        model.Add(sum(seat_ortool_ids) == 0).OnlyEnforceIf(is_seat.Not())
        model.Add(sum(location_ortool_ids) == 1).OnlyEnforceIf(is_location)
        model.Add(sum(location_ortool_ids) == 0).OnlyEnforceIf(is_location.Not())
        model.Add(is_room == 1).OnlyEnforceIf(is_seat)
        model.Add(is_location == 1).OnlyEnforceIf(is_room)
        for id in all_location_ids2:
            if self.users[id]['needroom']:
                model.Add(is_room == 1).OnlyEnforceIf(all_possible_ids_ortools_obj[id])
            else:
                model.Add(is_room == 0).OnlyEnforceIf(all_possible_ids_ortools_obj[id])
        for id in all_room_ids:
            if self.users[id]['needseat']:
                model.Add(is_seat == 1).OnlyEnforceIf(all_possible_ids_ortools_obj[id])

        def capacity_constraint_add(capacity1, bol):
            user1 = capacity1["user1"]
            disabled = capacity1["disabled"]
            activity_id = self.user_uuid_to_index[user1["id"]]
            role1 = capacity1["role1"]
            subgroup1 = capacity1["subgroup1"]
            min1 = capacity1["min1"]
            max1 = capacity1["max1"]
            role2 = capacity1["role2"]
            subgroup2 = capacity1["subgroup2"]
            min2 = capacity1["min2"]
            max2 = capacity1["max2"]
            role3 = capacity1["role3"]
            subgroup3 = capacity1["subgroup3"]
            min3 = capacity1["min3"]
            max3 = capacity1["max3"]
            role4 = capacity1["role4"]
            subgroup4 = capacity1["subgroup4"]
            min4 = capacity1["min4"]
            max4 = capacity1["max4"]
            role5 = capacity1["role5"]
            subgroup5 = capacity1["subgroup5"]
            min5 = capacity1["min5"]
            max5 = capacity1["max5"]
            locationDisabled = capacity1["locationDisabled"]
            activity_set = set()
            activity_set.add(activity_id)
            all_possible_ids_copy = all_possible_ids.copy()
            all_possible_ids_copy = all_possible_ids_copy.difference(
                activity_set)
            all_possible_ids_copy = all_possible_ids_copy.difference(
                full_location_ids)

            model.Add(all_possible_ids_ortools_obj[activity_id] ==
                      1).OnlyEnforceIf(bol)
            minimum_total = 2


            def apply_min_max(user_ids_role, min, max):
                arr2 = []
                for id in user_ids_role:
                    arr2.append(all_possible_ids_ortools_obj[id])
                
                if min is not None:
                    model.Add(sum(arr2) >= min).OnlyEnforceIf(bol)
                if max is not None:
                    # model.Add(sum(arr2) >= 1).OnlyEnforceIf(bol)
                    model.Add(sum(arr2) <= max).OnlyEnforceIf(bol)

            if role1 and subgroup1:
                user_ids_role1 = self.get_user_ids(role1["name"], 'roles').intersection(self.get_user_ids(subgroup1["name"],
                                                   'subgroups_real'))
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role1)
                apply_min_max(user_ids_role1, min1, max1)
                if min1 is not None:
                    minimum_total += min1
            elif role1:
                user_ids_role1 = self.get_user_ids(role1["name"], 'roles')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role1)
                apply_min_max(user_ids_role1, min1, max1)
                if min1 is not None:
                    minimum_total += min1
            elif subgroup1:
                user_ids_role1 = self.get_user_ids(subgroup1["name"],
                                                   'subgroups_real')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role1)
                apply_min_max(user_ids_role1, min1, max1)
                if min1 is not None:
                    minimum_total += min1

            if all_room_ids and len(all_room_ids) >0:
                apply_min_max(all_room_ids,0,1)
            
            if all_seat_ids and len(all_seat_ids) >0:
                apply_min_max(all_seat_ids,0,1)
            
            if role2 and subgroup2:
                user_ids_role2 = self.get_user_ids(role2["name"], 'roles').intersection(self.get_user_ids(subgroup2["name"],
                                                   'subgroups_real'))
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role2)
                apply_min_max(user_ids_role2, min2, max2)
                if min2 is not None:
                    minimum_total += min2
            elif role2:
                user_ids_role2 = self.get_user_ids(role2["name"], 'roles')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role2)
                apply_min_max(user_ids_role2, min2, max2)
                if min2 is not None:
                    minimum_total += min2
            elif subgroup2:
                user_ids_role2 = self.get_user_ids(subgroup2["name"],
                                                   'subgroups_real')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role2)
                apply_min_max(user_ids_role2, min2, max2)
                if min2 is not None:
                    minimum_total += min2


            if role3 and subgroup3:
                user_ids_role3 = self.get_user_ids(role3["name"], 'roles').intersection(self.get_user_ids(subgroup3["name"],
                                                   'subgroups_real'))
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role3)
                apply_min_max(user_ids_role3, min3, max3)
                if min3 is not None:
                    minimum_total += min3
            elif role3:
                user_ids_role3 = self.get_user_ids(role3["name"], 'roles')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role3)
                apply_min_max(user_ids_role3, min3, max3)
                if min3 is not None:
                    minimum_total += min3
            elif subgroup3:
                user_ids_role3 = self.get_user_ids(subgroup3["name"],
                                                   'subgroups_real')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role3)
                apply_min_max(user_ids_role3, min3, max3)
                if min3 is not None:
                    minimum_total += min3

            
            if role4 and subgroup4:
                user_ids_role4 = self.get_user_ids(role4["name"], 'roles').intersection(self.get_user_ids(subgroup4["name"],
                                                   'subgroups_real'))
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role4)
                apply_min_max(user_ids_role4, min4, max4)
                if min4 is not None:
                    minimum_total += min4
            elif role4:
                user_ids_role4 = self.get_user_ids(role4["name"], 'roles')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role4)
                apply_min_max(user_ids_role4, min4, max4)
                if min4 is not None:
                    minimum_total += min4
            elif subgroup4:
                user_ids_role4 = self.get_user_ids(subgroup4["name"],
                                                   'subgroups_real')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role4)
                apply_min_max(user_ids_role4, min4, max4)
                if min4 is not None:
                    minimum_total += min4

            
            if role5 and subgroup5:
                user_ids_role5 = self.get_user_ids(role5["name"], 'roles').intersection(self.get_user_ids(subgroup5["name"],
                                                   'subgroups_real'))
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role5)
                apply_min_max(user_ids_role5, min5, max5)
                if min5 is not None:
                    minimum_total += min5
            elif role5:
                user_ids_role5 = self.get_user_ids(role5["name"], 'roles')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role5)
                apply_min_max(user_ids_role5, min5, max5)
                if min5 is not None:
                    minimum_total += min5
            elif subgroup5:
                user_ids_role5 = self.get_user_ids(subgroup5["name"],
                                                   'subgroups_real')
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    user_ids_role5)
                apply_min_max(user_ids_role5, min5, max5)
                if min5 is not None:
                    minimum_total += min5

            if self.settings['blocks']:
                all_possible_ids_copy = all_possible_ids_copy.difference(
                    block_ids)
                apply_min_max(block_ids, 1, 1)

            if locationDisabled:
                apply_min_max(location_ids, 0, 0)
            else:
                apply_min_max(location_ids, 1, 1)

            for id in all_possible_ids_copy:
                model.Add(
                    all_possible_ids_ortools_obj[id] == 0).OnlyEnforceIf(bol)

        arr5 = []
        for capacity in self.capacities:
            user1 = capacity["user1"]
            if not capacity["disabled"] and user1 and user1[
                    "id"] in self.user_uuid_to_index_keys:
                # variable 6 - turn capacity constraint into variable
                bol = model.NewBoolVar('h')
                capacity_constraint_add(capacity, bol)
                arr5.append(bol)
        # Constraint - Make sure only one capacity constraint is valid at a time
        model.Add(sum(arr5) == 1)

        def add_forbidden_groups(role1_ids_union1, role2_ids_union2,
                                 subgroup_set, min, max, all_bol):
            for o in role1_ids_union1:
                o_subgroups = set(
                    self.users[o]["subgroups_real"]).intersection(subgroup_set)
                # Get Subgroups of this Group
                if all_bol:
                    min = len(o_subgroups)
                    max = len(o_subgroups)
                iiii=0
                for p in role2_ids_union2:
                    if p != o:
                        p_subgroups = set(
                            self.users[p]["subgroups_real"]).intersection(
                                subgroup_set)
                        o_p_subgroup_union = p_subgroups.intersection(
                            o_subgroups)
                        if (not (len(o_p_subgroup_union) >= min
                                 and len(o_p_subgroup_union) <= max)):
                            # print('orlando1')
                            if self.is_investigate:
                                if True:
                                    # print('orlando1')
                                    # Variable 7 - for grouping allow if investigating orange
                                    bol_here = model.NewBoolVar(
                                        f'Grouping {self.users[o]["firstName"]} {self.users[o]["lastName"]} & {self.users[p]["firstName"]} {self.users[p]["lastName"]}--{iiii}'
                                    )
                                    iiii+=1
                                    # print('snoody', bol_here)
                                    constraint_arr.append(bol_here)
                                    model.Add(
                                        sum([
                                            all_possible_ids_ortools_obj[o],
                                            all_possible_ids_ortools_obj[p]
                                        ]) == 2).OnlyEnforceIf(bol_here)
                                    model.Add(
                                        sum([
                                            all_possible_ids_ortools_obj[o],
                                            all_possible_ids_ortools_obj[p]
                                        ]) != 2).OnlyEnforceIf(bol_here.Not())

                            else:
                                
                                model.Add(all_possible_ids_ortools_obj[o] +
                                          all_possible_ids_ortools_obj[p] != 2)
                        pass

        user_availabilities_keys = user_availabilities.keys()
        user_capacities_keys = user_capacities.keys()

        for av in filter(lambda av: av['av'], self.availabilities):
            if av['resourceIds'][0] in self.user_uuid_to_index_keys:
                id = self.user_uuid_to_index[av['resourceIds'][0]]
                if id in user_availabilities_keys:
                    loc_ids = ''
                    if len(av['location']) > 0:
                        loc_ids = list(
                            map(
                                lambda num: self.user_uuid_to_index[num],
                                filter(
                                    lambda num: num in self.
                                    user_uuid_to_index_keys, av['location'])))
                    else:
                        loc_ids = location_ids.copy()
                    av_now = self.calc_availabilities(
                        av["start"].replace(':', ''),
                        av["end"].replace(':', ''), '%Y-%m-%dT%H%M%S%z')
                    for i in av_now:
                        for l in loc_ids:
                            user_availabilities[id][l][i] = 1
                            if not ('Activity' in self.users[id]['roles']
                                    and not self.users[id]['billable']):
                                user_availabilities_yellow[id][l][i] = 1

        if self.onCall:
            filtered_condition = filter(lambda av: not av['av'] or av['onCall'], self.availabilities)
        else:
            filtered_condition = filter(lambda av: not av['av'], self.availabilities)

        for av in filtered_condition:
            if av['resourceIds'][0] in self.user_uuid_to_index_keys:
                id = self.user_uuid_to_index[av['resourceIds'][0]]
                if id in user_availabilities_keys:
                    av_now = self.calc_availabilities(
                        av["start"].replace(':', ''),
                        av["end"].replace(':', ''), '%Y-%m-%dT%H%M%S%z')
                    for i in av_now:
                        for l in location_ids:
                            user_availabilities[id][l][i] = 0
                            user_availabilities_yellow[id][l][i] = 0
        
        roomy_ids = list(self.get_user_ids("Roomy"))
        client_ids_my = list(self.get_user_ids("Client"))
        employee_ids_my = list(self.get_user_ids("Employee"))
        employee_ids_my_ortool = []
        for id in employee_ids_my:
            employee_ids_my_ortool.append(all_possible_ids_ortools_obj[id])
        roomy_h = {}
        for id, obj in user_availabilities.items():
            if id in client_ids_my:
                for loc_i, slot_arr in obj.items():
                    if loc_i in roomy_ids:
                        if loc_i not in roomy_h:
                            roomy_h[loc_i] = zero_slots.copy()
                        roomy_h[loc_i] = [slot_arr[i] + roomy_h[loc_i][i] for i in range(len(slot_arr))]
        
        for r_id, slot_arr in roomy_h.items():
            clientratio = self.users[r_id]['clientratio']
            employeeratio = self.users[r_id]['employeeratio']
            max_client_num = __builtins__['max'](slot_arr)
            non_zero_elements = [x for x in slot_arr if x != 0]
            if clientratio == 0 or employeeratio == 0 or len(non_zero_elements) == 0:
                model.Add(all_possible_ids_ortools_obj[r_id] == 0)
            elif clientratio is not None:
                if employeeratio is None:
                    employeeratio = 1
                min_client_num = __builtins__['min'](non_zero_elements)
                min_emps_needed1 = math.ceil(max_client_num/clientratio*employeeratio)
                min_emps_needed2 = math.ceil(min_client_num/clientratio*employeeratio)
                if max_client_num == min_client_num:
                    model.Add(sum(employee_ids_my_ortool) == min_emps_needed1).OnlyEnforceIf(all_possible_ids_ortools_obj[r_id])
                else:
                    model.Add(sum(employee_ids_my_ortool) <= min_emps_needed1).OnlyEnforceIf(all_possible_ids_ortools_obj[r_id])
                    model.Add(sum(employee_ids_my_ortool) >= min_emps_needed2).OnlyEnforceIf(all_possible_ids_ortools_obj[r_id])

        for id in all_possible_ids:
            if 'Person' in self.users[id]["roles"]:
                for l in location_ids:
                    if 1 not in user_availabilities[id][l]:
                        model.Add(all_possible_ids_ortools_obj[id] +
                                  all_possible_ids_ortools_obj[l] != 2)

        user_ids = self.user_uuid_to_index.keys()
        work_together_arr = [0, 0, 0, 0, 0, 0, 0]
        work_together_obj = {}

        for event in self.events:
            bol = False
            activity_id = ''
            for res in event["resourceIds"]:
                if res in self.user_uuid_to_index_keys:

                    if self.users[self.user_uuid_to_index[res]]['billable']:
                        bol = True
                        break
            if bol:
                self.events_billable.append(event)
            else:
                self.events_nonbillable.append(event)

        for event in self.events:
            
            ev_now = self.calc_availabilities(event["start"],
                                              event["end_real_time"],
                                              '%Y-%m-%dT%H:%M:%S.%fZ', False)
            person_count = 0
            locations_arr = []
            work_together_obj_keys = work_together_obj.keys()
            for r in list(combinations(event["resourceIds"], 2)):
                if r[0] in self.user_uuid_to_index_keys and r[
                        1] in self.user_uuid_to_index_keys:
                    res1 = self.user_uuid_to_index[r[0]]
                    res2 = self.user_uuid_to_index[r[1]]
                    res_tup1 = (res1, res2)
                    res_tup2 = (res2, res1)
                    if len(ev_now) > 0:
                        ind = math.floor(ev_now[0] / (96*(15//self.slot_length)))
                        if res_tup1 in work_together_obj_keys:
                            work_together_obj[res_tup1][ind] = 1
                        elif res_tup2 in work_together_obj_keys:
                            work_together_obj[res_tup2][ind] = 1
                        else:
                            work_together_obj[
                                res_tup1] = work_together_arr.copy()
                            work_together_obj[res_tup1][ind] = 1
            roles_set = set()
            activityId = -1
            resourceIds_r = []
            for id in event["resourceIds"]:
                if id in self.user_uuid_to_index_keys:
                    index = self.user_uuid_to_index[id]
                    resourceIds_r.append(index)
                    roles5 = set(self.users[index]["roles"])
                    roles_set = roles_set.union(roles5)
                    if 'Activity' in self.users[index]["roles"]:
                        activityId = index
                    if id in user_ids and index in user_availabilities_keys:

                        if 'Location' in self.users[index]["roles"]:
                            locations_arr.append(index)
                        if 'Person' in self.users[index]["roles"] or 'Seat' in self.users[index]["roles"]:
                            person_count = person_count + 1
                            for i in ev_now:
                                for l in location_ids:
                                    user_availabilities[index][l][i] = 0
            if activityId >= 0 and activityId in e_pair_organized1.keys():
                resourceIds_r.append(activityId)
                bol_pair = False
                for roles in e_pair_organized1[activityId]:
                    # print('swimmers',set(roles),roles_set)
                    if len(set(roles).intersection(roles_set)) == len(roles):
                        resourceIds_r.sort()
                        resourceIds_r_tuple = tuple(resourceIds_r)
                        if resourceIds_r_tuple not in e_pair_slots.keys():
                            e_pair_slots[
                                resourceIds_r_tuple] = zero_slots.copy()
                        for i in ev_now:
                            e_pair_slots[resourceIds_r_tuple][i] = 1

            for l in locations_arr:
                if l in user_capacities_keys:
                    for i in ev_now:
                        user_capacities[l][i] = user_capacities[l][i] + \
                            person_count

        for id in user_capacities_keys:
            capacity = self.users[id]['capacity']
            if capacity:
                for i, value in enumerate(user_capacities[id]):
                    if value >= capacity:
                        for l in location_ids:
                            user_availabilities[id][l][i] = 0
        
        start1_4 = time.time()

        def events_billable_nonbillable(events, billable):
            n = 1
            if billable:
                n = 0
            for event in events:
                ev_now = self.calc_availabilities(event["start"],
                                                  event["end_real_time"],
                                                  '%Y-%m-%dT%H:%M:%S.%fZ',
                                                  False)
                for id in event["resourceIds"]:
                    if id in self.user_uuid_to_index_keys:
                        index = self.user_uuid_to_index[id]
                        if 'Person' in self.users[index]["roles"]:
                            for i in ev_now:
                                for l in location_ids:
                                    user_availabilities_yellow_blank[index][l][
                                        i] = n
                                    if 'Client' in self.users[index]["roles"]:
                                        user_availabilities_yellow[index][l][
                                            i] = 0

        events_billable_nonbillable(self.events_nonbillable, False)
        events_billable_nonbillable(self.events_billable, True)

        for index in user_availabilities_yellow:
            if 'Employee' in self.users[index]["roles"]:
                for l in location_ids:
                    for i in range(
                            len(user_availabilities_yellow_blank[index][l])):
                        if user_availabilities_yellow_blank[index][l][
                                i] == 1 and user_availabilities_yellow[index][
                                    l][i]:
                            user_availabilities_yellow[index][l][i] = 1
                        else:
                            user_availabilities_yellow[index][l][i] = 0

        #TODO- it's possible to remove
        if not self.is_orange or self.is_investigate:
            employees = self.get_user_ids("Employee")
            clients = self.get_user_ids("Client")
            for emp_id in employees:
                emp_branches = set(self.users[emp_id]['branches'])
                for client_id in clients:
                    client_branches = set(self.users[client_id]['branches'])
                    if len(emp_branches.intersection(client_branches)) == 0:
                        if not self.is_investigate:
                            model.AddForbiddenAssignments([
                                all_possible_ids_ortools_obj[emp_id],
                                all_possible_ids_ortools_obj[client_id]
                            ], [(1, 1)])
                        else:
                            # Variable 8 - investigate for branch, orange solution
                            bol_here = model.NewBoolVar(
                                f'Branch {self.users[emp_id]["firstName"]} {self.users[emp_id]["lastName"]} & {self.users[client_id]["firstName"]} {self.users[client_id]["lastName"]}'
                            )
                            constraint_arr.append(bol_here)
                            model.Add(
                                sum([
                                    all_possible_ids_ortools_obj[emp_id],
                                    all_possible_ids_ortools_obj[client_id]
                                ]) == 2).OnlyEnforceIf(bol_here)
                            model.Add(
                                sum([
                                    all_possible_ids_ortools_obj[emp_id],
                                    all_possible_ids_ortools_obj[client_id]
                                ]) != 2).OnlyEnforceIf(bol_here.Not())

# NOT MATCHING
        constraint_ids_dict = {}
        for ind, cus in enumerate(self.custom_constraints):
            c = cus
            
            if not (c['constraint'] == 'matching' or c['constraint']
                    == 'unmatching' or c['constraint'] == 'grouping'):
                id = ind
                constraint_ids_dict[id] = {
                    "min": c['min'],
                    "max": c['max'],
                    "frequency": c["frequency"],
                    "constraint": c["constraint"]
                }
                if c['type_or_specific'] == 'type':
                    users_antecedent = self.handle_general_constraint_type(
                        c["apply_constraint_to_this_role"],
                        c["apply_constraint_to_this_subgroup"],
                        c["apply_constraint_to_this_branch"])
                else:
                    users_antecedent = self.handle_general_constraint_specific_index(
                        c["apply_constraint_to_this_user"])
                if c['type_or_specific_consequence'] == 'type':
                    users_consequence = self.handle_general_constraint_type(
                        c["consequence_constraint_to_this_role"],
                        c["consequence_constraint_to_this_subgroup"],
                        c["consequence_constraint_to_this_branch"])
                else:
                    users_consequence = self.handle_general_constraint_specific_index(
                        c["consequence_constraint_to_this_user"])
                

                if c['constraint'] == 'time' or c['constraint'] == 'sessionlength':
                    frequency = c['frequency']
                    self.resources1.frequency_constraints.append({
                        "each_or_all_users":
                        c["each_or_all_users"],
                        "frequency":
                        c['frequency'],
                        "weight":
                        c["weight"],
                        "type":
                        c['constraint'],
                        "users_antecedent":
                        users_antecedent,
                        "users_consequence":
                        list(users_consequence),
                        "max":
                        c['max'],
                        "min":
                        c['min'],
                        "minSeconds":
                        c['minSeconds'],
                        "maxSeconds":
                        c['maxSeconds'],
                        "id":
                        c["id"],
                        "rank":
                        ind
                    })
                    for user_a in users_antecedent:
                        user_time_constraints = self.resources1.resources[
                            user_a].time_constraints[frequency]
                        obj_h = {
                            "min": c['min'],
                            "max": c['max'],
                            "units": c["units"],
                            "each_or_all_users": c["each_or_all_users"],
                            "weight": c["weight"],
                            "users_consequence": users_consequence,
                            "users_antecedent": users_antecedent
                        }
                        for user_c in users_consequence:
                            if user_c in user_time_constraints.keys():
                                pass
                            else:
                                self.resources1.resources[
                                    user_a].time_constraints[frequency][
                                        user_c] = obj_h
                                self.resources1.resources[
                                    user_c].time_constraints[frequency][
                                        user_a] = obj_h
                    pass
                else:
                    freq_obj = {
                        "each_or_all_users":
                        c["each_or_all_users"],
                        "frequency":
                        c['frequency'],
                        "weight":
                        c["weight"],
                        "users_antecedent":
                        users_antecedent,
                        "users_consequence":
                        list(users_consequence),
                        "max":
                        c['max'],
                        "min":
                        c['min'],
                        "minSeconds":
                        c['minSeconds'],
                        "maxSeconds":
                        c['maxSeconds'],
                        "description":c['description'],
                        "id":
                        c["id"],
                        "rank":
                        ind,
                        "antecedentTypeActivityId" : c["antecedentTypeActivityId"],
                        "antecedentLocationId" : c["antecedentLocationId"],
                        "rollover" : c["rollover"] if "rollover" in c.keys() else None,
                    }
                    type_label = 'nothing'
                    if c['constraint'] == 'usertouser':
                        for t in users_antecedent:
                            self.resources1.resources[t].onlyUserToUser[c['id']] = -1
                            self.resources1.onlyUserToUser = {**self.resources1.onlyUserToUser,c['id']:freq_obj}
                        c["id"]
                        together_arr_type = "work_together_arr"
                        type_label = 'frequency'
                    elif c['constraint'] == 'usertosession':
                        for t in users_antecedent:
                            self.resources1.resources[t].onlyUserToSession[c['id']] = -1
                            self.resources1.onlyUserToSession = {**self.resources1.onlyUserToSession,c['id']:freq_obj}
                        together_arr_type = "sessions_together_arr"
                        type_label = 'session'
                    else:
                        type_label = c['constraint']
                    freq_obj = {**freq_obj,"type":type_label,}
                    if c['constraint'] == 'priority':
                        freq_obj = {**freq_obj,"rank":c['max']}

                    self.resources1.frequency_constraints.append(freq_obj)

# # Matching && Unmatching
        users_ids_for_constraint = [i["id"] for i in self.users]
        users_ids_for_constraint = sorted(users_ids_for_constraint)
        for user_tup in combinations(users_ids_for_constraint,2):
                self.conflicted_constraints[tuple(user_tup)] = {"match":set(),"unmatch":set()}
        
        for ind, cus in enumerate(self.custom_constraints):
            c = cus
            if cus["id"] not in self.highPriority:
                continue 
            if not (c['constraint'] == 'matching' or c[
                    'constraint'] == 'unmatching' or c[
                        'constraint'] == 'grouping'):
                continue
            if c['type_or_specific'] == 'type':
                    users_antecedent = self.handle_general_constraint_type(
                        c["apply_constraint_to_this_role"],
                        c["apply_constraint_to_this_subgroup"], [])
                    users_antecedent = list(map(lambda x: tuple([self.users[x]['id']]),users_antecedent))
            else:
                users_antecedent = self.handle_general_constraint_specific(
                    c["apply_constraint_to_this_user"])

            if c['type_or_specific_consequence'] == 'type':
                users_consequence = self.handle_general_constraint_type(
                    c["consequence_constraint_to_this_role"],
                    c["consequence_constraint_to_this_subgroup"], [])
                users_consequence = list(map(lambda x: tuple([self.users[x]['id']]),users_consequence))
                
            else:
                users_consequence = self.handle_general_constraint_specific(
                    c["consequence_constraint_to_this_user"])
            if(c['id'] == '2d5601b2-63a2-4a85-b11d-ec44a75fe9d8'):
                    print('users_consequence_old',users_consequence)
                    print('users_antecedent_old',users_antecedent)
            
            merged_users_anti = []
            merged_users_cons = []
            for u_t in users_consequence:
                for i in u_t:
                    merged_users_cons.append(i)
            for u_t in users_antecedent:
                for i in u_t:
                    merged_users_anti.append(i)
            merged_users_cons = list(set(merged_users_cons))
            merged_users_anti = list(set(merged_users_anti))
            
            if c["constraint"] == "unmatching":
                for i in merged_users_anti:
                    for j in merged_users_cons:
                        sorted_tuple = tuple(sorted([i,j])) 
                        if sorted_tuple in self.conflicted_constraints.keys():
                            self.conflicted_constraints[sorted_tuple]["unmatch"].add(c["id"])
                users_anti = []
                users_cons = []
                for u_t in users_antecedent:
                    for i in u_t:
                        if i in users_ids_for_constraint:
                            users_anti.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[i]])
                for u_t in users_consequence:
                    for i in u_t:
                        if i in users_ids_for_constraint:
                            users_cons.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[i]])
                if len(users_anti) > 0 and len(users_cons) > 0:
                    arr_of_loc_act = []
                    if c["antecedentLocationId"] in users_ids_for_constraint:
                        arr_of_loc_act.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[c["antecedentLocationId"]]])
                    if c["antecedentTypeActivityId"] in users_ids_for_constraint:
                        arr_of_loc_act.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[c["antecedentTypeActivityId"]]])
                    if c["antecedentLocationId"] in users_ids_for_constraint or c["antecedentTypeActivityId"] in users_ids_for_constraint:
                        
                        for uu_anti in users_anti:
                            match_bool2 = model.NewBoolVar("match_bool2")
                            model.AddMinEquality(match_bool2,[uu_anti,*arr_of_loc_act])
                            model.Add(sum(users_cons) == 0).OnlyEnforceIf(match_bool2)
                    else:
                        match_bool = model.NewBoolVar("match_bool")
                        model.Add(sum(users_anti) == 1).OnlyEnforceIf(match_bool)
                        model.Add(sum(users_cons) == 0).OnlyEnforceIf(match_bool)
                        model.Add(sum(users_anti) == 0).OnlyEnforceIf(match_bool.Not())
            if c["constraint"] == "matching":
                person_ids = list(self.get_user_ids("Person"))
                users_role_consequence = self.handle_general_constraint_type(
                    c["consequence_constraint_to_this_role"],
                    [[]], [])
                
                users_role_consequence_ortools = []
                for i in merged_users_anti:
                    for j in merged_users_cons:
                        sorted_tuple = tuple(sorted([i,j])) 
                        if sorted_tuple in self.conflicted_constraints.keys():
                            self.conflicted_constraints[sorted_tuple]["match"].add(c["id"])
                users_anti = []
                users_anti_index = []
                users_cons = []
                for u_t in users_antecedent:
                    for i in u_t:
                        if i in users_ids_for_constraint:
                            users_anti_index.append(self.user_uuid_to_index[i])
                            users_anti.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[i]])
                
                for index_id in person_ids:
                    if index_id not in users_anti_index:
                        users_role_consequence_ortools.append(all_possible_ids_ortools_obj[index_id])
                    else:
                        print('hemmo3',index_id)
                for u_t in users_consequence:
                    for i in u_t:
                        if i in users_ids_for_constraint:
                            users_cons.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[i]])
                if len(users_anti) > 0 and len(users_cons) > 0:
                    
                    arr_of_loc_act = []
                    if c["antecedentLocationId"] in users_ids_for_constraint:
                        arr_of_loc_act.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[c["antecedentLocationId"]]])
                    if c["antecedentTypeActivityId"] in users_ids_for_constraint:
                        arr_of_loc_act.append(all_possible_ids_ortools_obj[self.user_uuid_to_index[c["antecedentTypeActivityId"]]])
                    
                    if c["antecedentLocationId"] in users_ids_for_constraint or c["antecedentTypeActivityId"] in users_ids_for_constraint:
                        for uu_anti in users_anti:
                            match_bool2 = model.NewBoolVar("match_bool2")
                            model.AddMinEquality(match_bool2,[uu_anti,*arr_of_loc_act,*users_role_consequence_ortools])
                            model.Add(sum(users_cons) == 1).OnlyEnforceIf(match_bool2)
                    else:
                        match_bool = model.NewBoolVar("match_bool")
                        match_bool_ortools = model.NewBoolVar("match_bool_ortools")
                        model.Add(sum(users_role_consequence_ortools) >= 1).OnlyEnforceIf(match_bool_ortools)
                        model.Add(sum(users_role_consequence_ortools) == 0).OnlyEnforceIf(match_bool_ortools.Not())
                        model.Add(sum(users_anti) == 1).OnlyEnforceIf(match_bool)
                        model.Add(sum(users_cons) >= 1).OnlyEnforceIf(match_bool).OnlyEnforceIf(match_bool_ortools)
                        model.Add(sum(users_anti) != 1).OnlyEnforceIf(match_bool.Not())
                        
                
        self.conflicted_constraints["conflicts"] = []
        for _i,v in self.conflicted_constraints.items():
            if _i == "conflicts":
                continue
            if len(v["match"]) > 0 and len(v["unmatch"]) > 0:
                for i in v["match"]:
                    for j in v["unmatch"]:
                        self.conflicted_constraints["conflicts"].append([i,j])
            
            
        
            
        start1_4_6 = time.time()
        for ind, cus in enumerate(self.custom_constraints):
            c = cus
            if (
                 c['constraint'] == 'grouping'):
                id = ind
                
                if c['type_or_specific'] == 'type':
                    users_antecedent = self.handle_general_constraint_type(
                        c["apply_constraint_to_this_role"],
                        c["apply_constraint_to_this_subgroup"], [])
                    users_antecedent = list(
                        map(lambda x: tuple([self.users[x]['id']]),
                            users_antecedent))
                else:
                    users_antecedent = self.handle_general_constraint_specific(
                        c["apply_constraint_to_this_user"])

                if c['type_or_specific_consequence'] == 'type':
                    users_consequence = self.handle_general_constraint_type(
                        c["consequence_constraint_to_this_role"],
                        c["consequence_constraint_to_this_subgroup"], [])
                    users_consequence = list(
                        map(lambda x: tuple([self.users[x]['id']]),
                            users_consequence))
                else:
                    users_consequence = self.handle_general_constraint_specific(
                        c["consequence_constraint_to_this_user"])
                if len(users_antecedent) == 0 or len(users_consequence) == 0:
                    continue

                if c['constraint'] == 'grouping':
                    group_name = c['grouping']
                    all_bol = c['all']
                    subgroup_set = set(self.subgroups[group_name])
                    users1 = []
                    users2 = []
                    for u in users_antecedent:
                        for j in u:
                            if j in self.user_uuid_to_index_keys:
                                users1.append(self.user_uuid_to_index[j])
                    for u in users_consequence:
                        for j in u:
                            if j in self.user_uuid_to_index_keys:
                                users2.append(self.user_uuid_to_index[j])
                    users1 = set(users1).intersection(all_possible_ids)
                    users2 = set(users2).intersection(all_possible_ids)
                    if c['limit']:
                        max = c["max"]
                        min = c["min"]
                    else:
                        min = 1
                        max = 100000000
                    add_forbidden_groups(users1, users2, subgroup_set, min,
                                         max, all_bol)

        self.user_availabilities_general_employees = {}
        self.user_availabilities_general_clients = {}

        for id in all_possible_ids:
            
            p_list = list(
                self.detect_range(
                    list(
                        sorted(
                            set(
                                self.convert_index_to_slot(
                                    list(
                                        np.array(
                                            list(user_availabilities[id].
                                                 values())).max(axis=0))))))))
            self.user_availabilities_general[self.users[id]["id"]] = copy.deepcopy(p_list)
            if 'Employee' in self.users[id]["roles"]: 
                self.user_availabilities_general_employees[self.users[id]["id"]] = copy.deepcopy(p_list)
            elif 'Client' in self.users[id]["roles"]:
                self.user_availabilities_general_clients[self.users[id]["id"]] = copy.deepcopy(p_list)

        start1_4_7 = time.time()

        solution_printer = VarArraySolutionPrinter([
            all_possible_ids_ortools_obj, slot_ortools_int, constraint_arr,
            priority_ortools_int, is_block_bol, self.users
        ],solution_limit_number)

        start1_5 = time.time()

        solver = cp_model.CpSolver()

        start1_6 = time.time()
        
        start1_6_1_1 = time.time()
        priority_obj = {}
        num = 0
        priority_arr = []
        for c in self.resources1.frequency_constraints:
            if c["type"] != "priority":
                continue
            rank = c['rank']
            antecedent_list = list(c["users_antecedent"])
            consequence_list = list(c["users_consequence"])
            if len(antecedent_list) == 0 or len(consequence_list) == 0:
                continue
            c_arr = []
            a_arr = []
            bol = model.NewBoolVar('f')
            int1 = model.NewIntVar(0,100,'d')
            model.Add(int1 == rank).OnlyEnforceIf(bol)
            model.Add(int1 == 100).OnlyEnforceIf(bol.Not())
            priority_arr.append(int1)
            for c in consequence_list:
                c_arr.append(all_possible_ids_ortools_obj[c])
            for a in antecedent_list:
                a_arr.append(all_possible_ids_ortools_obj[a])
            if len(a_arr) == 1:
                bol_a = a_arr[0]
            else:
                bol_a = model.NewBoolVar('f')
                model.AddMaxEquality(bol_a,a_arr)
            if len(c_arr) == 1:
                bol_c = c_arr[0]
            else:
                bol_c = model.NewBoolVar('f')
                model.AddMaxEquality(bol_c,c_arr) 
            num +=1    
            model.Add(bol_a + bol_c == 2).OnlyEnforceIf(bol)
            model.Add(bol_a + bol_c != 2).OnlyEnforceIf(bol.Not())

        efficiency_arr = []
        num = 0

        people = self.get_user_ids("Person")
        for p in people:
            if 'efficiency' in self.users[p].keys():
                bol = all_possible_ids_ortools_obj[p]
                int1 = model.NewIntVar(0,10000,'d')
                efficiency = self.users[p]['efficiency']
                if efficiency < 0:
                    efficiency = 0
                if efficiency > 100:
                    efficiency = 100
                model.Add((100 - efficiency) == int1).OnlyEnforceIf(bol)
                model.Add(int1 == 0).OnlyEnforceIf(bol.Not())
                efficiency_arr.append(int1)

        if len(priority_arr) > 0:
            model.AddMinEquality(priority_ortools_int, priority_arr)
        else:
            model.Add(priority_ortools_int == 0)

        solver.parameters.enumerate_all_solutions = True
        solver.parameters.log_search_progress = True

        model.AddDecisionStrategy([priority_ortools_int,*sorted_ortools_efficiency], cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE)
        solver.parameters.search_branching = cp_model.FIXED_SEARCH
        
        status = solver.Solve(model,solution_printer)
        all_solutions_clean = []
        events_poss = []
        events_poss_raw = []
        start_time = time.time()
        def get_slots_from_days(arr):
            p = set()
            s = set(range(7))
            t = s.difference(set(arr))
            for o in t:
                p = p.union(set(range(o * (96*(15//self.slot_length)), ((o + 1) * (96*(15//self.slot_length))))))
            return p

        def calculate_solutions(user_availabilities, yellow=False):

            for sol, slots in solution_printer.all_solutions.items():
                loc_id_arr1 = list(location_ids.intersection(set(sol)))
                loc_id = -1
                address = ''
                branch_id = ''
                priority = 0
                block = solution_printer.all_blocks[sol]
                if len(loc_id_arr1) > 0:
                    loc_id = loc_id_arr1[0]
                    address = self.users[loc_id]['address']
                    branch_id = self.users[loc_id]['branches'][0]
                arr = []
                person_count = 0
                bol = True
                locaition_arr = []

                forbidden_slots = get_slots_from_days(slots)
                forbidden_slots = set()
                client_arr = []
                for n in sol:
                    if 'Person' in self.users[n]["roles"]:
                        person_count = person_count + 1
                    if 'Location' in self.users[n]["roles"]:
                        locaition_arr.append(n)
                    if 'Client' in self.users[n]["roles"]:
                        client_arr.append(n)
                sol_inter = set(sol).intersection(set(
                    e_pair_organized2.keys()))
                dont_array = set()
                if len(sol_inter) > 0:
                    sol_not = set(sol).difference(sol_inter)
                    act = list(sol_inter)[0]
                    arr2 = [np.array(zero_slots.copy())]
                    for iq in e_pair_organized2[act].keys():
                        new_sol = list(sol_not.union(set([iq])))
                        for iq2 in e_pair_slots.keys():
                            new_sol_tuple = tuple(new_sol)
                            if len(set(iq2).intersection(
                                    set(sol))) >= len(set(iq2)) - 2:
                                dont_array = dont_array.union(set(iq2))
                                arr2.append(np.array(e_pair_slots[iq2]))
                                pass
                    if len(arr2) > 0:
                        arr.append(np.sum(np.vstack(arr2), axis=0))

                arr = []
                for n in sol:
                    
                    if loc_id == -1:
                        arr.append(
                            np.array(list(
                                user_availabilities[n].values())).max(axis=0))
                    else:
                        if n not in dont_array:
                            arr.append(np.array(
                                user_availabilities[n][loc_id]))
                         
                        else:
                            pass
                if bol:
                    result = np.prod(np.vstack(arr), axis=0)
                    if np.any(result):
                        pass

                    converted = self.convert_index_to_slot(result)
                 
                detected = detect_range(
                    list(sorted(set(converted).difference(forbidden_slots))))

                try:
                    for times in [tuple(i) for i in list(detected)]:
                        start = self.slot_to_time(times[0], slot_length)
                        end = self.slot_to_time(times[1], slot_length)
                        start_date_original = datetime.datetime.strptime(
                            self.start_date, "%Y-%m-%d")
                        start_day = math.floor(
                            times[0] /
                            (24 * 60 // slot_length)) - datetime.datetime.strptime(
                                self.start_date, '%Y-%m-%d').weekday()
                        end_day = math.floor(
                            times[1] /
                            (24 * 60 // slot_length)) - datetime.datetime.strptime(
                                self.start_date, '%Y-%m-%d').weekday()
                        start_day = (start_day + 7) % 7
                        end_day = (end_day + 7) % 7
                        new_start = datetime.datetime.strftime(
                            start_date_original +
                            datetime.timedelta(days=start_day), "%Y-%m-%d")
                        # print("bazo_mad : ",start_day,end_day,start_date_original,new_start)
                        new_end = datetime.datetime.strftime(
                            start_date_original +
                            datetime.timedelta(days=start_day + 1), "%Y-%m-%d")
                        new_end2 = datetime.datetime.strftime(
                            start_date_original +
                            datetime.timedelta(days=end_day), "%Y-%m-%d")
                        full_start = f'{new_start}T{start}.000Z'
                        full_end = f'{new_end2}T{end}.000Z'
                        resource_ids = []
                        resource_ids_raw = []
                        resource_names = []
                        sol_people = []
                        sol_location = []
                        sol_activity = []
                        sol_other = []
                        for user_index in sol:
                            roles = self.users[user_index]['roles']
                            if 'Person' in roles:
                                sol_people.append(user_index)
                            elif 'Activity' in roles:
                                sol_activity.append(user_index)
                            elif 'Location' in roles:
                                sol_location.append(user_index)
                            else:
                                sol_other.append(user_index)

                        sol_ordered = [
                            *sol_people, *sol_activity, *sol_location, *sol_other
                        ]

                        for user_index in sol_ordered:
                            user_id = self.users[user_index]["id"]
                            user_name = self.users[user_index]["firstName"]
                            if "lastName" in self.users[user_index].keys() and self.users[user_index]["lastName"] and len(self.users[user_index]["lastName"])>0:
                                user_name = f"{user_name} {self.users[user_index]['lastName'][0]}"
                            if 'efficiency' in self.users[user_index].keys():
                                user_name = f"{user_name} ({self.users[user_index]['efficiency']}%)"
                            if self.users[user_index][
                                    'id'] not in self.expanded_resources:
                                resource_names.append(user_name)
                            resource_ids.append(f'{user_id}a')

                        if loc_id == -1:
                            loc_real = None
                            loc_real2 = None
                        else:
                            loc_real = self.users[loc_id]['id']
                            loc_real2 = self.users[loc_id]['id']
                            home_id = self.get_id_from_role_array('Home', [loc_id])
                            if home_id != -1:
                                client_id = home_id = self.get_id_from_role_array('Client', sol)
                                if client_id != -1:
                                    address = self.users[client_id]['address']
                                
                            else:
                                pass
                              
                        priority = solution_printer.all_priorities[sol]
                        if priority == 0:
                            priority = 100
                        roomy_inter = set(sol).intersection(set(roomy_ids))
                        if len(roomy_inter) >= 1:
                            r_id = list(roomy_inter)[0]
                            if r_id in roomy_h.keys():
                                clientratio = self.users[r_id]['clientratio']
                                employeeratio = self.users[r_id]['employeeratio']
                                slot_arr = roomy_h[r_id]
                                slot_arr_p = slot_arr[times[0]:times[1]]
                                non_zero_elements = [x for x in slot_arr_p if x != 0]
                                max_client_num = __builtins__['max'](slot_arr_p)
                                min_emps_needed1 = math.ceil(max_client_num/clientratio*employeeratio)
                                if len(non_zero_elements) == 0 or len(set(sol).intersection(set(employee_ids_my))) != min_emps_needed1:
                                    continue
                        obj = {
                            "title": " - ".join(resource_names),
                            "resourceIds": resource_ids,
                            "resourceIds_r": sol,
                            "new_start": new_start,
                            "loc_id2": loc_real2,
                            "start": full_start,
                            "end": full_end,
                            "priority": priority,
                            "block": block,
                            "start_r": times[0],
                            "end_r": times[1],
                            'scheduled': False,
                            'address': address,
                            'branch_id': branch_id,
                            'loc_id': loc_real,
                            'id': str(uuid.uuid4()),
                            'orange_sol': False,
                        }
                        priority = 0
                        if yellow:
                            obj = {**obj, 'ov': 't'}
                        self.relevant_users = self.relevant_users.union(
                            set(sol))
                        obj2 = {
                            "title": resource_names,
                            "resourceIds": sol,
                            "start": times[0],
                            "end": times[1],
                            "reasons": []
                        }
                        if self.is_orange:
                            obj = {**obj, "reasons": [[]]}

                        if self.is_investigate:
                            pass
                            obj = {
                                **obj, "reasons":
                                list(solution_printer.
                                     all_solutions_constraints[sol].values())[0]
                            }
                        events_poss.append(obj)
                        events_poss_raw.append({**obj, **obj2})
                except Exception as e:
                    print("Exception:", e)
                
                all_solutions_clean.append(sol)
       
        calculate_solutions(user_availabilities)
        
        calculate_solutions(user_availabilities_yellow, True)
        
        self.events_poss = events_poss
        self.events_poss_raw = events_poss_raw
        
        
        return events_poss
    

    def all_main(self):
        self.main2()

