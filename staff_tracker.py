import itertools
import random
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


class Data_Gatherer_Staff_Tracker:
    def __init__(self, dict_data):
        self.start_date = dict_data["start_date"]
        self.end_date = dict_data["end_date"]
        d1 = datetime.datetime.strptime(dict_data['end_date'], "%Y-%m-%d")
        d2 = datetime.datetime.strptime(dict_data['start_date'], "%Y-%m-%d")
        self.branch_id = dict_data['branch']
        self.branchType_id = dict_data.get('branchType', None)
        self.activity_ids = dict_data['activities']
        if 'roles' not in dict_data.keys():
            self.roles = set()
        else:
            print('simmy',dict_data['roles'])
            self.roles = set(dict_data['roles'])
        self.distance_matrix = {}
        self.user_uuid_to_index = {}
        delta = d1 - d2
        self.offset = dict_data['offset']
        self.real_branches = []

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
            'settings': [],
        }
        d.update(dict_data)
        # print("what_is_this : ", d)
        some_data = Get_Data(d)
        self.some_data = some_data
        get_data_arr = []
        method_names = [
            'get_availability', 'get_resources', 'get_branches',
            'get_branch_structure', 'get_events_branch_activity'
        ]
        results = [None] * len(method_names)

        def call_method(method, index):
            result = method()
            results[index] = result

        threads = []
        time1 = time.time()
        # for i, method_name in enumerate(method_names):
        #     method = getattr(some_data, method_name)
        #     t = threading.Thread(target=call_method, args=(method, i))
        #     threads.append(t)
        #     t.start()
        # for t in threads:
        #     t.join()

        print('total_time', time.time() - time1)

        # self.availabilities = results[0]
        self.availabilities = some_data.get_availability()
        time2 = time.time()
        print('Timer availabilty_time: ', time2-time1)
        # self.users = results[1]
        self.users = some_data.get_resources(True)
        new_users = []
        if len(self.roles) > 0:
            for user in self.users:
                if 'Employee' in user['roles']:
                    if len(set(user['roles']).intersection(self.roles)) > 0:
                       new_users.append(user) 
                else:
                    new_users.append(user)
            self.users = new_users

        print('self.users',self.users)
        time3 = time.time()
        # print('Timer resource_time: ', time3-time2)
        # print('soolies', self.users)
        # print('Timer funder_time: ', time4-time3)
        # self.branches = results[2]
        self.branches = some_data.get_branches()
        time5 = time.time()
        # print('Timer capacity_time: ', time5-time4)
        # self.branch_structure = results[3]
        self.branch_structure = some_data.get_branch_structure()
        print('branch_structure',self.branch_structure)
        time6 = time.time()
        # print('Timer groupings_time: ', time6-time5)

        # print('Timer subgroups_time: ', time7-time6)

        # self.events = results[4]
        self.events = some_data.get_events_branch_activity()
        # for s in results[4]:
        #     for element in s:
        #         self.events.append(element)

        # print('smooshie', self.events)
        # print('smooshie2', self.availabilities)
        # print('smooshie3', self.users)
        # print('smooshie4', self.branches)
        # print('smooshie5', self.branch_structure)
        for i, user in enumerate(self.users):
            self.user_uuid_to_index[user["id"]] = i
        self.user_uuid_to_index_keys = self.user_uuid_to_index.keys()

    def get_user_ids(self, role_name, type_str='roles'):
        indexes = set()
        for i, user in enumerate(self.users):
            if role_name in user[type_str]:
                indexes.add(i)
        return indexes

    def time_to_slot(self, t, day, minutes):
        day = 0
        x = time.strptime(t, '%H:%M:%S')
        output = datetime.timedelta(
            hours=x.tm_hour, minutes=x.tm_min,
            seconds=x.tm_sec).total_seconds() / 60 / minutes
        output = int(day * 24 * 60 / minutes + output)
        return output

    def calc_availabilities(self,
                            start_time,
                            end_time,
                            format,
                            timezone_bol=True):
        start = datetime.datetime.strptime(start_time, format)
        end = datetime.datetime.strptime(end_time, format)

        if timezone_bol:
            start = start.astimezone(timezone.utc)
            end = end.astimezone(timezone.utc)

        interval_start = self.time_to_slot(start.strftime('%H:%M:%S'),
                                           (start.weekday() + 1) % 7, 15)
        interval_end = self.time_to_slot(end.strftime('%H:%M:%S'),
                                         (end.weekday() + 1) % 7, 15)
        ##CHEATCODE FIX for when availability is too late
        if interval_end <= interval_start:
            print('something',interval_end,start,end)
            interval_end = 90
            print('simple',interval_end,interval_start,interval_end)
        return [i for i in range(interval_start, interval_end)]

    def main(self,oncall=False):
        user_availabilities = {}
        total_slots = 96
        zero_slots = []
        for i in range(total_slots):
            zero_slots.append(0)

        all_possible_ids = self.get_user_ids("Resource")

        for id in all_possible_ids:
            user_availabilities[id] = {}
            user_availabilities[id] = zero_slots.copy()

        user_availabilities_keys = user_availabilities.keys()
        # print('soolhy', user_availabilities_keys)

        for av in filter(lambda av: av['av'] or av['onCall'], self.availabilities):
            print('loohy',av)
            d = av['resourceIds']
            if len(d) > 0:
                if d[0] in self.user_uuid_to_index_keys:
                    id = self.user_uuid_to_index[d[0]]
                    if id in user_availabilities_keys:
                        if oncall and av['branchId']:
                            self.users[id]['branches'] = [av['branchId']]
                        av_now = self.calc_availabilities(av["start"].replace(
                            ':', ''), av["end"].replace(':', ''), '%Y-%m-%dT%H%M%S%z')
                        if oncall:
                            print(av,'av_now',av_now,)
                        for i in av_now:
                            user_availabilities[id][i] = 1
        
        print('user_info',self.users)
        
        for av in filter(lambda av: not av['av'] and not av['onCall'], self.availabilities):
            d = av['resourceIds']
            if len(d) > 0:
                if d[0] in self.user_uuid_to_index_keys:
                    id = self.user_uuid_to_index[d[0]]
                    if id in user_availabilities_keys:
                        av_now = self.calc_availabilities(av["start"].replace(
                            ':', ''), av["end"].replace(':', ''), '%Y-%m-%dT%H%M%S%z')
                        for i in av_now:
                            user_availabilities[id][i] = 0

        # subtract_ids = ['c2c8fa42-d7dd-41df-b210-b66e2ff90650']
        subtract_ids = self.activity_ids
        print('leefly', subtract_ids)
        for event in self.events:
            ev_now = self.calc_availabilities(event["start"],
                                              event["end_real_time"],
                                              '%Y-%m-%dT%H:%M:%S.%fZ', False)

            # print('lifty2',)
            for id in event["resourceIds"]:
                if id in self.user_uuid_to_index_keys:
                    index = self.user_uuid_to_index[id]
                    # print('seemy', id)
                    if index in user_availabilities_keys:
                        for i in ev_now:
                            # print('jumpy')
                            user_availabilities[index][i] = 0

        data_final = []
        data_obj = {}

        # center_branch_id = '9c0b9117-e863-4932-bf32-374c5941a2a7'
        center_branch_id = self.branchType_id
        # print('smivery3', self.branches)
        for id, value in self.branch_structure.items():
            if self.branch_id in value:
                self.real_branches.append(id)

        for branch, value in self.branches.items():
            if value['branchTypeId'] == center_branch_id:
                if branch in self.real_branches:
                    obj = {"id":value['id'],"name": value['name'].strip(), "client_count": zero_slots.copy(
                    ), "emp_count": zero_slots.copy()}
                    print('semmer',value)
                    if value['userId']:
                        if value['userId'] in self.user_uuid_to_index_keys:
                            user_info = self.users[self.user_uuid_to_index[value['userId']]]
                            if "clientratio" in user_info.keys() and "employeeratio" in user_info.keys():
                                print('foober',user_info['clientratio'])
                                obj["clientratio"] = user_info['clientratio']
                                obj["employeeratio"] = user_info['employeeratio']
                    data_obj[branch] = obj

        for index, slots in user_availabilities.items():
            roles = self.users[index]['roles']
            branch = self.users[index]['branches'][0]
            if 'Employee' in roles or 'Client' in roles:
                count_type = "client_count"
                if 'Employee' in roles:
                    count_type = "emp_count"
                # branch_inter = set(self.branch_structure[branch]).intersection(
                #     set(data_obj.keys()))
                branch_inter = set(self.branch_structure[branch]).intersection(
                    set(data_obj.keys()))
                for b in branch_inter:
                    for i, s in enumerate(slots):
                        data_obj[b][count_type][i] += s

        data_scrubbed = []
        def get_target_employees(i):
            adder = math.floor(i/8) + 1
            emps = i + adder
            return emps
        for d, value in data_obj.items():
            arr = []
            # i = 44
            i = 6*4 + (self.offset // 60) * 4
            
            # for hour in range(0, 24):
            for hour in range(6, 19):
                for minute in range(0, 46, 15):
                    if i >= len(value["client_count"]):
                        break
                    target_employees = get_target_employees(value["client_count"][i])
                    if hour < 11 or (hour == 11 and minute <= 15) or hour > 15 or (hour == 15 and minute >= 30):
                        target_ratio = 1
                    else:
                        if value["client_count"][i] == 0:
                            target_ratio = 0
                            actual_ratio = 0
                        else:
                            target_ratio = target_employees / value["client_count"][i]
                    am_pm = 'p' if hour >= 12 else 'a'
                    formatted_hour = hour - 12 if hour > 12 else hour
                    time = f"{formatted_hour}:{str(minute).zfill(2)}{am_pm}"
                    minimum_need = 0
                    minimum_give = 0
                    if 'clientratio' in value.keys() and value['clientratio'] is not None and value['clientratio'] != 0:
                        print('target_ratio',value['clientratio'],1/value['clientratio'])
                        target_ratio = 1/value['clientratio']
                    if value["emp_count"][i] == 0 and value["client_count"][i] != 0:
                        v = .01
                        actual_ratio = .01
                    elif value["emp_count"][i] == 0 or value["client_count"][i] == 0 or target_ratio == 0:
                        v = 0
                        actual_ratio = 0
                    else:
                        actual_ratio = value["emp_count"][i] / value["client_count"][i]
                        v = round(actual_ratio / target_ratio,3)

                        minimum_need = round(
                            (1.1-(value["emp_count"][i])/value["client_count"][i])*value["client_count"][i])
                        minimum_give = round(
                            ((value["emp_count"][i])/value["client_count"][i]-1.125)*value["client_count"][i])

                    if minimum_give < 0:
                        minimum_give = 0
                    if minimum_need < 0:
                        minimum_need = 0
                    print('meeper')

                    arr.append(
                        {'x': time, 'y': v, 'value': random.randint(1, 20), 'target_ratio':round(target_ratio,3),'actual_ratio':round(actual_ratio,3), 'minimum_need': minimum_need, 'minimum_give': minimum_give, 'emp_count': value["emp_count"][i], 'client_count': value['client_count'][i]})
                    i += 1
            max_need = 0
            max_give = 0
            for i in (arr):
                if i['minimum_need'] > max_need:
                    max_need = i['minimum_need']
                if max_give == 0 and i['minimum_give'] > 0:
                    max_give = i['minimum_give']
                elif i['minimum_give'] < max_give and i['minimum_give'] > 0:
                    max_give = i['minimum_give']

            data_scrubbed.append(
                {"id":value['id'],"name": value['name'].strip(), "data": arr})

        length = len(data_scrubbed[0]["data"])
        r = -1
        for n in range(len(data_scrubbed[0]["data"])):
            r = r+1
            bol = False
            # print('flogy2', r)
            for i in range(len(data_scrubbed)):
                # print('foolgy', i, r)
                if r < len(data_scrubbed[i]["data"]):
                    if data_scrubbed[i]["data"][r]["y"] != 0:
                        bol = True
            if r < len(data_scrubbed[i]["data"]):
                if bol == False:
                    for t in range(len(data_scrubbed)):
                        del data_scrubbed[t]["data"][r]
                    r = r-1
                    # print('flogy1', r)

       
        for index, n in enumerate(data_scrubbed):
            max_need = 0
            max_give = 0
            for i in n['data']:
                if i['minimum_need'] > max_need:
                    max_need = i['minimum_need']
                if max_give == 0 and i['minimum_give'] > 0:
                    max_give = i['minimum_give']
                elif i['minimum_give'] < max_give and i['minimum_give'] > 0:
                    max_give = i['minimum_give']
            data_scrubbed[index] = {**n, 'max_need': max_need,
                                    'max_give': max_give}


        return data_scrubbed
