# ABA Scheduling Automation Script
from external import *

import gc
import math
import time
import random
import requests
import datetime
import itertools
import copy
import pickle
from random import randrange
from get_data import Get_Data
from itertools import combinations
from ortools.sat.python import cp_model
from concurrent.futures import ThreadPoolExecutor
from events_durations_calc import Time_Constraint_Handler
from solve import Solution_Generator, Data_Gatherer
from core.shared.event_schedular.main import EventScheduler
from todo import gap_finder
import uuid
import traceback
from calculate_drive_time import *
from external import round_to_nearest_interval
from analyzer import Analyzer

class Resource:
    def __init__(self, info):
        self.name = info['name']
        self.firstName = info['firstName']
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
        self.priorities = {}
        self.activities = {}
        self.events_scheduled = []
        self.events_notScheduled = []
        self.hard_bools = []


class Resources:
    def __init__(self, resources):
        self.resources = {}
        self.roles = {}
        self.events = []
        self.appointments = []
        self.priorities = {}
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


def get_weekday_index_by_date(date_string):
    date = datetime.datetime.strptime(date_string, "%Y-%m-%dT%H:%M:%S.%fZ")
    return date.weekday() + 1


class Automate:
    def __init__(self, resources, roles_hierarchy, given_data, resources_not,
                 distance_matrix, solution1):
        self.model = cp_model.CpModel()
        self.model_actual = cp_model
        self.solver = cp_model.CpSolver()

        self.created_events = list(
            map(lambda x: x["data"], solution1.created_events))
        self.resources1 = Resources(solution1.users)
        self.roles_hierarchy = roles_hierarchy
        self.printer = []
        self.gaps_to_minimize = []
        self.blocks = []
        self.events_break_session_length_long = {}
        self.events_break_session_length_short = {}
        self.scheduled_dict = {}
        self.person_blocks = {}
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
        self.solutions1 = solution1
        self.best_objective_bound = 0
        self.del_bol_array = 0
        self.update_bol_array = 0
        self.constraint_bols = []
        self.delete_bool = []
        self.update_bool = []
        self.hard_bools = []
        self.block_slot_adam = []
        self.clients_durations = {
            i: 0
            for i in self.find_ids_by_role(['Client'])
        }
        self.deletable_events = []
        self.bol_appointments_dict = {}
        self.persons_bol_appointments = {}
        self.fake_whites = {}
        self.count_fake = []
        self.individual_fake_boolean = {}
        self.created_fake_variables = {}
        self.priority_array = []
        self.drive_time_data = {}
        self.over_availability_events = []
        self.fake_gap_durations = []
        self.not_updated_count = 0
        self.employees_ids = []
        self.availability_persons = {}
    def get_team_vals(self):
        return self.team_vals

    def get_status_name(self):
        return self.status_name

    def get_best_objective_bound(self):
        return self.best_objective_bound

    def find_ids_by_role(self, roles):
        resources_ids = []
        for id, resource in self.resources1.resources.items():
            for resource_role in resource.roles:
                if resource_role in self.roles_hierarchy.keys():
                    print("activity5544 : ",resource_role)
                    if len(
                            intersection(
                                roles,
                                self.roles_hierarchy[resource_role])) > 0:
                        resources_ids.append(id)
        return list(set(resources_ids))

    def add_appointments_to_resources(self):
        slots = self.resources1.slots
        for tup, event in slots.items():
            resources_ids = list(tup)
            for res in resources_ids:
                bol = event[5]
                if res in self.resources1.resources.keys():
                    if event[5]:
                        self.resources1.resources[res].events_scheduled.append(
                            [tup, event])
                    else:
                        self.resources1.resources[
                            res].events_notScheduled.append([tup, event])

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

    def objective(self, id):
        objective_role = self.var_data["objective_role"]
        objective_activity = self.var_data["objectiveactivity"]
        objective_activity_without = []
        for i in self.var_data["objectiveactivity"]:
            if i not in self.var_data["notWorking"]:
                print('something_new1',i)
                objective_activity_without.append(i)
        # print('self.var_data["objectiveactivity"]',objective_activity)
        if self.var_data["run_with_teams"]:
            print('joomy2')
            objective_role = [self.var_data["objective_role"][0]]
        else:
            print('joomy3')
        if self.var_data['is_lunch_constraint']:
            self.var_data["maxEmployeeHoursPerDay"] += 0.5
        employees = list(set(self.find_ids_by_role(['Employee'])))
        clients = list(set(self.find_ids_by_role(['Client'])))
        for i in range(8):
            for idr in clients+employees:
                for obj_id in objective_activity:
                    s_val = self.get_appointments([[str(i)],[idr],[obj_id]])
                    if len(s_val) == 0:
                        continue
                    # print("bazo_length : ",len(s_val),s_val)
                    sum_val = sum(map(lambda num: num[6], s_val.values()))
                    
                    #self.model.Add(sum_val <= 5)
        self.employees_ids = employees
        
        people = employees + clients
        av_arr_for_fake_raw = self.solutions1.user_availabilities_general
        av_arr_for_fake = {}
        print('self.var_data["percentage"]',self.var_data["percentage"])
        for some_id in people:
            av_arr_for_fake[some_id] = {
                0: [],
                1: [],
                2: [],
                3: [],
                4: [],
                5: [],
                6: [],
                7: []
            }
        for some_id in people:
            for i in av_arr_for_fake_raw[some_id]:
                some_index = i[0] // (
                    (24 * 60) // self.var_data["slot_length"])
                av_arr_for_fake[some_id][some_index].append(i)
        # for i in range(8):
        #     for p_id in people:
        #         if av_arr_for_fake[p_id][i] == []:
        #             continue
        #         val_p = self.get_appointments([[p_id],[str(i)]])
        #         if len(val_p) == 0:
        #             continue
        #         val_p_duration_sum = sum(map(lambda x: x[0], val_p.values()))
        #         max_p = max([aa[1] for aa in av_arr_for_fake[p_id][i]])
        #         min_p = max([aa[0] for aa in av_arr_for_fake[p_id][i]])
        #         self.model.Add(max_p-min_p >= val_p_duration_sum)
        # av_arr_for_max_appointments = self.solutions1.user_availabilities_general
        # Should be calculated
        # for index in range(7):
        #     for client_id in clients:
        #         # av_data = av_arr_for_max_appointments[client_id]
        #         # av_start = min([i[0] for i in av_data])
        #         # av_end = max([i[1] for i in av_data])
        #         # min_session_in_slots = int(self.var_data["min_session_dur"]
        #         #                            ) // self.var_data["slot_length"]
        #         # max_appointment_num = (av_end - av_start) // min_session_in_slots
        #         val = self.get_appointments([[client_id], [str(index)]])
        #         print("bazo_max_index :  ", index, len(val))
        #         # b_appointment = list(map(lambda num: num[6], val.values()))
        #         # self.model.Add(
        #         #     sum(b_appointment) <= min(
        #         #         int(self.var_data["clientsMaxAppointmentsPerDay"]),
        #         #         max_appointment_num))
        #         # intervals = list(map(lambda num: num[2], val.values()))
        #         durations = list(map(lambda num: num[0], val.values()))
        #         if len(durations) > 0:
        #             self.model.Add(
        #                 sum(durations) <=
        #                 int(self.var_data["maxClientHoursPerDay"] * 60 //
        #                     self.var_data["slot_length"]))
        # for index in range(7):
        #     for emp_id in employees:
        #         # av_data = av_arr_for_max_appointments[emp_id]
        #         # av_start = min([i[0] for i in av_data])
        #         # av_end = max([i[1] for i in av_data])
        #         # min_session_in_slots = int(self.var_data["min_session_dur"]
        #         #                            ) // self.var_data["slot_length"]
        #         # max_appointment_num = (av_end - av_start) // min_session_in_slots
        #         val = self.get_appointments([[emp_id], [str(index)]])
        #         # b_appointment = list(map(lambda num: num[6], val.values()))
        #         # self.model.Add(
        #         #     sum(b_appointment) <= min(
        #         #         int(self.var_data["employeesMaxAppointmentsPerDay"]),
        #         #         max_appointment_num))
        #         durations = list(map(lambda num: num[0], val.values()))
        #         # intervals = list(map(lambda num: num[2], val.values()))
        #         if len(durations) > 0:
        #             self.model.Add(
        #                 sum(durations) <=
        #                 int(self.var_data["maxEmployeeHoursPerDay"] * 60 //
        #                     self.var_data["slot_length"]))

        # days_arrays = days_arr(self.var_data['slot_length'])
        # index = self.var_data['today_index']

        val = self.get_appointments([self.find_ids_by_role(objective_role),objective_activity])
        val_without = self.get_appointments([self.find_ids_by_role(objective_role),objective_activity_without])
        # print("what_is_bug :", val, val.keys(), len(val.keys()),
        #       objective_activity)
        # print("bazo_some_val : ", val.keys())
        undeleted_appointments = []
        del_bol_array = []
        update_bol_array = []
        if self.var_data["percentage"] != 0:
            for i in val.values():
                if i[5]:
                    undeleted_appointments.append(i[0])
                    del_bol_array.append(i[11])
                    update_bol_array.append(i[16])
            if self.var_data["percentage"] != 0:
                print("bazo_del_bol_len : ",len(del_bol_array),len(update_bol_array),len(val))
                if len(del_bol_array) > 0 and len(update_bol_array) > 0:
                    self.model.Add(sum(del_bol_array) >= len(del_bol_array)-self.var_data["percentage"])
                    self.model.Add(sum(update_bol_array) >= len(update_bol_array)- self.var_data["percentage"])
                # self.model.Add(2 * (len(del_bol_array) - sum(del_bol_array) - 1) <=(len(update_bol_array) - sum(update_bol_array)))
                pass
            if self.var_data["percentage"] == 0:
                self.model.Add(sum(del_bol_array) == 0)

        # else:
        #     self.model.Add(sum(update_bol_array) == len(update_bol_array))
        # self.model.Add(
        #     sum(update_bol_array) >= len(update_bol_array) -
        #     self.var_data["percentage"])
        # self.model.Add(
        #     sum(del_bol_array) >= int((
        #         (100 - self.var_data["percentage"]) / 100) *
        #         len(del_bol_array)))

        # if self.var_data["percentage"] == 0:
        #     self.model.Add(sum(del_bol_array) == len(del_bol_array))

        del_bol_array = self.delete_bool
        update_bol_array = self.update_bool
        # for i in val.values():
        #     if i[5]:
        #         undeleted_appointments.append(i[0])
        #         del_bol_array.append(i[11])

        # min_undeleted_appointments = self.direct_events_sum * (
        #     100 - self.var_data["percentage"]) // 100
        # self.model.Add(
        #     sum(undeleted_appointments) >= min_undeleted_appointments)
        # bound = self.model.NewIntVar(0, 10000000, "bound")
        # # self.model.Add(bound == sum(del_bol_array))
        # self.del_bol_array = bound
        # Squared objective start

        arr = []
        orange_array = []
        white_array = []
        normal_orange_array = []
        normal_white_array = []
        j = 0
        # for i in map(lambda num: num, val.values()):
        #     target = self.model.NewIntVar(0, 1000000, f"target{j}")
        #     self.model.AddMultiplicationEquality(target, [i[0], i[0]])
        #     arr.append(target)
        #     if i[10]:
        #         orange_array.append(target)
        #         normal_orange_array.append(i[0])
        #         normal_orange_array.append(i[14])
        #     else:
        #         white_array.append(target)
        #         normal_white_array.append(i[0])
        #         normal_white_array.append(i[14])
        #     j += 1
        # self.model.Maximize(
        #     sum(arr) + sum(del_bol_array)
        #     + sum(self.constraint_bols)
        # )

        # self.model.Maximize(2 * sum(white_array) + sum(orange_array) +
        #                     sum(del_bol_array)
        #                     # + sum(self.constraint_bols)
        #
        #                      )
        # if True or self.var_data["part1"]:
        #     num = 3
        #     for i in range(num):
        #         self.block_slot_adam.append(
        #             self.model.NewIntVar(0, 10000, 'd'))

        #     for index, n in enumerate(self.block_slot_adam):
        #         for index2, n2 in enumerate(self.block_slot_adam):
        #             if index != index2:
        #                 self.model.Add(n2 != n)

        #     # val_scheduled = list(
        #     #     filter(lambda num: not num[5] or num[5], val.values()))
        #     val_scheduled = list(
        #         filter(lambda num: num[5], val.values()))
        #     for v in val_scheduled:
        #         start = v[3]
        #         end = v[4]
        #         b_appointment = v[6]
        #         d_bol = self.model.NewBoolVar('f')
        #         dur = v[0]
        #         actual_bol = self.model.NewBoolVar('k')
        #         self.model.Add(dur == 0).OnlyEnforceIf(d_bol.Not())
        #         self.model.Add(dur > 0).OnlyEnforceIf(d_bol)
        #         self.model.AddMinEquality(actual_bol, [b_appointment, d_bol])
        #         bol_arr = []
        #         for index, n in enumerate(self.block_slot_adam):
        #             bol = self.model.NewBoolVar('f')
        #             bol2 = self.model.NewBoolVar('f')
        #             bol_arr.append(bol)
        #             bol_arr.append(bol2)
        #             self.model.Add(start == n).OnlyEnforceIf(bol)
        #             self.model.Add(start != n).OnlyEnforceIf(bol.Not())
        #             self.model.Add(end == n).OnlyEnforceIf(bol2)
        #             self.model.Add(end != n).OnlyEnforceIf(bol2.Not())
        #         self.model.Add(sum(bol_arr) >= 1).OnlyEnforceIf(actual_bol)
        #         self.model.Add(sum(bol_arr) <= 2).OnlyEnforceIf(actual_bol)
        # for bol_dict in self.bol_appointments_dict.values():
        #     self.model.Add(sum(bol_dict) <= 1)

        adam_max_total_hours = int(
            get_number_per_slot(self.solutions1)
            # //(60 // self.var_data['slot_length'])
        )
        # print("bazo_adam_max_total_hours : ", adam_max_total_hours)
        # self.model.Add(
        #     sum(map(lambda num: num[0], val.values())) <= adam_max_total_hours)
        #** New part1 objective with multiple roles and actives
        try : 
            if self.var_data["part1"]:
                appointments_dict = {}
                len_role = len(objective_role)
                len_actives = len(objective_activity)
                while len_role > 0:
                    for delta_ in range(len_actives):
                        appointments_dict[len_role*(delta_+1)*1] = []
                    len_role -= 1
                # print("bb_app : ",appointments_dict)
                len_role = len(objective_role)
                len_actives = len(objective_activity)
                for index1,value1 in enumerate(objective_role):
                    for index2,value2 in enumerate(objective_activity):
                        app_value = self.get_appointments([
                            self.find_ids_by_role([value1]),
                        [value2]
                        ])
                        appointments_dict[(len_role-index1)*(len_actives-index2)*1].append(app_value)
                
                # self.model.Maximize(
                #      sum([sum([sum(map(lambda num: num[0] if not num[10] else 0, v2.values())) for v2 in v])*i*100 for i,v in appointments_dict.items()])
                #      +sum([sum([sum(map(lambda num: num[0] if num[10] else 0, v2.values())) for v2 in v])*i*90 for i,v in appointments_dict.items()])
                #     #-sum([sum([sum(map(lambda num: num[6] if not num[10] else 0, v2.values())) for v2 in v])*i*39 for i,v in appointments_dict.items()])
                #      #-sum([sum([sum(map(lambda num: num[6] if num[10] else 0, v2.values())) for v2 in v])*i*40 for i,v in appointments_dict.items()])
                     
                # )
                
                # print("bb_app2 : ",{i : len(v) for i,v in appointments_dict.items()})
        except Exception as e:
            print("bb_error_adam2 : ",e)
            traceback.print_exc()
        #**
        
        # self.model.Maximize(
        #     2 * sum(white_array) + sum(orange_array) + sum(del_bol_array) +
        #     sum(self.constraint_bols) +
        #     (sum(normal_white_array) + sum(normal_orange_array)) * 10000)

        # self.model.Maximize(
        #     sum(white_array) + sum(del_bol_array) +
        #     sum(self.constraint_bols)
        #     + (sum(white_array) + sum(orange_array)) * 100)
        # Squared objective end

        # print('guru_guru', "success2")
        # mm_week = self.var_data["max_hours"]
        # weekly_avb = self.var_data["weekly_avb"]
        # c_dict = {
        #     k: v
        #     for sub_dict in mm_week.values() for k, v in sub_dict.items()
        # }

        # max_week = max([v for k, v in weekly_avb.items()])
        # total_sum = []
        # for k, v in c_dict.items():
        #     c_dict[k] = int(10 * max_week * v / weekly_avb[k])
        # print('guru_guru', "success3")
        # for k, v in c_dict.items():
        #     therapy_val = self.get_appointments(
        #         [[k], objective_activity,
        #          list(range(days_arrays[index], days_arrays[index + 1]))])
        #     total_sum.append(
        #         v * sum(map(lambda num: num[0], therapy_val.values())))

        # self.model.Maximize(
        #     sum(map(lambda num: num[0], val.values())) + sum(del_bol_array))

        # for per in self.persons_bol_appointments.values():
        #     self.model.Add(sum(per) <= 4)

        # THIS MAKES EMPLOYEE ON HAVE 1 APPOINTMENT WITH CLIENT PER DAY
        try : 
            if True or not self.var_data["part1"]:
                # print("our_percent : ", self.var_data["percentage"],self.not_updated_count)
                print("bazo_len_values : ",len(val))
                
                appointments_dict = {}
                len_role = len(objective_role)
                len_actives = len(objective_activity)
                while len_role > 0:
                    for delta_ in range(len_actives):
                        appointments_dict[len_role*(delta_+1)*1] = []
                    len_role -= 1
                # print("bb_app : ",appointments_dict)
                len_role = len(objective_role)
                len_actives = len(objective_activity)
                for index1,value1 in enumerate(objective_role):
                    for index2,value2 in enumerate(objective_activity):
                        app_value = self.get_appointments([
                            self.find_ids_by_role([value1]),
                        [value2]
                        ])
                        appointments_dict[(len_role-index1)*(len_actives-index2)*1].append(app_value)
                

                white_durations = []
                orange_durations = []
                white_keys = []
                orange_keys = []
                all_keys = []
                white_durations_priority = []
                orange_durations_priority = []
                white_durations_on = []
                orange_durations_on = []
                for key,i in val.items():
                    all_keys.append(key)
                for key,i in val_without.items():
                    priority = self.resources1.priorities[key]['priorities']
                    print('simmty',priority)
                    if not i[10]:
                        #white_keys.append(key)
                        white_durations.append(i[0])
                        white_durations_priority.append(i[0]*priority)
                        white_durations_on.append(i[6])
                    else:
                        #orange_keys.append(key)
                        orange_durations.append(i[0])
                        orange_durations_priority.append(i[0]*priority)
                        orange_durations_on.append(i[6])
                
                print('all_keys',all_keys)
                for key,value in self.resources1.slots.items():
                    if key not in all_keys and not value[5]:
                        self.model.Add(value[0] == 0)
                

                    
                
                
                days_arrays = days_arr(self.var_data['slot_length'])
                # for index, x in enumerate(days_arrays[1:]):
                #     print('something',self.var_data['today_index'],index)
                #     if index == self.var_data['today_index']:
                #         for client_id in clients:
                #             val_client = self.get_appointments(
                #                 [[client_id], list(range(days_arrays[index],days_arrays[index + 1])),objective_activity])
                #             actual_durations = list(map(lambda num: num[-1] if num[5] else 0, val_client.values()))
                #             future_durations = list(map(lambda num: num[0], val_client.values()))
                #             self.model.Add(sum(future_durations) >= sum(actual_durations))
                #             print('goomby',sum(actual_durations))

                #durations = list(map(lambda num: num[0], val.values()))
                self.solver.parameters.search_branching = cp_model.FIXED_SEARCH
                self.model.AddDecisionStrategy([*white_durations,*orange_durations], cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE)
                print('hyert',len(white_durations),len(orange_durations),white_durations)
                #part2
                print('stiffer',self.constraint_bols)
                
           
                #part2
                self.model.Maximize(
                    sum([*white_durations,*orange_durations])*10000
                    #sum([*white_durations])*2000
                    
                    + sum(del_bol_array)*500 + sum(update_bol_array)*300
                   # + sum([*white_durations])*50
                   #+sum(self.constraint_bols)*50
                   #-max_deviation*20
                   +sum([*white_durations_priority,*orange_durations_priority])*100
                   -sum([*white_durations_on])
                    -sum([*orange_durations_on])*2
                    #sum([sum([sum(map(lambda num: v2[num][0] if not v2[num][10] else 0, v2.keys())) for v2 in v]) for i,v in appointments_dict.items()])
                    #sum([sum([sum(map(lambda num: v2[num][0], v2.keys())) for v2 in v]) for i,v in appointments_dict.items()])
                    #sum([sum([sum(map(lambda num: v2[num][0]*self.resources1.priorities[num]['priorities'], v2.keys())) for v2 in v]) for i,v in appointments_dict.items()])
                     #sum([sum([sum(map(lambda num: v2[num][0] if not v2[num][10] else 0, v2.keys())) for v2 in v])*i*100 for i,v in appointments_dict.items()])
                     #+sum([sum([sum(map(lambda num: v2[num][0] if v2[num][10] else 0, v2.keys())) for v2 in v])*i*90 for i,v in appointments_dict.items()])
                    #+ sum(del_bol_array) + sum(update_bol_array)
                    # - sum(self.gaps_to_minimize)*1000000
                   #-sum([sum([sum(map(lambda num: num[6] if not num[10] else 0, v2.values())) for v2 in v])*i*39 for i,v in appointments_dict.items()])
                   #-sum([sum([sum(map(lambda num: num[6] if num[10] else 0, v2.values())) for v2 in v])*i*40 for i,v in appointments_dict.items()])
                     
                )

        except Exception as e:
            print("bb_error_adam1 : ",e)
            traceback.print_exc()
        
        if not self.var_data["part1"] and False: # old
            print("part2_ok")
            # if True or not self.var_data["part2_in_part1"]:
            #     for id_of_client, val_of_client in self.clients_durations.items(
            #     ):
            #         val_one_client = self.get_appointments(
            #             [[id_of_client], objective_activity,[self.var_data["today_index"]]])
            #         print("Client_Error : ", val_one_client)
            #         sum_client = sum(
            #             map(lambda x: x[0], val_one_client.values()))
            #         print("Before : ", id_of_client, val_of_client)
            #         self.model.Add(sum_client >= val_of_client)
            # self.model.Add(
            #     sum(map(lambda num: num[0], val.values())) >=
            #     self.direct_events_sum)
            # self.model.Add(sum(self.hard_bools) >= 1)
            # print("---length of hard_bools: ", len(self.hard_bools))
            # val2 = list(filter(lambda num: not num[5], val.values()))
            bill_arr_part2 = []
            for bill_appoint_id in objective_activity:
                val_bill = self.get_appointments([
                    self.find_ids_by_role(objective_role),
                    [bill_appoint_id]  # , [self.var_data["today_index"]]
                ])
                # print(val_bill)
                bill_arr_part2.append(val_bill)
            ll = len(bill_arr_part2)
            self.model.Maximize(
                sum([sum(map(lambda num: num[0] if not num[10] else 0, v.values()))*(ll-i)*5 for i,v in enumerate(bill_arr_part2)])
                +sum([sum(map(lambda num: num[0] if num[10] else 0, v.values()))*(ll-i)*3 for i,v in enumerate(bill_arr_part2)])
                -sum([sum(map(lambda num: num[6] if not num[10] else 0, v.values()))*(ll-i)*2 for i,v in enumerate(bill_arr_part2)])
                -sum([sum(map(lambda num: num[6] if num[10] else 0, v.values()))*(ll-i)*3 for i,v in enumerate(bill_arr_part2)])

                + sum(del_bol_array) + sum(update_bol_array)
                # sum(self.constraint_bols)
                # + sum(self.hard_bools) * 100
            )
            print("bazo_percentage  : ", self.var_data["percentage"])
            self.model.Add(len(del_bol_array)-sum(del_bol_array)
                           <= self.var_data["percentage"])

            # bl_arr = []
            # for i in list(map(lambda num: num[0], val.values())):
            #     bl = self.model.NewBoolVar("bl")
            #     self.model.Add(i != 0).OnlyEnforceIf(bl)
            #     self.model.Add(i == 0).OnlyEnforceIf(bl.Not())
            #     bl_arr.append(bl)
            # print('silly5', len(list(map(lambda num: num[0], val.values()))))

            # self.model.Add(sum(map(lambda num: num[0], val.values())) > 549)
            # print("siri : ", self.direct_events_sum)
            # self.model.Maximize(
            #     sum(map(lambda num: num[0], val_one_client.values())))
            # self.model.Maximize(
            #     sum(map(lambda num: num[0], val.values())) * 10 +
            #     sum(del_bol_array) + sum(self.constraint_bols))

    def solve(self):
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.var_data[
            'max_time_in_seconds']
        if self.var_data["companyId"] == "090121f7-8598-463e-92c4-f501c2576e60":
            self.solver.parameters.max_time_in_seconds = 240.0
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.num_search_workers = self.var_data["workers"] if "workers" in self.var_data.keys() else 128
        # self.solver.parameters.num_search_workers = 8
        #self.solver.parameters.num_search_workers = 16
        # self.solver.parameters.detect_table_with_cost = True
        # # self.solver.parameters.diversify_lns_params = True
        # # self.solver.parameters.add_lin_max_cuts = True
        # self.solver.parameters.add_lp_constraints_lazily = True
        # # self.solver.parameters.add_clique_cuts = True
        # self.solver.parameters.also_bump_variables_in_conflict_reasons = True
        # self.solver.parameters.search_branching = "AUTOMATIC"
        # self.solver.parameters.convert_intervals = True
        # self.solver.parameters.use_timetable_edge_finding_in_cumulative = True
        # self.solver.parameters.use_probing_search = True
        self.solver.log_callback = print
        solution_printer = VarArraySolutionPrinter([])
        self.printer = solution_printer
        status = self.solver.Solve(self.model, solution_printer)
        print('Status = %s' % self.solver.StatusName(status))
        print('Number of solutions found: %i' %
              solution_printer.solution_count())
        # print("bazo_model : ", self.model.ModelStats())
        # self.model.ExportToFile("/bazo_model.dot")
        self.status_name = self.solver.StatusName(status)
        self.best_objective_bound = self.solver.BestObjectiveBound()
        # print("bazo_proto:", self.solver.ResponseProto())
        # print("bazo_proto2:", self.solver.ResponseStats())
        # print("bazo_bool : ", self.solver.NumBooleans())

        # Inspired by McKenna strategy


    def data_insert(self, data):
        # print("bazo_data : ", data)
        current_utc_time = datetime.datetime.now(datetime.timezone.utc).time()
        now = str(current_utc_time)[:8]
        print("now :",self.var_data["start_date"]+"T"+now)
        filtered_people = []
        # filtered_people = ['e23a24bc-89d6-4dec-83f9-a65f8790463f', '44aa6d6c-e07b-40c1-bf49-6fc798c95524', '0ed471f2-4ece-476a-af8c-a63558c21b87', 'fa658025-f602-4eda-ad14-8143f737ef9c', 'a808545c-0b0f-46da-9b24-e334c9caee1e', 'ccce9dcd-29af-4575-8be5-c3568da21ca3', 'e0ff44e2-ded3-4df2-b0ee-4367f305decc', '67be20a6-e0e4-49a8-aa05-1847d70e003c', '917df0a2-7d65-42e6-8ee0-c45570f7fee2', 'a7597d3b-0f88-4337-97b5-f6e603e5109d', '6ca9e2a7-1ce3-4254-9524-0859c006806a', 'c9feb968-9561-4378-afd3-940948e94cb6', '2809515d-2598-46a0-aa3f-89b5915b26e4']
        
        people5 = self.find_ids_by_role(['Person'])
        activity5 = self.find_ids_by_role(['Activity'])
        print("activity555 : ",activity5)
        people_array_filter = []
        resource5 = self.find_ids_by_role(['Resource'])
        funders = self.find_ids_by_role(['Funder'])
        location_ids = self.find_ids_by_role(['Location'])
        not_in = funders+location_ids
        resource_without_funder = [i for i in resource5 if not i in not_in]
        clients_ids = self.find_ids_by_role(['Client'])
        # set_clients_ids = set(clients_ids)
        emp_ids = self.find_ids_by_role(['Employee'])
        av_arr_for_fake_raw = self.solutions1.user_availabilities_general
        av_arr_for_fake = {}
        for some_id in people5:
            av_arr_for_fake[some_id] = {0: [],1: [],2: [],3: [],4: [],5: [],6: [],7: []}
        for some_id in people5:
            for i in av_arr_for_fake_raw[some_id]:
                some_index = i[0] // (
                    (24 * 60) // self.var_data["slot_length"])
                av_arr_for_fake[some_id][some_index].append(i)
        self.availability_persons = av_arr_for_fake
        set_emp_ids = set(emp_ids)
        block_person_obj = {}
        for i in people5:
            self.persons_bol_appointments[i] = []
        if not self.var_data["part1"]:
            arr_of_some_client_ids = []
            xy = []
            # print("--->", len(self.var_data["sols_with_events"]))
            for i in self.var_data["sols_with_events"]:
                paired_array = []
                for j in i["resourceIds"]:
                    if len(intersection([j[:-1]], people5)) > 0:
                        paired_array.append(j[:-1])
                xy.append(sorted(paired_array))

            # for i in self.var_data["sols_with_events"]:
            #     for j in i["resourceIds"][:2]:
            #         xy.append(j[:-1])
            # print(list(set(xy)))
            arr_of_some_client_ids = xy
            # print("some_client_ids_length: ", len(arr_of_some_client_ids))
        waitlist_count = 1
        event_ids = []
        bug_arr = []
        # people = self.find_ids_by_role([self.var_data['insert_data_role']])
        people = self.find_ids_by_role(['Resource'])
        fake_events = []
        for ss_id in people5:
            fake_events += self.var_data["fake_user_starts_ends"][ss_id]["fakes"]
        # print("bazo_fake_events : ",fake_events)
        data_arr = data + self.created_events + self.var_data["gg"] + fake_events #+self.var_data["clients_events_fake"]

        priority_arr = []
        # print('loony',len(data_arr))

        print('diller',len(data_arr))
        for info in data_arr:
            # if "6f390447-6dfe-4705-a795-34a817a378b1a" in info["resourceIds"]:
            #     print("bazo_lunch_found_with_a")
            # if "6f390447-6dfe-4705-a795-34a817a378b1" in info["resourceIds"]:
            #     print("bazo_lunch_found")
            # print("bazo_lunch_bug  :", info["resourceIds"])
            if not info["scheduled"]:
                # print(info)
                slots = time_to_int(info, self.var_data['slot_length'])
                interval_start = slots[0]
                duration = slots[1]
                interval_end = slots[2]
                people_array_filter += intersection(people5,[i[:-1]for i in info["resourceIds"]])
                intersection_of_resources = sorted(list(set(intersection(resource_without_funder,[i[:-1]for i in info["resourceIds"]]))))
                # if len(intersection_of_resources) == 2:
                my_obj = {
                    'start': interval_start,
                    "duration": duration,
                    "end": interval_end
                }
                self.bol_appointments_dict[tuple(intersection_of_resources)] = []
                if tuple(intersection_of_resources) in self.scheduled_dict.keys():
                    self.scheduled_dict[tuple(intersection_of_resources)].append(my_obj)
                else:
                    print("bazo_1234")
                    self.scheduled_dict[tuple(intersection_of_resources)] = [ my_obj]

            loc_id2 = info["loc_id2"] if "loc_id2" in info.keys() else ""
            if 'priority' in info.keys():
                if type(info['priority']) == int:
                    priority = info['priority']
                    if priority not in priority_arr:
                        priority_arr.append(priority)
        priority_arr.sort(reverse=True)
        #*** Do not touch appointments which starts before less than 30 min
        current_utc_time = datetime.datetime.now(datetime.timezone.utc)
        formatted_z_time = current_utc_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        formatted_z_time = str(formatted_z_time)
        # print("type_of_z_time : ",formatted_z_time)
        #***
        print("bazo_filterd_people : ",list(set(people_array_filter)))
        # print("bazo6", len(data_arr),len(set([i["loc_id"] for i in data_arr])),set([i["loc_id"] for i in data_arr]))
        
        #********************************
        # Filtering data
        # filtered_data = []
        # for info in data_arr:
        #     if not info["scheduled"]:
        #         len1 = len(intersection(people5,[i[:-1]for i in info["resourceIds"]]))
        #         len2 = len(intersection(filtered_people,[i[:-1]for i in info["resourceIds"]]))
        #         if len1 == len2:
        #             filtered_data.append(info)
        #     else:
        #         filtered_data.append(info)
        # if len(filtered_people) > 0:
        #     data_arr = filtered_data
        #********************************
        current_time = self.var_data["start_date"]+"T"+now+".000Z"
        current_time_dict = {
            "start":current_time,
            "end":current_time
        }
        current_time_slot = time_to_int(current_time_dict,self.var_data["slot_length"])[0]
        for info in data_arr:
            print("bazo_True : ",info)
            if self.var_data["part1"]:
                if 'block' in info.keys():
                    block = info['block']
                else:
                    block = 0
            else:
                block = 0
            block = 0
            weight = 0
            if 'priority' in info.keys() and type(info['priority']) == int:
                weight += priority_arr.index(info['priority']) * 10000

            slots = time_to_int(info, self.var_data['slot_length'])
            interval_start = slots[0]
            duration = slots[1]
            interval_end = slots[2]
            weekday_index = slots[3]

            address = None
            if 'address' in info.keys():
                address = info['address']
            if "loc_id" in info.keys():
                loc_id = info['loc_id']
            else:
                loc_id = ""
            yellow_sol = False

            if "ov" in info.keys():
                yellow_sol = True
            if "id" not in info.keys():
                info["id"] = str(uuid.uuid4())

            resource_list = []
            for res in sorted(info['resourceIds']):
                if not info["scheduled"]:
                    resource_list.append(res[:-1])
                else:
                    resource_list.append(res)
            intersection_of_resources = sorted(list(set(intersection(resource_without_funder,[i[:-1] for i in info["resourceIds"]]))))
            print('soomy3',interval_start, interval_end)
            # if interval_end < interval_start:
            #     interval_end = interval_start + 6
            if not info["scheduled"] and duration > 0:
                print("bazo_info_dub_title : ",info["title"])
                fake_bool = False
                duration_int = self.model.NewIntVar(0, duration, f'session length {info["title"]} {duration}')
                start_int = self.model.NewIntVar(interval_start, interval_end,f'{interval_start}')
                end_int = self.model.NewIntVar(interval_start, interval_end,f'{interval_end}')
                id_for_bol = info["id"]
                bol_appointment = self.model.NewBoolVar(f'hi{id_for_bol}')
                self.priority_array.append(info["priority"]*bol_appointment)
                event_interval = self.model.NewOptionalIntervalVar(start_int, duration_int, end_int, bol_appointment,'interval')
                
                ##All or nothing blocks
                # self.model.Add(duration_int == duration).OnlyEnforceIf(bol_appointment)
                # self.model.Add(duration_int == 0).OnlyEnforceIf(bol_appointment.Not())

                priority_actual = 1000 - info['priority']
                print('siller1',priority_actual)
                if priority_actual <= 0:
                    priority_actual = 1
                
                print('siller2',priority_actual)
                if tuple(intersection_of_resources) in self.scheduled_dict.keys():
                    for n in self.scheduled_dict[tuple(intersection_of_resources)]:
                        if interval_start >= n['start'] and interval_end <= n['end']:
                            # print("it_happens_some_time")
                            n.update({"bol_appointment": bol_appointment})
                            n.update({"priority": priority_actual})

                for i in intersection_of_resources:
                    if i in self.persons_bol_appointments:
                        self.persons_bol_appointments[i].append(bol_appointment)

                self.model.Add(0 == duration_int).OnlyEnforceIf(bol_appointment.Not())
                self.model.Add(0 < duration_int).OnlyEnforceIf(bol_appointment)

                self.bol_appointments_dict[tuple(intersection_of_resources)].append(bol_appointment)

                weekday_index = interval_start // (
                    (24 * 60) // self.var_data["slot_length"])
                
                self.resources1.priorities[tuple([interval_start]) +
                                      tuple([interval_end]) +
                                      tuple(["not_scheduled"]) +
                                      tuple([str(weekday_index)]) +
                                      tuple(resource_list)] = {"priorities":priority_actual ,"faker":False,'info':info}
                
                self.resources1.slots[tuple([interval_start]) +
                                      tuple([interval_end]) +
                                      tuple(["not_scheduled"]) +
                                      tuple([str(weekday_index)]) +
                                      tuple(resource_list)] = [
                                          duration_int, 1, event_interval,
                                          start_int, end_int, False,
                                          bol_appointment, address,
                                          waitlist_count, info["id"],
                                          info["orange_sol"], 2, loc_id,
                                          yellow_sol, weight, loc_id2, 2,
                                          fake_bool,False,duration
                ]

            if info['scheduled']:
                print('lipper',info)
                if "Grace Hynes" in info["title"]:
                    print("bazo_title : ",info)
                inter_notWorking = intersection(info["resourceIds"],self.var_data["nonbillable"])
                print("bazo_objective_activity : ",info)
                if len(inter_notWorking) > 0:
                    # self.var_data["percentage"] +=1
                    # print("bazo_nonebill : ",self.var_data["nonbillable"])
                    ave = {"type" : "delete"}
                    info.update(ave)
                    print("bazo_delete88 : ",info)
                    self.over_availability_events.append(info)
                    print('kooky10')
                    continue
                inter_notWorking = intersection(info["resourceIds"],self.var_data["notWorking"])

                print('sibber',info["resourceIds"],info)
                bol_users = False
                if 'users' in info.keys():
                    bol_users = True
                faker = False
                if 'faker' in info.keys():
                    faker = True
                if self.var_data["lunch_id"] in info["resourceIds"] or (bol_users and f"{self.var_data['lunch_id']}" in info["users"]):
                    if 'faker' in info.keys():
                        print('kooky9')
                        continue
                    ave = {"type" : "delete"}
                    info.update(ave)
                    # print("bazo_delete88 : ",info)
                    if 'faker' not in info.keys():
                        self.over_availability_events.append(info)
                    else:
                        print('gallop')
                    print('kooky9')
                    continue
                if "admin_id" in self.var_data.keys() and self.var_data["admin_id"] in info["resourceIds"]:
                    ave = {"type" : "delete"}
                    info.update(ave)
                    # print("bazo_delete88 : ",info)
                    self.over_availability_events.append(info)
                    print('kooky7')
                    continue 

                ####Not working activity and in objective activity, deletes

                if len(inter_notWorking) > 0 and len(intersection(inter_notWorking,self.var_data["objectiveactivity"])) > 0:
                    print("bazo_increament2",inter_notWorking,self.var_data["objectiveactivity"])
                    ave = {"type" : "delete"}
                    info.update(ave)
                    # print("bazo_delete88 : ",info)
                    self.over_availability_events.append(info)
                    print('kooky6')
                    continue
                    self.var_data["percentage"] +=1
                
                con = False
                ####Break Session Length
                for c in self.solutions1.resources1.frequency_constraints:
                    if c["type"] == "sessionlength":
                        for user_c in c['users_consequence']:
                            user_c_id = self.solutions1.resources1.resources[
                                user_c].id
                            if user_c_id in info["resourceIds"]:
                                c_min = (int(c["minSeconds"]) //
                                    60) // self.var_data["slot_length"]
                                c_max = (int(c["maxSeconds"]) //
                                    60) // self.var_data["slot_length"]
                                if duration > c_max or duration < c_min:
                                    # ave2 = {"type" : "delete"}
                                    # info.update(ave2)
                                    # self.over_availability_events.append(info)
                                    if duration > c_max:
                                        self.events_break_session_length_long = {**self.events_break_session_length_long,info['id']:duration}
                                    else:
                                        self.events_break_session_length_short = {**self.events_break_session_length_short,info['id']:duration}
                                    #con = True
                                    break
                if con:
                    # print("bazo_delete88 : ",info)
                    # print("bazo_continue_and_del : ",info)
                    print('kooky5')
                    continue
                # print("make_sure : ",con)

                ###Not in branch
                other_branches_activity = False
                for id_b in info["resourceIds"]:
                    if not id_b in resource5:
                        #ave = {"type" : "delete"}
                        #info.update(ave)
                        # print("bazo_delete88 : ",info)
                        #self.over_availability_events.append(info)

                        other_branches_activity = True
                        # print("bazo_tt : ",info["title"])
                        break
                
                # if other_branches_activity:
                #     continue
                ###Not in branch

                weekday_index = interval_start // ((24 * 60) // self.var_data["slot_length"])
                print("bazo_weekday_index : ",weekday_index)
                if int(weekday_index) == 3:
                    print("bazo_weekday_index_info: ",info)
                pass_event = False
                ####Outside Availability
                for res_id in info["resourceIds"]:
                    if res_id in av_arr_for_fake.keys():
                        if av_arr_for_fake[res_id][weekday_index] == []:
                            print('kooky4')
                            # pass_event = True
                            continue
                        else:
                            set_a = set()
                            for x in [list(range(i[0],i[1]+1)) for i in av_arr_for_fake[res_id][weekday_index]]:
                                for xb in x:
                                    set_a.add(xb)
                            set_b = set(list(range(interval_start,interval_end+1)))
                            if len(set_b.difference(set_a)) > 0:
                                pass_event = True
                                pass
            
                # if pass_event:
                #     #info["type"] = "delete"
                #     print("bazo_delete89 : ",info)
                #     self.over_availability_events.append(info)
                #     print('kooky3')
                #     continue
                
                        
                id_for_bool = info['id']
                # print("bazo_find_scheduled")
                fake_bool = False
                if info["title"] == "ByPass Activity":
                    # print("fake_info : ", info)
                    fake_bool = True
                # print("yes_we_have_events", info)
                orange_sol = False
                if "orange_sol" in info.keys():
                    # print("bazo_orange_sol_found", info)
                    orange_sol = info["orange_sol"]
                del_bol = self.model.NewBoolVar("del_bol")
                update_bol = self.model.NewBoolVar("update_bol")
                if other_branches_activity:
                    self.model.Add(del_bol == 1)
                    self.model.Add(update_bol == 1)
                print("bazo_cur : ",interval_start,current_time_slot,info["start"],current_time)
                today = datetime.datetime.now().date()
                target_date = datetime.datetime.strptime(self.var_data["start_date"], '%Y-%m-%d').date()
                print('see today',today, target_date,self.var_data["start_date"],now,interval_start,current_time_slot)
                if today == target_date and interval_start < current_time_slot:
                    print("bazo_applied")
                    self.model.Add(del_bol == 1)
                    self.model.Add(update_bol == 1)
                start_int_bol = self.model.NewBoolVar(
                    f"start_int_bol-{id_for_bool}")
                end_int_bol = self.model.NewBoolVar("end_int_bol")
                resource_list = list(set(info['resourceIds']))
                resource_list = [res for res in sorted(resource_list)]
                intersection_of_resources = sorted(list(set(intersection(resource_without_funder, info["resourceIds"]))))
                # self.priority_array.append(info["priority"]*del_bol)
                # print(
                #     'froohy',
                #     duration,
                #     resource_list,
                # )
                interval_start_embed = interval_start
                interval_end_embed = interval_end

                emp_id_arr = sorted(intersection(emp_ids, info["resourceIds"]))
                client_id_arr = sorted(intersection(clients_ids, info["resourceIds"]))

                if len(client_id_arr) > 0:
                    client_id = client_id_arr[0]

                if len(emp_id_arr) > 0:
                    emp_id2 = emp_id_arr[0]

                need_arr = []

                if len(client_id_arr) > 0 and len(emp_id_arr) > 0:
                    for emp_id in emp_id_arr:
                        if len(emp_id_arr) > 0 and emp_id != emp_id2:
                            tup = tuple(sorted([client_id, emp_id]))
                            if tup in self.scheduled_dict.keys():
                                for n in self.scheduled_dict[tup]:
                                    need_arr.append(n['bol_appointment'])

                # self.model.Add(sum(need_arr) >= 1).OnlyEnforceIf(
                #     del_bol.Not())
                priority_actual = 5
                update_false = False
                print("bazo_dub_dub : ",len(set(intersection_of_resources)),len(intersection_of_resources))
                if tuple(intersection_of_resources) in self.scheduled_dict.keys():
                    for n in self.scheduled_dict[tuple(intersection_of_resources)]:
                        if n["end"] < interval_start_embed or n["start"] > interval_end_embed:
                            print('kooky2')
                            continue
                        else:
                            start_end1 = set(range(n['start'], n['end'] + 1))
                            start_end2 = set(range(interval_start_embed,interval_end_embed + 1))
                            start_end_new = list(start_end1.union(start_end2))
                            if len(start_end_new) > 0 and len(intersection(self.var_data['objectiveactivity'],info["resourceIds"])) > 0:
                                if self.var_data['lunch_id'] in info['resourceIds']:
                                    # print("bazo_lunch_merged")
                                    pass
                                interval_start_embed = min(start_end_new)
                                interval_end_embed = max(start_end_new)
                                update_false  = True
                                priority_actual = n['priority']
                                self.model.Add(n['bol_appointment'] == 0)
                                break

                # else:
                #     self.model.Add(n['bol_appointment'] == 0)

                            # break
                if not update_false:
                    # print("bazo_event_updated : ",update_false,info)
                    self.not_updated_count += 1
                
                # start_int = self.model.NewConstant(interval_start)
                # end_int = self.model.NewConstant(interval_start + duration)
                # print('jeery', intersection_of_resources, interval_start_embed,
                #       interval_end_embed)
                # print('jeery2', interval_start, interval_end)
                start_int = self.model.NewIntVar(interval_start_embed,
                                                 interval_end_embed,
                                                 f'start-{id_for_bool}')

                duration_int = self.model.NewIntVar(
                    0, interval_end_embed - interval_start_embed, "some_dur")
                end_int = self.model.NewIntVar(interval_start_embed,
                                               interval_end_embed,
                                               f'end-{id_for_bool}')
                event_interval = self.model.NewOptionalIntervalVar(
                    start_int, duration_int, end_int, del_bol,
                    f'interval-{id_for_bool}')

                # self.model.Add(duration_int <= 8)
                # self.model.Add(duration_int != 1)
                # self.model.Add(duration_int != 2)
                # self.model.Add(duration_int != 3)
                # self.model.Add(
                #     start_int == interval_start).OnlyEnforceIf(update_bol)
                # self.model.Add(
                #     end_int == interval_end).OnlyEnforceIf(update_bol)
                self.model.Add(start_int == interval_start).OnlyEnforceIf(start_int_bol)
                self.model.Add(end_int == interval_end).OnlyEnforceIf(end_int_bol)

                self.model.Add(start_int != interval_start).OnlyEnforceIf(start_int_bol.Not())
                self.model.Add(end_int != interval_end).OnlyEnforceIf(end_int_bol.Not())
                # **
                # self.model.Add(update_bol == 1).OnlyEnforceIf(del_bol.Not())
                # self.model.Add(del_bol == 1).OnlyEnforceIf(update_bol.Not())
                # **
                # self.model.Add(start_int_bol + end_int_bol == 1).OnlyEnforceIf(
                #     update_bol.Not()).OnlyEnforceIf(del_bol)
                # self.model.Add(start_int_bol + end_int_bol == 2).OnlyEnforceIf(
                #     update_bol).OnlyEnforceIf(del_bol)
                self.model.Add(start_int_bol + end_int_bol < 2).OnlyEnforceIf(update_bol.Not())
                self.model.Add(duration_int > 0).OnlyEnforceIf(update_bol.Not())
                self.model.Add(start_int_bol + end_int_bol == 2).OnlyEnforceIf(update_bol)

                # self.model.AddMinEquality(
                #     update_bol2, [start_int_bol, end_int_bol])
                # self.model.Add(
                #     update_bol2 == update_bol).OnlyEnforceIf(del_bol)
                # self.model.Add(1 == update_bol).OnlyEnforceIf(del_bol.Not())

                # self.model.Add(
                #     del_bol == 1).OnlyEnforceIf(update_bol)

                # self.model.Add(end_int == interval_end).OnlyEnforceIf(update_bol)
                practice_bol = True
                self.model.AddHint(del_bol,1)
                self.model.AddHint(update_bol,1)
                #self.model.Add(del_bol == 0)
                if self.var_data['percentage'] == 0:
                    self.model.Add(del_bol == 1)
                    self.model.Add(update_bol == 1)
                # else:
                #     self.model.AddHint(del_bol,1)
                #     self.model.AddHint(update_bol,1)
             
                # print("bazo_ev : ",info["resourceIds"])
                # for id_b in info["resourceIds"]:
                #     if not id_b in resource5:
                #         self.model.Add(del_bol == 0)
                #         print("bazo_increament")
                #         self.var_data["percentage"] +=1
                #         practice_bol = False
                #         break
                # for res_id in info["resourceIds"]:
                #     if not res_id in self.var_data["objectiveactivity"]:
                #         self.model.Add(del_bol == 1)
                # self.var_data["notWorking"]
                
                
                if practice_bol and len(intersection(self.var_data['objectiveactivity'],info["resourceIds"])) == 0:
                    self.model.Add(del_bol == 1)
                    self.model.Add(update_bol == 1)
                # #**
                # curr_time = datetime.datetime.fromisoformat(formatted_z_time.replace('Z', '+00:00'))
                # info_time = datetime.datetime.fromisoformat(info["start"].replace('Z', '+00:00'))
                # curr_hms = (curr_time.hour, curr_time.minute, curr_time.second)
                # info_hms = (info_time.hour, info_time.minute, info_time.second)
                # # Calculate time difference
                # time_diff = info_time - curr_time
                
                
                # print("bazo_time_diff :", time_diff.seconds)
                # if info_hms <= curr_hms or time_diff.seconds/60 <= 30:
                #     print("bazo_hms",info)
                #     self.model.Add(del_bol==1)
                #     self.model.Add(update_bol==1)
                # #**
                self.model.Add(duration_int > 0).OnlyEnforceIf(del_bol)
                self.model.Add(duration_int == 0).OnlyEnforceIf(del_bol.Not())
                # self.direct_events_sum += duration
                weekday_index = interval_start // ((24 * 60) // self.var_data["slot_length"])
                if info["id"] in event_ids:
                    print('kooky1')
                    #continue
                
                
                else:
                    # print("bazo_ev88 : ",info["resourceIds"])
                    
                    self.resources1.priorities[tuple([interval_start]) +
                                          tuple([interval_end]) +
                                          tuple(["scheduled"]) +
                                          tuple([str(weekday_index)]) +
                                          tuple(resource_list)] ={"priorities":priority_actual,"faker":faker,'info':info}
                    self.resources1.slots[tuple([interval_start]) +
                                          tuple([interval_end]) +
                                          tuple(["scheduled"]) +
                                          tuple([str(weekday_index)]) +
                                          tuple(resource_list)] = [
                                              duration_int, 1, event_interval,
                                              start_int, end_int, True, 1,
                                              address, waitlist_count,
                                              info["id"], orange_sol, del_bol,
                                              loc_id, yellow_sol, weight,
                                              loc_id2, update_bol, fake_bool,con,duration
                    ]
                    if tuple(intersection_of_resources) in self.bol_appointments_dict.keys() and info["title"] != "ByPass Activity":
                        self.bol_appointments_dict[tuple(intersection_of_resources)].append(del_bol)
                    elif info["title"] != "ByPass Activity":
                        self.bol_appointments_dict[tuple(intersection_of_resources)] = [del_bol]

                    for i in intersection_of_resources:
                        if i in self.persons_bol_appointments:
                            self.persons_bol_appointments[i].append(del_bol)

                    self.delete_bool.append(del_bol)
                    self.update_bool.append(update_bol)
                    if info["title"] != "ByPass Activity":
                        self.direct_events_sum += duration
                    client_intersections = intersection(
                        clients_ids, resource_list)
                    # print("wow : ", resource_list, len(resource_list))
                    self.deletable_events.append(info)
                    if len(client_intersections) >= 1:
                        # print('howdy3', client_intersections[0], duration)
                        if info["title"] != "ByPass Activity":
                            self.clients_durations[
                                client_intersections[0]] += duration
                event_ids.append(info["id"])
                event_ids = list(set(event_ids))
                print('niffer')

            # for key, value in block_person_obj.items():
            #     self.model.Add(sum(value) >= 1)

        print(
            "--------------------------------*--------------------------------*--------------------------------"
        )

    def min_session(self):
        val = self.get_appointments([self.var_data["objectiveactivity"]])
        # admin_activity_id = self.find_ids_by_role(["Admin"])
        # val_admin = self.get_appointments([admin_activity_id])
        # val_admin = list(filter(lambda num: not num[17], val_admin.values()))
        # Should remove scheduled appointments? Not if playing tetris
        val = list(filter(lambda num: not num[17], val.values()))
        durations = list(map(lambda num: num[0], val))
        min_session_arr = min_session_array(self.var_data['slot_length'],
                                            self.var_data['min_session_dur'])
        max_slot = self.var_data["max_session_length"] // self.var_data[
            "slot_length"]
        # print('flicky1', max_slot, min_session_arr)

        # for dur in durations:
        #     self.model.Add(dur != 1)
        #     self.model.Add(dur != 3)
        #     self.model.Add(dur != 5)
        #     self.model.Add(dur != 7)
        #     self.model.Add(dur != 9)
        #     self.model.Add(dur != 11)
        #     self.model.Add(dur != 13)

        for dur in durations:
            for i in min_session_arr:
                self.model.Add(dur != i)
            # print('flicky2', max_slot, dur)
            self.model.Add(dur <= int(max_slot))

    def no_overlap(self, e_pair):
        # print("bazo_emp_ids : ",list(set(self.find_ids_by_role(["Employee"]))))
        supervision_activity_id = "f39d479c-ea0f-4dcf-86e1-3e47c19328c7"
        for id in list(set(self.find_ids_by_role(["Client"]))):
            extra_arr = self.fake_whites[id] if id in self.fake_whites else []
            val = self.get_appointments([[id]])
            val_super = self.get_appointments([[id],[supervision_activity_id]])
            if len(val) > 0:
                arr = []
                for key,value in val.items():
                    if not supervision_activity_id in key:
                        arr.append(value)
                    else:
                        print("Found_Supervision_Activity")
                flimp = list((map(lambda num: num[2], arr))) + extra_arr #+fake_interval_array_clients
                self.model.AddNoOverlap(flimp)
            if len(val_super) > 0:
                arr2 = val_super.values()
                flip_super = list((map(lambda num: num[2], arr2)))
                self.model.AddNoOverlap(flip_super)

        for id in list(set(self.find_ids_by_role(["Roomy"]))):
            val = self.get_appointments([[id]])
            print('roomy1')
            if len(val) > 0:
                print('roomy2')
                arr = []
                for key,value in val.items():
                    arr.append(value)
                flimp = list((map(lambda num: num[2], arr)))
                self.model.AddNoOverlap(flimp)
                
        for id in list(set(self.find_ids_by_role(["Employee"]))):
            extra_arr = self.fake_whites[id] if id in self.fake_whites else []
            val = self.get_appointments([[id],
                                        #  self.var_data["objectiveactivity"]
                                         ])
            # print("bazo_overlap : ", list(val.values()))
            # time_to_int(info, self.var_data['slot_length'])
            ################################
            # fake_interval_array = []
            # if len(self.var_data["fake_user_starts_ends"][id]["fakes"]) == 0:
            #     pass
            # else:
            #     for info in self.var_data["fake_user_starts_ends"][id]["fakes"]:
            #         f_slot = time_to_int(info, self.var_data['slot_length'])
            #         f_start = f_slot[0]
            #         f_end = f_slot[2]
            #         # print("bazo_slot_length_f : ",info,f_start,f_end)
            #         start_var = self.model.NewIntVar(f_start, f_end,f"fake_so-{id}")
            #         end_var = self.model.NewIntVar(f_start, f_end,f"fake_eo-{id}")
            #         dur_var = self.model.NewIntVar(0, f_end-f_start,f"fake_do-{id}")
            #         self.model.Add(dur_var == f_end-f_start)
            #         interval_var = self.model.NewIntervalVar(start_var,dur_var,end_var,f"fake_io-{id}")
            #         fake_interval_array.append(interval_var)
                    
            #     pass
            ################################
            # print("bazo_fake_interval_array : ",fake_interval_array)
            if len(val) > 0:
                arr = val.values()
                over_yellow = []
                over_normal = []
                for i in arr:
                    if i[13]:
                        over_yellow.append(i)
                    else:
                        over_normal.append(i)
                flimp1 = list((map(lambda num: num[2], over_yellow)))
                flimp2 = list(
                    (map(lambda num: num[2], over_normal))) + extra_arr #+fake_interval_array
                # print("Overlap_Found_Bug : ", flimp1)
                self.model.AddNoOverlap(flimp1)
                self.model.AddNoOverlap(flimp2)

    def no_gap2(self):
        days_arrays = days_arr(self.var_data['slot_length'])
        employees = self.find_ids_by_role(['Employee'])
        clients = self.find_ids_by_role(['Client'])
        people = self.find_ids_by_role(['Person'])

        # for emp_id in people:
        #     # for emp_id in employees:
        #     # if self.resources1.resources[emp_id].firstName == 'Luis':
        #     #     pass
        #     for index, x in enumerate(days_arrays[1:]):
        #         if index == self.var_data['today_index']:
        #             val = self.get_appointments(
        #                 [[emp_id], [self.var_data["today_index"]]])

        #             durations = list(map(lambda num: num[0], val.values()))

        # if len(durations) > 0:
        #     self.model.Add(sum(durations) <= 16)

        # print('soogy')
        # for client_id in clients:
        #     # if self.resources1.resources[client_id].firstName == 'Luis':
        #     #     pass
        #     av_arr = self.solutions1.user_availabilities_general[client_id]
        #     for index, x in enumerate(days_arrays[1:]):
        #         if index == self.var_data['today_index']:
        #             val = self.get_appointments([[client_id]])
        #             print('smooky', val, client_id)
        #             durations = list(map(lambda num: num[0], val.values()))
        #             starts = list(map(lambda num: num[3], val.values()))
        #             ends = list(map(lambda num: num[4], val.values()))
        #             actual_bol = self.model.NewBoolVar('k')
        #             # b_appointment = list(map(lambda num: num[6], val.values()))
        #             bol_d = self.model.NewBoolVar('f')
        #             self.model.Add(sum(durations) > 0).OnlyEnforceIf(bol_d)
        #             self.model.Add(sum(durations) ==
        #                            0).OnlyEnforceIf(bol_d.Not())
        #             # self.model.AddMinEquality(
        #             #     actual_bol, [b_appointment, bol_d])
        #             actual_starts = list(
        #                 map(lambda num: list(num)[0], val.keys()))
        #             print('salties5', actual_starts)
        #             if len(actual_starts) > 0:
        #                 absolute_start = min(actual_starts)
        #                 print('soomys', absolute_start)

        #                 start_arr = []
        #                 for index, s in enumerate(starts):
        #                     bol_start = self.model.NewBoolVar('f')
        #                     self.model.Add(
        #                         s == absolute_start).OnlyEnforceIf(bol_start)
        #                     self.model.Add(
        #                         ends[index] != absolute_start).OnlyEnforceIf(bol_start)
        #                     self.model.Add(
        #                         durations[index] > 0).OnlyEnforceIf(bol_start)
        #                     self.model.Add(s != absolute_start).OnlyEnforceIf(
        #                         bol_start.Not())
        #                     start_arr.append(bol_start)
        #                 self.model.Add(sum(start_arr) ==
        #                                1).OnlyEnforceIf(bol_d)

        # for index, x in enumerate(days_arrays):
        #     if index == self.var_data['today_index']:
        #         # if index != 0 and index < len(days_arrays)-2:
        #         for person_id in self.find_ids_by_role(
        #             [self.var_data['no_gap_role']]):
        #             pp = False
        #             if person_id == "2995143d-5778-4ced-945b-81b9907a0d57":
        #                 pp = True
        #             ok_gap_value = 0
        #             max9_value = 0
        #             try:
        #                 if person_id in list(self.var_data['max_hours']
        #                                      ["employees"].keys()):
        #                     max9_value = self.var_data["max_hours"][
        #                         "employees"][person_id] * 60 // self.var_data[
        #                             "slot_length"]
        #                 else:
        #                     max9_value = self.var_data["max_hours"]["clients"][
        #                         person_id] * 60 // self.var_data["slot_length"]
        #             except:
        #                 pass
        #             # try:
        #             #     ok_gap_value = self.var_data["gg"][
        #             #         person_id] / self.var_data["slot_length"]
        #             # except:
        #             #     print("Error Occurs : ", person_id)
        #             # print("ok_gap_value", ok_gap_value)
        #             if index == 0:
        #                 pass
        #             val = self.get_appointments(
        #                 [[person_id],
        #                  list(range(days_arrays[index],
        #                             days_arrays[index + 1])),
        #                  self.find_ids_by_role(['Activity'])])
        #             if val:
        #                 arr4 = []
        #                 arr5 = []
        #                 for e in list(map(lambda num: num, val.values())):
        #                     b3 = self.model.NewBoolVar('f')
        #                     target = self.model.NewIntVar(
        #                         0, 1000000000, 'snip1')
        #                     target2 = self.model.NewIntVar(
        #                         0, 1000000000, 'snip2')
        #                     target3 = self.model.NewIntVar(
        #                         0, 1000000000, 'snip3')
        #                     target4 = self.model.NewIntVar(
        #                         0, 1000000000, 'snip4')
        #                     self.model.Add(e[0] > 0).OnlyEnforceIf(b3)
        #                     self.model.Add(e[0] == 0).OnlyEnforceIf(b3.Not())
        #                     self.model.Add(target3 == 1).OnlyEnforceIf(b3)
        #                     self.model.Add(target4 == 1).OnlyEnforceIf(b3)
        #                     self.model.Add(target3 == 1000000).OnlyEnforceIf(
        #                         b3.Not())
        #                     self.model.Add(target4 == 0).OnlyEnforceIf(
        #                         b3.Not())
        #                     self.model.AddMultiplicationEquality(
        #                         target, [e[3], target3])
        #                     self.model.AddMultiplicationEquality(
        #                         target2, [e[4], target4])
        #                     arr4.append(target)
        #                     arr5.append(target2)

        #                 min9 = self.model.NewIntVar(0, 10000000000, 'snip5')
        #                 max9 = self.model.NewIntVar(0, 1000000000, 'snip6')
        #                 min9_array = list(map(lambda num: num[3],
        #                                       val.values()))
        #                 max9_array = list(map(lambda num: num[4],
        #                                       val.values()))
        #                 durations = list(map(lambda num: num[0], val.values()))
        #                 # self.model.Add(sum(durations) <= int(max9_value) + 1)
        #                 # self.model.Addmin9Equality(min9, min9_array)
        #                 # self.model.Addmax9Equality(max9, max9_array)
        #                 self.model.AddMinEquality(min9, arr4)
        #                 self.model.AddMaxEquality(max9, arr5)

        #                 bol = self.model.NewBoolVar(f'{person_id}')
        #                 if True:
        #                     pass
        #                 if person_id in employees:
        #                     # bol_new = self.model.NewBoolVar(f'b')
        #                     # self.model.Add(
        #                     #     sum(durations) >= 16).OnlyEnforceIf(bol_new)
        #                     # self.model.Add(sum(durations) < 16).OnlyEnforceIf(
        #                     #     bol_new.Not())
        #                     # self.model.Add(
        #                     #     max9 - min9 -
        #                     #     sum(durations) >= 1).OnlyEnforceIf(bol_new)
        #                     self.model.Add(sum(durations) >= max9 - min9 -
        #                                    2).OnlyEnforceIf(bol)
        #                     self.model.Add(sum(durations) == 0).OnlyEnforceIf(
        #                         bol.Not())

        #                 elif person_id in clients:
        #                     self.model.Add(sum(durations) == max9 -
        #                                    min9).OnlyEnforceIf(bol)
        #                     self.model.Add(sum(durations) == 0).OnlyEnforceIf(
        #                         bol.Not())

    def no_gap(self):
        days_arrays = days_arr(self.var_data['slot_length'])
        employees = self.find_ids_by_role(['Employee'])
        clients = self.find_ids_by_role(['Client'])
        people = employees + clients
        av_arr_for_fake_raw = self.solutions1.user_availabilities_general
        av_arr_for_fake = {}
        for some_id in people:
            av_arr_for_fake[some_id] = {
                0: [],
                1: [],
                2: [],
                3: [],
                4: [],
                5: [],
                6: [],
                7: []
            }
        for some_id in people:
            for i in av_arr_for_fake_raw[some_id]:
                some_index = i[0] // (
                    (24 * 60) // self.var_data["slot_length"])

                av_arr_for_fake[some_id][some_index].append(i)
        for i in av_arr_for_fake:
            pass
            # print("bazo_av_data : ", i, av_arr_for_fake)
        # print("my_act : ", self.find_ids_by_role(['Activity']))
        # print("bbb  :", self.solutions1.user_availabilities_general)

        # for emp_id in employees:
        #     # for emp_id in employees:
        #     # if self.resources1.resources[emp_id].firstName == 'Luis':
        #     #     pass
        #     for index, x in enumerate(days_arrays[1:]):
        #         if index == self.var_data['today_index']:
        #             val = self.get_appointments(
        #                 [[emp_id], self.var_data["objectiveactivity"]])

        #             durations = list(map(lambda num: num[0], val.values()))

        #             if len(durations) > 0:
        #                 print('soovly', emp_id)
        #                 self.model.Add(sum(durations) <= 16)
        # bol = self.model.NewBoolVar('b')
        # inte = self.model.NewIntVar(0, 10000000000, 'snip1')
        # # self.constraint_bols.append(bol)
        # self.model.Add(inte == 10).OnlyEnforceIf(bol)
        # self.model.Add(inte == 0).OnlyEnforceIf(bol.Not())
        # self.constraint_bols.append(inte)

        # bol2 = self.model.NewBoolVar('b')
        # inte2 = self.model.NewIntVar(0, 10000000000, 'snip1')
        # # self.constraint_bols.append(bol)
        # self.model.Add(inte2 == 10).OnlyEnforceIf(bol2)
        # self.model.Add(inte2 == 0).OnlyEnforceIf(bol2.Not())
        # self.constraint_bols.append(inte2)

        # tot = 0
        # # print('simple1')
        # for i in self.solutions1.user_availabilities_general[
        #         emp_id]:
        #     # print('simple2', i)
        #     tot += (list(i)[1] - list(i)[0])
        # tot = int(tot / (self.var_data['slot_length'] // 15) *
        #           6) // 10
        # # print('simple3', tot)
        # self.model.Add(
        #     sum(durations) >= tot).OnlyEnforceIf(bol)
        # self.model.Add(sum(durations) < tot).OnlyEnforceIf(
        #     bol.Not())

        # self.model.Add(
        #     sum(durations) >= int(6 // (self.var_data['slot_length'] // 60))).OnlyEnforceIf(bol2)
        # self.model.Add(sum(durations) < int(6 // (self.var_data['slot_length'] // 60))).OnlyEnforceIf(
        #     bol2.Not())
        # UNCOMMENT
        # for client_id in clients:
        #     # if self.resources1.resources[client_id].firstName == 'Luis':
        #     #     pass
        #     av_arr = self.solutions1.user_availabilities_general[client_id]
        #     for index, x in enumerate(days_arrays[1:]):
        #         if index == self.var_data['today_index']:
        #             val = self.get_appointments([[client_id]])
        #             print('smooky', val, client_id)
        #             durations = list(map(lambda num: num[0], val.values()))
        #             starts = list(map(lambda num: num[3], val.values()))
        #             ends = list(map(lambda num: num[4], val.values()))
        #             actual_bol = self.model.NewBoolVar('k')
        #             # b_appointment = list(map(lambda num: num[6], val.values()))
        #             bol_d = self.model.NewBoolVar('f')
        #             self.model.Add(sum(durations) > 0).OnlyEnforceIf(bol_d)
        #             self.model.Add(sum(durations) ==
        #                            0).OnlyEnforceIf(bol_d.Not())
        #             # self.model.AddMinEquality(
        #             #     actual_bol, [b_appointment, bol_d])
        #             actual_starts = list(
        #                 map(lambda num: list(num)[0], val.keys()))
        #             print('salties5', actual_starts)
        #             if len(actual_starts) > 0:
        #                 absolute_start = min(actual_starts)
        #                 print('soomys', absolute_start)

        #                 start_arr = []
        #                 for index, s in enumerate(starts):
        #                     bol_start = self.model.NewBoolVar('f')
        #                     self.model.Add(
        #                         s == absolute_start).OnlyEnforceIf(bol_start)
        #                     self.model.Add(
        #                         ends[index] != absolute_start).OnlyEnforceIf(bol_start)
        #                     self.model.Add(
        #                         durations[index] > 0).OnlyEnforceIf(bol_start)
        #                     self.model.Add(s != absolute_start).OnlyEnforceIf(
        #                         bol_start.Not())
        #                     start_arr.append(bol_start)
        #                 self.model.Add(sum(start_arr) ==
        #                                1).OnlyEnforceIf(bol_d)
        #                 # self.model.Add(sum(start_arr) ==
        #                 #                0).OnlyEnforceIf(bol_d.Not())

        #                 print(
        #                     'somly2', self.var_data["max_session_length"], self.var_data["min_session_dur"])
        #                 max_slot = self.var_data["max_session_length"] // self.var_data[
        #                     "slot_length"]
        #                 min_slot = self.var_data["min_session_dur"] // self.var_data[
        #                     "slot_length"]
        #                 for av in av_arr:
        #                     [start1, end1] = list(av)
        #                     start = start1 // (self.var_data[
        #                         "slot_length"]//15)
        #                     end = end1 // (self.var_data[
        #                         "slot_length"]//15)
        #                     print('goofy1', av)
        #                     for s in starts:
        #                         for i in range(1, min_slot):
        #                             print('soofy1', s, start, i, start + i)
        #                             self.model.Add(s != start + i)

        #                     for e in ends:
        #                         for i in range(1, min_slot):
        #                             print('soofy2', e, end, i, end - i)
        #                             self.model.Add(e != e - i)

        # print('s')
        # if len(durations) > 0:
        #     bol = self.model.NewBoolVar('b')
        #     inte = self.model.NewIntVar(0, 1000_000_000, 'snip1')
        #     # self.constraint_bols.append(bol)
        #     self.model.Add(inte == 20).OnlyEnforceIf(bol)
        #     self.model.Add(inte == 0).OnlyEnforceIf(bol.Not())
        #     self.constraint_bols.append(inte)
        #     tot = 0
        #     # print('simple1')
        #     for i in self.solutions1.user_availabilities_general[
        #             client_id]:
        #         print('simple2', i)
        #         tot += (list(i)[1] - list(i)[0])
        #     tot = int(tot / (self.var_data['slot_length'] // 15) *
        #               10) // 10
        #     # print('simple3', tot)
        #     self.model.Add(
        #         sum(durations) >= tot).OnlyEnforceIf(bol)
        #     self.model.Add(sum(durations) < tot).OnlyEnforceIf(
        #         bol.Not())

        # UNCOMMENT
        # # for index, x in enumerate(days_arrays[1:]):
        # #     print('doothy', index, x, list(range(days_arrays[1:][index - 1],
        # #                                          x)))

        for index, x in enumerate(days_arrays):
            bazo_count = 0
            # print("bazo_ids_for_no_gap : ",
            #       len(self.find_ids_by_role([self.var_data['no_gap_role']])),
            #       self.find_ids_by_role([self.var_data['no_gap_role']]))
            if index in list(
                    range(7)):  # index == self.var_data['today_index']:
                # if index != 0 and index < len(days_arrays)-2:
                for person_id in self.find_ids_by_role(
                        [self.var_data['no_gap_role']]):
                    # pp = False
                    # if person_id == "2995143d-5778-4ced-945b-81b9907a0d57":
                    #     pp = True
                    # ok_gap_value = 0
                    # max9_value = 0
                    try:
                        if person_id in list(self.var_data['max_hours']
                                             ["employees"].keys()):
                            max9_value = self.var_data["max_hours"][
                                "employees"][person_id] * 60 // self.var_data[
                                    "slot_length"]
                        else:
                            max9_value = self.var_data["max_hours"]["clients"][
                                person_id] * 60 // self.var_data["slot_length"]
                    except:
                        pass
                    # try:
                    #     ok_gap_value = self.var_data["gg"][
                    #         person_id] / self.var_data["slot_length"]
                    # except:
                    #     print("Error Occurs : ", person_id)
                    # print("ok_gap_value", ok_gap_value)
                    if index == 0:
                        pass
                    val = self.get_appointments(
                        [[person_id], [str(index)]
                         #  self.find_ids_by_role(['Activity'])
                         ])
                    # if person_id == "46c3b666-975e-4305-bbd2-ff0e5e4e32fa":
                    #     print("ok_find_gap : ", val)
                    if len(val) > 0:
                        arr4 = []
                        arr5 = []
                        # for e in list(map(lambda num: num, val.values())):
                        #     b3 = self.model.NewBoolVar('f')
                        #     # b3 = e[6]
                        #     target = self.model.NewIntVar(
                        #         0, 1000000000, 'snip1')
                        #     target2 = self.model.NewIntVar(
                        #         0, 1000000000, 'snip2')
                        #     target3 = self.model.NewIntVar(
                        #         0, 1000000000, 'snip3')
                        #     target4 = self.model.NewIntVar(
                        #         0, 1000000000, 'snip4')
                        #     self.model.Add(e[0] > 0).OnlyEnforceIf(b3)
                        #     self.model.Add(e[0] == 0).OnlyEnforceIf(b3.Not())
                        #     # **New
                        #     self.model.Add(target == e[3]).OnlyEnforceIf(b3)
                        #     self.model.Add(target == 100000).OnlyEnforceIf(
                        #         b3.Not())
                        #     self.model.Add(target2 == e[4]).OnlyEnforceIf(b3)
                        #     self.model.Add(target2 == 0).OnlyEnforceIf(
                        #         b3.Not())

                        # #     # **New

                        # #     # self.model.Add(target3 == 1).OnlyEnforceIf(b3)
                        # #     # self.model.Add(target4 == 1).OnlyEnforceIf(b3)
                        # #     # self.model.Add(target3 == 1000000).OnlyEnforceIf(
                        # #     #     b3.Not())
                        # #     # self.model.Add(target4 == 0).OnlyEnforceIf(
                        # #     #     b3.Not())
                        # #     # self.model.AddMultiplicationEquality(
                        # #     #     target, [e[3], target3])
                        # #     # self.model.AddMultiplicationEquality(
                        # #     #     target2, [e[4], target4])
                        # #     arr4.append(target)
                        # #     arr5.append(target2)

                        # min9 = self.model.NewIntVar(0, 10000000000, 'snip5')
                        # max9 = self.model.NewIntVar(0, 1000000000, 'snip6')
                        # min9_array = list(map(lambda num: num[3],
                        #                       val.values()))
                        # max9_array = list(map(lambda num: num[4],
                        #                       val.values()))

                        durations = list(map(lambda num: num[0], val.values()))

                        # # self.model.Add(sum(durations) <= int(max9_value) + 2)
                        # # self.model.Addmin9Equality(min9, min9_array)
                        # # self.model.Addmax9Equality(max9, max9_array)
                        # # self.model.AddMinEquality(min9, arr4)
                        # # self.model.AddMaxEquality(max9, arr5)

                        # bol = self.model.NewBoolVar(f'{person_id}')
                        # if True:
                        #     pass
                        # print("bazo_gapp : ",
                        #       av_arr_for_fake[person_id][index])
                        if person_id in employees:
                            fake_bol1 = self.model.NewBoolVar(
                                f"fake1{person_id}")
                            fake_bol2 = self.model.NewBoolVar(
                                f"fake2{person_id}")
                            fake_bol3 = self.model.NewBoolVar(
                                f"fake3{person_id}")
                            fake_bol4 = self.model.NewBoolVar(
                                f"fake4{person_id}")
                            av_data = av_arr_for_fake[person_id][index]
                            fake_start = min([i[0] for i in av_data])
                            fake_end = max([i[1] for i in av_data])
                            fake_start_int_1 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_start")
                            fake_end_int_1 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_end")
                            fake_start_int_2 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_start2")
                            fake_end_int_2 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_end2")
                            fake_start_int_3 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_start3")
                            fake_end_int_3 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_end3")
                            fake_start_int_4 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_start4")
                            fake_end_int_4 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_end4")

                            fake_duration_int_1 = self.model.NewIntVar(
                                0, fake_end - fake_start, "dur1")
                            fake_duration_int_2 = self.model.NewIntVar(
                                0, fake_end - fake_start, "dur2")
                            fake_duration_int_3 = self.model.NewIntVar(
                                0, fake_end - fake_start, "dur3")
                            fake_duration_int_4 = self.model.NewIntVar(
                                0, fake_end - fake_start, "dur4")

                            fake1 = self.model.NewOptionalIntervalVar(
                                fake_start_int_1, fake_duration_int_1,
                                fake_end_int_1, fake_bol1, "fake1")
                            fake2 = self.model.NewOptionalIntervalVar(
                                fake_start_int_2, fake_duration_int_2,
                                fake_end_int_2, fake_bol2, "fake2")
                            fake3 = self.model.NewOptionalIntervalVar(
                                fake_start_int_3, fake_duration_int_3,
                                fake_end_int_3, fake_bol3, "fake3")
                            fake4 = self.model.NewOptionalIntervalVar(
                                fake_start_int_4, fake_duration_int_4,
                                fake_end_int_4, fake_bol4, "fake4")

                            self.fake_whites[person_id] = [
                                fake1, fake2, fake3, fake4
                            ]
                            self.model.Add(fake_duration_int_1 > 0
                                           ).OnlyEnforceIf(fake_bol1)
                            self.model.Add(
                                fake_duration_int_1 == 0).OnlyEnforceIf(
                                    fake_bol1.Not())
                            self.model.Add(fake_duration_int_2 > 0
                                           ).OnlyEnforceIf(fake_bol2)
                            self.model.Add(
                                fake_duration_int_2 == 0).OnlyEnforceIf(
                                    fake_bol2.Not())
                            self.model.Add(fake_duration_int_3 > 0
                                           ).OnlyEnforceIf(fake_bol3)
                            self.model.Add(
                                fake_duration_int_3 == 0).OnlyEnforceIf(
                                    fake_bol3.Not())
                            self.model.Add(fake_duration_int_4 > 0
                                           ).OnlyEnforceIf(fake_bol4)
                            self.model.Add(
                                fake_duration_int_4 == 0).OnlyEnforceIf(
                                    fake_bol4.Not())

                            self.model.Add(fake_start_int_1 == fake_start)
                            self.model.Add(fake_end_int_2 == fake_end)
                            self.model.Add(
                                sum(durations) + fake_duration_int_1 +
                                fake_duration_int_2 + fake_duration_int_3 +
                                fake_duration_int_4 == fake_end - fake_start)
                            self.model.Add(
                                fake_duration_int_3 + fake_duration_int_4 <=
                                int(self.var_data["maxGapEmployeeSchedule"]) //
                                self.var_data["slot_length"])
                            self.individual_fake_boolean[person_id] = [
                                fake_bol2, fake_bol1, fake_bol3, fake_bol4
                            ]

                            # bol_new = self.model.NewBoolVar(f'b')
                            # self.model.Add(
                            #     sum(durations) >= 16).OnlyEnforceIf(bol_new)
                            # self.model.Add(sum(durations) < 16).OnlyEnforceIf(
                            #     bol_new.Not())
                            # self.model.Add(
                            #     max9 - min9 -
                            #     sum(durations) >= 1).OnlyEnforceIf(bol_new)
                            # self.model.Add(
                            #     sum(durations) >= max9 - min9 -
                            #     int(self.var_data["maxGapEmployeeSchedule"]) //
                            #     self.var_data["slot_length"]).OnlyEnforceIf(
                            #         bol).OnlyEnforceIf(bol)
                            # self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                            #     bol.Not())
                            pass

                        elif person_id in clients:
                            clients_gaps_interval = []
                            clients_gaps_duration = []
                            fake_bol1 = self.model.NewBoolVar(
                                f"fake1{person_id}")
                            fake_bol2 = self.model.NewBoolVar(
                                f"fake2{person_id}")

                            av_data = av_arr_for_fake[person_id][index]

                            try:
                                if len(av_data) > 1:
                                    count_gaps_fake = 3
                                    for i in find_gaps(
                                            av_data)["gap_intervals"]:
                                        fake_start = i[0]
                                        fake_end = i[1]
                                        # fake_bol_gaps = self.model.NewBoolVar(
                                        #     f"fake{count_gaps_fake}{person_id}"
                                        # )
                                        fake_gaps_start_int = self.model.NewIntVar(
                                            fake_start, fake_end,
                                            f"fake_gaps_start{count_gaps_fake}"
                                        )
                                        # fake_gaps_end_int = self.model.NewIntVar(
                                        #     fake_start, fake_end,
                                        #     f"fake_gaps_end{count_gaps_fake}")
                                        fake_gaps_duration_int = self.model.NewIntVar(
                                            0, fake_end - fake_start,
                                            f"dur{count_gaps_fake}")
                                        # fake_interval = self.model.NewOptionalIntervalVar(
                                        #     fake_gaps_start_int,
                                        #     fake_gaps_duration_int,
                                        #     fake_gaps_end_int, fake_bol_gaps,
                                        #     f"fake{count_gaps_fake}")
                                        fake_interval = self.model.NewFixedSizeIntervalVar(
                                            fake_gaps_start_int,
                                            fake_end - fake_start,
                                            f"fake{count_gaps_fake}")
                                        clients_gaps_interval.append(
                                            fake_interval)
                                        clients_gaps_duration.append(
                                            fake_gaps_duration_int)
                                        # self.model.Add(
                                        #     fake_gaps_duration_int > 0
                                        # ).OnlyEnforceIf(fake_bol_gaps)
                                        # self.model.Add(fake_gaps_duration_int
                                        #                == 0).OnlyEnforceIf(
                                        #                    fake_bol_gaps.Not())
                                        count_gaps_fake += 1
                            except Exception as e:
                                print("bazo_Error: ", e)
                            fake_start = min([i[0] for i in av_data])
                            fake_end = max([i[1] for i in av_data])
                            gap_length = find_gaps(av_data)["gap_length"]
                            # print("bazo_some_gaps : ", clients_gaps_duration,
                            #       clients_gaps_interval, gap_length)
                            fake_start_int_1 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_start")
                            fake_end_int_1 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_end")
                            fake_start_int_2 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_start2")
                            fake_end_int_2 = self.model.NewIntVar(
                                fake_start, fake_end, "fake_end2")

                            fake_duration_int_1 = self.model.NewIntVar(
                                0, fake_end - fake_start, "dur1")
                            fake_duration_int_2 = self.model.NewIntVar(
                                0, fake_end - fake_start, "dur2")

                            fake1 = self.model.NewOptionalIntervalVar(
                                fake_start_int_1, fake_duration_int_1,
                                fake_end_int_1, fake_bol1, "fake1")
                            fake2 = self.model.NewOptionalIntervalVar(
                                fake_start_int_2, fake_duration_int_2,
                                fake_end_int_2, fake_bol2, "fake2")

                            self.fake_whites[person_id] = [
                                fake1, fake2
                            ] + clients_gaps_interval
                            self.model.Add(fake_duration_int_1 > 0
                                           ).OnlyEnforceIf(fake_bol1)
                            self.model.Add(
                                fake_duration_int_1 == 0).OnlyEnforceIf(
                                    fake_bol1.Not())
                            self.model.Add(fake_duration_int_2 > 0
                                           ).OnlyEnforceIf(fake_bol2)
                            self.model.Add(
                                fake_duration_int_2 == 0).OnlyEnforceIf(
                                    fake_bol2.Not())

                            self.model.Add(fake_start_int_1 == fake_start)
                            self.model.Add(fake_end_int_2 == fake_end)
                            self.model.Add(
                                sum(durations) + fake_duration_int_1 +
                                fake_duration_int_2 +
                                sum(clients_gaps_duration) == fake_end -
                                fake_start -
                                int(self.var_data["maxGapClientSchedule"]) //
                                self.var_data["slot_length"])
                            if len(clients_gaps_duration) > 0:
                                self.model.Add(
                                    sum(clients_gaps_duration) == gap_length)

                            # new_bol1 = self.model.NewBoolVar("new_bol1")
                            # new_bol2 = self.model.NewBoolVar("new_bol2")
                            # self.model.Add(
                            #     fake_duration_int_1 == 0).OnlyEnforceIf(
                            #         new_bol1.Not())

                            # self.model.Add(
                            #     fake_duration_int_2 == 0).OnlyEnforceIf(
                            #         new_bol2.Not())

                            # self.count_fake.append(fake_bol1)
                            # self.count_fake.append(fake_bol2)
                            # self.count_fake.append(new_bol1)
                            # self.count_fake.append(new_bol2)

                            self.individual_fake_boolean[person_id] = [
                                fake_bol2, fake_bol1
                            ]

                            # some_new_bol = self.model.NewBoolVar(
                            #     "some_new_bol")
                            # self.model.Add(fake_duration_int_1 +
                            #                fake_duration_int_2 <= 0 * 60 //
                            #                self.var_data["slot_length"]
                            #                ).OnlyEnforceIf(some_new_bol)
                            # self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                            #     some_new_bol.Not())

                            # self.model.Add(fake_duration_int_1 == 0)
                            # self.model.Add(fake_duration_int_2 == 0)
                            # self.model.Add(
                            #     sum(durations) == max9 - min9 -
                            #     int(self.var_data["maxGapClientSchedule"]) //
                            #     self.var_data["slot_length"]).OnlyEnforceIf(
                            #         bol)
                            # self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                            #     bol.Not())

    def lunch_constraints(self):
        # print("bazo_lunch_start")
        "6f390447-6dfe-4705-a795-34a817a378b1"  # this lunch id
        days_arrays = days_arr(self.var_data['slot_length'])
        lunch_length = 30 // self.var_data['slot_length']
        for index in range(7):
            # print("bazo_lunch : ", self.var_data['lunch_role'])
            for id in self.find_ids_by_role([self.var_data['lunch_role']]):
                val = self.get_appointments([[id], [str(index)],
                                             [self.var_data["lunch_id"]]])
                if len(val) == 0:
                    continue
                therapy_val = self.get_appointments(
                    [[id], [str(index)], self.var_data["objectiveactivity"]])
                # print("bazzoooo : ", id, self.var_data["objectiveactivity"],
                #       therapy_val, val)
                xy = self.model.NewBoolVar('hello')
                dur_lunch = sum(map(lambda num: num[0], val.values()))
                min_start = self.model.NewIntVar(0, 1000,
                                                 f"min_start-{index}-{id}")
                max_end = self.model.NewIntVar(0, 1000,
                                               f"max_end-{index}-{id}")
                # self.model.AddMinEquality(
                #     min_start,
                #     list(map(lambda num: num[3], therapy_val.values())))
                # self.model.AddMinEquality(
                #     max_end, list(map(lambda num: num[4],
                #                       therapy_val.values())))

                bol_lunch = sum(map(lambda num: num[6], val.values()))
                self.model.Add(bol_lunch <= 1)

                dur_therapy = sum(map(lambda num: num[0],
                                      therapy_val.values()))

                if (len(val) > 0):
                    # print("bazo_bug_lunch : ", list(val.values()))
                    # self.model.Add(min_start >= list(val.values())[0][3]
                    #                ).OnlyEnforceIf(xy)
                    # self.model.Add(
                    #     max_end <= list(val.values())[0][4]).OnlyEnforceIf(xy)
                    self.model.Add(dur_lunch == lunch_length).OnlyEnforceIf(xy)
                    self.model.Add(
                        dur_therapy > 240 //
                        self.var_data["slot_length"]).OnlyEnforceIf(xy)
                    self.model.Add(dur_lunch == 0).OnlyEnforceIf(xy.Not())
                    self.model.Add(dur_therapy <= 240 //
                                   self.var_data["slot_length"]).OnlyEnforceIf(
                                       xy.Not())

    def break_constraints(self):
        days_arrays = days_arr(self.var_data['slot_length'])
        break_length = 15 // self.var_data['slot_length']
        for index, x in enumerate(days_arrays[1:]):
            for id in self.find_ids_by_role([self.var_data['break_role']]):
                break_val = self.get_appointments([[id], [str(index)],
                                                   [self.var_data["break_id"]]
                                                   ])
                therapy_val = self.get_appointments(
                    [[id], [str(index)], self.var_data["objectiveactivity"]])

                dur_break = sum(map(lambda num: num[0], break_val.values()))
                bol_break = sum(map(lambda num: num[6], break_val.values()))
                self.model.Add(bol_break <= 2)

                b_bol1 = self.model.NewBoolVar("bol1")
                b_bol2 = self.model.NewBoolVar("bol2")

                arr_exists_bool = []

                for break_data in list(map(lambda num: num,
                                           break_val.values())):
                    m_bol = self.model.NewBoolVar("m_bol")
                    max_bool_arr = []
                    min_bool_arr = []
                    for info in list(map(lambda num: num,
                                         therapy_val.values())):
                        d_bol_se = self.model.NewBoolVar("d_bol_se")
                        d_bol_es = self.model.NewBoolVar("d_bol_es")
                        not_zero = self.model.NewBoolVar("not_zero")

                        self.model.Add(info[0] != 0).OnlyEnforceIf(not_zero)
                        self.model.Add(info[0] == 0).OnlyEnforceIf(
                            not_zero.Not())

                        target1 = self.model.NewBoolVar("target1")
                        target2 = self.model.NewBoolVar("target2")

                        self.model.Add(
                            break_data[3] == info[4]).OnlyEnforceIf(d_bol_se)
                        self.model.Add(break_data[3] != info[4]).OnlyEnforceIf(
                            d_bol_se.Not())
                        self.model.Add(
                            break_data[4] == info[3]).OnlyEnforceIf(d_bol_es)
                        self.model.Add(break_data[4] != info[3]).OnlyEnforceIf(
                            d_bol_es.Not())

                        self.model.AddMultiplicationEquality(
                            target1, [d_bol_es, not_zero])
                        self.model.AddMultiplicationEquality(
                            target2, [d_bol_se, not_zero])

                        max_bool_arr.append(target1)
                        min_bool_arr.append(target2)
                    self.model.Add(sum(max_bool_arr) == 1).OnlyEnforceIf(m_bol)
                    self.model.Add(sum(min_bool_arr) == 1).OnlyEnforceIf(m_bol)
                    arr_exists_bool.append(m_bol)

                dur_therapy = sum(map(lambda num: num[0],
                                      therapy_val.values()))

                # new_bb1 = self.model.NewBoolVar("nn_bol1")
                # new_bb2 = self.model.NewBoolVar("nn_bol2")
                # self.model.Add(
                #     dur_therapy >= int(3.25 * 60 //
                #                        self.var_data["slot_length"])
                # ).OnlyEnforceIf(new_bb1)
                # self.model.Add(
                #     dur_therapy < int(3.25 * 60 //
                #                       self.var_data["slot_length"])
                # ).OnlyEnforceIf(new_bb1.Not())
                # self.model.Add(
                #     dur_therapy >= int(2 * 3.25 * 60 //
                #                        self.var_data["slot_length"])
                # ).OnlyEnforceIf(new_bb2)
                # self.model.Add(
                #     dur_therapy < int(2 * 3.25 * 60 //
                #                       self.var_data["slot_length"])
                # ).OnlyEnforceIf(new_bb2.Not())

                # print("buggy_ford : ", break_val)
                if len(break_val) > 0:
                    # print("salamura")
                    # therapy_list = list(
                    #     map(lambda num: num, break_val.values()))
                    # nn = len(therapy_list)
                    # for i in range(nn):
                    #     arr_t = []
                    #     for j in range(nn):
                    #         if not i == j:
                    #             bb1 = self.model.NewBoolVar("bbbb1")
                    #             bb2 = self.model.NewBoolVar("bbbb2")
                    #             d_target = self.model.NewIntVar(
                    #                 0, 1000000, "d_target")
                    #             self.model.Add(
                    #                 therapy_list[i][3] == therapy_list[j]
                    #                 [4]).OnlyEnforceIf(bb1)
                    #             self.model.Add(
                    #                 therapy_list[i][3] != therapy_list[j]
                    #                 [4]).OnlyEnforceIf(bb1.Not())
                    #             self.model.Add(
                    #                 therapy_list[i][4] == therapy_list[j]
                    #                 [3]).OnlyEnforceIf(bb1)
                    #             self.model.Add(
                    #                 therapy_list[i][4] != therapy_list[j]
                    #                 [3]).OnlyEnforceIf(bb1.Not())
                    ii = 0
                    xy_arr = []
                    for break_data in list(
                            map(lambda num: num, break_val.values())):
                        exist_bool = self.model.NewBoolVar('exist_bool')
                        xy = self.model.NewBoolVar('hello')

                        self.model.AddMultiplicationEquality(
                            exist_bool, [xy, arr_exists_bool[ii]])

                        self.model.Add(break_data[0] ==
                                       break_length).OnlyEnforceIf(exist_bool)

                        self.model.Add(break_data[0] == 0).OnlyEnforceIf(
                            exist_bool.Not())

                        self.model.Add(
                            dur_therapy >= int(3.25 * 60 //
                                               self.var_data['slot_length'])
                        ).OnlyEnforceIf(exist_bool)

                        self.model.Add(
                            dur_therapy < int(3.25 * 60 //
                                              self.var_data['slot_length'])
                        ).OnlyEnforceIf(exist_bool.Not())
                        xy_arr.append(xy)
                        ii += 1

        # days_arrays = days_arr(self.var_data['slot_length'])
        # for index, x in enumerate(days_arrays):
        #     if index == self.var_data["today_index"]:
        #         for id in self.find_ids_by_role([self.var_data['break_role']]):
        #             val = self.get_appointments(
        #                 [[id],
        #                  list(range(days_arrays[index],
        #                             days_arrays[index + 1])),
        #                  [self.var_data["break_id"]]])
        #             val_lunch = self.get_appointments(
        #                 [[id],
        #                  list(range(days_arrays[index],
        #                             days_arrays[index + 1])),
        #                  [self.var_data["lunch_id"]]])
        #             therapy_val = self.get_appointments(
        #                 [[id],
        #                  list(range(days_arrays[index],
        #                             days_arrays[index + 1])),
        #                  [self.var_data[" ctiveactivity"]]])
        #             xy = self.model.NewBoolVar('hello')

        #             print("break_ggmg : ", val, therapy_val, val_lunch)

        #             break_max = self.model.NewIntVar(0, 100000, 'snip1')
        #             break_min = self.model.NewIntVar(0, 100000, 'snip2')
        #             lunch_max = self.model.NewIntVar(0, 100000, 'snip3')
        #             lunch_min = self.model.NewIntVar(0, 100000, 'snip4')
        #             direct_max = self.model.NewIntVar(0, 100000, 'snip5')
        #             direct_min = self.model.NewIntVar(0, 10000000, 'snip6')

        #             # if len(therapy_val) > 0:
        #             #     direct_end_slots = list(
        #             #         map(lambda num: num[4], therapy_val.values()))
        #             #     direct_start_slots = list(
        #             #         map(lambda num: num[3], therapy_val.values()))
        #             #     # self.model.AddMaxEquality(direct_max, direct_end_slots)
        #             #     self.model.AddMinEquality(direct_min,
        #             #                               direct_start_slots)
        #             # else:
        #             #     self.model.Add(xy == 0)

        #             if len(val_lunch) > 0:
        #                 lunch_end_slots = list(
        #                     map(lambda num: num[4], val.values()))
        #                 lunch_start_slots = list(
        #                     map(lambda num: num[3], val_lunch.values()))
        #                 self.model.AddMaxEquality(lunch_max, lunch_end_slots)
        #                 self.model.AddMinEquality(lunch_min, lunch_start_slots)
        #             # else:
        #             #     pass

        #             if len(val) > 0:
        #                 break_end_slots = list(
        #                     map(lambda num: num[4], val.values()))
        #                 break_start_slots = list(
        #                     map(lambda num: num[3], val.values()))
        #                 self.model.AddMaxEquality(break_max, break_end_slots)
        #                 self.model.AddMinEquality(break_min, break_start_slots)

        #             # else:
        #             #     pass

        #             if (len(val) > 0) and ((len(therapy_val) > 0)):
        #                 and_bools = []
        #                 max_arr = []
        #                 min_arr = []
        #                 for i in therapy_val.values():
        #                     break_bool = self.model.NewBoolVar("break_")
        #                     self.model.Add(i[0] != 0).OnlyEnforceIf(break_bool)
        #                     self.model.Add(i[0] == 0).OnlyEnforceIf(
        #                         break_bool.Not())
        #                     target = self.model.NewIntVar(0, 1000000, "tt")
        #                     target_min = self.model.NewIntVar(
        #                         0, 10000000, "tt")
        #                     target2 = self.model.NewIntVar(0, 1, "tt")
        #                     target3 = self.model.NewIntVar(0, 1000000, "tt")
        #                     self.model.Add(
        #                         target2 == 1).OnlyEnforceIf(break_bool)
        #                     self.model.Add(target2 == 0).OnlyEnforceIf(
        #                         break_bool.Not())
        #                     self.model.Add(
        #                         target3 == 1).OnlyEnforceIf(break_bool)
        #                     self.model.Add(target3 == 1000).OnlyEnforceIf(
        #                         break_bool.Not())
        #                     self.model.AddMultiplicationEquality(
        #                         target, [i[4], target2])
        #                     self.model.AddMultiplicationEquality(
        #                         target_min, [i[3], target3])
        #                     max_arr.append(target)
        #                     min_arr.append(target_min)
        #                 # self.model.AddMaxEquality(direct_max, max_arr)

        #                 # self.model.AddMinEquality(direct_min, min_arr)
        #                 # self.model.Add(direct_min < break_min)
        #                 # self.model.Add(direct_max > break_max)

        #                 # lb = self.model.NewBoolVar("lunch_break")
        #                 # self.model.Add(
        #                 #     break_max < lunch_min).OnlyEnforceIf(lb)
        #                 # self.model.Add(
        #                 #     break_min > lunch_max).OnlyEnforceIf(lb.Not())

        #                 # self.model.Add(
        #                 #     lunch_min - 2 >= break_max).OnlyEnforceIf(lb)

        #                 # self.model.Add(
        #                 #     lunch_max <= break_min - 2).OnlyEnforceIf(lb.Not())

        #                 # if len(val_lunch) > 0:
        #                 #     target = self.model.NewIntVar(0, 1000, "target")
        #                 #     dif = self.model.NewIntVar(0, 1000, "dif")
        #                 #     self.model.Add(lunch_max - break_max == dif)
        #                 #     self.model.AddAbsEquality(target, dif)
        #                 #     self.model.Add(
        #                 #         target >= 180 //
        #                 #         self.var_data["slot_length"]).OnlyEnforceIf(xy)
        #                 self.model.Add(
        #                     sum(map(lambda num: num[0], val.values())) == 15 //
        #                     self.var_data["slot_length"]).OnlyEnforceIf(xy)
        #                 self.model.Add(
        #                     sum(map(lambda num: num[0], val.values())) ==
        #                     0).OnlyEnforceIf(xy.Not())
        #                 self.model.Add(
        #                     sum(map(lambda num: num[0],
        #                             therapy_val.values())) >= (240) //
        #                     self.var_data["slot_length"]).OnlyEnforceIf(xy)
        #                 self.model.Add(
        #                     sum(map(lambda num: num[0],
        #                             therapy_val.values())) < (240) //
        #                     self.var_data["slot_length"]).OnlyEnforceIf(
        #                         xy.Not())

        #             else:
        #                 self.model.Add(
        #                     sum(map(lambda num: num[0], val.values())) == 0)

    def team_constraints(self, team_bounds):
        people = self.find_ids_by_role(['Person'])
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
                per1, per2 = peep[0], peep[1]
                self.model.Add(some_val[per1] == some_val[per2]).OnlyEnforceIf(
                    event[6])

    def constraint_drive(self):
        constraint_drive_data = get_drive_time_data(self.var_data["header"],self.var_data["host"])
        persons_ids_arr = self.find_ids_by_role(['Person'])
        # day_times = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
        # drive_keys = constraint_drive.keys()
        count_applied = 0
        max_time_for_drive = 60 # in minutes
        max_time_slots_array = list(range(max_time_for_drive//self.var_data["slot_length"]+1))
        boost_cof = 1 # now it is hard coded 
        is_high_traffic = False # hard coded
        days_arrays = days_arr(self.var_data['slot_length'])
        all_act = [i for i in self.find_ids_by_role(['Activity']) if i not in self.var_data["notWorking"]]
        for index, x in enumerate(days_arrays):
            if index == self.var_data['today_index'] and index != 0:
                for id in self.find_ids_by_role(['Employee']):
                    # val = self.get_appointments([[id], [str(index)],self.find_ids_by_role(['Activity'])])
                    # val = self.get_appointments([[id], [str(index)],all_act])
                    # val_not = self.get_appointments([[id], [str(index)],self.var_data["notWorking"]])
                    val = self.get_appointments([[id], ['1','2','3','4','5','6','7'],all_act])
                    val_not = self.get_appointments([[id], ['1','2','3','4','5','6','7'],self.var_data["notWorking"]])
                    print('snoopy3',len(val),len(val_not),index)
                    combs = list(combinations(map(lambda num: num, val.values()), 2))
                    val_not_values = list(map(lambda num: num,val_not.values()))
                    val_values = list(map(lambda num: num,val.values()))
                    all_combs = []
                    for r11 in val_values:
                        for r22 in val_not_values:
                            all_combs.append((r11,r22))
                    all_combs = all_combs + combs
                    count = len(combs)
                    print('filly2',count,len(val.values()))
                    # for r_keys in list(combinations(map(lambda num: num, val.keys()),2)):
                    #     key1 = r_keys[0]
                    #     key2 = r_keys[1]
                    #     res1 = val[key1]
                    #     res2 = val[key2]
                    #     users1 = list(key1)
                    #     users2 = list(key2)
                    #     check_inter1 = list(set([*users1]) & set(self.var_data["notWorking"]))
                    #     check_inter2 = list(set([*users2]) & set(self.var_data["notWorking"]))
                    #     if len(check_inter1)+len(check_inter2) > 1:
                    #         print('wooty3',check_inter1,check_inter2)
                    #         continue
                    for r in all_combs:
                        res1 = r[0]
                        res2 = r[1]
                        print('rooty7')
                        if res1[12] is None or res2[12] is None:
                            print('rooty9')
                            continue
                        address1 = res1[7]
                        address2 = res2[7]
                        loc1 = self.solutions1.user_uuid_to_index[res1[12]]
                        loc2 = self.solutions1.user_uuid_to_index[res2[12]]
                        # print('bazo_addr : ',loc1,loc2,address1,address2)
                        branchId1 = 'd'
                        branchId2 = 's'
                        user1_address = self.solutions1.users[loc1]["address"]
                        user2_address = self.solutions1.users[loc2]["address"]
                        # print("bazo_adresses : ",user1_address,user2_address)
                        user1_id = self.solutions1.users[loc1]["id"]
                        user2_id = self.solutions1.users[loc2]["id"]
                        # if loc1 is None and loc2 is None:
                        #     continue
                        # if loc1 == loc2:
                        #     continue
                        print('rooty1')
                        if address1 is None or address2 is None:
                            continue
                        print('rooty2')
                        if address1 == address2:
                            continue
                        print('rooty3')
                        if loc1:
                            # print('ss_bb',loc1,self.solutions1.users[loc1])
                            branchId1 = self.solutions1.users[loc1]['branches'][0]
                        if loc2:
                            # print('ss_bb2',loc2,self.solutions1.users[loc2])
                            branchId2 = self.solutions1.users[loc2]['branches'][0]
                        # print('bazo_loc_ids',loc1,loc2)
                        if len(branchId1) > 1 and len(branchId2) > 1 and (loc1 or loc2):
                            print('rooty4')
                            # print("bb_what_is_going_on1")
                            # if address1 and address2 and len(address1) > 1 and len(
                            #         address2

                            # #) > 1 and address2 != address1 and address1 in drive_keys:
                            # ) > 1 and address2 != address1 and address1:
                            if True:
                                # if address2 in constraint_drive[address1].keys(
                                # ) and constraint_drive[address1][address2][1]:
                                #     drive_time = ceil_to_multiple(
                                #         constraint_drive[address1][address2][1] /
                                #         60.0, self.var_data['slot_length'])
                                drive_time = self.solutions1.branches[branchId1]['drivetime']
                                #tuple_ids = tuple(sorted([user1_id, user2_id])) 
                                tuple_ids = tuple([address1, address2]) 
                                tuple_ids_reverse = tuple([address2, address1]) 
                                # print("bazo_user_tuple : ", tuple_ids)
                                
                                #TEST
                                print('rooty5')
                                if tuple_ids in constraint_drive_data.keys() and self.var_data["companyId"] != "090121f7-8598-463e-92c4-f501c2576e60":
                                    print('constraint_drive_data1',constraint_drive_data,tuple_ids,constraint_drive_data[tuple_ids])
                                    d_data_duration = constraint_drive_data[tuple_ids]['mid']
                                    # d_data = convert_drive_time(d_data)
                                    # d_data = sum([int(i[1]) for i in d_data])/len(d_data)
                                    # cof = return_cofficients_of_polinomial([(i+5)*4 for i in day_times],[int(i[1]) for i in d_data])
                                    # int_cof = [int(i*1000) for i in cof]
                                    # print("bazo_cof : ",int_cof)
                                    # drive_time_data = round(int(d_data)/60)
                                    drive_time_data = round_to_nearest_interval(d_data_duration // 60,self.var_data["slot_length"])
                                    if is_high_traffic:
                                        drive_time_data = drive_time_data*boost_cof
                                    for i in max_time_slots_array:
                                        if i > drive_time_data/self.var_data["slot_length"]:
                                            drive_time = i
                                            break
                                        
                                    # if drive_time_data > 0 and drive_time_data <= 15:
                                    #     drive_time = 15
                                    #     print("bb_drive_time : ",drive_time)
                                    # if drive_time_data > 15 and drive_time_data <= 30:
                                    #     drive_time = 30
                                    # if drive_time_data > 30 and drive_time_data <= 45:
                                    #     drive_time = 45
                                    #     print("bb_drive_time2 : ",drive_time)
                                    # else:
                                    #     drive_time = 0
                                elif self.var_data["companyId"] != "090121f7-8598-463e-92c4-f501c2576e60":
                                    #result_distance_dur_early = return_interval_drive_time(address1, address2,8,30)
                                    result_distance_dur_early = return_interval_drive_time(address1, address2,11,30)
                                    result_distance_dur_early_reverse = result_distance_dur_early
                                    print('llama',address1, address2, result_distance_dur_early)
                                    #result_distance_dur_early_reverse = return_interval_drive_time(loc_address2, loc_address,8,30)
                                    if result_distance_dur_early != [0,0]:
                                        result_distance_dur_mid = result_distance_dur_early
                                        result_distance_dur_late = result_distance_dur_early
                                        #result_distance_dur_mid = return_interval_drive_time(address1, address2,11,30)
                                        #result_distance_dur_late = return_interval_drive_time(address1, address2,5,30)
                                        result_distance_dur_mid_reverse = result_distance_dur_mid
                                        result_distance_dur_late_reverse = result_distance_dur_late
                                        #result_distance_dur_mid_reverse = return_interval_drive_time(loc_address, loc_address2,11,30)
                                        #result_distance_dur_late_reverse = return_interval_drive_time(loc_address, loc_address2,5,30)
                                        print('soover')
                                        post_drive_time_data(self.var_data['header'],{
                                            "data" :{
                                                "address1": address1,
                                                "address2":address2,
                                                "duration": result_distance_dur_mid[1],
                                                "duration_early": result_distance_dur_early[1],
                                                "duration_late": result_distance_dur_late[1],
                                                "distance": result_distance_dur_early[0],
                                                }
                                        },self.var_data['host'])
                                        post_drive_time_data(self.var_data['header'],{
                                            "data" :{
                                                "address1": address2,
                                                "address2": address1,
                                                "duration": result_distance_dur_mid_reverse[1],
                                                "duration_early": result_distance_dur_early_reverse[1],
                                                "duration_late": result_distance_dur_late_reverse[1],
                                                "distance": result_distance_dur_early_reverse[0],
                                                }
                                        },self.var_data['host'])
                                    constraint_drive_data[tuple_ids] = {"early": result_distance_dur_early[1],"mid":result_distance_dur_mid[1],"late":result_distance_dur_late[1]}
                                    constraint_drive_data[tuple_ids_reverse] = {"early": result_distance_dur_early_reverse[1],"mid":result_distance_dur_mid_reverse[1],"late":result_distance_dur_late_reverse[1]}
                                    # d_data = convert_drive_time(result_distance_dur_str)
                                    # d_data = sum([int(i[1]) for i in d_data])/len(d_data)
                                    drive_time_data = round_to_nearest_interval(result_distance_dur_mid[1] // 60,self.var_data["slot_length"])
                                    if is_high_traffic:
                                        drive_time_data = drive_time_data*boost_cof
                                    for i in max_time_slots_array:
                                        if i > drive_time_data/self.var_data["slot_length"]:
                                            drive_time = i
                                            break
                                    # if drive_time_data > 0 and drive_time_data <= 15:
                                    #     drive_time = 15
                                    # if drive_time_data > 15 and drive_time_data <= 30:
                                    #     drive_time = 30
                                    # if drive_time_data > 30 and drive_time_data <= 45:
                                    #     drive_time = 45
                                #TEST
                                if drive_time == 0 or not drive_time:
                                    drive_time = 0
                                    constraint_drive_data[tuple_ids] = {"early": 0,"mid":0,"late":0}
                                    constraint_drive_data[tuple_ids_reverse] = {"early": 0,"mid":0,"late":0}
                                    drive_time = 0//self.var_data["slot_length"]
                                else:
                                    # print('snoofy', drive_time)
                                    pass
                                # print("bbdd_drive_time: ", drive_time)
                                drive_time_slot = int(drive_time)
                                print('rooty6')
                                
                                # print("what_is_drive_time: ",drive_time_slot)
                                if self.var_data["companyId"] == "090121f7-8598-463e-92c4-f501c2576e60":
                                    drive_time_slot = 15 // self.var_data["slot_length"]
                                # drive_time_slot = 3
                                print("Drive_bazo : ",drive_time_slot,loc1==loc2,loc1,loc2)
                                end2 = res2[4]
                                start2 = res2[3]
                                end1 = res1[4]
                                start1 = res1[3]
                                duration2 = res2[0]
                                duration1 = res1[0]
                                if address1 != address2: # We have to check both locations are the same home
                                    is_left = self.model.NewBoolVar("is_left")
                                    is_drive = self.model.NewBoolVar("is_drive")
                                    # is_right = self.model.NewBoolVar("is_right")
                                    self.model.Add(start1 <= start2).OnlyEnforceIf(is_left)
                                    # self.model.Add(start1 <= start2).OnlyEnforceIf(is_right.Not())
                                    self.model.Add(start2 < start1).OnlyEnforceIf(is_left.Not())
                                    # self.model.Add(start2 < start1).OnlyEnforceIf(is_right)
                                    self.model.Add(start2-end1 >= drive_time_slot).OnlyEnforceIf(is_left).OnlyEnforceIf(is_drive)
                                    self.model.Add(start1-end2 >= drive_time_slot).OnlyEnforceIf(is_left.Not()).OnlyEnforceIf(is_drive)
                                    # self.model.Add(start1-end2 >= drive_time_slot).OnlyEnforceIf(is_right).OnlyEnforceIf(is_drive)
                                    self.model.AddMinEquality(is_drive,[res1[6],res2[6]])
                                    
                                    # self.model.Add(start1 > start2).OnlyEnforceIf(is_right)
                                    # self.model.Add(start2-end1 >= drive_time_slot).OnlyEnforceIf(is_left)
                                    # self.model.Add(start1-end2 >= drive_time_slot).OnlyEnforceIf(is_right)
                                    # self.model.Add(duration1 != 0).OnlyEnforceIf(is_left)
                                    # self.model.Add(duration2 != 0).OnlyEnforceIf(is_left)
                                    # self.model.Add(duration1 != 0).OnlyEnforceIf(is_right)
                                    # self.model.Add(duration2 != 0).OnlyEnforceIf(is_right)
                                    count_applied += 1
                                    print('goopy4',index)
                                    # Working one
                                    # is_drive = self.model.NewBoolVar("is_drive")
                                    # # is_drive2 = self.model.NewBoolVar("is_drive2")
                                    # min_int = self.model.NewIntVar(0,10000,"min_int")
                                    # max_int = self.model.NewIntVar(0,10000,"max_int")
                                    # self.model.AddMinEquality(min_int,[start1,start2])
                                    # self.model.AddMaxEquality(max_int,[end1,end2])
                                    
                                    # self.model.Add(max_int-min_int >= duration1+duration2+drive_time_slot).OnlyEnforceIf(is_drive)
                                    # self.model.Add(res1[6]+res2[6] == 2).OnlyEnforceIf(is_drive)
                                    # self.model.Add(res1[6]+res2[6] < 2).OnlyEnforceIf(is_drive.Not())
                                    
                                    # self.model.Add(end2-end1 >= duration2+drive_time_slot).OnlyEnforceIf(is_drive)
                                    # self.model.Add(end1-end2 >= duration1+drive_time_slot).OnlyEnforceIf(is_drive.Not())
                                    # Working one
                                
                                # newBol = self.model.NewBoolVar('yo')
                                # self.model.AddMultiplicationEquality(
                                #     newBol, [res1[6], res2[6]])
                                # newInt1 = self.model.NewIntVar(
                                #     -100000000, 100000000, 'h')
                                # newInt3 = self.model.NewIntVar(
                                #     -100000, 100000, 'h')
                                # max_end = self.model.NewIntVar(
                                #     -100000, 100000, 'h')
                                # min_end = self.model.NewIntVar(
                                #     -100000, 100000, 'h')
                                # self.model.AddMaxEquality(
                                #     max_end, [end1, end2])
                                # self.model.AddMinEquality(
                                #     min_end, [start1, start2])

                                # # x_squared = self.model.NewIntVar(0,1000_000_00,"x_squared")
                                # # self.model.AddMultiplicationEquality(x_squared, [min_end, min_end])
                                # # x = min_end
                                # # self.model.Add(int_cof[0]*x_squared+int_cof[1]*x+int_cof[2] <= newInt1*1000*60*15)
                                # # print('sloofy', end1, end2, start1, start2,
                                # #       duration1, duration2)

                                # self.model.Add(newInt1 == max_end - min_end -
                                #                duration2 - duration1)
                                # self.model.Add(newInt1 >= drive_time_slot
                                #                ).OnlyEnforceIf(newBol)
                                # self.model.Add(
                                #     duration1 != 0).OnlyEnforceIf(newBol)
                                # self.model.Add(
                                #     duration2 != 0).OnlyEnforceIf(newBol)
                                # # self.model.Add(
                                # #     newInt1 < drive_time_slot).OnlyEnforceIf(
                                # #         newBol.Not())
                                # # self.drive_time_data[tuple_ids] = newInt1
        self.drive_time_data = constraint_drive_data
        print("OK_WITH : DRIVE_CONS")
        print("drive_time_applied : ",count_applied)

    def create_fake_variable(self):
        people = self.find_ids_by_role(["Resource"])
        av_arr_for_fake_raw = self.solutions1.user_availabilities_general
        av_arr_for_fake = {}
        for some_id in people:
            av_arr_for_fake[some_id] = {
                0: [],
                1: [],
                2: [],
                3: [],
                4: [],
                5: [],
                6: [],
                7: []
            }
        for some_id in people:
            for i in av_arr_for_fake_raw[some_id]:
                some_index = i[0] // (
                    (24 * 60) // self.var_data["slot_length"])
                av_arr_for_fake[some_id][some_index].append(i)
        for people_id in people:
            for day_index in range(7):
                if av_arr_for_fake[people_id][day_index] == []:
                    continue
                av_d = av_arr_for_fake[people_id][day_index]
                f_start = min([i[0] for i in av_d])
                f_end = min([i[1] for i in av_d])

                fake_dict = {
                    "start_int":
                    f_start,
                    "end_int":
                    f_end,
                    "fake_bool":
                    self.model.NewBoolVar(f"fake_bool_{people}_{day_index}"),
                    "fake_start":
                    self.model.NewIntVar(f_start, f_end,
                                         f"fake_start_{people}_{day_index}"),
                    "fake_end":
                    self.model.NewIntVar(f_start, f_end,
                                         f"fake_end_{people}_{day_index}"),
                    "fake_dur":
                    self.model.NewIntVar(0, f_end - f_start,
                                         f"fake_dur_{people}_{day_index}"),
                }
                f_interval = self.model.NewOptionalIntervalVar(
                    fake_dict["fake_start"], fake_dict["fake_dur"],
                    fake_dict["fake_end"], fake_dict["fake_bool"],
                    f"fake_interval_{people}_{day_index}")
                fake_dict.update({"fake_interval": f_interval})
            pass
        pass
    
    def supervision_constraint(self,run_bool):
        print("super_vision_constraint")
        clients = self.find_ids_by_role(["Client"])
        direct_activity_id = "2faf27ca-9120-486c-9738-83714f0ee50d"
        supervision_activity_id = "f39d479c-ea0f-4dcf-86e1-3e47c19328c7"
        for id in clients:
            val_direct = self.get_appointments([[id], [direct_activity_id]])
            val_super = self.get_appointments([[id], [supervision_activity_id]])
            print(len(val_direct),len(val_super))
            for super_a in list(map(lambda x: x,val_super.values())):
                super_bol = self.model.NewBoolVar(f"super_bol-{id}")
                super_arr = []
                for direct in list(map(lambda x: x,val_direct.values())):
                    print("he_we_go_direct")
                    direct_super_bol = self.model.NewBoolVar(f"direct_super_bol-{id}")
                    self.model.Add(direct[3] <= super_a[3]).OnlyEnforceIf(direct_super_bol)
                    self.model.Add(direct[4] >= super_a[4]).OnlyEnforceIf(direct_super_bol)
                    self.model.Add(direct[0] >= super_a[0]).OnlyEnforceIf(direct_super_bol)
                    super_arr.append(direct_super_bol)
                self.model.Add(sum(super_arr) == 1).OnlyEnforceIf(super_bol)
                self.model.Add(sum(super_arr) == 0).OnlyEnforceIf(super_bol.Not())
                self.model.Add(super_a[0] > 0).OnlyEnforceIf(super_bol)   
                self.model.Add(super_a[0] == 0).OnlyEnforceIf(super_bol.Not())
    
    def matches_frequency(self):
        weekly_data  =self.var_data["weekly_events_data"]
        gaps_ids_arr = []
        hour_slot_ratio = 60 // self.var_data["slot_length"]
        max_total_hours = int(
            get_number_per_slot(self.solutions1) //
            (60 // self.var_data['slot_length']))
        max_total_hours = max_total_hours if max_total_hours > 0 else 1
        # print("my_matches_bazo_total_max: ", max_total_hours)
        # print("hour_slot_ratio : ", hour_slot_ratio)
        people = self.find_ids_by_role(["Resource"])
        days_arrays = days_arr(self.var_data['slot_length'])
        employees = self.find_ids_by_role(['Employee'])
        clients = self.find_ids_by_role(['Client'])
        people = employees + clients
        av_arr_for_fake_raw = self.solutions1.user_availabilities_general
        av_arr_for_fake = {}
        for some_id in people:
            av_arr_for_fake[some_id] = {
                0: [],
                1: [],
                2: [],
                3: [],
                4: [],
                5: [],
                6: [],
                7: []
            }
        for some_id in people:
            for i in av_arr_for_fake_raw[some_id]:
                some_index = i[0] // (
                    (24 * 60) // self.var_data["slot_length"])
                av_arr_for_fake[some_id][some_index].append(i)

        # for person_id in people:
        #     # val = self.get_appointments([[person_id]])
        #     for person_id2 in self.resources1.resources[
        #             person_id].matches2.keys():
        #         # val2 = self.get_appointments([[person_id2]], False, val)

        #         for index, x in enumerate(days_arrays):
        #             if index == self.var_data['today_index']:
        #                 # print('hello7', index, x,
        #                 #       list(range(days_arrays[index - 1], x)))
        #                 # val3 = self.get_appointments(
        #                 #     [list(range(days_arrays[index - 1], x))], False,
        #                 #     val2)
        #                 val3 = self.get_appointments([[person_id],
        #                                               [person_id2]])
        #                 #  list(range(days_arrays[index - 1], x))])
        #                 durations = list(map(lambda num: num[0],
        #                                      val3.values()))
        #                 sessions = list(map(lambda num: num[6], val3.values()))
        #                 matching_bol = self.resources1.resources[
        #                     person_id].matches2[person_id2][index - 1]
        #                 int_duration = self.resources1.resources[
        #                     person_id].matches2_durations[person_id2][index -
        #                                                               1]
        #                 int_session = self.resources1.resources[
        #                     person_id].matches2_sessions[person_id2][index - 1]

        #                 if len(val3) == 0:
        #                     self.model.Add(matching_bol == 0)
        #                     self.model.Add(int_duration == 0)
        #                     self.model.Add(int_session == 0)
        #                 else:
        #                     self.model.Add(sum(durations) == 0).OnlyEnforceIf(
        #                         matching_bol.Not())
        #                     self.model.Add(
        #                         sum(durations) > 0).OnlyEnforceIf(matching_bol)
        #                     self.model.Add(sum(durations) == int_duration)
        #                     self.model.Add(sum(sessions) == int_session)

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
        # weights_dict = {
        #     i: self.model.NewIntVar(0, 1000000, f"{i}")
        #     for i in "soft_const_array"
        # }
        # vars_dict = {i: 0 for i in "soft_const_array"}
        # print("bazo_wants_know : ", self.solutions1.resources1.keys())
        # print("bazo_wants_know : ", self.solutions1.resources1.values())
        # print("bazo_wants_to_know : ",
        #       self.solutions1.resources1.frequency_constraints)

        if self.solutions1.resources1.frequency_constraints != []:
            counts_of_vars = {
                i["id"]: 0
                for i in self.solutions1.resources1.frequency_constraints
            }
            rank_of_vars = {
                i["id"]: 0
                for i in self.solutions1.resources1.frequency_constraints
            }
            rank_count = 2
            for i in self.var_data["highPriority"]:
                rank_of_vars[i] = rank_count
                rank_count += 1
            for i in self.var_data["hard"]:
                rank_of_vars[i] = 1
            for i in self.solutions1.resources1.frequency_constraints:
                if i["id"] in self.var_data["hard"]:
                    continue
                if i["id"] in self.var_data["highPriority"]:
                    continue
                rank_of_vars[i["id"]] = rank_count + 1
                rank_count += 1
            inte_vars = {
                i["id"]: self.model.NewIntVar(1, 1000_0000, i["id"])
                for i in self.solutions1.resources1.frequency_constraints
            }
            pair_vars = {
                i["id"]: i["id"]
                for i in self.solutions1.resources1.frequency_constraints
            }
            counts_of_vars.update({"max_total_durations": max_total_hours})
            rank_of_vars.update({
                "max_total_durations":
                2 + len(self.var_data["highPriority"])
            })
            pair_vars.update({"max_total_durations": "max_total_durations"})
            inte_vars.update({
                "max_total_durations":
                self.model.NewIntVar(0, 1000_0000, "mx_total")
            })
            # print("bazo_ranks : ", rank_of_vars)
            # print("my_matches_bazo : ", counts_of_vars, rank_of_vars,
            #       pair_vars)
            for c in self.solutions1.resources1.frequency_constraints:
                pass
                # print('constraint_bazo3', c['type'], c['min'], c['max'])
            print("old-frequency_constraints:", self.solutions1.resources1.frequency_constraints)
            for c in self.solutions1.resources1.frequency_constraints:
                # print('constraint_bazo', c['type'], c['users_antecedent'])
                print('constraint_bazo2', c)
                c_min = (int(c["minSeconds"]) //
                         60) // self.var_data["slot_length"]
                c_max = (int(c["maxSeconds"]) //
                         60) // self.var_data["slot_length"]
                # print("bazo_convert_confirmation_min : ", c["minSeconds"],
                #       c_min)
                # print("bazo_convert_confirmation_max : ", c["maxSeconds"],
                #       c_max)
                if not c["id"] in self.var_data["highPriority"]:
                    # print("  :  [YES]")
                    continue

                elif c['type'] == 'frequency':
                    for user_a in c['users_antecedent']:
                        user_a_id = self.solutions1.resources1.resources[user_a].id
                        if c['frequency'] == 'day':
                            for index, x in enumerate(days_arrays):
                                if index == self.var_data["today_index"] or True:
                                    arr = []
                                    for user_c in c['users_consequence']:
                                        user_c_id = self.solutions1.resources1.resources[user_c].id
                                        val = self.get_appointments([[user_c_id], [user_a_id],[str(index)]])
                                        if len(val) == 0:
                                            continue
                                        target1 = self.model.NewBoolVar(f"freq_bool-{user_c_id}")
                                        self.model.AddMaxEquality(target1,list(map(lambda num: num[6],val.values())))
                                        arr.append(target1)
                                        # arr = arr + list(map(lambda num: num[6],val.values()))
                                    if len(arr) == 0:
                                        continue
                                    if c["id"] in self.var_data["highPriority"]:
                                        print("bazo_freq_bool")
                                        self.model.Add(sum(arr) <= int(c['max']))
                                        if c["min"] != 0:
                                            self.model.Add(sum(arr) >= c['min'])
                                        counts_of_vars[c["id"]] += 1
                                    # else:
                                    #     bol = self.model.NewBoolVar('y')
                                    #     inte = self.model.NewIntVar(0, 10000000000, 'snip1')
                                    #     self.model.Add(inte == 1).OnlyEnforceIf(bol)
                                    #     self.model.Add(inte == 0).OnlyEnforceIf(bol.Not())
                                    #     self.constraint_bols.append(inte)
                                    #     counts_of_vars[c["id"]] += 1
                                    #     self.model.Add(sum(arr) <= c['max']).OnlyEnforceIf(bol)
                                    #     self.model.Add(sum(arr) >= c['min']).OnlyEnforceIf(bol)
                                    

                        elif c['frequency'] == 'week':
                            arr = []
                            for index, x in enumerate(days_arrays):
                                if index != 0:
                                    continue
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[
                                        user_c].id
                                    val = self.get_appointments([[user_c_id], [user_a_id],[str(index)]])
                                    if len(val) == 0:
                                        continue
                                    arr = arr + list(map(lambda num: num[6],val.values()))
                            if len(arr) == 0:
                                continue
                            bol = self.model.NewBoolVar('y')
                            inte = self.model.NewIntVar(0, 10000000000, 'snip1')

                            self.model.Add(inte == 1).OnlyEnforceIf(bol)
                            self.model.Add(inte == 0).OnlyEnforceIf(bol.Not())
                            self.constraint_bols.append(inte)

                            counts_of_vars[c["id"]] += 1
                            self.model.Add(sum(arr) <= c['max']).OnlyEnforceIf(bol)
                            self.model.Add(sum(arr) >= c['min']).OnlyEnforceIf(bol)
                elif c['type'] == 'time':
                    for user_a in c['users_antecedent']:
                        user_a_id = self.solutions1.resources1.resources[user_a].id
                        if c['frequency'] == 'session':
                            for index, x in enumerate(days_arrays):
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[user_c].id
                                    val = self.get_appointments([[user_c_id], [user_a_id],[str(index)]])
                                    if len(val) == 0:
                                        continue
                                    durations = list(map(lambda num: num[0],val.values()))
                                    for dur in durations:
                                        if c["id"] in self.var_data["highPriority"]:
                                            self.model.Add(dur <= c_max)
                                            if c_min != 0:
                                                inc = 1
                                                while inc < c_min:
                                                    self.model.Add(dur != inc)
                                                    inc += 1
                                            counts_of_vars[c["id"]] += 1
                                        else:
                                            bol = self.model.NewBoolVar('y')
                                            inte = self.model.NewIntVar(0, 10000000000, 'snip1')
                                            self.model.Add(inte == 1).OnlyEnforceIf(bol)
                                            counts_of_vars[c["id"]] += 1
                                            self.model.Add(inte == 0).OnlyEnforceIf(bol.Not())
                                            self.constraint_bols.append(inte)
                                            self.model.Add(dur <= c_max).OnlyEnforceIf(bol)
                                            self.model.Add(dur >= c_max).OnlyEnforceIf(bol)

                        if c["each_or_all_users"] == 'each':
                            if c['frequency'] == 'day':
                                for index, x in enumerate(days_arrays):
                                    for user_c in c['users_consequence']:
                                        bol = self.model.NewBoolVar('y')
                                        self.constraint_bols.append(bol)
                                        user_c_id = self.solutions1.resources1.resources[user_c].id
                                        arr = list(map(lambda num: num[0],self.get_appointments([[user_c_id],[user_a_id],
                                                        [str(index)]]).values()))
                                        if len(arr) == 0:
                                            continue
                                        print('look at me')
                                        if False and c["id"] in self.var_data["highPriority"]:
                                            self.model.Add(sum(arr) <= c_max)
                                            if c["min"] != 0:self.model.Add(sum(arr) >= c_min)
                                            counts_of_vars[c["id"]] += 1
                                        else:
                                            print('joomby')
                                            bol = self.model.NewBoolVar('y')
                                            inte = self.model.NewIntVar(0, 10000000000, 'snip1')
                                            self.model.Add( inte == 1).OnlyEnforceIf(bol)
                                            self.model.Add( inte == 0).OnlyEnforceIf(bol.Not())
                                            counts_of_vars[c["id"]] += 1
                                            self.constraint_bols.append(inte)
                                            self.model.Add(sum(arr) <= c_max).OnlyEnforceIf(bol)
                                            self.model.Add(sum(arr) >= c_min).OnlyEnforceIf(bol)

                            elif c['frequency'] == 'week':
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[user_c].id
                                    arr = list( map(lambda num: num[0],
                                            self.get_appointments([[user_c_id], [user_a_id]]).values()))
                                    if len(arr) == 0:
                                        continue
                                    if c["id"] in self.var_data["highPriority"]:
                                        self.model.Add(sum(arr)+weekly_data[user_a_id][user_c_id]//self.var_data["slot_length"] <= c_max)
                                        counts_of_vars[c["id"]] += 1
                                    else:
                                        bol = self.model.NewBoolVar('y')
                                        inte = self.model.NewIntVar(0, 10000000000, 'snip1')
                                        self.model.Add(inte == 1).OnlyEnforceIf(bol)
                                        self.model.Add(inte == 0).OnlyEnforceIf(bol.Not())
                                        counts_of_vars[c["id"]] += 1
                                        self.constraint_bols.append(inte)
                                        self.constraint_bols.append(bol)
                                        self.model.Add(sum(arr)+weekly_data[user_a_id][user_c_id]//self.var_data["slot_length"] <= c_max).OnlyEnforceIf(bol)
                                    
                        else:
                            if len(c['users_consequence']) == 0:
                                continue
                            user_cons = c['users_consequence']
                            if c['frequency'] == 'day':
                                for index, _ in enumerate(days_arrays):
                                    user_c_ids = [self.solutions1.resources1.resources[user_cc].id for user_cc in user_cons]
                                    arr = list( map(lambda num: num[0],
                                            self.get_appointments([user_c_ids, [user_a_id],[str(index)]]).values()))
                                    if len(arr) > 0:
                                        if c["id"] in self.var_data["highPriority"]:
                                            self.model.Add(sum(arr) <= c_max)
                                            if c["min"] != 0:
                                                self.model.Add(sum(arr) >= c_min)
                                            counts_of_vars[c["id"]] += 1
                                        else:
                                            bol = self.model.NewBoolVar('y')
                                            inte = self.model.NewIntVar( 0, 10000000000, 'snip1')
                                            self.model.Add(inte == 1).OnlyEnforceIf(bol)
                                            self.model.Add(inte == 0).OnlyEnforceIf( bol.Not())
                                            self.constraint_bols.append( inte)
                                            counts_of_vars[c["id"]] += 1
                                            self.model.Add(sum(arr) <= c_max).OnlyEnforceIf(bol)
                                            self.model.Add(sum(arr) >= c_min).OnlyEnforceIf(bol)
                            elif c['frequency'] == 'week':
                                user_c_id = self.solutions1.resources1.resources[user_c].id
                                arr = list( map(lambda num: num[0],
                                        self.get_appointments([[user_c_id],
                                                               [user_a_id],
                                                               [str(index)]
                                                               ]).values()))
                                if len(arr) == 0:
                                    continue
                                if c["id"] in self.var_data["highPriority"]:
                                    self.model.Add(bol == 1)
                                    self.model.Add(
                                        sum(arr) <= c['max'] * hour_slot_ratio)
                                    if c["min"] != 0:
                                        self.model.Add(
                                            sum(arr) >= c['min'] *
                                            hour_slot_ratio)
                                    counts_of_vars[c["id"]] += 1
                                bol = self.model.NewBoolVar('y')
                                inte = self.model.NewIntVar(
                                    0, 10000000000, 'snip1')

                                self.model.Add(inte == inte_vars[
                                    c["id"]]).OnlyEnforceIf(bol)
                                self.model.Add(inte == 0).OnlyEnforceIf(
                                    bol.Not())
                                self.constraint_bols.append(inte)

                                counts_of_vars[c["id"]] += 1
                                self.model.Add(
                                    sum(arr) <= c['max'] *
                                    hour_slot_ratio).OnlyEnforceIf(bol)
                                self.model.Add(
                                    sum(arr) >= c['min'] *
                                    hour_slot_ratio).OnlyEnforceIf(bol)
                elif c["type"] == "gaps":  # it should be "gaps"
                    if "gaps" in self.var_data["ignoredConstrainTypes"]:
                        print("bazo_ignore",True)
                        #continue
                    supervision_activity_id = "f39d479c-ea0f-4dcf-86e1-3e47c19328c7" # Hard coded
                    for user_a in c['users_antecedent']:
                        user_a_id = self.solutions1.resources1.resources[
                            user_a].id
                        for index, x in enumerate(days_arrays):
                            if c["each_or_all_users"] == 'each' or True:
                                if c_min == 0 and c_max == 0:
                                    # print("bazo_constraint_applied", user_a_id)
                                    val_gaps = self.get_appointments(
                                        [[user_a_id], [str(index)]])
                                    if len(val_gaps) == 0:
                                        # print("there_is_no_val : ", index,
                                        #       user_a_id)
                                        continue
                                    av_data = av_arr_for_fake[user_a_id][index]
                                    if [i[0] for i in av_data] == [] or [i[1] for i in av_data] == []:
                                        continue
                                    # print("bazo_av : ",av_data)
                                    clients_gaps_interval = []
                                    clients_gaps_duration = []
                                    durations = []
                                    for val_key,val_data in val_gaps.items():
                                        if not supervision_activity_id in val_key:
                                            durations.append(val_data[0])
                                    try:
                                        if len(av_data) > 1:
                                            fake_start_actual = min([i[0] for i in av_data])
                                            fake_end_actual = max([i[1] for i in av_data])
                                            count_gaps_fake = 3
                                            for i in find_gaps(av_data)["gap_intervals"]:
                                                fake_start = i[0]
                                                fake_end = i[1]
                                                fake_gaps_bool = self.model.NewBoolVar(f"fake_gaps_bool-{count_gaps_fake}")
                                                fake_gaps_start_int = self.model.NewIntVar(fake_start_actual, fake_end_actual,f"fake_gaps_start{count_gaps_fake}")
                                                fake_gaps_end_int = self.model.NewIntVar(fake_start_actual, fake_end_actual,f"fake_gaps_end{count_gaps_fake}")
                                                fake_gaps_duration_int = self.model.NewIntVar(0, fake_end_actual - fake_start_actual,f"dur{count_gaps_fake}")
                                                fake_interval = self.model.NewOptionalIntervalVar(fake_gaps_start_int,fake_gaps_duration_int, fake_gaps_end_int, fake_gaps_bool ,f"fake{count_gaps_fake}")

                                                self.model.Add(fake_gaps_duration_int > 0).OnlyEnforceIf(fake_gaps_bool)
                                                self.model.Add(fake_gaps_duration_int == 0).OnlyEnforceIf(fake_gaps_bool.Not())
                                                self.model.Add( fake_gaps_start_int <= fake_start)
                                                self.model.Add(fake_gaps_end_int >= fake_end)
                                                clients_gaps_interval.append(fake_interval)
                                                clients_gaps_duration.append(fake_gaps_duration_int)
                                                count_gaps_fake += 1
                                    except Exception as e:
                                        print("bazo_Error: ", e)
                                    fake_bol1 = self.model.NewBoolVar(f"fake1{user_a_id}")
                                    fake_bol2 = self.model.NewBoolVar( f"fake2{user_a_id}")
                                    if [i[0] for i in av_data] == [] or [i[1] for i in av_data] == []:
                                        continue
                                    fake_start = min([i[0] for i in av_data])
                                    fake_end = max([i[1] for i in av_data])
                                    gap_length = find_gaps(av_data)["gap_length"]
                                    fake_start_int_1 = self.model.NewIntVar(fake_start, fake_end, "fake_start")
                                    fake_end_int_1 = self.model.NewIntVar(fake_start, fake_end, "fake_end")
                                    fake_start_int_2 = self.model.NewIntVar(fake_start, fake_end, "fake_start2")
                                    fake_end_int_2 = self.model.NewIntVar(fake_start, fake_end, "fake_end2")

                                    fake_duration_int_1 = self.model.NewIntVar(
                                        0, fake_end - fake_start, "dur1")
                                    fake_duration_int_2 = self.model.NewIntVar(
                                        0, fake_end - fake_start, "dur2")

                                    fake1 = self.model.NewOptionalIntervalVar(
                                        fake_start_int_1, fake_duration_int_1,
                                        fake_end_int_1, fake_bol1, "fake1")
                                    fake2 = self.model.NewOptionalIntervalVar(
                                        fake_start_int_2, fake_duration_int_2,
                                        fake_end_int_2, fake_bol2, "fake2")

                                    self.fake_whites[user_a_id] = [
                                        fake1, fake2
                                    ] + clients_gaps_interval
                                    self.model.Add(fake_duration_int_1 > 0).OnlyEnforceIf(fake_bol1)
                                    self.model.Add(fake_duration_int_1 == 0).OnlyEnforceIf(fake_bol1.Not())
                                    self.model.Add(fake_duration_int_2 > 0).OnlyEnforceIf(fake_bol2)
                                    self.model.Add(fake_duration_int_2 == 0).OnlyEnforceIf(fake_bol2.Not())
                                    # fake_int_adam = self.model.NewIntVar(0,10000,"fake_int_for_adam")
                                    # self.fake_gap_durations.append(fake_int_adam)
                                    self.model.Add(fake_start_int_1 == fake_start)
                                    self.model.Add(fake_end_int_2 == fake_end)
                                    #int_sum = self.model.NewIntVar(0,10000,'d')
                                    self.model.Add(sum(durations) + fake_duration_int_1 +fake_duration_int_2 + sum(clients_gaps_duration) == fake_end - fake_start - c_max)
                                    #self.gaps_to_minimize.append(int_sum)
                                    if len(clients_gaps_duration) > 0:
                                        self.model.Add(sum(clients_gaps_duration) >= gap_length)
                                    if user_a_id in self.individual_fake_boolean.keys():
                                        self.individual_fake_boolean[user_a_id] += [fake_bol2, fake_bol1]
                                    else:
                                        self.individual_fake_boolean[user_a_id] = [fake_bol2, fake_bol1]
                                    # if user_a_id in self.fake_whites.keys():
                                    #     self.fake_whites[user_a_id] += [
                                    #         fake1, fake2
                                    #     ]
                                    # else:
                                    #     self.fake_whites[user_a_id] = [
                                    #         fake1, fake2
                                    #     ]

                                else:
                                    # print("this_bazo_gap")
                                    gaps_ids_arr.append(user_a_id)
                                    max_gap = c_max
                                    val_gaps = self.get_appointments(
                                        [[user_a_id], [str(index)]])
                                    if len(val_gaps) == 0:
                                        continue
                                    # print("bazo_it_is_working : ", c["max"],
                                    #       user_a_id, max_gap)
                                    var_dict_bools = {}
                                    var_dict_starts = {}
                                    var_dict_ends = {}
                                    var_dict_durations = {}
                                    var_dict_intervals = {}
                                    av_data = av_arr_for_fake[user_a_id][index]
                                    if [i[0] for i in av_data] == []:
                                        continue
                                    fake_start = min([i[0] for i in av_data])
                                    fake_end = max([i[1] for i in av_data])
                                    durations = list(
                                        map(lambda x: x[0], val_gaps.values()))
                                    for n in range(
                                            4):  # fake variables defined
                                        var_dict_bools[
                                            f"fake_bool-{n}-{user_a_id}"] = self.model.NewBoolVar(
                                                f"fake_bool-{n}-{user_a_id}")
                                        var_dict_starts[
                                            f"fake_start-{n}-{user_a_id}"] = self.model.NewIntVar(
                                                fake_start, fake_end,
                                                f"fake_start-{n}-{user_a_id}")
                                        var_dict_ends[
                                            f"fake_end-{n}-{user_a_id}"] = self.model.NewIntVar(
                                                fake_start, fake_end,
                                                f"fake_end-{n}-{user_a_id}")
                                        var_dict_durations[
                                            f"fake_dur-{n}-{user_a_id}"] = self.model.NewIntVar(
                                                0, fake_end - fake_start,
                                                f"fake_dur-{n}-{user_a_id}")
                                        var_dict_intervals[
                                            f"fake_interval-{n}-{user_a_id}"] = self.model.NewOptionalIntervalVar(
                                                var_dict_starts[
                                                    f"fake_start-{n}-{user_a_id}"],
                                                var_dict_durations[
                                                    f"fake_dur-{n}-{user_a_id}"],
                                                var_dict_ends[
                                                    f"fake_end-{n}-{user_a_id}"],
                                                var_dict_bools[
                                                    f"fake_bool-{n}-{user_a_id}"],
                                                f"fake_interval-{n}-{user_a_id}"
                                        )
                                    self.model.Add(
                                        fake_start == var_dict_starts[
                                            f"fake_start-{0}-{user_a_id}"])
                                    self.model.Add(fake_end == var_dict_ends[
                                        f"fake_end-{1}-{user_a_id}"])
                                    # print("bazo_dur : ",
                                    #       var_dict_durations.values())
                                    self.model.Add(
                                        sum(list(var_dict_durations.values()))
                                        + sum(durations) == fake_end -
                                        fake_start)
                                    for n in range(4):
                                        self.model.Add(
                                            var_dict_durations[
                                                f"fake_dur-{n}-{user_a_id}"] >
                                            0).OnlyEnforceIf(var_dict_bools[
                                                f"fake_bool-{n}-{user_a_id}"])
                                        self.model.Add(
                                            var_dict_durations[
                                                f"fake_dur-{n}-{user_a_id}"] ==
                                            0).OnlyEnforceIf(var_dict_bools[
                                                f"fake_bool-{n}-{user_a_id}"].
                                            Not())
                                    self.model.Add(
                                        var_dict_durations[
                                            f"fake_dur-{2}-{user_a_id}"] +
                                        var_dict_durations[
                                            f"fake_dur-{3}-{user_a_id}"] <=
                                        max_gap)
                                    self.model.Add(
                                        var_dict_starts[
                                            f"fake_start-{3}-{user_a_id}"] >=
                                        var_dict_ends[
                                            f"fake_end-{2}-{user_a_id}"])
                                    # ********************************
                                    # try:
                                    #     for some_break_id in self.var_data[
                                    #             "notWorking"]:
                                    #         break_val2 = self.get_appointments(
                                    #             [[user_a_id], [some_break_id],
                                    #              [str(index)]])
                                    #         # print("bazo_nope :", break_val2)
                                    #         if len(break_val2) > 0:
                                    #             for break_data2 in list(
                                    #                     map(
                                    #                         lambda x: x,
                                    #                         break_val2.values(
                                    #                         ))):
                                    #                 # self.model.Add(break_data2[0])
                                    #                 # print(
                                    #                 #     "ok_bazo : ",
                                    #                 #     break_data2[4],
                                    #                 #     break_data2[3])
                                    #                 self.model.Add(
                                    #                     var_dict_starts[
                                    #                         f"fake_start-{1}-{user_a_id}"]
                                    #                     > break_data2[4])
                                    #                 self.model.Add(var_dict_ends[
                                    #                     f"fake_end-{0}-{user_a_id}"]
                                    #                                <
                                    #                                break_data2[
                                    #                                    3])
                                    # except Exception as e:
                                    #     print("bazo_not_found : ", e)
                                    # ********************************
                                    # self.model.Add(
                                    #     var_dict_starts[
                                    #         f"fake_start-{3}-{user_a_id}"] -
                                    #     var_dict_ends[
                                    #         f"fake_end-{2}-{user_a_id}"] <=
                                    #     (4 * 60) //
                                    #     self.var_data["slot_length"])
                                    # self.model.Add(
                                    #     var_dict_starts[
                                    #         f"fake_start-{2}-{user_a_id}"] -
                                    #     var_dict_ends[
                                    #         f"fake_end-{0}-{user_a_id}"] <=
                                    #     (4 * 60) //
                                    #     self.var_data["slot_length"])
                                    # self.model.Add(
                                    #     var_dict_starts[
                                    #         f"fake_start-{1}-{user_a_id}"] -
                                    #     var_dict_ends[
                                    #         f"fake_end-{3}-{user_a_id}"] <=
                                    #     (4 * 60) //
                                    #     self.var_data["slot_length"])
                                    if user_a_id in self.fake_whites.keys():
                                        self.fake_whites[user_a_id] += list(
                                            var_dict_intervals.values())
                                    else:
                                        self.fake_whites[user_a_id] = list(
                                            var_dict_intervals.values())
                                    pass
                            else:
                                pass
                
                elif c["type"] == "authorization":
                    print("authorization_c : ",c)
                    # Data manipulation part
                    weekly_events_filtered = {}
                    poss_hours = {}
                   
                    user_anti_arr = [self.solutions1.resources1.resources[user_a].id for user_a in c['users_antecedent']]
                    user_cons_arr = [self.solutions1.resources1.resources[user_c].id for user_c in c['users_consequence']]
                    for d in range(7):
                        poss_hours[d] = {}
                    for d in range(7):
                        for u in user_anti_arr:
                            poss_hours[d][u] = 0
                    print("macaron  : ",self.var_data["weekdays_av_data"])
                    for u in user_anti_arr:
                        for d in range(7):
                            if d in self.var_data["weekdays_av_data"].keys():
                                if u in self.var_data["weekdays_av_data"][d].keys():
                                    poss_hours[d][u] += self.var_data["weekdays_av_data"][d][u]
                    print("macaron2  : ",poss_hours)
                                
                    for ev in self.var_data["auth_week"][0]:
                        if len(intersection(ev["resourceIds"],user_anti_arr))>0 and len(intersection(ev["resourceIds"],user_cons_arr))>0:
                            print("why777 : ",calculate_duration_hours({"start":ev["start"],"end":ev["end"]}))
                            total_hours,weekday_index = calculate_duration_hours({"start":ev["start"],"end":ev["end"]})
                            print("total_hours_why  :" ,total_hours,weekday_index)
                            for x in intersection(ev["resourceIds"],user_anti_arr):
                                poss_hours[weekday_index][x] -= total_hours
                    print("macaron3  : ",poss_hours)
                    
                    for u in user_anti_arr:
                        sum_hours = 0
                        for d in range(7):
                            if u in poss_hours[d].keys():
                                sum_hours += poss_hours[d][u]
                        print("bazo_bugssss : ",sum_hours,poss_hours[4][u])
                        for d in range(7):
                            if u in poss_hours[d].keys():
                                if sum_hours == 0:
                                    poss_hours[d][u] = 0
                                else:
                                    poss_hours[d][u] = poss_hours[d][u] / sum_hours
                                    print("macaron5",poss_hours[d][u])

                    print("bazz_anti : ",user_anti_arr,poss_hours)
                    # Data manipulation part
                    
                    try:
                        
                        
                        total_weekly_activity = 0
                        arr_act_loc = []
                        if not c["antecedentTypeActivityId"] is None:
                            arr_act_loc.append(c["antecedentTypeActivityId"])
                        # if not c["antecedentLocationId"] is None:
                        #     arr_act_loc.append(c["antecedentLocationId"])
                        for d in range(7):
                            for user_a in c["users_antecedent"]:
                                user_a_id = self.solutions1.resources1.resources[user_a].id
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[user_c].id
                                    val_auth = self.get_appointments([[user_c_id],[user_a_id],str(d)])
                                    if d in poss_hours.keys():
                                        if user_a_id in poss_hours[d].keys():
                                            max_poss = int(c["maxSeconds"]*poss_hours[d][user_a_id]/60/self.var_data["slot_length"])
                                            sum_val = sum(map(lambda x: x[0],val_auth.values()))
                                            self.model.Add(sum_val <= max_poss)
                                            print("applied_auth_bazo",max_poss,c_max,poss_hours[d][user_a_id])
                                
                    
                    except Exception as e:
                        print("Exception at Authorization Constraint : ",e)
                        traceback.print_exc()
                        
                    pass
                elif c["type"] == "sessionlength":
                    try:
                        for user_a in c['users_antecedent']:

                            user_a_id = self.solutions1.resources1.resources[
                                user_a].id
                            for index, x in enumerate(days_arrays):
                                # print("bazo_today_index",self.var_data["today_index"])
                                if index == self.var_data['today_index'] or True:
                                    for user_c in c['users_consequence']:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        val = self.get_appointments([[user_c_id],
                                                                    [user_a_id],
                                                                    [str(index)]])
                                        if len(val) == 0:
                                            continue
                                        durations = list(
                                            map(lambda num: num, val.values()))
                                        for dur in durations:
                                            c_min2 = None
                                            if dur[-2]:
                                                c_min2 = dur[-1]
                                            if c_min2 is None:
                                                c_min2 = c_min  
                                            if c["id"] in self.var_data["highPriority"]:
                                                if dur[9] in self.events_break_session_length_long.keys():
                                                    self.model.Add(dur[0] <= self.events_break_session_length_long[dur[9]])
                                                else:
                                                    self.model.Add(dur[0] <= c_max)
                                                # print("bazo_session_length: ",c_max,c_min2,str(index))
                                                if c_min != 0:

                                                    inc = 1
                                                    
                                                    if dur[9] in self.events_break_session_length_short.keys():
                                                        c_min2 = self.events_break_session_length_short[dur[9]]
                                                    while inc < c_min2:
                                                        self.model.Add(dur[0] != inc)
                                                        inc += 1
                                        # durations = list(
                                        #     map(lambda num: num[0] if not num[-2] else None, val.values()))
                                        # for dur in durations:
                                        #     if dur is None:
                                        #         continue
                                        #     if c["id"] in self.var_data["highPriority"]:
                                        #         self.model.Add(dur <= c_max)
                                        #         print("bazo_session_length: ",c_max,c_min,str(index))
                                        #         if c_min != 0:

                                        #             inc = 1
                                                    
                                        #             while inc < c_min:
                                        #                 self.model.Add(dur != inc)
                                        #                 inc += 1
                                        #         counts_of_vars[c["id"]] += 1
                    except Exception as e:
                        print("bazo_session_leng_error : ",e)
                        traceback.print_exc()
                elif c["type"] == "backToBack":
                    people_type = self.find_ids_by_role(['Person'])
                    activity_type = self.find_ids_by_role(['Activity'])
                    print("people_type_bazo  : ",people_type)
                    print("activity_type_bazo : ",activity_type)
                    is_person_and_activity = False
                    all_user_anti = []
                    all_user_cons = []
                    for user_a in c["users_antecedent"]:
                        user_a_id = self.solutions1.resources1.resources[user_a].id
                        all_user_anti.append(user_a_id)
                    for user_c in c['users_consequence']:
                                user_c_id = self.solutions1.resources1.resources[user_c].id
                                all_user_cons.append(user_c_id)
                    if len(intersection(all_user_anti,people_type)) > 0 or len(intersection(all_user_cons,people_type)) > 0:
                        is_person_and_activity = True
                    if is_person_and_activity:
                        print("bazo_bact_to_back_type : Person-Activity")
                        for user_a in c["users_antecedent"]:
                            user_a_id = self.solutions1.resources1.resources[user_a].id
                            for index in range(1, 6):
                                some_array = {}
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[user_c].id
                                    val_back_to_back = self.get_appointments([[user_c_id], [user_a_id], [str(index)]])
                                    some_array.update(val_back_to_back)
                                len_back = len(some_array)
                                back_to_back_values = list(some_array.values())
                                for i1 in range(len_back):
                                    for i2 in range(i1 + 1, len_back):
                                        # target1 = self.model.NewIntVar(0,10000,f"target1-{user_a}-{user_c}-{i1}")
                                        # target2 = self.model.NewIntVar(0,10000,f"target2-{user_a}-{user_c}-{i1}")
                                        # self.model.AddAbsEquality(target1, back_to_back_values[i1][3] - back_to_back_values[i2][4])
                                        # self.model.AddAbsEquality(target2,back_to_back_values[i1][4] - back_to_back_values[i2][3])
                                        # self.model.Add(target1 >= 60//self.var_data["slot_length"])
                                        # self.model.Add(target2 >= 60//self.var_data["slot_length"])
                                        bool_left = self.model.NewBoolVar(f"left")
                                        self.model.Add(back_to_back_values[i1][4]<=back_to_back_values[i2][3]).OnlyEnforceIf(bool_left)
                                        self.model.Add(back_to_back_values[i2][4]<= back_to_back_values[i1][3]).OnlyEnforceIf(bool_left.Not())
                                        # self.model.Add(back_to_back_values[i2][3]- back_to_back_values[i1][4] >= 60//self.var_data["slot_length"]).OnlyEnforceIf(bool_left)
                                        # self.model.Add(back_to_back_values[i1][3]- back_to_back_values[i2][4] >= 60//self.var_data["slot_length"]).OnlyEnforceIf(bool_left.Not())
                                        self.model.Add(back_to_back_values[i2][3]- back_to_back_values[i1][4] >= 150//self.var_data["slot_length"]).OnlyEnforceIf(bool_left)
                                        self.model.Add(back_to_back_values[i1][3]- back_to_back_values[i2][4] >= 150//self.var_data["slot_length"]).OnlyEnforceIf(bool_left.Not())
                                        self.model.Add(back_to_back_values[i2][3]- back_to_back_values[i1][4] <= 240//self.var_data["slot_length"]).OnlyEnforceIf(bool_left)
                                        self.model.Add(back_to_back_values[i1][3]- back_to_back_values[i2][4] <= 240//self.var_data["slot_length"]).OnlyEnforceIf(bool_left.Not())
                    else:
                        print("bazo_back_to_back_type : Activity-Activity")
                        for index in range(1, 6):
                            some_array_anti = []
                            some_array_cons = []
                            for user_a in c["users_antecedent"]:
                                user_a_id = self.solutions1.resources1.resources[user_a].id
                                val_back_to_back_anti = self.get_appointments([[user_a_id], [str(index)]])
                                some_array_anti = some_array_anti + list(val_back_to_back_anti.values())
                            for user_c in c['users_consequence']:
                                user_c_id = self.solutions1.resources1.resources[user_c].id
                                val_back_to_back_cons = self.get_appointments([[user_c_id], [str(index)]])
                                some_array_cons = some_array_cons + list(val_back_to_back_cons.values())
                            for i1 in some_array_anti:
                                inc = 0
                                for i2 in some_array_cons:
                                    # target1 = self.model.NewIntVar(0,10000,f"target1-{user_a}-{user_c}-{inc}")
                                    # target2 = self.model.NewIntVar(0,10000,f"target2-{user_a}-{user_c}-{inc}")
                                    # self.model.AddAbsEquality(target1, i1[3] - i2[4])
                                    # self.model.AddAbsEquality(target2,i1[4] - i2[3])
                                    # self.model.Add(target1 >= 60//self.var_data["slot_length"])
                                    # self.model.Add(target2 >= 60//self.var_data["slot_length"])
                                    bool_left = self.model.NewBoolVar(f"left")
                                    self.model.Add(i1[3]<=i2[3]).OnlyEnforceIf(bool_left)
                                    self.model.Add(i2[3]<i1[3]).OnlyEnforceIf(bool_left.Not())
                                    self.model.Add(i2[3]-i1[4] >= 60//self.var_data["slot_length"]).OnlyEnforceIf(bool_left)
                                    self.model.Add(i1[3]-i2[4] >= 60//self.var_data["slot_length"]).OnlyEnforceIf(bool_left.Not())
                                    
                                    self.model.Add(i2[3]-i1[4] <= 240//self.var_data["slot_length"]).OnlyEnforceIf(bool_left)
                                    self.model.Add(i1[3]-i2[4] <= 240//self.var_data["slot_length"]).OnlyEnforceIf(bool_left.Not())
                elif c["type"] == "breakQuantity":
                    print('soomer4',self.resources1.slots)
                    for user_a in c["users_antecedent"]:
                        user_a_id = self.solutions1.resources1.resources[
                            user_a].id
                        for index in range(1, 6):
                            for user_c in c['users_consequence']:
                                # print("bazo_bug_again : ", user_a_id, user_c)
                                user_c_id = self.solutions1.resources1.resources[
                                    user_c].id
                                # print("bazo_bug_again2 : ", user_a_id,
                                #       user_c_id)
                                work_ids = [
                                    i
                                    for i in self.var_data["objectiveactivity"]
                                    if i not in self.var_data["notWorking"]
                                ]
                                therapy_val = self.get_appointments(
                                    [[user_a_id], [str(index)],
                                     self.var_data["objectiveactivity"]])
                                working = self.get_appointments([[user_a_id],
                                                                 [str(index)],
                                                                 work_ids])
                                # print("goofyyy", therapy_val)
                                break_val = self.get_appointments(
                                    [[user_a_id], [user_c_id], [str(index)]])
                                print('soomer3',len(break_val),break_val)
                                # print("voofyyy", break_val)
                                if len(break_val) == 0 or len(
                                        therapy_val) == 0:
                                    continue
                                # print("bazo_bug_break : ", therapy_val,
                                #       break_val)
                                bol_break = sum(
                                    map(lambda num: num[6],
                                        break_val.values()))
                                # print("bazo_ok0")
                                self.model.Add(bol_break <= int(c["min"]))
                                # self.model.Add(bol_break <= 1)
                                dur_therapy = sum(
                                    map(lambda num: num[0],
                                        therapy_val.values()))
                                dur_working = sum(
                                    map(lambda num: num[0], working.values()))

                                if len(break_val) > 0:
                                    ii = 0
                                    all_lunches_bol = []
                                    i_break_count = 0
                                    num_scheduled = [0]+[1 for break_d in list(map(lambda num: num,break_val.values())) if break_d[5]]
                                    sum_scheduled = sum(num_scheduled)
                                    for break_d in list(map(lambda num: num,break_val.values())):
                                        if not break_d[5] and sum_scheduled >= 1:
                                            self.model.Add(break_d[6] == 0)
                                            print('bazo_something')
                                            continue
                                        break_exists = self.model.NewBoolVar(f'break_exists-{i_break_count}')
                                        i_break_count += 1
                                        # self.model.Add(dur_working >= c_max).OnlyEnforceIf(break_exists)
                                        self.model.Add(break_d[0] > 0).OnlyEnforceIf(break_exists)
                                        self.model.Add(break_d[0] == 0).OnlyEnforceIf(break_exists.Not())
                                        # self.model.Add(dur_working < c_max).OnlyEnforceIf(break_exists.Not())
                                        # print("bazo_break_count : ",i_break_count,sum_scheduled)
                                        all_lunches_bol.append(break_exists)
                                    final_lunch_bol = self.model.NewBoolVar("final_lunch_bol")
                                    self.model.Add(dur_working >= c_max).OnlyEnforceIf(final_lunch_bol)
                                    self.model.Add(dur_working < c_max).OnlyEnforceIf(final_lunch_bol.Not())
                                    self.model.Add(sum(all_lunches_bol) == 1).OnlyEnforceIf(final_lunch_bol)
                                    self.model.Add(sum(all_lunches_bol) == 0).OnlyEnforceIf(final_lunch_bol.Not())
                                    print('breakquantity_bazo',len(break_d),len(all_lunches_bol),user_a_id,user_c_id)
                                    
                            
                                    # print("bazo_break_val: ", break_val)
                                    # ii = 0
                                    # print("holly : ", list(
                                    #     map(lambda num: num,
                                    #         break_val.values())))
                                    # for break_data in list(
                                    #         map(lambda num: num,
                                    #             break_val.values())):
                                    #     if not break_data[5] and sum_scheduled >= 1:
                                    #         self.model.Add(break_data[6] == 0)
                                    #         continue
                                    #     exist_bool = self.model.NewBoolVar(
                                    #         'exist_bool')
                                    #     print(
                                    #         f"bazo_break-{ii} : ", ii,sum_scheduled)
                                    #     if not user_a_id in gaps_ids_arr:
                                    #         # print("error_found_break : ",
                                    #         #       user_a_id)
                                    #         av_data = av_arr_for_fake[
                                    #             user_a_id][index]
                                    #         if [i[0] for i in av_data] == [] or [i[1] for i in av_data] == []:
                                    #             continue
                                    #         fake_start = min(
                                    #             [i[0] for i in av_data])
                                    #         fake_end = max(
                                    #             [i[1] for i in av_data])
                                    #         bool_arr = [
                                    #             self.model.NewBoolVar(
                                    #                 f"fake_break_bool-{i}")
                                    #             for i in range(2)
                                    #         ]
                                    #         start_arr = [
                                    #             self.model.NewIntVar(
                                    #                 fake_start, fake_end,
                                    #                 f"fake_start_var-{i}")
                                    #             for i in range(2)
                                    #         ]
                                    #         end_arr = [
                                    #             self.model.NewIntVar(
                                    #                 fake_start, fake_end,
                                    #                 f"fake_end_var-{i}")
                                    #             for i in range(2)
                                    #         ]
                                    #         dur_arr = [
                                    #             self.model.NewIntVar(
                                    #                 0, fake_end - fake_start,
                                    #                 f"fake_dur_var-{i}")
                                    #             for i in range(2)
                                    #         ]
                                    #         interval_arr = [
                                    #             self.model.
                                    #             NewOptionalIntervalVar(
                                    #                 start_arr[i], dur_arr[i],
                                    #                 end_arr[i], bool_arr[i],
                                    #                 f"fake_interval_var-{i}")
                                    #             for i in range(2)
                                    #         ]
                                    #         for i in range(2):
                                    #             self.model.Add(dur_arr[i] > 0
                                    #                            ).OnlyEnforceIf(
                                    #                                bool_arr[i])
                                    #             self.model.Add(
                                    #                 dur_arr[i] ==
                                    #                 0).OnlyEnforceIf(
                                    #                     bool_arr[i].Not())
                                    #         self.model.Add(
                                    #             start_arr[0] == fake_start)
                                    #         self.model.Add(
                                    #             end_arr[1] == fake_end)
                                    #         self.model.Add(
                                    #             break_data[4] -
                                    #             fake_start < dur_therapy +
                                    #             dur_arr[0]).OnlyEnforceIf(
                                    #                 exist_bool)
                                    #         self.model.Add(
                                    #             fake_end -
                                    #             break_data[3] < dur_therapy +
                                    #             dur_arr[1]).OnlyEnforceIf(
                                    #                 exist_bool)
                                    #         if user_a_id in self.fake_whites.keys(
                                    #         ):
                                    #             self.fake_whites[
                                    #                 user_a_id] += interval_arr
                                    #         else:
                                    #             self.fake_whites[
                                    #                 user_a_id] = interval_arr

                                    #     # bool1 = self.model.NewBoolVar(
                                    #     #     f"bool1{ii}")
                                    #     # bool2 = self.model.NewBoolVar(
                                    #     #     f"bool2{ii}")
                                    #     # self.model.Add(
                                    #     #     sum(gen_arr[ii]["left"]) > 0
                                    #     # ).OnlyEnforceIf(bool1)
                                    #     # self.model.Add(
                                    #     #     sum(gen_arr[ii]["left"]) ==
                                    #     #     0).OnlyEnforceIf(bool1.Not())
                                    #     # self.model.Add(
                                    #     #     sum(gen_arr[ii]["right"]) > 0
                                    #     # ).OnlyEnforceIf(bool2)
                                    #     # self.model.Add(
                                    #     #     sum(gen_arr[ii]["right"]) ==
                                    #     #     0).OnlyEnforceIf(bool2.Not())

                                    #     # xy = self.model.NewBoolVar('hello')

                                    #     # **
                                    #     self.model.Add(
                                    #         break_data[0] > 0).OnlyEnforceIf(
                                    #             exist_bool)
                                    #     self.model.Add(
                                    #         break_data[0] == 0).OnlyEnforceIf(
                                    #             exist_bool.Not())
                                    #     self.model.Add(
                                    #         dur_working >= int(c_max)
                                    #     ).OnlyEnforceIf(exist_bool)

                                    #     self.model.Add(dur_working < int(c_max)
                                    #                    ).OnlyEnforceIf(
                                    #                        exist_bool.Not())
                                    #     # xy_arr.append(xy)
                                    #     ii += 1
                elif c['type'] == 'session':
                    # print("bazo_custom_type_session")
                    for user_a in c['users_antecedent']:
                        user_a_id = self.solutions1.resources1.resources[
                            user_a].id
                        if c['frequency'] == 'day':
                            # print("bazo_custom_frequency_day")
                            for index, x in enumerate(days_arrays) or True:
                                if index != 0:
                                    if c["each_or_all_users"] == 'each':
                                        # print("bazo_custom_frequency_each")
                                        for user_c in c['users_consequence']:
                                            arr = []
                                            user_c_id = self.solutions1.resources1.resources[
                                                user_c].id
                                            arr = list(
                                                map(
                                                    lambda num: num[6],
                                                    self.get_appointments(
                                                        [[user_c_id],
                                                         [user_a_id],
                                                         [str(index)]]).values()))
                                            if len(arr) == 0:
                                                continue
                                            # if user_a_id in self.resources1.resources.keys(
                                            # ) and user_c_id in self.resources1.resources[
                                            #         user_a_id].matches2_durations.keys(
                                            #         ):
                                            #     int_duration = self.resources1.resources[
                                            #         user_a_id].matches2_sessions[
                                            #             user_c_id][index - 1]
                                            #     arr.append(int_duration)
                                            bol = self.model.NewBoolVar('y')
                                            inte = self.model.NewIntVar(
                                                0, 10000000000, 'snip1')

                                            self.model.Add(inte == inte_vars[
                                                c["id"]]).OnlyEnforceIf(bol)
                                            self.model.Add(
                                                inte == 0).OnlyEnforceIf(
                                                    bol.Not())
                                            self.constraint_bols.append(inte)
                                            counts_of_vars[c["id"]] += 1
                                            self.model.Add(
                                                sum(arr) <= c['max']
                                            ).OnlyEnforceIf(bol)
                                            self.model.Add(
                                                sum(arr) >= c['min']
                                            ).OnlyEnforceIf(bol)
                                            if c["id"] in self.var_data[
                                                    "highPriority"]:
                                                self.model.Add(bol == 1)
                                    else:
                                        # print("bazo_custom_frequency_all")
                                        arr = []
                                        for user_c in c['users_consequence']:
                                            user_c_id = self.solutions1.resources1.resources[
                                                user_c].id
                                            val = self.get_appointments(
                                                [[user_c_id], [user_a_id],
                                                 [str(index)]])
                                            if len(val) == 0:
                                                continue
                                            arr = arr + list(
                                                map(lambda num: num[0],
                                                    val.values()))
                                        if len(arr) == 0:
                                            continue
                                        # if user_a_id in self.resources1.resources.keys(
                                        # ) and user_c_id in self.resources1.resources[
                                        #         user_a_id].matches2_sessions.keys(
                                        #         ):
                                        #     int_duration = self.resources1.resources[
                                        #         user_a_id].matches2_sessions[
                                        #             user_c_id][index - 1]
                                        #     arr.append(int_duration)
                                        bol = self.model.NewBoolVar('y')
                                        inte = self.model.NewIntVar(
                                            0, 10000000000, 'snip1')

                                        self.model.Add(inte == inte_vars[
                                            c["id"]]).OnlyEnforceIf(bol)
                                        self.model.Add(
                                            inte == 0).OnlyEnforceIf(bol.Not())
                                        self.constraint_bols.append(inte)
                                        counts_of_vars[c["id"]] += 1
                                        self.model.Add(sum(arr) <= c['max']
                                                       ).OnlyEnforceIf(bol)
                                        self.model.Add(sum(arr) >= c['min']
                                                       ).OnlyEnforceIf(bol)
                                        if c["id"] in self.var_data["highPriority"]:
                                            self.model.Add(bol == 1)

                        elif c['frequency'] == 'week':
                            # print("bazo_custom_frequency_week")
                            if c["each_or_all_users"] == 'each':
                                # print("bazo_custom_frequency_each")
                                for user_c in c['users_consequence']:
                                    arr = []
                                    for index, x in enumerate(days_arrays):
                                        if index != 0:
                                            user_c_id = self.solutions1.resources1.resources[
                                                user_c].id
                                            val = self.get_appointments(
                                                [[user_c_id], [user_a_id],
                                                 [index]])
                                            if len(val) == 0:
                                                continue
                                            arr = arr + list(
                                                map(lambda num: num[0],
                                                    val.values()))
                                            # if user_a_id in self.resources1.resources.keys(
                                            # ) and user_c_id in self.resources1.resources[
                                            #         user_a_id].matches2_durations.keys(
                                            #         ):
                                            #     int_duration = self.resources1.resources[
                                            #         user_a_id].matches2_sessions[
                                            #             user_c_id][index - 1]
                                            #     arr.append(int_duration)
                                    if len(arr) == 0:
                                        continue
                                    if c["id"] in self.var_data["hard"]:
                                        self.model.Add(sum(arr) <= c['max'])
                                        if c["min"] != 0:
                                            self.model.Add(
                                                sum(arr) >= c['min'])
                                        counts_of_vars[c["id"]] += 1
                                    else:
                                        bol = self.model.NewBoolVar('y')
                                        inte = self.model.NewIntVar(
                                            0, 10000000000, 'snip1')

                                        self.model.Add(inte == inte_vars[
                                            c["id"]]).OnlyEnforceIf(bol)
                                        self.model.Add(
                                            inte == 0).OnlyEnforceIf(bol.Not())
                                        self.constraint_bols.append(inte)
                                        counts_of_vars[c["id"]] += 1
                                        self.model.Add(sum(arr) <= c['max']
                                                       ).OnlyEnforceIf(bol)
                                        self.model.Add(sum(arr) >= c['min']
                                                       ).OnlyEnforceIf(bol)

                            else:
                                # print("bazo_custom_frequency_all")
                                arr = []
                                for user_c in c['users_consequence']:
                                    for index, x in enumerate(days_arrays):
                                        if index != 0:
                                            user_c_id = self.solutions1.resources1.resources[
                                                user_c].id
                                            val = self.get_appointments(
                                                [[user_c_id], [user_a_id],
                                                 [index]])
                                            if len(val) == 0:
                                                continue
                                            arr = arr + list(
                                                map(lambda num: num[0],
                                                    val.values()))
                                            # if user_a_id in self.resources1.resources.keys(
                                            # ) and user_c_id in self.resources1.resources[
                                            #         user_a_id].matches2_durations.keys(
                                            #         ):
                                            #     int_duration = self.resources1.resources[
                                            #         user_a_id].matches2_sessions[
                                            #             user_c_id][index - 1]
                                            #     arr.append(int_duration)
                                if len(arr) == 0:
                                    continue
                                if c["id"] in self.var_data["hard"]:
                                    self.model.Add(sum(arr) <= c['max'])
                                    if c["min"] != 0:
                                        self.model.Add(sum(arr) >= c['min'])
                                    counts_of_vars[c["id"]] += 1
                                else:
                                    bol = self.model.NewBoolVar('y')
                                    inte = self.model.NewIntVar(
                                        0, 10000000000, 'snip1')

                                    self.model.Add(inte == inte_vars[
                                        c["id"]]).OnlyEnforceIf(bol)
                                    self.model.Add(inte == 0).OnlyEnforceIf(
                                        bol.Not())
                                    self.constraint_bols.append(inte)
                                    counts_of_vars[c["id"]] += 1
                                    self.model.Add(sum(arr) <= c['max']
                                                   ).OnlyEnforceIf(bol)
                                    self.model.Add(sum(arr) >= c['min']
                                                   ).OnlyEnforceIf(bol)

            for k, v in counts_of_vars.items():
                if v == 0:
                    counts_of_vars[k] = 1
            for k,v in inte_vars.items():
                self.model.Add(v == 1)
            # return_of_optimal_weights = optimal_weights(
            #     counts_of_vars, rank_of_vars, pair_vars)
            # # print("my_matches_bazo : ", counts_of_vars, rank_of_vars,
            # #       pair_vars)
            # # print("my_matches_bazo_return : ", return_of_optimal_weights)
            # for k, v in return_of_optimal_weights.items():
            #     if k != "max_total_durations" and k not in self.var_data[
            #             "hard"]:
            #         self.model.Add(inte_vars[k] == v)
            #     if k in self.var_data["hard"]:
            #         self.model.Add(inte_vars[k] == 1)

    def part2_strategy(self):
        dict_av = {}
        temple_id = "090725f4-978d-41a2-82ed-e2ffa8711fb9"
        # for res, av_arr in self.solutions1.user_availabilities_general.items():
        if True:
            res = temple_id
            av_arr = self.solutions1.user_availabilities_general[res]

            for arr in self.resources1.resources[res].events_notScheduled:
                [tup, event] = arr
                ortool_arr = []
                for av in av_arr:
                    [start, end] = list(av)
                    start = 164
                    end = 168
                    # bol = False
                    bol = True
                    # for res2 in tup:
                    #     if res2 != res and res2 in self.solutions1.user_availabilities_general.keys():
                    #         for av2 in self.solutions1.user_availabilities_general[res2]:
                    #             [start2, end2] = list(av2)
                    #             if start2 <= start and end2 >= end:
                    #                 print('gylopi', start2, start,
                    #                       end2, end, res, res2)
                    #                 bol = True
                    if bol:
                        # print('smother', tup)
                        bol1 = self.model.NewBoolVar("bol1")
                        ortool_arr.append(bol1)
                        self.constraint_bols.append(bol1)
                        bol2 = self.model.NewBoolVar("bol2")
                        bol3 = self.model.NewBoolVar("bol3")
                        bol4 = self.model.NewBoolVar("bol4")
                        event_start = event[3]
                        event_end = event[4]
                        event_duration = event[0]
                        # print('looly1', event_duration, start, event_start,
                        #       end, event_end)
                        self.model.Add(
                            event_start <= start).OnlyEnforceIf(bol2)
                        self.model.Add(event_start > start).OnlyEnforceIf(
                            bol2.Not())

                        self.model.Add(event_end >= end).OnlyEnforceIf(bol3)
                        self.model.Add(event_end < end).OnlyEnforceIf(
                            bol3.Not())

                        self.model.Add(event_duration != 0).OnlyEnforceIf(bol4)
                        self.model.Add(event_duration == 0).OnlyEnforceIf(
                            bol4.Not())

                        bol_arr = [bol2, bol3, event[6]]

                        # self.model.AddMultiplicationEquality(bol1, bol_arr)

                        self.model.Add(sum(bol_arr) == 3).OnlyEnforceIf(bol1)
                        self.model.Add(sum(bol_arr) != 3).OnlyEnforceIf(
                            bol1.Not())
                    else:
                        pass
                        # print('sirisy')
                if len(ortool_arr) > 0:
                    # print("how many")
                    self.model.Add(sum(ortool_arr) >= 1)

        # self.resources1.resources[res].events_notScheduled

    def solve_model(self, data, timeconstraints, e_pair):
        # pl = create_blocks(self)
        # self.blocks = pl[1]
        # self.person_blocks = pl[2]
        self.data_insert(data)
        # if self.var_data['is_minSession_constraint']:
        #     self.min_session()
        try:
            self.matches_frequency()
        except Exception as e:
            print("bazo_matches_frequency_error : ", e)
            traceback.print_exc()
        # self.add_appointments_to_resources()
        # self.part2_strategy()
        # if self.var_data['is_time_constraint']:
        #     self.time_constraints(timeconstraints)
        # try:
        #     if self.var_data['is_lunch_constraint'] or True:
        #         self.lunch_constraints()
        # except Exception as e:
        #     print("bazo_lunch_error : ", e)
        # if self.var_data['is_break_constraint']:
        #     self.break_constraints()
        # if self.var_data['is_team_constraint']:
        #     self.team_constraints(self.var_data['team_bounds'])
        # if True:
        try:
            if self.var_data["settings"]['driveTime']:
                self.constraint_drive()
        except Exception as e:
            print("bazo_drive_error: ",e)
            traceback.print_exc()
        # try:
        #     if self.var_data['is_noGap_constraint']:
        #         self.no_gap()
        # except Exception as e:
        #     print("bazo_no_gap_error : ", e)
        if self.var_data['is_overlap_constraint']:
            self.no_overlap(e_pair)
        if False:
            self.supervision_constraint(True)
        try:
            self.objective(self.var_data["objectiveactivity"])
        except Exception as e:
            print("bazo_objective_error : ", e)
            traceback.print_exc()
        self.status_name = self.solve()


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
        self.availability = {}
        self.efficiency = {}
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
    def rocket(self, dd):
        self.data = dd
        data = self.data
        d1 = datetime.datetime.strptime(data['end_date'], "%Y-%m-%d")
        d2 = datetime.datetime.strptime(data['start_date'], "%Y-%m-%d")
        delta = d1 - d2
        num_of_days = int(delta.days) + 1
        d = {
            'num_of_days': num_of_days,
        }
        d.update(data)
        start = str(d2.strftime("%Y-%m-%d"))
        end = str((d2 + datetime.timedelta(days=1)).strftime("%Y-%m-%d"))
        host = self.data['host']
        branch = self.data['branch']
        header = self.data['header']
        
        
        stat = availabilities(host, header, start, end, branch)
        availabilities_for_fake_white_sol = {}
        for i_dict in stat[2]:
            res_id = i_dict["resourceIds"][0]
            if res_id in availabilities_for_fake_white_sol:
                availabilities_for_fake_white_sol[res_id].append({
                    "start":
                    i_dict["start"],
                    "end":
                    i_dict["end"]
                })
            else:
                availabilities_for_fake_white_sol[res_id] = [{
                    "start":
                    i_dict["start"],
                    "end":
                    i_dict["end"]
                }]
        # print("bazo_av : ", availabilities_for_fake_white_sol)
        # print("stat_of_av", stat[2])
        # print("stat_of_ids", stat[3])
        self.availability.update(stat[0])
        max_h = {"max_hours": stat[0]}
        # print("bazo_max_hours", max_h)
        self.data.update(max_h)
        self.efficiency = stat[1]

        some_data = Get_Data(d)
        self.resources = some_data.res()
        
        self.auth_week = some_data.get_events3()[1]
        self.data.update({"auth_week": self.auth_week})
        print("some_resources : ", self.auth_week)
        self.data["admin_id"] = "admin_id123"
        for ss_res in self.resources:
            print("Res_Name : ",ss_res)
            if "Admin" in ss_res["name"] and "admin_id" in self.data.keys():
                self.admin_id = ss_res["id"]
                self.data["admin_id"] = self.admin_id
        print("bazo_admin_id :" , self.admin_id) 
        self.data["notWorking"] = []
        print("bazo_empty_notWorking : ",self.data["notWorking"])
        self.data["notWorking"] = some_data.get_notWorking()
        print("bazo_finally : ",self.data["notWorking"])
        employee_ids = []
        persons_ids = []
        client_ids = []
        # print("bazo_resss : ",self.solution1.users)
        # arr_of_overlap_allowed = [i['id'] for i in self.solution1.users if i["firstName"] == "iudchc22"]
        arr_of_overlap_allowed = [i['id'] for i in self.solution1.users if i["overlap"]]
        for e in self.resources:
            if "Employee" in e["roles"]:
                employee_ids.append(e["id"])
            if "Person" in e["roles"]:
                persons_ids.append(e["id"])
            if "Client" in e["roles"]:
                client_ids.append(e["id"])
        # print("my_fav_emp", employee_ids)
        # print("my_fav_clt", client_ids)
        people_ids23 = {'employee_ids': employee_ids, 'client_ids': client_ids}
        self.max_total_hours = max_possible_total_hours(
            stat[2], people_ids23, 15)

        # solution to
        # print("some_emp_ids:", employee_ids)
        # self.events = some_data.get_events()
        ####Admin gets deleted
        # print("bazo_events_reload  : ",self.solution1.events2)
        print("compare_events :  ",self.solution1.events2)
        print("compare_events2 :  ",self.data["new_created_events"])
        scheduled_events = self.solution1.events2 + self.data["new_created_events"]
        try:
            ev_dd = [e for e in scheduled_events if len(intersection(e["resourceIds"],arr_of_overlap_allowed)) == 0]
            ev_admin = [e for e in ev_dd if self.admin_id in e["resourceIds"]]
            ev_dd = [e for e in ev_dd if not self.admin_id in e["resourceIds"]]
            for i in ev_admin:
                i.update({"type":"delete"})
                self.deletingEvents.append(i)
            # self.excluded_events = [e for e in self.solution1.events2 if len(intersection(e["resourceIds"],arr_of_overlap_allowed)) != 0]
            self.excluded_events += [i for i in ev_dd if len(intersection(self.data['objectiveactivity'],i["resourceIds"])) == 0]
            no_overlap_events = events_overlap(ev_dd,self.resources)
            self.events = no_overlap_events[0]
            print("bazo_wow : ",self.events)
        except Exception as e:
            print("bazo_wow : ",e)
            traceback.print_exc()
        fake_user_starts_ends = no_overlap_events[1]
        self.data["fake_user_starts_ends"] = fake_user_starts_ends
        self.data["clients_events_fake"] = no_overlap_events[2]
        # self.overlaped_ids = no_overlap_events[-1]
        # print("bazo_events_fake :",fake_user_starts_ends)
        for e_idd in persons_ids:
            self.excluded_events += fake_user_starts_ends[e_idd]["fakes"]
        self.data["weekly_events_data"] = weekly_events(scheduled_events,self.resources)
        self.gap_filler = []
        # self.event_possibly = some_data.get_direct_activities()
        # self.event_possibly = self.solution1.events_poss
        arr_poss = []
        # print('ploort', len(self.solution1.events_poss), len(self.orange_data))

        # print('prolong1', self.solution1.users)
        # print('prolong2', self.solution1.events_poss)
        # arr = get_number_per_slot(self.solution1)
        true_events_poss = []
        # for i, val in enumerate(arr):
        #     if val == 1:
        #         true_events_poss.append(self.solution1.events_poss[i])
        # print('sooby',len(self.orange_data),len(self.solution1.events_poss))
        for i in random.sample(self.solution1.events_poss,
                               len(self.solution1.events_poss) //
                               1) + random.sample(self.orange_data,
                                                  len(self.orange_data) // 1):
            # print('smookie2', len(true_events_poss),
            #       len(self.solution1.events_poss))
            # for i in true_events_poss:
            if data["start_date"] == i["new_start"] or True:
                arr_poss.append(i)
        event_arr = []
        # if data['is_orange']:
        #     for i in self.solution2.events_poss:
        #         if data["start_date"] == i["new_start"]:
        #             arr_poss.append(i)

        self.event_possibly = arr_poss
        # gg = gap_finder(arr_poss, stat[2])
        gg = []
        if len(data["teams"]) <= 1:  # and len(persons_ids) >= 20:
            # data["teams"] = get_groups_array(arr_poss, 20, persons_ids)
            data["teams"] = get_groups_array(self.solution1, 20, persons_ids,
                                             arr_poss)
            # print("my_best_teams : ", data["teams"])

        for i in self.events:
            if True or str(data["start_date"]) == i["start"][:10]:
                arr_poss.append(i)
                event_arr.append(i)
        gg_data = {"gg": gg}
        self.data.update(gg_data)
        # print("new_event_poss : ", self.event_possibly)
        self.roles_hierarchy = some_data.get_roles_hierarchy()
        self.distance_matrix = some_data.get_distance_matrix()
        self.event_pair = []  # some_data.get_event_pair()

        for i in range(1):
            a = self.event_possibly
            self.actual_data.append(a)
        if not data["daily"]:
            actual_data = []
            # print("bazo_actual_data : ", self.actual_data)
            for i in self.actual_data:
                actual_data = actual_data + i
            self.actual_data = actual_data
            a = {
                'start_date': data["start_date"],
                'day_increment': num_of_days,
                'actual_data': actual_data
            }
            cc = self.test_runner(a)
            if cc is not None:
                self.solution1.created_events += cc["created_events"]
            return cc
        else:
            some_array = []
            sd = data['start_date']
            x = len(self.actual_data)
            for i in range(x):
                a = {
                    'start_date': sd,
                    'day_increment': 1,
                    'actual_data': self.actual_data[i]
                }
                some_array.append(a)
                sd = datetime.datetime.strptime(sd, "%Y-%m-%d")
                sd = datetime.datetime.strftime(
                    sd + datetime.timedelta(days=1), "%Y-%m-%d")
            if data['is_Multi']:
                with ThreadPoolExecutor() as executor:
                    results = executor.map(self.test_runner, some_array)
            else:
                for tup in some_array:
                    cc = self.test_runner(tup)
                    self.solution1.created_events += cc["created_events"]
                    return cc

    def test_runner(self, testing_data):
        aut_arr = []
        date_original = testing_data['start_date']
        start_date_original = datetime.datetime.strptime(
            date_original, "%Y-%m-%d")
        self.date_original = date_original
        self.start_date_original = start_date_original
        if self.data['run_with_teams']:
            some_arr_of_data = []
            #aut2.solutions1.branches
            print('tupper2',self.solution1.branch_id)
            children_branches = []
            print('team_branch',self.solution1.branches,self.data['teams'])
            for b_id, value in self.solution1.branches.items():
                print('parentId2',value['parentId'],self.solution1.branch_id)
                if value['parentId'] == self.solution1.branch_id:
                    children_branches.append(b_id)
            if len(children_branches) == 0:
                self.data['teams'] = [self.solution1.branch_id]
            else:
                self.data['teams'] = children_branches
            print('children_branches',children_branches)
            team_index = 0
            for team in self.data['teams']:
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                true_team = [i[:-1] for i in team]
                # print('sloogy', team)
                for res in self.resources:
                    if 'Person' not in res['roles'] or team in res['branches']:
                        resources_team.append(res)
                for res in self.resources:
                    if 'Person' in res['roles'] and team in res['branches']:
                        resource_id_team.append(f'{res["id"]}a')
                        resource_id_team.append(f'{res["id"]}')
                    if 'Person' in res['roles'] and team not in res['branches']:
                        resource_id_team_not.append(f'{res["id"]}a')
                        resource_id_team_not.append(f'{res["id"]}')
                for dat in testing_data['actual_data']:
                    print('kooly',dat)

                    if not dat["scheduled"] and len(intersection(dat['resourceIds'],resource_id_team_not)) == 0:
                    #if len(intersection(dat['resourceIds'],resource_id_team)) > 0:
                        data2_team.append(dat)
                    elif dat["scheduled"] and len(intersection(dat['resourceIds'],resource_id_team)) > 0:
                        data2_team.append(dat)
                    
                    # if self.data["lunch_id"] in dat['resourceIds']:
                    #     data2_team.append(dat)

                    #For Multithreading teams lowest branch
                    # if len(intersection(dat['resourceIds'],
                    #                     data2_team)) >= 2:
                    #     # print("lord_of_the_ring  :", "founded")
                    #     data2_team.append(dat)
                self.data.update({'true_team': true_team})
                d = {
                    'objectiveactivity': self.data["objectiveactivity"],
                    'start_date_original': start_date_original,
                    'resources_team': resources_team,
                    'data': self.data,
                    'date_original': date_original,
                    'data2_team': data2_team,
                    'aut_arr': [team_index],
                }
                team_index += 1
                some_arr_of_data.append(d)
            print('jiffy',len(some_arr_of_data),some_arr_of_data)
            with ThreadPoolExecutor() as executor:
                results = executor.map(self.test_insert, some_arr_of_data)
        else:
            for team in range(1):
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                scheduled_ids = []
                k = []
                for res in self.resources:
                    if 'Person' not in res['roles'] or True:
                        resources_team.append(res)
                for res in self.resources:
                    if 'Person' in res['roles'] and True:
                        resource_id_team.append(f'{res["id"]}a')
                        resource_id_team.append(f'{res["id"]}')
                    if 'Person' in res['roles'] and True:
                        resource_id_team_not.append(f'{res["id"]}a')
                        resource_id_team_not.append(f'{res["id"]}')
                for dat in testing_data['actual_data']:
                    if len(
                            intersection(dat['resourceIds'],
                                         resource_id_team_not)) == 0 or True:
                        data2_team.append(dat)
                d = {
                    'objectiveactivity': self.data["objectiveactivity"],
                    'start_date_original': start_date_original,
                    'resources_team': resources_team,
                    'data': self.data,
                    'date_original': date_original,
                    'data2_team': data2_team,
                    'aut_arr': aut_arr
                }
                return (self.test_insert(d))

    def calculate_efficiency(self):
        adam_max_total_hours = get_number_per_slot(self.solution1) / (
            60 // self.data['slot_length']) / (self.data['slot_length'] / 15)
        # print('centers', adam_max_total_hours)
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
        print('self.solutions1.user_availabilities_general',self.solution1.user_availabilities_general)
        print('self.solutions1.user_availabilities_general_client',self.solution1.user_availabilities_general_clients)
        print('self.solutions1.user_availabilities_general_employees',self.solution1.user_availabilities_general_employees)
        print("inside_calc : ", self.availability)
        employees_total_availability = 0
        clients_total_availability = 0
        for value in self.solution1.user_availabilities_general_clients.values():
            for tup in value:
                tup_list = list(tup)
                start = tup_list[0]
                end = tup_list[1]
                clients_total_availability += (end-start)/ (60/self.solution1.slot_length)
        for value in self.solution1.user_availabilities_general_employees.values():
            for tup in value:
                tup_list = list(tup)
                start = tup_list[0]
                end = tup_list[1]
                employees_total_availability += (end-start)/ (60/self.solution1.slot_length)

        for k, v in self.availability["employees"].items():
            total_availability += v
        for k, v in self.availability["clients"].items():
            total_availability += v
        total_appointments_duration = sum(
            [i for i in self.efficiency.values()])
        efficiency_data["total_efficiency"] = round(
            total_appointments_duration / total_availability, 2)
        employees_id = list(self.availability["employees"].keys())
        clients_id = list(self.availability["clients"].keys())
        # print("Person_ids : ", employees_id + clients_id)
        employees_total_duration = sum(
            [v for i, v in self.efficiency.items() if i in employees_id])
        clients_total_duration = sum(
            [v for i, v in self.efficiency.items() if i in clients_id])
        # clients_total_availability = sum(self.availability["clients"].values())
        # employees_total_availability = sum(
        #     self.availability["employees"].values())
        efficiency_data["total_employees_efficiency"] = round(
            employees_total_duration / employees_total_availability, 2)
        efficiency_data["total_clients_efficiency"] = round(
            clients_total_duration / clients_total_availability, 2)
        for k, v in self.efficiency.items():
            if k in employees_id:
                a = {k: round(v / self.availability["employees"][k], 2)}
                efficiency_data["employees_efficiency"].update(a)
            elif k in clients_id:
                a = {k: round(v / self.availability["clients"][k], 2)}
                efficiency_data["clients_efficiency"].update(a)
        efficiency_data["status"] = self.status_name
        efficiency_data[
            "deleted_appointments"] = self.deleted_appointments_list
        efficiency_data["deleted_appointments_number"] = len(
            self.deleted_appointments_list)
        # efficiency_data['upper_bound'] = self.best_bound
        # efficiency_data["founded_solution"] = self.founded
        # print("eff_cal : ", efficiency_data)
        self.response = efficiency_data
        efficiency_data["total_clients_efficiency"] = str(efficiency_data["total_clients_efficiency"]*100)+"%"
        efficiency_data["total_employees_efficiency"] = str(efficiency_data["total_employees_efficiency"]*100) +"%"
        efficiency_data["total_efficiency"] = str(efficiency_data["total_efficiency"]*100) + "%"
        return efficiency_data

    def test_insert(self, d):
        start_date_original = d['start_date_original']
        resources_team = d['resources_team']
        data = d['data']
        date_original = d['date_original']
        data2_team = d['data2_team']
        aut_arr = d['aut_arr']
        print("team_index : ",aut_arr)
        returned_arr = []
        objective_value = 0
        host = data["host"]
        for act_id in [self.data["objectiveactivity"]]:
            day = 0
            resources_used = []
            aut2 = Automate(resources_team, self.roles_hierarchy, data,
                            resources_used, self.distance_matrix,
                            self.solution1)
            aut2.solve_model(data2_team, self.time_constraints,
                             self.event_pair)
            # resources_used += aut2.resources_yes
            if aut2 is None:
                pass
            self.employees_ids = aut2.employees_ids
            self.availability_person = aut2.availability_persons
            activity_list = aut2.find_ids_by_role(['Activity'])
            people_list = aut2.find_ids_by_role(['Employee'])
            deletable_events_list = aut2.deletable_events
            people_appointments = {}
            for id in people_list:
                people_appointments[id] = []
            event_obj = {}
            teams_dict = {}
            if len(aut2.get_team_vals()) > 0:
                for k, v in aut2.get_team_vals().items():
                    teams_dict[k] = aut2.solver.Value(v)

            if aut2.printer.solution_count() != 0:
                # print("at_least_one_solution_bazo")
                for tup, event in aut2.resources1.slots.items():
                    if (aut2.solver.Value(event[0]) > 0 or (event[5] == True)):

                        resources_ids = tuple(list(tup)[3:])
                        first = tuple(list(tup)[:3])
                        slot = list(tup)[0]
                        if resources_ids in event_obj.keys():
                            event_obj[resources_ids].append(first)
                        else:
                            event_obj[resources_ids] = [first]
                del_arr = []
                # print("bazo_object  : ", event_obj)
                # for tup, slots in event_obj.items():
                #     print("bazo_debug : ", tup)
                #     print("bazo_tuple_event : ", tup, slots)

                print('snoppy',self.created_events)
                for tup, slots in event_obj.items():
                    # print("bazo_debug : ", tup)
                    # print("bazo_tuple_event : ", tup, slots)
                    # detected_arr = detect_range(list(sorted(set(slots))))
                    users = list(set(list(tup)))
                    
                    
                    if len(users) == 1:
                        continue
                    for times in slots:
                        # print("bazo_debug1 : ", times)
                        try:
                            # print("bazo_debug2 : ", users)
                            # print('soolfer2')
                            # str3 = tuple([int(times[0])]) + \
                            #     tuple([int(times[-1])]) + tuple([n]) + tup
                            str3 = times + tup
                            print('pleaseplease',aut2.resources1.priorities[str3]['info'])
                            # print(
                            #     'soolfer3',
                            #     times,sa
                            #     str3,
                            # )
                            if str3 in aut2.resources1.slots.keys(
                            ) and False == aut2.resources1.slots[str3][17]:
                                # print('bazo_houser2', str3)
                                inte = aut2.solver.Value(
                                    aut2.resources1.slots[str3][0])
                                inte_start = aut2.solver.Value(
                                    aut2.resources1.slots[str3][3])
                                inte_end = aut2.solver.Value(
                                    aut2.resources1.slots[str3][4])
                                address = aut2.resources1.slots[str3][7]
                                loc_id = aut2.resources1.slots[str3][12]
                                loc_id2 = aut2.resources1.slots[str3][15]
                                scheduled = aut2.resources1.slots[str3][5]
                                real_event_ids = []
                                for event in self.solution1.events2:
                                    real_event_ids.append(event['id'])
                                print('real_event_ids',real_event_ids)
                                delete_event = aut2.solver.Value(
                                    aut2.resources1.slots[str3][11])
                                update_event = aut2.solver.Value(
                                    aut2.resources1.slots[str3][16])
                                event_id = aut2.resources1.slots[str3][9]
                                delete_event_id = aut2.resources1.slots[
                                    str3][9]
                                if aut2.resources1.priorities[str3]['faker']:
                                    print('stumpy',delete_event,update_event,scheduled,users)
                                if aut2.resources1.priorities[str3]['faker'] and delete_event == 0:
                                    print('dinner')
                                    continue
                                try:
                                    if delete_event == 0 and update_event == 0:
                                        pass
                                        # print("Evreka_bazo")
                                    if delete_event == 0 and update_event == 1:
                                        del_arr.append(delete_event_id)
                                        for del_event in aut2.deletable_events:
                                            # print(
                                            #     "bazo_delete : ", del_event)
                                            if del_event[
                                                    "id"] == delete_event_id:
                                                type_delete = {
                                                    "type": "delete"
                                                }

                                                some_dict_for_delete = find_from_resources(
                                                    self.resources,
                                                    del_event[
                                                        "resourceIds"])
                                                type_delete.update(
                                                    del_event)
                                                type_delete.update(
                                                    some_dict_for_delete)
                                                self.deletingEvents.append(
                                                    type_delete)
                                                self.deleted_hours += calculate_time_difference(
                                                    type_delete["start"],
                                                    type_delete[
                                                        "end_real_time"])
                                            else:
                                                pass
                                                # print(
                                                #     "****OKOKOK : ",
                                                #     del_event)
                                except Exception as e:
                                    print("bazo_Error : ", e)

                                # if update_event == 0:

                                #     my_obj = object_for_return(
                                #         new_start, new_end, start, end, users,
                                #         activity, loc_id2, address)
                                #     self.created_events.append(my_obj)
                                #     returned_arr.append(my_obj)
                                objective_best_bound = aut2.get_best_objective_bound(
                                )

                                sum_del_bol_array = aut2.solver.Value(
                                    aut2.del_bol_array)

                                self.best_bound = objective_best_bound - sum_del_bol_array

                                self.status_name = aut2.solver.StatusName()

                                objective_val = aut2.solver.ObjectiveValue(
                                )

                                self.founded = objective_val - sum_del_bol_array

                                start = slot_to_time(
                                    inte_start, data['slot_length'])
                                end = slot_to_time(inte_end,
                                                    data['slot_length'])
                                start_date_original = datetime.datetime.strptime(
                                    date_original, "%Y-%m-%d")
                                start_day = math.floor(
                                    inte_start /
                                    (24 * 60 // data['slot_length'])
                                ) - datetime.datetime.strptime(
                                    date_original,
                                    '%Y-%m-%d').weekday() - 1
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
                                        'loc_id':
                                        loc_id,
                                        'new_start':
                                        new_start,
                                        'users':users,
                                        'start_time_r':start,
                                        'end_time_r':end,

                                    })
                                people_ids = self.efficiency.keys()
                                if len(intersection(people_ids,
                                                    users)) > 0:
                                    ids_of_intersection = intersection(
                                        people_ids, users)
                                    for id in ids_of_intersection:
                                        dur = round(
                                            int(inte) *
                                            self.data['slot_length'] / 60,
                                            2)
                                        self.efficiency[id] += dur
                                if (len(intersection(users, activity_list))
                                        > 0):
                                    activity = intersection(
                                        users, activity_list)[0]
                                    
                                    all_obj = object_for_return(
                                        new_start, new_end, start, end,
                                        users, activity, loc_id, address,self.data['start_date'],self.data['end_date'])
                                    self.all_appointments.append(all_obj)
                                # print("i_have_no_idea : ", users,
                                #       activity_list)
                                if not scheduled or update_event == 0:
                                    if (len(
                                            intersection(
                                                users, activity_list)) >
                                            0):

                                        activity = intersection(
                                            users, activity_list)[0]
                                        if self.data[
                                                "drive_id"] in activity:

                                            pass
                                        if self.data[
                                                "drive_id"][:
                                                            -1] in activity:

                                            pass
                                        my_obj = object_for_return(
                                            new_start, new_end, start, end,
                                            users, activity, loc_id,
                                            address,self.data['start_date'],self.data['end_date'])
                                        self.loc_id_2 = loc_id2
                                        returned_arr.append(my_obj)
                                        if True:
                                            resources_with_names = find_from_resources(
                                                self.resources,
                                                my_obj["data"]["users"])
                                            my_obj["data"].update(
                                                resources_with_names)
                                            my_obj["data"].update({
                                                'users':list(set(users))
                                            })
                                            if update_event == 0:
                                                event_here = {
                                                    **my_obj["data"], "id":
                                                    event_id,
                                                    "type": 'update'
                                                }
                                                self.updatingEvents.append({
                                                    **event_here, 'newEvent':
                                                    {
                                                        **event_here
                                                    },
                                                    'oldEvent': {
                                                        **event_here
                                                    }
                                                })
                                            else:
                                                my_obj["data"].update({
                                                'users':list(set(users))})
                                                self.creatingEvents.append(
                                                    my_obj["data"])
                                            host = data['host']
                                            self.created_hours += calculate_time_difference(
                                                my_obj["data"]["start"],
                                                my_obj["data"]["end"])
                                            # response = requests.post(
                                            #     f'{host}/events',
                                            #     headers=data['header'],
                                            #     json=my_obj)
                                            # print("Received : ", my_obj)
                                            print("\n")
                                        self.created_events.append(my_obj)
                        except Exception as e:
                            print("bazo_error : ", e)
                self.deleted_appointments_list = del_arr + self.overlaped_ids + [i["id"] for i in aut2.over_availability_events]
                self.deletingEvents = self.deletingEvents + [{"id":i,"type": "delete"} for i in self.overlaped_ids] + aut2.over_availability_events
                # response = requests.post(f'{host}/events/remove/multiple',
                #                          headers=data['header'],
                #                          json={
                #                              "toBeDeletedIds": del_arr,
                #                              "pushNotification": {
                #                                  "send": False,
                #                                  "message": "",
                #                                  "to": []
                #                              }
                #                          })
            distance_matrix_keys = aut2.distance_matrix.keys()
            # print("bb_dd_data : ",aut2.drive_time_data)
            apps = []
            arr_of_not_exist = []
            try :
                for id, arr in people_appointments.items():

                    arr_sorted = sorted(arr,key=lambda x: datetime.datetime.strptime(x['start'], "%Y-%m-%dT%H:%M:%S.000Z"),reverse=False)
                    # print('sneebler5', people_appointments
                    # )

                    for i in range(len(arr_sorted) - 1):
                        # print("bazo_pp : ",i)
                        new_list = arr_sorted[i:i + 2]
                        address1 = new_list[0]['address']
                        address2 = new_list[1]['address']
                        users1 = new_list[0]['users']
                        users2 = new_list[1]['users']
                        check_inter1 = list(set([*users1]) & set(self.data["notWorking"]))
                        check_inter2 = list(set([*users2]) & set(self.data["notWorking"]))
                        if len(check_inter1)+len(check_inter2) > 1:
                            continue
                        # print('sloofyer5', new_list[0]['loc_id'],
                        #       new_list[1]['loc_id'])
                        # if new_list[0]['loc_id'] in aut2.solutions1.user_uuid_to_index.keys() and new_list[1]['loc_id'] in aut2.solutions1.user_uuid_to_index.keys():
                        if self.data["settings"]['driveTime']:
                            # print("Bazo3",new_list)
                            if new_list[0]["loc_id"] is None or new_list[1]["loc_id"] is None:
                                continue
                            loc1 = aut2.solutions1.user_uuid_to_index[new_list[0]['loc_id']]
                            loc2 = aut2.solutions1.user_uuid_to_index[new_list[1]['loc_id']]
                            if loc1 is None or loc2 is None:
                                continue
                            loc1_actual = new_list[0]['loc_id']
                            loc2_actual = new_list[1]['loc_id']
                            user1_id = aut2.solutions1.users[loc1]["id"]
                            user2_id = aut2.solutions1.users[loc2]["id"]
                            
                            branchId1 = 'd'
                            branchId2 = 's'
                            if loc1:
                                # print('bb_skooky')
                                branchId1 = aut2.solutions1.users[loc1][
                                    'branches'][0]
                            if loc2:
                                # print('bb_skooky2')
                                branchId2 = aut2.solutions1.users[loc2][
                                    'branches'][0]

                            if True or (len(branchId1) > 1 and len(
                                    branchId2
                            ) > 1 and loc1 and loc2 and loc1 != loc2):
                                # print("Bazo4")
                                # if (address1 and address2 and len(address2) > 0
                                #         and len(address1) > 0
                                #         and address1 in distance_matrix_keys):
                                #     if (address2 in aut2.distance_matrix[address1].keys()
                                #             and
                                #             aut2.distance_matrix[address1][address2][1]):
                                if address1 is None or address2 is None:
                                    continue
                                drive_time = aut2.solutions1.branches[branchId1][
                                    'drivetime']
                                user_tuples = tuple([address1,address2])
                                if user_tuples in aut2.drive_time_data.keys():
                                    drive_time_r = round_to_nearest_interval(aut2.drive_time_data[user_tuples]['mid'] / 60,aut2.var_data["slot_length"])
                                    print('foory',drive_time_r,aut2.drive_time_data[user_tuples]['mid'])
                                else:
                                    drive_time_r = 0
                                drive_time = drive_time_r
                                if drive_time == 0:
                                    continue
                                # drive_time_r = convert_drive_time(drive_time_r)
                                # drive_time_r = sum([int(i[1]) for i in drive_time_r])/len(drive_time_r)
                                # drive_time_r = drive_time_r/60
                                # drive_time_r = aut2.solver.Value(drive_time_r)*15
                                # print("bb_dt : ",drive_time_r)
                                # if drive_time_r > 0 and drive_time_r <= 15:
                                #     drive_time = 15
                                # if drive_time_r > 15 and drive_time_r <= 30:
                                #     drive_time = 30
                                # if drive_time_r > 30 and drive_time_r <= 45:
                                #     drive_time = 45
                                # if drive_time == 0 or not drive_time:
                                #     drive_time = 0
                                # else:
                                #     print('snoofy', drive_time)
                                drive_time_slot = int(drive_time //aut2.var_data['slot_length'])
                                # drive_time = ceil_to_multiple(
                                #     aut2.distance_matrix[address1][address2][1] /
                                #     60.0, data['slot_length'])
                                # drive_time_slot = int(drive_time //
                                #                     data['slot_length'])
                                date_string = new_list[0]['end']
                                date_object = datetime.datetime.strptime(
                                    date_string, '%Y-%m-%dT%H:%M:%S.%fZ')
                                new_date = date_object + datetime.timedelta(
                                    minutes=drive_time)
                                new_date_string = new_date.strftime(
                                    '%Y-%m-%dT%H:%M:%S.%fZ')
                                # print('hiffy', aut2.var_data["drive_id"])
                                # print("Bazo5")
                                # Convert the time string to a datetime object
                                time_obj = datetime.datetime.strptime(new_list[0]['end_time_r'], '%H:%M:%S')

                                # Add 15 minutes
                                new_time_obj = time_obj + datetime.timedelta(minutes=drive_time)

                                # Convert the new datetime object back to a string
                                new_time_str = new_time_obj.strftime('%H:%M:%S')
                                
                                
                                myobj = object_for_return(
                                            date_original, '', new_list[0]['end_time_r'], new_time_str,
                                            [id,aut2.var_data["drive_id"]], aut2.var_data["drive_id"], None,
                                            None,self.data['start_date'],self.data['end_date'])
                                # myobj = {
                                #     'data': {
                                #         'start':
                                #         new_list[0]['end'],
                                #         'end':
                                #         new_date_string,
                                #         'users': [id,aut2.var_data["drive_id"]],
                                #         # "location0Id": loc1_actual,
                                #         # "loc_id": loc2_actual,
                                #         "resourceIds" : [id,aut2.var_data["drive_id"]],
                                #         "orange_sol":
                                #         False,
                                #         'scheduled':
                                #         True,
                                #         'activity0Id':
                                #         aut2.var_data["drive_id"],
                                #         'notes':
                                #         '',
                                #         'frequency':
                                #         'Weekly',
                                #         'startRecur':
                                #         new_list[0]['endRecur'][:10],
                                #         'endRecur':
                                #         new_list[1]['startRecur'][:10],
                                #         'interval':
                                #         1,
                                #         "type": "create",
                                #         'daysOfWeek': [
                                #             day_ids[(datetime.datetime.strptime(
                                #                 new_list[0]['new_start'],
                                #                 '%Y-%m-%d').weekday() + 1) % 7]
                                #         ]
                                #     }
                                # }
                                resources_with_names = find_from_resources(
                                                    self.resources,
                                                    myobj["data"]["users"])
                                # print("bb_res : ",resources_with_names)
                                myobj["data"].update(
                                                    resources_with_names)
                                # myobj['data']['activity0Id'] = self.data[
                                #     "drive_id"]
                                # print("Bazo6")
                                returned_arr.append(myobj)
                                # print('herro1')
                                abcdef = self.data["drive_id"][:-1]
                                tuple_check = tuple(id) + tuple(
                                    myobj['data']['start']) + tuple(
                                        myobj['data']['end'])
                                if tuple_check in arr_of_not_exist and False:
                                    continue
                                if False:
                                    host = data['host']
                                    response = requests.post(
                                        f'{host}/events',
                                        headers=data['header'],
                                        json=myobj)
                                    arr_of_not_exist.append(tuple_check)
                                    apps.append(myobj['data'])
                                self.creatingEvents.append(myobj["data"])
                                # print("Bazo7 : ",myobj)
            except Exception as e:
                print('*** drive_time_error', e)
                traceback.print_exc()  # Print to console

            # print("hello_bug : ", apps)
        gc.collect()
        # print('throomer',)
        # self.solution1.created_events += self.created_events

        return {
            'returned_arr': returned_arr,
            'objective_value': objective_value,
            "status": "status",
            "created_events": self.created_events
        }

    def part_one(self):
        dd = self.data
        
        self.rocket(dd)
        a = self.calculate_efficiency()
        # b = {"appointments": self.all_appointments}
        c = {
            "creatingEvents": self.creatingEvents,
            "deletingEvents": self.deletingEvents,
            "updatingEvents": self.updatingEvents,
            "statistics": a
        }

        return c

    def part_two(self):
        dd = self.data

        self.rocket(dd)
        print('jimmy',self.admin_id)
        if not self.admin_id is None and (self.admin_id == "661650b0-c24a-4234-a0ab-1e7c879dfc0c" or self.admin_id == 'bfa0101d-5d9c-465b-905d-3bab7db276b9'):
            print('jimmy2')
            update_events_ids = [i["id"] for i in self.updatingEvents]
            not_include_ids = update_events_ids+self.deleted_appointments_list
            allEvents = self.creatingEvents+self.updatingEvents+self.excluded_events +[i for i in self.events if not i["id"] in not_include_ids]
            # allEvents = [i for i in allEvents if not i["id"] in self.deleted_appointments_list]
            allEvents_dict = {}
            gapEvents_dict = {}
            for _id in self.employees_ids:
                allEvents_dict[_id] = []
            weekday_all = 0
            for _event in allEvents:
                inter_emp = intersection(_event["resourceIds"], self.employees_ids)
                if len(inter_emp) > 0:
                    s_times = time_to_int(_event,self.data["slot_length"])
                    start_time = s_times[0]
                    end_time = s_times[2]
                    weekday = s_times[3]
                    weekday_all = weekday
                    allEvents_dict[inter_emp[0]]+= list(range(start_time,end_time))
            # for i,v in allEvents_dict.items():
            #     allEvents_dict[i].append(self.availability_person[i][int(weekday_all)])
            admin_filler_data = []
            weekday_all = int(weekday_all)-1
            print('jimmy3',allEvents_dict)
            adjust = 24*60 // self.data['slot_length']
            for i,v in allEvents_dict.items():
                all_int_av = []
                print('jimmy5',int(weekday_all),self.availability_person[i])
                for x in self.availability_person[i][int(weekday_all)]:
                    print("bazo_x_av : ",x)

                    all_int_av += list(range(x[0]+adjust,x[1]+adjust))
                set_v = set(v)
                ddd = [z for z in all_int_av if not z in set_v]
                ranges = detect_range2(ddd)
                # if len(ranges) == 1:
                #     pass
                # for xs in range(len(ranges)-1):
                    
                # print("bazo_ddelta : ", ddd,ranges)
                for rang in ranges:
                    print('jimmy4')
                    start = slot_to_time(rang[0], self.data['slot_length'])
                    end = slot_to_time(rang[1],self.data['slot_length'])
                    start_date_original = datetime.datetime.strptime(self.date_original, "%Y-%m-%d")
                    start_day = math.floor(rang[0] /(24 * 60 // self.data['slot_length'])) - datetime.datetime.strptime(self.date_original,'%Y-%m-%d').weekday() - 1
                    new_start = datetime.datetime.strftime(start_date_original +datetime.timedelta(days=start_day),"%Y-%m-%d")
                    new_end = datetime.datetime.strftime(start_date_original +datetime.timedelta(days=start_day + 1),"%Y-%m-%d")
                    fake_admin = object_for_return(new_start, new_end, start, end,[i], self.admin_id, self.loc_id_2,"fake adress",self.data['start_date'],self.data['end_date'])
                    #self.creatingEvents.append(fake_admin["data"])
                    admin_filler_data.append(fake_admin["data"])
            
            self.admin_filler = admin_filler_data
                    # print("bazo_added : ",fake_admin)
                
        a = self.calculate_efficiency()
        # b = {"appointments": self.all_appointments}
        c = {
            "creatingEvents": self.creatingEvents,
            "deletingEvents": self.deletingEvents,
            "updatingEvents": self.updatingEvents,
            "statistics": a
        }
        return c

    def run(self):
        pass


def get_weekday_index(date_string):
    date = datetime.datetime.strptime(date_string, "%Y-%m-%d")
    return date.weekday()


def rocket_luncher2(data):
    d1 = datetime.datetime.strptime(data['end_date'], "%Y-%m-%d")
    d2 = datetime.datetime.strptime(data['start_date'], "%Y-%m-%d")
    s = d2
    e = (d1 + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    delta = d1 - d2
    num_of_days = delta.days + 1
    sd = d2.strftime("%Y-%m-%d")
    data["is_events"] = False
    data["is_session_for_part2"] = False
    getter_data1 = data
    getter_data2 = copy.deepcopy(data)
    sols = {}
    sols2 = {}
    results_array = []
    with ThreadPoolExecutor() as executor:
                results = executor.map(solution_getter, [getter_data1, getter_data2])    
                for i in results:
                    results_array.append(i)
    
    sols,sols2 = results_array[0],results_array[1]        
    
    get_week_dates = get_week_start_end(data['start_date'])
    print ("get_week_dates",get_week_dates)
    weekdays_av_data = {i:{} for i in range(len(get_week_dates["week_dates"]))}
    for i in range(len(weekdays_av_data)-1):
        sss = get_week_dates["week_dates"][i]
        eee = get_week_dates["week_dates"][i+1]
        avv = availabilities(data["host"], data["header"], sss, eee, data["branch"])
        weekdays_av_data[i].update(avv[4])
        
    week_start ,week_end = get_week_dates["week_dates"][0],get_week_dates["week_dates"][1]
    av = availabilities(data["host"], data["header"], week_start, week_end, data["branch"])

    nested_dict = av[0]
    
    print("nested_dict_bazo : ",av[4],weekdays_av_data)
    combined_dict = {
        k: v
        for sub_dict in nested_dict.values() for k, v in sub_dict.items()
    }
    
    print("bazo_combined_dict: " ,combined_dict)

    obj = {}
    result = []
    arr = []
    day_arr = []
    for i in range(num_of_days):
        a = data.copy()
        a['start_date'] = sd
        a['end_date'] = sd
        a["weekdays_av_data"] = weekdays_av_data
        sd = (d2 + datetime.timedelta(days=i + 1)).strftime("%Y-%m-%d")
        day = get_weekday_index(sd)
        day_arr.append(day)
        a['today_index'] = day
        x = {"data": a, "int": i}
        obj[sd] = []
        arr.append(x)

    e_arr = []
    admin_filler_data = []
    for i in arr:
        i_data = i['data']
        i_data2 = copy.deepcopy(i['data'])
        print('i_data2',i_data2)
        if i_data["analyzeMode"]:
            print("run_with_team : ",False,"analyze mode")
            i_data["run_with_teams"] = False
            i_data["workers"] = 128
            i_data["sol_1"] = sols[0]
            i_data["sol_2"] = sols[1]
            i_data["sol_3"] = sols[2]
            i_data["sols_with_events"] = []
            i_data["new_created_events"] = []

            i_data2["run_with_teams"] = False
            i_data2["sol_1"] = sols2[0]
            i_data2["sol_2"] = sols2[1]
            i_data2["sol_3"] = sols2[2]
            i_data2["sols_with_events"] = []
            i_data2["new_created_events"] = []
            print("wakavu_data : ", i_data)
            print("bazo_second_time_ORTOOLS_run_analyzer ",i_data)
            solver = Solver(i_data)
            first_result = solver.part_two()
            admin_filler_data = solver.admin_filler
            first_result.update({"analyzerMessage":f"Issue is","issueArray":i_data["ignoredConstrainTypes"]})
            if len(first_result["creatingEvents"]) == 0:
                first_result["statistics"].update({"status": "INFEASIBLE"})
            result.append(first_result)
            pass
        elif i_data["part1"] and not i_data["analyzeMode"]:
            i_data["sol_1"] = sols[0]
            i_data["sol_2"] = sols[1]
            i_data["sol_3"] = sols[2]
            i_data2["sol_1"] = sols2[0]
            i_data2["sol_2"] = sols2[1]
            i_data2["sol_3"] = sols2[2]
            i_data["percentage"] = 0
            i_data2["percentage"] = 0
            solver = Solver(i_data)
            result.append(solver.part_one())
            sols[0].created_events += solver.created_events
        else:
            if i_data["percentage"] == 0: 
                print("run_with_team : ",True)
                workers = 128
                if len(i_data["teams"]) <= 5:
                    pass
                else:
                    workers = 128//len(i_data["teams"])*2
                i_data["workers"] = workers
                i_data["run_with_teams"] = True
                i_data["sol_1"] = sols[0]
                i_data["sol_2"] = sols[1]
                i_data["sol_3"] = sols[2]
                i_data["sols_with_events"] = []
                i_data["new_created_events"] = []

                i_data2["run_with_teams"] = False
                i_data2["workers"] = 128
                i_data2["sol_1"] = sols2[0]
                i_data2["sol_2"] = sols2[1]
                i_data2["sol_3"] = sols2[2]
                i_data2["sols_with_events"] = []
                i_data2["new_created_events"] = []
                i_data2["percentage"] = 0
                print("bazo_second_time_ORTOOLS_run ",i_data)
                solver = Solver(i_data)
                first_result = solver.part_two()
                admin_filler_data = solver.admin_filler
                new_creatingEvents = []
                new_deletingEvents = []
                for event in first_result["creatingEvents"]:
                    lunch_id = 'ab0bc43a-b680-4642-88e1-2c2f4236dd5e'
                    if lunch_id != event['activity0Id']:
                        new_creatingEvents.append(event)
                    else:
                        print('yamal')
                for event in first_result["deletingEvents"]:
                    lunch_id = 'ab0bc43a-b680-4642-88e1-2c2f4236dd5e'
                    if lunch_id not in event['resourceIds']:
                        new_deletingEvents.append(event)
                    else:
                        print('yamal')
                first_result["creatingEvents"] = new_creatingEvents
                first_result["deletingEvents"] = new_deletingEvents
                print('first_result["creatingEvents"]',first_result["creatingEvents"])
                print('first_result["updatingEvents"]',first_result["updatingEvents"])
                print('"new_created_events"',"new_created_events")
                i_data["new_created_events"] += first_result["creatingEvents"]+first_result["updatingEvents"]
                
                i_data2["new_created_events"] += copy.deepcopy(first_result["creatingEvents"])+copy.deepcopy(first_result["updatingEvents"])
                lunch_ids = []
                
                fake_uuids  = []
                if len(i_data2["new_created_events"]) > 0:
                    for i in i_data2["new_created_events"]:
                        temp_uuid = str(uuid.uuid4())
                        i["id"] = temp_uuid
                        timestamp = datetime.datetime.strptime(i['end'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        formatted_timestamp = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
                        i['end'] = formatted_timestamp
                        print('filly',formatted_timestamp)
                        i['resourceIds'] = list(filter(lambda x: x != '1',i['users']))
                        i["title"] = ""
                        fake_uuids.append(temp_uuid)
                        print('footy',i['resourceIds'])
                for i in i_data2["new_created_events"]:
                    if i["activity"] == "Lunch":
                        print('lunch_here',i["activity0Id"],i_data2['lunch_id'])
                        lunch_ids.append(i["id"])
                print('hoopy3',i_data2["new_created_events"])
                print('gooly1',i_data2["new_created_events"])
                print("definetly_new_changes")
                if first_result["statistics"]["total_clients_efficiency"] != '100.0%':
                    print("bazo_second_time_ORTOOLS_run ",i_data2)
                    
                    solver2 = Solver(i_data2)
                    all_events = solver2.part_two()
                    admin_filler_data = solver2.admin_filler
                    dont_send = []
                    
                    
                    print('simba',all_events)
                    print('gooly2',i_data2["new_created_events"])
                    l_events = [i for i in i_data2["new_created_events"] if i["id"] not in dont_send]
                    all_events["creatingEvents"] = [*all_events["creatingEvents"],*l_events]
                    print('gooly3',all_events["creatingEvents"])
                    filtered_create_events = []
                    for i in all_events["creatingEvents"]:
                        if "type" in i.keys():
                            
                            if i["type"] == "create":
                                print('seemer3',i)
                                filtered_create_events.append(i)
                            elif i["type"] == "update":
                                print('seemer5',i)
                                all_events["updatingEvents"].append(i)
                            elif i["type"] == "delete":
                                print('seemer6',i)
                                all_events["deletingEvents"].append(i)

                        else:
                            print('moofer2')
                    all_events["creatingEvents"] = filtered_create_events
                    
                    real_event_ids = []
                    for event in sols2[1].events2:
                        real_event_ids.append(event['id'])
                    print('sols2.events2',real_event_ids,sols2[1].events2)
                    all_events["deletingEvents"] = list(filter(lambda x: x['id'] in real_event_ids,all_events["deletingEvents"]))
                    updating_to_creating = list(filter(lambda x: x['id'] not in real_event_ids,all_events["updatingEvents"]))
                    for event in updating_to_creating:
                        event['type'] = 'create'

                    
                    updating_to_creating_ids = []
                    for e in updating_to_creating:
                        updating_to_creating_ids.append(e['id'])
                    all_events["creatingEvents"] = list(filter(lambda x: 'id' not in x.keys() or x['id'] not in updating_to_creating_ids,all_events["creatingEvents"]))
                    all_events["creatingEvents"] = [*all_events["creatingEvents"], *updating_to_creating]


                    all_events["updatingEvents"] = list(filter(lambda x: x['id'] in real_event_ids,all_events["updatingEvents"]))
                    deletingEvents_ids = list(map(lambda x: x['id'],all_events["deletingEvents"]))
                    all_events['statistics']['deleted_appointments'] = deletingEvents_ids
                    result.append(all_events)
                else:
                    print("bazo_no_need_for_second_run")
                    result.append(first_result)   
                print('sols2.events2',sols2[1].events2)
                print("bazo__created_events : ",solver.created_events)
            else:
                print("run_with_team : ",False)
                i_data["run_with_teams"] = False
                i_data["workers"] = 128
                i_data["sol_1"] = sols[0]
                i_data["sol_2"] = sols[1]
                i_data["sol_3"] = sols[2]
                i_data["sols_with_events"] = []
                i_data["new_created_events"] = []

                i_data2["run_with_teams"] = False
                i_data2["sol_1"] = sols2[0]
                i_data2["sol_2"] = sols2[1]
                i_data2["sol_3"] = sols2[2]
                i_data2["sols_with_events"] = []
                i_data2["new_created_events"] = []
                print("bazo_second_time_ORTOOLS_run ",i_data)
                solver = Solver(i_data)
                first_result = solver.part_two()
                admin_filler_data = solver.admin_filler
                result.append(first_result)
    print("bazo_result : ", result)
    result[0]["creatingEvents"] += admin_filler_data
    return result


def rocket_luncher3(data):
    start_day = datetime.datetime.strptime(data['start_date'], "%Y-%m-%d")
    end_day = datetime.datetime.strptime(data['end_date'], "%Y-%m-%d")
    end_day_2 = (end_day + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    delta = end_day - start_day
    num_of_days = delta.days + 1
    sd = start_day.strftime("%Y-%m-%d")
    data["is_events"] = False
    data["is_session_for_part2"] = False
    sols = solution_getter(data)
    av = availabilities(data["host"], data["header"], start_day, end_day_2,
                        data["branch"])
    # print("bazo_availabilities : ", av)
    if data["part1"]:
        i_data = data.copy()
        i_data["sol_1"] = sols[0]
        i_data["sol_2"] = sols[1]
        i_data["sol_3"] = sols[2]
        i_data['today_index'] = 1
        # i_data['today_index'] = day
        # i_data["weekly_avb"] = combined_dict
        i_data["percentage"] = 0
        solver = Solver(i_data)
        return [solver.part_one()]
    else:
        pass


def solution_getter(a):
    # print("why_not : ", a)
    events_poss = []
    data_gatherer = []
    d1 = datetime.datetime.strptime(a['end_date'], "%Y-%m-%d")
    d2 = datetime.datetime.strptime(a['start_date'], "%Y-%m-%d")

    delta = d1 - d2
    # Added by Adam
    # print('folly1', a, 'folly2')
    start_date_original = datetime.datetime.strptime(a['start_date'],
                                                     "%Y-%m-%d")
    real_end_date = datetime.datetime.strftime(
        start_date_original + datetime.timedelta(days=int(delta.days) + 1),
        "%Y-%m-%d")
    # data_gatherer = Data_Gatherer({
    #     **a, 'end_date': real_end_date,
    #     'is_events': True
    #     # a['part1']
    # })
    data_gatherer = Data_Gatherer({
        **a, 'end_date': real_end_date,
        'is_events': True,
        "optimizer_sol": True
        # a['part1']
    })
    # print('sooty', data_gatherer.events)
    is_session = False
    if "is_session_for_part2" in a.keys():
        is_session = a["is_session_for_part2"]

    solutions1 = Solution_Generator(
        data_gatherer, {
            "is_orange": False,
            "is_session": is_session,
            'investigate': [],
            "ignoreConstraintArray": a["uncheckWhiteSolutionConstraints"],
            "soft": False
        })
    
    events_poss = solutions1.main2()
    result = []
    for item in events_poss:
        modified_resource_ids = [resource_id[:-1] for resource_id in item['resourceIds']]
        result.append(modified_resource_ids)
    print('slimmy',result)
    data_gatherer.resourceCombinationsExclude = result

    # solutions2 = solutions1

    solutions2 = Solution_Generator(
        data_gatherer, {
            "is_orange": True,
            "is_session": False,
            "ignoreConstraintArray": a["uncheckOrangeSolutionConstraints"],
            "soft": True
        })

    # solutions2 = Solution_Generator(data_gatherer, {"is_orange": True})
    
    # print("bazo_ppp2 : ",len(set([i["loc_id"] for i in events_poss])),[i["loc_id"] for i in events_poss])
    # events_poss = solutions1.main3()
    # print('simily4')
    # solutions1.all_main()
    # events_poss = solutions1.events_poss
    #solutions2 = solutions1

    events_poss_white = []
    events_poss_orange = []
    # for event in events_poss:
    #     if len(event['reasons']) == 0:
    #         events_poss_white.append(event)
    #     else:
    #         events_poss_orange.append(event)
    unmatch_poss_events = []
    unmatch_poss_events = solutions2.main2()
    # print('simily1')

    # unmatch_poss_events = solutions2.main2()
    # # print('simily2')
    # unmatch_poss_events = solutions2.main3()

    # print('simily3')
    # unmatch_poss_events_new = []
    # poss_events_obj = {}
    # unmatch_poss_events_obj = {}
    # for event in events_poss:
    #     tup = tuple(event['resourceIds_r'])
    #     print('footy',event)
    #     ev_now = set(
    #         solutions2.calc_availabilities(event['start'], event['end'],
    #                                        '%Y-%m-%dT%H:%M:%S.%fZ'))
    #     if tup in poss_events_obj.keys():
    #         poss_events_obj[tup] = poss_events_obj[tup].union(ev_now)
    #     else:
    #         poss_events_obj[tup] = ev_now

    # for event in unmatch_poss_events:
    #     tup = tuple(event['resourceIds_r'])
    #     if tup in poss_events_obj.keys():
    #         ev_now = set(
    #             solutions2.calc_availabilities(
    #                 event['start'], event['end'],
    #                 '%Y-%m-%dT%H:%M:%S.%fZ')).difference(poss_events_obj[tup])
    #         detected = solutions2.detect_range(list(ev_now))
    #         for times in list(detected):
    #             start = solutions2.slot_to_time(times[0], 15)
    #             end = solutions2.slot_to_time(times[1], 15)
    #             start_date_original = datetime.datetime.strptime(
    #                 solutions2.start_date, "%Y-%m-%d")
    #             start_day = math.floor(
    #                 times[0] / (24 * 60 // 15)) - datetime.datetime.strptime(
    #                     solutions2.start_date, '%Y-%m-%d').weekday() - 1
    #             new_start = datetime.datetime.strftime(
    #                 start_date_original + datetime.timedelta(days=start_day),
    #                 "%Y-%m-%d")
    #             new_end = datetime.datetime.strftime(
    #                 start_date_original +
    #                 datetime.timedelta(days=start_day + 1), "%Y-%m-%d")

    #             full_start = f'{new_start}T{start}.000Z'
    #             full_end = f'{new_start}T{end}.000Z'

    #             obj = {**event, "start": full_start, "end": full_end}
    #             unmatch_poss_events_new.append(obj)
    #     else:
    #         unmatch_poss_events_new.append(event)

    # events_poss_orange = solutions2.main2()
    # events_poss_orange = solutions2.main3()
    # print('baz_bug', events_poss)
    # events_poss = solutions1.main3()
    ######
    # events_poss_obj = {
    #     'intersections': [],
    #     'poss_events': events_poss,
    #     'unmatch_poss_events': unmatch_poss_events_new
    #     # 'poss_events': events_poss_white,
    #     # 'unmatch_poss_events': events_poss_orange
    # }
    a_orange = []
    for i in unmatch_poss_events:
        or_sol = i.copy()
        or_sol["orange_sol"] = True
        a_orange.append(or_sol)
    print("bazo_orange : ", len(a_orange),len(solutions1.events_poss),solutions1.events_poss,a_orange)
    return [solutions1, solutions2, a_orange, events_poss]


def rocket_luncher_inbloom(data):
    data["blocks"] = False
    data["optimizer_sol"] = True
    t1 = time.time()
    if data.get("part1"):
        data.update({
            "percentage": 0,
            "part1": False,
            "part2_in_part1": False,
            "is_orange": True,
            "max_time_in_seconds": 5.0,
        })
        return rocket_luncher2(data)

    data.update({
        "percentage": 10,  # Uncommented default percentage
        "part2_in_part1": False,
        "is_orange": True,
        "max_time_in_seconds": 5.0,
    })
    res2 = rocket_luncher2(data)
    run_time = round(time.time() - t1)

    # Attach runtime to results
    for entry in res2:
        if "statistics" in entry:
            entry["statistics"]["run_time"] = run_time
    return res2
