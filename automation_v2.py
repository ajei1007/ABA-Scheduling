from external import *

import gc
import math
import time
import random
import requests
import datetime
import itertools
from random import randrange
from get_data import Get_Data
from itertools import combinations
from ortools.sat.python import cp_model
from concurrent.futures import ThreadPoolExecutor
from events_durations_calc import Time_Constraint_Handler
from solve import Solution_Generator, Data_Gatherer
from todo import gap_finder
import uuid
import traceback
from calculate_drive_time import *
from testing import hard_coded_data

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
        self.blocks = []
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
    def get_team_vals(self):
        return self.team_vals

    def get_best_objective_bound(self):
        return self.best_objective_bound

    def find_ids_by_role(self, roles):
        resources_ids = []
        for id, resource in self.resources1.resources.items():
            for resource_role in resource.roles:
                if resource_role in self.roles_hierarchy.keys():
                    if len(
                            intersection(
                                roles,
                                self.roles_hierarchy[resource_role])) > 0:
                        resources_ids.append(id)
        return list(set(resources_ids))
    
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
        val = self.get_appointments([self.find_ids_by_role(self.var_data['objective_role']),self.var_data["objectiveactivity"]])
        undeleted_appointments = []
        del_bol_array = []
        update_bol_array = []
        if not self.var_data["part1"]:
            for i in val.values():
                if i[5]:
                    undeleted_appointments.append(i[0])
                    del_bol_array.append(i[11])
                    update_bol_array.append(i[16])
            if self.var_data["percentage"] != 0:
                self.model.Add(sum(del_bol_array) >= len(del_bol_array) -self.var_data["percentage"])
                self.model.Add(sum(update_bol_array) >= len(update_bol_array) -self.var_data["percentage"])
                self.model.Add(2 * (len(del_bol_array) - sum(del_bol_array) - 1) <=(len(update_bol_array) - sum(update_bol_array)))

        del_bol_array = self.delete_bool
        update_bol_array = self.update_bool

        try : 
            if self.var_data["part1"]:
                appointments_dict = {}
                len_role = len(self.var_data["objective_role"])
                len_actives = len(self.var_data["objectiveactivity"])
                while len_role > 0:
                    for delta_ in range(len_actives):
                        appointments_dict[len_role*(delta_+1)*1] = []
                    len_role -= 1
                print("bb_app : ",appointments_dict)
                len_role = len(self.var_data["objective_role"])
                len_actives = len(self.var_data["objectiveactivity"])
                for index1,value1 in enumerate(self.var_data["objective_role"]):
                    for index2,value2 in enumerate(self.var_data["objectiveactivity"]):
                        app_value = self.get_appointments([self.find_ids_by_role([value1]),[value2]])
                        appointments_dict[(len_role-index1)*(len_actives-index2)*1].append(app_value)
                
                self.model.Maximize(
                     sum([sum([sum(map(lambda num: num[0] if not num[10] else 0, v2.values())) for v2 in v])*i*100 for i,v in appointments_dict.items()])
                     +sum([sum([sum(map(lambda num: num[0] if num[10] else 0, v2.values())) for v2 in v])*i*90 for i,v in appointments_dict.items()])
                     -sum([sum([sum(map(lambda num: num[6] if not num[10] else 0, v2.values())) for v2 in v])*i*39 for i,v in appointments_dict.items()])
                     -sum([sum([sum(map(lambda num: num[6] if num[10] else 0, v2.values())) for v2 in v])*i*40 for i,v in appointments_dict.items()])
                     
                )
        except Exception as e:
            print("bb_error : ",e)

        try : 
            if not self.var_data["part1"]:
                appointments_dict = {}
                len_role = len(self.var_data["objective_role"])
                len_actives = len(self.var_data["objectiveactivity"])
                while len_role > 0:
                    for delta_ in range(len_actives):
                        appointments_dict[len_role*(delta_+1)*1] = []
                    len_role -= 1
                len_role = len(self.var_data["objective_role"])
                len_actives = len(self.var_data["objectiveactivity"])
                for index1,value1 in enumerate(self.var_data["objective_role"]):
                    for index2,value2 in enumerate(self.var_data["objectiveactivity"]):
                        app_value = self.get_appointments([self.find_ids_by_role([value1]),[value2]])
                        appointments_dict[(len_role-index1)*(len_actives-index2)*1].append(app_value)
                
                self.model.Maximize(
                     sum([sum([sum(map(lambda num: num[0] if not num[10] else 0, v2.values())) for v2 in v])*i*100 for i,v in appointments_dict.items()])
                     +sum([sum([sum(map(lambda num: num[0] if num[10] else 0, v2.values())) for v2 in v])*i*90 for i,v in appointments_dict.items()])
                     -sum([sum([sum(map(lambda num: num[6] if not num[10] else 0, v2.values())) for v2 in v])*i*39 for i,v in appointments_dict.items()])
                     -sum([sum([sum(map(lambda num: num[6] if num[10] else 0, v2.values())) for v2 in v])*i*40 for i,v in appointments_dict.items()])
                     + sum(del_bol_array) + sum(update_bol_array)
                )
                self.model.Add(len(del_bol_array)-sum(del_bol_array)+len(update_bol_array) - sum(update_bol_array)<= self.var_data["percentage"])
        except Exception as e:
            print("bb_error_adam2 : ",e, traceback.print_exc())
            
    def solve(self):
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.var_data[
            'max_time_in_seconds']
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.num_search_workers = 64
        self.solver.log_callback = print
        solution_printer = VarArraySolutionPrinter([])
        self.printer = solution_printer
        status = self.solver.Solve(self.model, solution_printer)
        print('Status = %s' % self.solver.StatusName(status))
        print('Number of solutions found: %i' %
              solution_printer.solution_count())
        self.status_name = self.solver.StatusName(status)
        self.best_objective_bound = self.solver.BestObjectiveBound()

    def data_insert(self, data):
        # print("bazo_data : ", data)
        people5 = self.find_ids_by_role(['Person'])
        resource5 = self.find_ids_by_role(['Resource'])
        clients_ids = self.find_ids_by_role(['Client'])
        emp_ids = self.find_ids_by_role(['Employee'])
        av_arr_for_fake_raw = self.solutions1.user_availabilities_general
        av_arr_for_fake = {}
        for some_id in people5:
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
        for some_id in people5:
            for i in av_arr_for_fake_raw[some_id]:
                some_index = i[0] // ((24 * 60) // self.var_data["slot_length"])
                av_arr_for_fake[some_id][some_index].append(i)
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
        waitlist_count = 1
        event_ids = []
        people = self.find_ids_by_role(['Resource'])
        data_arr = data + self.created_events + self.var_data["gg"] #+self.var_data["clients_events_fake"]
        priority_arr = []
        for info in data_arr:
            if not info["scheduled"]:
                slots = time_to_int(info, self.var_data['slot_length'])
                interval_start = slots[0]
                duration = slots[1]
                interval_end = slots[2]
                intersection_of_resources = sorted(list(set(intersection(people5,[i[:-1]for i in info["resourceIds"]]))))

                my_obj = {
                    'start': interval_start,
                    "duration": duration,
                    "end": interval_end
                }
                self.bol_appointments_dict[tuple(
                    intersection_of_resources)] = []
                if tuple(intersection_of_resources) in self.scheduled_dict.keys():
                    self.scheduled_dict[tuple(intersection_of_resources)].append(my_obj)
                else:
                    self.scheduled_dict[tuple(intersection_of_resources)] = [my_obj]
            loc_id2 = info["loc_id2"] if "loc_id2" in info.keys() else ""
            if 'priority' in info.keys():
                if type(info['priority']) == int:
                    priority = info['priority']
                    if priority not in priority_arr:
                        priority_arr.append(priority)
        priority_arr.sort(reverse=True)
        print("bazo6", len(data_arr),len(set([i["loc_id"] for i in data_arr])),set([i["loc_id"] for i in data_arr]))
        for info in data_arr:
            if 'priority' in info.keys() and type(info['priority']) == int:
                weight += priority_arr.index(info['priority']) * 10000

            slots = time_to_int(info, self.var_data['slot_length'])
            interval_start = slots[0]
            duration = slots[1]
            interval_end = slots[2]
            weekday_index = slots[3]
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
            intersection_of_resources = sorted(list(set(intersection(people5,[i[:-1] for i in info["resourceIds"]]))))
            if not info["scheduled"] and duration > 0:
                fake_bool = False
                duration_int = self.model.NewIntVar(
                    0, duration, f'session length {duration}')

                start_int = self.model.NewIntVar(interval_start, interval_end,f'{interval_start}')
                end_int = self.model.NewIntVar(interval_start, interval_end,f'{interval_end}')
                id_for_bol = info["id"]
                bol_appointment = self.model.NewBoolVar(f'hi{id_for_bol}')
                self.priority_array.append(info["priority"]*bol_appointment)
                event_interval = self.model.NewOptionalIntervalVar(start_int, duration_int, end_int, bol_appointment,'interval')
                if tuple(intersection_of_resources) in self.scheduled_dict.keys():
                    for n in self.scheduled_dict[tuple(intersection_of_resources)]:
                        if interval_start >= n['start'] and interval_end <= n[ 'end']:
                            n.update({"bol_appointment": bol_appointment})

                for i in intersection_of_resources:
                    self.persons_bol_appointments[i].append(bol_appointment)
                self.model.Add(0 == duration_int).OnlyEnforceIf(bol_appointment.Not())
                self.model.Add(0 < duration_int).OnlyEnforceIf(bol_appointment)
                self.bol_appointments_dict[tuple(intersection_of_resources)].append(bol_appointment)
                weekday_index = interval_start // ((24 * 60) // self.var_data["slot_length"])
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
                con = False
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
                                    con = True
                                    break

                print("make_sure : ",con)
                for id_b in info["resourceIds"]:
                    if not id_b in resource5:
                        ave = {"type" : "delete"}
                        info.update(ave)
                        self.over_availability_events.append(info)
                        continue
                weekday_index = interval_start // ((24 * 60) // self.var_data["slot_length"])
                pass_event = False
                for res_id in info["resourceIds"]:
                    if res_id in av_arr_for_fake.keys():
                        if av_arr_for_fake[res_id][weekday_index] == []:
                            pass_event = True
                        else:
                            for intervals_av in av_arr_for_fake[res_id][weekday_index]:
                                if intervals_av[0] > interval_start:
                                    pass_event = True
                                    break
                                if intervals_av[1] < interval_end:
                                    pass_event = True
                                    break
                if pass_event:
                    info["type"] = "delete"
                    self.over_availability_events.append(info)
                    continue
                id_for_bool = info['id']
                fake_bool = False
                if info["title"] == "ByPass Activity":
                    fake_bool = True
                orange_sol = False
                if "orange_sol" in info.keys():
                    orange_sol = info["orange_sol"]
                del_bol = self.model.NewBoolVar("del_bol")
                update_bol = self.model.NewBoolVar("update_bol")
                start_int_bol = self.model.NewBoolVar(f"start_int_bol-{id_for_bool}")
                end_int_bol = self.model.NewBoolVar("end_int_bol")
                resource_list = list(set(info['resourceIds']))
                resource_list = [res for res in sorted(resource_list)]
                intersection_of_resources = sorted(list(set(intersection(people5, info["resourceIds"]))))
                interval_start_embed = interval_start
                interval_end_embed = interval_end

                emp_id_arr = sorted(intersection(emp_ids, info["resourceIds"]))
                client_id_arr = sorted(
                    intersection(clients_ids, info["resourceIds"]))

                if len(client_id_arr) > 0:
                    client_id = client_id_arr[0]

                if len(emp_id_arr) > 0:
                    emp_id2 = emp_id_arr[0]

                need_arr = []

                for emp_id in emp_id_arr:
                    if len(emp_id_arr) > 0 and emp_id != emp_id2:
                        tup = tuple(sorted([client_id, emp_id]))
                        if tup in self.scheduled_dict.keys():
                            for n in self.scheduled_dict[tup]:
                                need_arr.append(n['bol_appointment'])

                if tuple(intersection_of_resources) in self.scheduled_dict.keys() and info["title"] != "ByPass Activity":
                    for n in self.scheduled_dict[tuple(
                            intersection_of_resources)]:
                        if n["end"] < interval_start_embed or n[
                                "start"] > interval_start_embed:
                            continue
                        else:
                            start_end1 = set(range(n['start'], n['end'] + 1))
                            start_end2 = set(
                                range(interval_start_embed,
                                      interval_end_embed + 1))
                            start_end_new = list(start_end1.union(start_end2))
                            if len(start_end_new) > 0 and len(intersection(self.var_data['objectiveactivity'],info["resourceIds"])) > 0:
                                interval_start_embed = min(start_end_new)
                                interval_end_embed = max(start_end_new)
                                self.model.Add(n['bol_appointment'] == 0)
                                break
                            
                start_int = self.model.NewIntVar(interval_start_embed,interval_end_embed,f'start-{id_for_bool}')

                duration_int = self.model.NewIntVar(0, interval_end_embed - interval_start_embed, "some_dur")
                end_int = self.model.NewIntVar(interval_start_embed,interval_end_embed,f'end-{id_for_bool}')
                event_interval = self.model.NewOptionalIntervalVar(start_int, duration_int, end_int, del_bol,f'interval-{id_for_bool}')
                self.model.Add(start_int == interval_start).OnlyEnforceIf(start_int_bol)
                self.model.Add(end_int == interval_end).OnlyEnforceIf(end_int_bol)

                self.model.Add(start_int != interval_start).OnlyEnforceIf(start_int_bol.Not())
                self.model.Add(end_int != interval_end).OnlyEnforceIf(end_int_bol.Not())
                # **
                # self.model.Add(update_bol == 1).OnlyEnforceIf(del_bol.Not())
                # self.model.Add(del_bol == 1).OnlyEnforceIf(update_bol.Not())
                # **
                self.model.Add(start_int_bol + end_int_bol < 2).OnlyEnforceIf(update_bol.Not())
                self.model.Add(duration_int > 0).OnlyEnforceIf(update_bol.Not())
                self.model.Add(start_int_bol +end_int_bol == 2).OnlyEnforceIf(update_bol)

                if len(intersection(self.var_data['objectiveactivity'],info["resourceIds"])) == 0:
                    self.model.Add(del_bol == 1)
                    self.model.Add(update_bol == 1)
                if self.var_data['percentage'] == 0:
                    self.model.Add(del_bol == 1)
                    self.model.Add(update_bol == 1)
                for id_b in info["resourceIds"]:
                    if not id_b in resource5:
                        self.model.Add(del_bol == 0)
                        break
                else:
                    self.model.Add(duration_int > 0).OnlyEnforceIf(del_bol)
                    self.model.Add(duration_int == 0).OnlyEnforceIf(del_bol.Not())
                if info["id"] in event_ids:
                    continue

                else:
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
                        self.persons_bol_appointments[i].append(del_bol)

                    self.delete_bool.append(del_bol)
                    self.update_bool.append(update_bol)
                    if info["title"] != "ByPass Activity":
                        self.direct_events_sum += duration
                    client_intersections = intersection(clients_ids, resource_list)
                    self.deletable_events.append(info)
                    if len(client_intersections) >= 1:
                        if info["title"] != "ByPass Activity":
                            self.clients_durations[client_intersections[0]] += duration
                event_ids.append(info["id"])
                event_ids = list(set(event_ids))
        print("--------------------------------*--------------------------------*--------------------------------")

    def no_overlap(self, e_pair):
        for id in list(set(self.find_ids_by_role(["Client"]))):
            extra_arr = self.fake_whites[id] if id in self.fake_whites else []
            val = self.get_appointments([[id]])
            if len(val) > 0:
                arr = val.values()
                flimp = list((map(lambda num: num[2], arr))) + extra_arr
                self.model.AddNoOverlap(flimp)
        for id in list(set(self.find_ids_by_role(["Employee"]))):
            extra_arr = self.fake_whites[id] if id in self.fake_whites else []
            val = self.get_appointments([[id]])
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
                flimp2 = list((map(lambda num: num[2], over_normal))) + extra_arr 
                self.model.AddNoOverlap(flimp1)
                self.model.AddNoOverlap(flimp2)
      
    def constraint_drive(self):
        constraint_drive_data = get_drive_time_data(self.var_data["header"],self.var_data["host"])
        max_time_for_drive = 60 # in minutes
        max_time_slots_array = list(range(max_time_for_drive//self.var_data["slot_length"]+1))
        boost_cof = 2 # now it is hard coded 
        is_high_traffic = False # hard coded
        days_arrays = days_arr(self.var_data['slot_length'])
        for index, x in enumerate(days_arrays):
            if index != 0:
                continue
            for id in self.find_ids_by_role(['Employee']):
                val = self.get_appointments([[id], [str(index)],self.find_ids_by_role(['Activity'])])
                for r in list(combinations(map(lambda num: num, val.values()),2)):
                    res1 = r[0]
                    res2 = r[1]
                    # address1 = res1[7]
                    # address2 = res2[7]
                    loc1 = self.solutions1.user_uuid_to_index[res1[12]]
                    loc2 = self.solutions1.user_uuid_to_index[res2[12]]
                    branchId1 = 'd'
                    branchId2 = 's'
                    user1_address = self.solutions1.users[loc1]["address"]
                    user2_address = self.solutions1.users[loc2]["address"]
                    user1_id = self.solutions1.users[loc1]["id"]
                    user2_id = self.solutions1.users[loc2]["id"]
                    
                    if loc1:
                        branchId1 = self.solutions1.users[loc1]['branches'][0]
                    if loc2:
                        branchId2 = self.solutions1.users[loc2]['branches'][0]
                    if len(branchId1) <= 1 or len(branchId2) <= 1 or loc1 == loc2:
                        continue
                    # print("bb_what_is_going_on1")
                    drive_time = self.solutions1.branches[branchId1]['drivetime']
                    tuple_ids = tuple(sorted([user1_id, user2_id])) 
                    if tuple_ids in constraint_drive_data.keys():
                        d_data_duration = constraint_drive_data[tuple_ids]
                        drive_time_data = d_data_duration / 60
                        if is_high_traffic:
                            drive_time_data = drive_time_data*boost_cof
                        for i in max_time_slots_array:
                            if i > drive_time_data/self.var_data["slot_length"]:
                                drive_time = i
                                break
                    else:
                        result_distance_dur = return_interval_drive_time(user1_address, user2_address,return_ten_time())
                        post_drive_time_data(self.var_data["header"],{
                            "data" :{
                                "duration": result_distance_dur[1],
                                "distance": result_distance_dur[0],
                                "user1" : user1_id,
                                "user2" : user2_id
                                }
                        },self.var_data["host"])
                        constraint_drive_data[tuple_ids] = result_distance_dur[1]
                        drive_time_data = result_distance_dur[1] / 60
                        if is_high_traffic:
                            drive_time_data = drive_time_data*boost_cof
                        for i in max_time_slots_array:
                            if i > drive_time_data/self.var_data["slot_length"]:
                                drive_time = i
                    if drive_time == 0 or not drive_time:
                        drive_time = 30
                    else:
                        pass
                    print("bbdd_drive_time: ", drive_time)
                    drive_time_slot = int(drive_time)
                    end2 = res2[4]
                    start2 = res2[3]
                    end1 = res1[4]
                    start1 = res1[3]
                    duration2 = res2[0]
                    duration1 = res1[0]
                    newBol = self.model.NewBoolVar('yo')
                    self.model.AddMultiplicationEquality(newBol, [res1[6], res2[6]])
                    newInt1 = self.model.NewIntVar(-100000, 100000, 'h')
                    max_end = self.model.NewIntVar(-100000, 100000, 'h')
                    min_end = self.model.NewIntVar(-100000, 100000, 'h')
                    self.model.AddMaxEquality(max_end, [end1, end2])
                    self.model.AddMinEquality(min_end, [start1, start2])

                    self.model.Add(newInt1 == max_end - min_end -duration2 - duration1)
                    self.model.Add(newInt1 >= drive_time_slot).OnlyEnforceIf(newBol)
                    self.model.Add(duration1 != 0).OnlyEnforceIf(newBol)
                    self.model.Add(duration2 != 0).OnlyEnforceIf(newBol)
        self.drive_time_data = constraint_drive_data
        print("OK_WITH : DRIVE_CONS")

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
                    print("  :  [YES]")
                    continue

                elif c['type'] == 'frequency':
                    # print("bazo_is_disabled :  [NO]")
                    # print("bazo_custom_type_frequency")
                    for user_a in c['users_antecedent']:
                        user_a_id = self.solutions1.resources1.resources[
                            user_a].id
                        # print('gooly',
                        #       self.resources1.resources[user_a_id].firstName)
                        if c['frequency'] == 'day':
                            # print("bazo_custom_frequency_day")
                            for index, x in enumerate(days_arrays):
                                if index == self.var_data[
                                        "today_index"] or True:
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
                                            map(lambda num: num[6],
                                                val.values()))
                                        # if user_a_id in self.resources1.resources.keys(
                                        # ) and user_c_id in self.resources1.resources[
                                        #         user_a_id].matches2.keys():
                                        #     matching_bol = self.resources1.resources[
                                        #         user_a_id].matches2[user_c_id][
                                        #             index - 1]
                                        #     arr.append(matching_bol)
                                    if len(arr) == 0:
                                        continue
                                    if c["id"] in self.var_data["highPriority"]:
                                        # self.model.Add(bol == 1)
                                        self.model.Add(sum(arr) <= c['max'])
                                        if c["min"] != 0:
                                            self.model.Add(
                                                sum(arr) >= c['min'])
                                        counts_of_vars[c["id"]] += 1
                                        # print("bazo_why_this : ", arr)
                                    else:
                                        bol = self.model.NewBoolVar('y')
                                        inte = self.model.NewIntVar(
                                            0, 10000000000, 'snip1')

                                        # print('goomy', inte_vars, arr,
                                        #       c['max'], c['min'])
                                        self.model.Add(inte == inte_vars[
                                            c["id"]]).OnlyEnforceIf(bol)
                                        self.model.Add(
                                            inte == 0).OnlyEnforceIf(bol.Not())
                                        self.constraint_bols.append(inte)
                                        # print("bazo_why_this : ", arr)
                                        counts_of_vars[c["id"]] += 1
                                        self.model.Add(sum(arr) <= c['max']
                                                       ).OnlyEnforceIf(bol)
                                        self.model.Add(sum(arr) >= c['min']
                                                       ).OnlyEnforceIf(bol)
                                    # print('slimmy', c["id"],
                                    #       self.var_data["hard"])

                        elif c['frequency'] == 'week':
                            # print("bazo_custom_frequency_week")
                            arr = []
                            for index, x in enumerate(days_arrays):
                                if index != 0:
                                    for user_c in c['users_consequence']:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        val = self.get_appointments(
                                            [[user_c_id], [user_a_id],
                                             [self.var_data["today_index"]]])
                                        if len(val) == 0:
                                            continue
                                        arr = arr + list(
                                            map(lambda num: num[6],
                                                val.values()))
                            if len(arr) == 0:
                                continue
                            bol = self.model.NewBoolVar('y')
                            inte = self.model.NewIntVar(
                                0, 10000000000, 'snip1')

                            self.model.Add(
                                inte == inte_vars[c["id"]]).OnlyEnforceIf(bol)
                            self.model.Add(inte == 0).OnlyEnforceIf(bol.Not())
                            self.constraint_bols.append(inte)

                            counts_of_vars[c["id"]] += 1
                            self.model.Add(
                                sum(arr) <= c['max']).OnlyEnforceIf(bol)
                            self.model.Add(
                                sum(arr) >= c['min']).OnlyEnforceIf(bol)
                elif c['type'] == 'time':
                    # print("bazo_custom_type_time", c['frequency'],
                    #       c['users_antecedent'])
                    for user_a in c['users_antecedent']:

                        user_a_id = self.solutions1.resources1.resources[
                            user_a].id
                        # print("why_bazo_why : ", user_a, user_a_id)
                        if c['frequency'] == 'session':
                            # print("bazo_custom_frequency_session")
                            for index, x in enumerate(days_arrays):
                                if index == self.var_data[
                                        'today_index'] or True:
                                    for user_c in c['users_consequence']:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        val = self.get_appointments(
                                            [[user_c_id], [user_a_id],
                                             [str(index)]])
                                        if len(val) == 0:
                                            continue
                                        # print("bazo_user_ids  :", user_a_id,
                                        #       user_c_id)
                                        durations = list(
                                            map(lambda num: num[0],
                                                val.values()))
                                        for dur in durations:
                                            if c["id"] in self.var_data[
                                                    "highPriority"]:
                                                self.model.Add(dur <= c_max)
                                                if c_min != 0:

                                                    inc = 1
                                                    while inc < c_min:
                                                        # while inc < 2:
                                                        # print(
                                                        #     "bazo_min : ",
                                                        #     c_min, inc)
                                                        self.model.Add(
                                                            dur != inc)
                                                        inc += 1
                                                counts_of_vars[c["id"]] += 1
                                            else:
                                                bol = self.model.NewBoolVar(
                                                    'y')
                                                inte = self.model.NewIntVar(
                                                    0, 10000000000, 'snip1')
                                                # self.constraint_bols.append(bol)
                                                self.model.Add(
                                                    inte == inte_vars[c["id"]]
                                                ).OnlyEnforceIf(bol)
                                                counts_of_vars[c["id"]] += 1
                                                self.model.Add(
                                                    inte == 0).OnlyEnforceIf(
                                                        bol.Not())
                                                self.constraint_bols.append(
                                                    inte)
                                                # print('gilter3')
                                                self.model.Add(
                                                    dur <= c_max
                                                ).OnlyEnforceIf(bol)
                                                self.model.Add(
                                                    dur >= c_max
                                                ).OnlyEnforceIf(bol)

                        if c["each_or_all_users"] == 'each':
                            print("bazo_custom_each_or_all_users_each_bb")
                            if c['frequency'] == 'day':
                                # print("bazo_custom_frequency_day")
                                for index, x in enumerate(days_arrays):
                                    if index == self.var_data[
                                            'today_index'] or True:
                                        # if index != 0:
                                        for user_c in c['users_consequence']:
                                            # print('lifterz5', c["min"],
                                            #       c["max"], c["id"])
                                            bol = self.model.NewBoolVar('y')
                                            self.constraint_bols.append(bol)
                                            user_c_id = self.solutions1.resources1.resources[
                                                user_c].id
                                            # user_cons_ids = [self.solutions1.resources1.resources[user_cc].id for user_cc in c['users_consequence']]
                                            arr = list(
                                                map(
                                                    lambda num: num[0],
                                                    self.get_appointments(
                                                        [[user_c_id],
                                                            [user_a_id],
                                                            [str(index)]]).values()))
                                            if len(arr) == 0:
                                                print("oooh no")
                                                continue
                                            if c["id"] in self.var_data[
                                                    "highPriority"]:
                                                print("bb_high : ",c_max,c_min)
                                                self.model.Add(
                                                    sum(arr) <= c_max)
                                                if c["min"] != 0:
                                                    self.model.Add(
                                                        sum(arr) >= c_min)
                                                counts_of_vars[c["id"]] += 1
                                            else:
                                                bol = self.model.NewBoolVar(
                                                    'y')
                                                inte = self.model.NewIntVar(
                                                    0, 10000000000, 'snip1')
                                                # self.constraint_bols.append(bol)
                                                self.model.Add(
                                                    inte == inte_vars[c["id"]]
                                                ).OnlyEnforceIf(bol)
                                                self.model.Add(
                                                    inte == 0).OnlyEnforceIf(
                                                        bol.Not())
                                                counts_of_vars[c["id"]] += 1
                                                self.constraint_bols.append(
                                                    inte)
                                                # self.constraint_bols.append(bol)
                                                self.model.Add(
                                                    sum(arr) <= c_max
                                                ).OnlyEnforceIf(bol)
                                                self.model.Add(
                                                    sum(arr) >= c_min
                                                ).OnlyEnforceIf(bol)

                                            # self.model.Add(
                                            #     sum(arr) == 0).OnlyEnforceIf(
                                            #         bol.Not())

                            elif c['frequency'] == 'week':
                                # print("bazo_custom_frequency_week")
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[
                                        user_c].id
                                    arr = list(
                                        map(
                                            lambda num: num[0],
                                            self.get_appointments([
                                                [user_c_id], [user_a_id]
                                            ]).values()))
                                    if len(arr) == 0:
                                        continue
                                    if c["id"] in self.var_data["highPriority"]:
                                        print("bazo_yeh : ",weekly_data[user_a_id][user_c_id],c_max)
                                        self.model.Add(sum(arr)+weekly_data[user_a_id][user_c_id]//self.var_data["slot_length"] <= c_max)
                                        counts_of_vars[c["id"]] += 1
                                    else:
                                        bol = self.model.NewBoolVar('y')
                                        inte = self.model.NewIntVar(
                                            0, 10000000000, 'snip1')
                                        # self.constraint_bols.append(bol)
                                        self.model.Add(inte == inte_vars[
                                            c["id"]]).OnlyEnforceIf(bol)
                                        self.model.Add(
                                            inte == 0).OnlyEnforceIf(bol.Not())
                                        counts_of_vars[c["id"]] += 1
                                        self.constraint_bols.append(inte)
                                        self.constraint_bols.append(bol)
                                        # print('here I am')
                                        self.model.Add(sum(arr)+weekly_data[user_a_id][user_c_id]//self.var_data["slot_length"] <= c_max).OnlyEnforceIf(bol)
                                    # self.model.Add(sum(arr) == 0).OnlyEnforceIf(
                                    #     bol.Not())
                        else:
                            # print("bazo_custom_each_or_all_users_all")
                            if len(c['users_consequence']) == 0:
                                continue
                            user_cons = c['users_consequence']
                            if c['frequency'] == 'day':
                                # print("bazo_custom_frequency_day")
                                for index, x in enumerate(days_arrays):
                                    if index == self.var_data[
                                            "today_index"] or True:
                                        user_c_ids = [self.solutions1.resources1.resources[user_cc].id for user_cc in user_cons]
                                        arr = list(
                                            map(
                                                lambda num: num[0],
                                                self.get_appointments(
                                                    [user_c_ids, [user_a_id],
                                                     [str(index)]]).values()))
                                        if len(arr) > 0:
                                            if c["id"] in self.var_data[
                                                    "highPriority"]:
                                                self.model.Add(
                                                    sum(arr) <= c_max)
                                                if c["min"] != 0:
                                                    self.model.Add(
                                                        sum(arr) >= c_min)
                                                counts_of_vars[c["id"]] += 1
                                            else:
                                                bol = self.model.NewBoolVar(
                                                    'y')
                                                inte = self.model.NewIntVar(
                                                    0, 10000000000, 'snip1')
                                                # self.constraint_bols.append(bol)
                                                self.model.Add(
                                                    inte == inte_vars[c["id"]]
                                                ).OnlyEnforceIf(bol)
                                                self.model.Add(
                                                    inte == 0).OnlyEnforceIf(
                                                        bol.Not())
                                                self.constraint_bols.append(
                                                    inte)
                                                counts_of_vars[c["id"]] += 1

                                                # newBol = self.model.NewBoolVar('l')
                                                self.model.Add(
                                                    sum(arr) <= c_max
                                                ).OnlyEnforceIf(bol)

                                                self.model.Add(
                                                    sum(arr) >= c_min
                                                ).OnlyEnforceIf(bol)

                                            # self.model.Add(
                                            #     sum(arr) == 0).OnlyEnforceIf(
                                            #         bol.Not())
                            elif c['frequency'] == 'week':
                                # print("bazo_custom_frequency_week")
                                user_c_id = self.solutions1.resources1.resources[
                                    user_c].id
                                arr = list(
                                    map(
                                        lambda num: num[0],
                                        self.get_appointments([[user_c_id],
                                                               [user_a_id],
                                                               [str(index)]
                                                               ]).values()))
                                if len(arr) == 0:
                                    continue
                                # for user_c in c['users_consequence']:
                                #     for index, x in enumerate(days_arrays):
                                #         if index != 0:
                                #             print("first_if : ", user_c, user_a)
                                #             user_c_id = self.solutions1.resources1.resources[
                                #                 user_c].id
                                #             if user_a_id in self.resources1.resources.keys(
                                #             ) and user_c_id in self.resources1.resources[
                                #                     user_a_id].matches2_durations.keys(
                                #                     ):

                                #                 int_duration = self.resources1.resources[
                                #                     user_a_id].matches2_durations[
                                #                         user_c_id][index - 1]
                                #                 arr.append(int_duration)
                                #             elif user_c_id in self.resources1.resources.keys(
                                #             ) and user_a_id in self.resources1.resources[
                                #                     user_c_id].matches2_durations.keys(
                                #                     ):

                                #                 int_duration = self.resources1.resources[
                                #                     user_c_id].matches2_durations[
                                #                         user_a_id][index - 1]
                                #                 arr.append(int_duration)
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
                                    print("bazo_av : ",av_arr_for_fake_raw)
                                    clients_gaps_interval = []
                                    clients_gaps_duration = []
                                    durations = list(
                                        map(lambda x: x[0], val_gaps.values()))
                                    try:
                                        if len(av_data) > 1:
                                            fake_start_actual = min(
                                                [i[0] for i in av_data])
                                            fake_end_actual = max(
                                                [i[1] for i in av_data])
                                            count_gaps_fake = 3
                                            for i in find_gaps(
                                                    av_data)["gap_intervals"]:
                                                fake_start = i[0]
                                                fake_end = i[1]
                                                fake_gaps_bool = self.model.NewBoolVar(
                                                    f"fake_gaps_bool-{count_gaps_fake}")
                                                fake_gaps_start_int = self.model.NewIntVar(
                                                    fake_start_actual, fake_end_actual,
                                                    f"fake_gaps_start{count_gaps_fake}"
                                                )
                                                fake_gaps_end_int = self.model.NewIntVar(
                                                    fake_start_actual, fake_end_actual,
                                                    f"fake_gaps_end{count_gaps_fake}"
                                                )
                                                fake_gaps_duration_int = self.model.NewIntVar(
                                                    0, fake_end_actual - fake_start_actual,
                                                    f"dur{count_gaps_fake}")
                                                fake_interval = self.model.NewOptionalIntervalVar(
                                                    fake_gaps_start_int,
                                                    fake_gaps_duration_int, fake_gaps_end_int, fake_gaps_bool,
                                                    f"fake{count_gaps_fake}")

                                                self.model.Add(fake_gaps_duration_int > 0).OnlyEnforceIf(
                                                    fake_gaps_bool)
                                                self.model.Add(fake_gaps_duration_int == 0).OnlyEnforceIf(
                                                    fake_gaps_bool.Not())
                                                self.model.Add(
                                                    fake_gaps_start_int <= fake_start)
                                                self.model.Add(
                                                    fake_gaps_end_int >= fake_end)
                                                clients_gaps_interval.append(
                                                    fake_interval)
                                                clients_gaps_duration.append(
                                                    fake_gaps_duration_int)
                                                count_gaps_fake += 1
                                    except Exception as e:
                                        print("bazo_Error: ", e)
                                    fake_bol1 = self.model.NewBoolVar(
                                        f"fake1{user_a_id}")
                                    fake_bol2 = self.model.NewBoolVar(
                                        f"fake2{user_a_id}")
                                    if [i[0] for i in av_data] == [] or [i[1] for i in av_data] == []:
                                        continue
                                    fake_start = min([i[0] for i in av_data])
                                    fake_end = max([i[1] for i in av_data])
                                    gap_length = find_gaps(
                                        av_data)["gap_length"]
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

                                    self.fake_whites[user_a_id] = [
                                        fake1, fake2
                                    ] + clients_gaps_interval
                                    self.model.Add(fake_duration_int_1 > 0
                                                   ).OnlyEnforceIf(fake_bol1)
                                    self.model.Add(fake_duration_int_1 ==
                                                   0).OnlyEnforceIf(
                                                       fake_bol1.Not())
                                    self.model.Add(fake_duration_int_2 > 0
                                                   ).OnlyEnforceIf(fake_bol2)
                                    self.model.Add(fake_duration_int_2 ==
                                                   0).OnlyEnforceIf(
                                                       fake_bol2.Not())
                                    # fake_int_adam = self.model.NewIntVar(0,10000,"fake_int_for_adam")
                                    # self.fake_gap_durations.append(fake_int_adam)
                                    self.model.Add(
                                        fake_start_int_1 == fake_start)
                                    self.model.Add(fake_end_int_2 == fake_end)
                                    self.model.Add(
                                        sum(durations) + fake_duration_int_1 +
                                        fake_duration_int_2 +
                                        sum(clients_gaps_duration) ==
                                        fake_end - fake_start - c_max)
                                    if len(clients_gaps_duration) > 0:
                                        self.model.Add(
                                            sum(clients_gaps_duration) >=
                                            gap_length)
                                    if user_a_id in self.individual_fake_boolean.keys(
                                    ):
                                        self.individual_fake_boolean[
                                            user_a_id] += [
                                                fake_bol2, fake_bol1
                                        ]
                                    else:
                                        self.individual_fake_boolean[
                                            user_a_id] = [
                                                fake_bol2, fake_bol1
                                        ]
                                    # if user_a_id in self.fake_whites.keys():
                                    #     self.fake_whites[user_a_id] += [
                                    #         fake1, fake2
                                    #     ]
                                    # else:
                                    #     self.fake_whites[user_a_id] = [
                                    #         fake1, fake2
                                    #     ]

                                else:
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
                elif c["type"] == "sessionlength":
                    try:
                        for user_a in c['users_antecedent']:

                            user_a_id = self.solutions1.resources1.resources[
                                user_a].id
                            for index, x in enumerate(days_arrays):
                                print("bazo_today_index",self.var_data["today_index"])
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
                                                self.model.Add(dur[0] <= c_max)
                                                print("bazo_session_length: ",c_max,c_min2,str(index))
                                                if c_min != 0:

                                                    inc = 1
                                                    
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
                    for user_a in c["users_antecedent"]:
                        user_a_id = self.solutions1.resources1.resources[
                            user_a].id
                        for index in range(1, 6):
                            some_array = {}
                            for user_c in c['users_consequence']:
                                user_c_id = self.solutions1.resources1.resources[
                                    user_c].id
                                val_back_to_back = self.get_appointments(
                                    [[user_c_id], [user_a_id], [str(index)]])
                                # print("adam_want_some_print :", user_a_id,
                                #       user_c_id, val_back_to_back)
                                some_array.update(val_back_to_back)
                            len_back = len(some_array)
                            back_to_back_values = list(some_array.values())
                            for i1 in range(len_back):
                                for i2 in range(i1 + 1, len_back):
                                    # maybe we can add OnlyEnforceIf for bol values [6]
                                    some_or_bool = self.model.NewBoolVar(
                                        f"some-{user_a_id}")
                                    # print("worked_well")
                                    # self.model.AddMinEquality(
                                    #     some_or_bool, [
                                    #         back_to_back_values[i1][6],
                                    #         back_to_back_values[i2][6]
                                    #     ])
                                    # self.model.Add(
                                    #     back_to_back_values[i1][6] +
                                    #     back_to_back_values[i2][6] ==
                                    #     2).OnlyEnforceIf(some_or_bool)
                                    # self.model.Add(
                                    #     back_to_back_values[i1][6] +
                                    #     back_to_back_values[i2][6] < 2
                                    # ).OnlyEnforceIf(some_or_bool.Not())
                                    self.model.Add(
                                        back_to_back_values[i1][3] !=
                                        back_to_back_values[i2][4])
                                    self.model.Add(
                                        back_to_back_values[i1][4] !=
                                        back_to_back_values[i2][3])
                elif c["type"] == "breakQuantity":
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
                                dur_therapy = sum(
                                    map(lambda num: num[0],
                                        therapy_val.values()))
                                dur_working = sum(
                                    map(lambda num: num[0], working.values()))

                                if len(break_val) > 0:
                                    # print("bazo_break_val: ", break_val)
                                    ii = 0
                                    xy_arr = []
                                    print("holly : ", list(
                                        map(lambda num: num,
                                            break_val.values())))
                                    for break_data in list(
                                            map(lambda num: num,
                                                break_val.values())):
                                        if not break_data[5] and not self.var_data["part1"]:
                                            self.model.Add(break_data[0] == 0)
                                            continue
                                        exist_bool = self.model.NewBoolVar(
                                            'exist_bool')
                                        print(
                                            f"bazo_break-{ii} : ", break_data)
                                        if not user_a_id in gaps_ids_arr:
                                            # print("error_found_break : ",
                                            #       user_a_id)
                                            av_data = av_arr_for_fake[
                                                user_a_id][index]
                                            if [i[0] for i in av_data] == [] or [i[1] for i in av_data] == []:
                                                continue
                                            fake_start = min(
                                                [i[0] for i in av_data])
                                            fake_end = max(
                                                [i[1] for i in av_data])
                                            bool_arr = [
                                                self.model.NewBoolVar(
                                                    f"fake_break_bool-{i}")
                                                for i in range(2)
                                            ]
                                            start_arr = [
                                                self.model.NewIntVar(
                                                    fake_start, fake_end,
                                                    f"fake_start_var-{i}")
                                                for i in range(2)
                                            ]
                                            end_arr = [
                                                self.model.NewIntVar(
                                                    fake_start, fake_end,
                                                    f"fake_end_var-{i}")
                                                for i in range(2)
                                            ]
                                            dur_arr = [
                                                self.model.NewIntVar(
                                                    0, fake_end - fake_start,
                                                    f"fake_dur_var-{i}")
                                                for i in range(2)
                                            ]
                                            interval_arr = [
                                                self.model.
                                                NewOptionalIntervalVar(
                                                    start_arr[i], dur_arr[i],
                                                    end_arr[i], bool_arr[i],
                                                    f"fake_interval_var-{i}")
                                                for i in range(2)
                                            ]
                                            for i in range(2):
                                                self.model.Add(dur_arr[i] > 0
                                                               ).OnlyEnforceIf(
                                                                   bool_arr[i])
                                                self.model.Add(
                                                    dur_arr[i] ==
                                                    0).OnlyEnforceIf(
                                                        bool_arr[i].Not())
                                            self.model.Add(
                                                start_arr[0] == fake_start)
                                            self.model.Add(
                                                end_arr[1] == fake_end)
                                            self.model.Add(
                                                break_data[4] -
                                                fake_start < dur_therapy +
                                                dur_arr[0]).OnlyEnforceIf(
                                                    exist_bool)
                                            self.model.Add(
                                                fake_end -
                                                break_data[3] < dur_therapy +
                                                dur_arr[1]).OnlyEnforceIf(
                                                    exist_bool)
                                            if user_a_id in self.fake_whites.keys(
                                            ):
                                                self.fake_whites[
                                                    user_a_id] += interval_arr
                                            else:
                                                self.fake_whites[
                                                    user_a_id] = interval_arr

                                        # bool1 = self.model.NewBoolVar(
                                        #     f"bool1{ii}")
                                        # bool2 = self.model.NewBoolVar(
                                        #     f"bool2{ii}")
                                        # self.model.Add(
                                        #     sum(gen_arr[ii]["left"]) > 0
                                        # ).OnlyEnforceIf(bool1)
                                        # self.model.Add(
                                        #     sum(gen_arr[ii]["left"]) ==
                                        #     0).OnlyEnforceIf(bool1.Not())
                                        # self.model.Add(
                                        #     sum(gen_arr[ii]["right"]) > 0
                                        # ).OnlyEnforceIf(bool2)
                                        # self.model.Add(
                                        #     sum(gen_arr[ii]["right"]) ==
                                        #     0).OnlyEnforceIf(bool2.Not())

                                        # xy = self.model.NewBoolVar('hello')

                                        # **
                                        self.model.Add(
                                            break_data[0] > 0).OnlyEnforceIf(
                                                exist_bool)
                                        self.model.Add(
                                            break_data[0] == 0).OnlyEnforceIf(
                                                exist_bool.Not())
                                        self.model.Add(
                                            dur_working >= int(c_max)
                                        ).OnlyEnforceIf(exist_bool)

                                        self.model.Add(dur_working < int(c_max)
                                                       ).OnlyEnforceIf(
                                                           exist_bool.Not())
                                        # xy_arr.append(xy)
                                        ii += 1
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

    def solve_model(self, data, timeconstraints, e_pair):
        self.data_insert(data)
        try:
            self.matches_frequency()
        except Exception as e:
            print("bazo_matches_frequency_error : ", e)
            traceback.print_exc()
        try:
            if self.var_data["settings"]['driveTime']:
                self.constraint_drive()
        except Exception as e:
            print("bazo_drive_error: " + str(e))
            traceback.print_exc()
        if self.var_data['is_overlap_constraint']:
            self.no_overlap(e_pair)
        try:
            self.objective(self.var_data["objectiveactivity"])
        except Exception as e:
            print("bazo_objective_error : ", e)
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
        self.availability.update(stat[0])
        max_h = {"max_hours": stat[0]}
        self.data.update(max_h)
        self.efficiency = stat[1]

        some_data = Get_Data(d)
        self.resources = some_data.res()
        employee_ids = []
        persons_ids = []
        client_ids = []
        # arr_of_overlap_allowed = [i['id'] for i in self.solution1.users if i["firstName"] == "iudchc22"]
        arr_of_overlap_allowed = [i['id'] for i in self.solution1.users if not i["overlap"]]
        for e in self.resources:
            if "Employee" in e["roles"]:
                employee_ids.append(e["id"])
            if "Person" in e["roles"]:
                persons_ids.append(e["id"])
            if "Client" in e["roles"]:
                client_ids.append(e["id"])
        people_ids23 = {'employee_ids': employee_ids, 'client_ids': client_ids}
        self.max_total_hours = max_possible_total_hours(stat[2], people_ids23, 15)
        ev_dd = [e for e in self.solution1.events2 if len(intersection(e["resourceIds"],arr_of_overlap_allowed)) == 0]
        print("bazo_ev_dd : ",ev_dd)
        no_overlap_events = events_overlap(ev_dd,self.resources)
        self.events = no_overlap_events[0]
        print("bazo_wow3 : ",self.events)
        fake_user_starts_ends = no_overlap_events[1]
        self.data["fake_user_starts_ends"] = fake_user_starts_ends
        self.data["clients_events_fake"] = no_overlap_events[2]
        self.overlaped_ids = no_overlap_events[-1]
        # print("bazo_events_fake :",fake_user_starts_ends)
        # self.data["weekly_events_data"] = weekly_events(self.solution1.events2,self.resources)
        self.data["weekly_events_data"] = {}
        print("here_is_ok_rocket2")
        self.gap_filler = []
        arr_poss = []
        for i in random.sample(self.solution1.events_poss,len(self.solution1.events_poss) //1) + random.sample(self.orange_data,len(self.orange_data) // 1):
            if data["start_date"] == i["new_start"] or True:
                arr_poss.append(i)
        event_arr = []
        self.event_possibly = arr_poss
        gg = []
        if len(data["teams"]) <= 1: 
            data["teams"] = get_groups_array(self.solution1, 20, persons_ids,arr_poss)
        for i in self.events:
            if str(data["start_date"]) == i["start"][:10]:
                arr_poss.append(i)
                event_arr.append(i)
        gg_data = {"gg": gg}
        self.data.update(gg_data)
        print("here_is_ok_rocket3")
        self.roles_hierarchy = some_data.get_roles_hierarchy()
        self.distance_matrix = some_data.get_distance_matrix()
        print("here_is_ok_rocket3",self.event_possibly)
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
        date_original = testing_data['start_date']
        print("ok_test_runner")
        start_date_original = datetime.datetime.strptime(date_original, "%Y-%m-%d")
        if self.data['part1']:
            some_arr_of_data = []
            for team in self.data['teams']:
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                true_team = [i[:-1] for i in team]
                for res in self.resources:
                    if 'Person' not in res['roles'] or team in res['branches']:
                        resources_team.append(res)
                for res in self.resources:
                    if 'Person' in res['roles'] and team in res['branches']:
                        resource_id_team.append(f'{res["id"]}a')
                    if 'Person' in res['roles'] and team not in res['branches']:
                        resource_id_team_not.append(f'{res["id"]}a')
                for dat in testing_data['actual_data']:
                    if self.data["lunch_id"] in dat['resourceIds']:
                        data2_team.append(dat)
                    if len(intersection(dat['resourceIds'],team)) >= 2 or True:
                        data2_team.append(dat)
                self.data.update({'true_team': true_team})
                d = {
                    'objectiveactivity': self.data["objectiveactivity"],
                    'start_date_original': start_date_original,
                    'resources_team': resources_team,
                    'data': self.data,
                    'date_original': date_original,
                    'data2_team': data2_team,
                }
                some_arr_of_data.append(d)
            with ThreadPoolExecutor() as executor:
                results = executor.map(self.test_insert, some_arr_of_data)
        else:
            for team in range(1):
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                for res in self.resources:
                    if 'Person' not in res['roles'] or True:
                        resources_team.append(res)
                for res in self.resources:
                    if 'Person' in res['roles'] and True:
                        resource_id_team.append(f'{res["id"]}a')
                    if 'Person' in res['roles'] and True:
                        resource_id_team_not.append(f'{res["id"]}a')
                for dat in testing_data['actual_data']:
                    if len(intersection(dat['resourceIds'],resource_id_team_not)) == 0 or True:
                        data2_team.append(dat)
                d = {
                    'objectiveactivity': self.data["objectiveactivity"],
                    'start_date_original': start_date_original,
                    'resources_team': resources_team,
                    'data': self.data,
                    'date_original': date_original,
                    'data2_team': data2_team,
                }
                return (self.test_insert(d))

    def calculate_efficiency(self):
        adam_max_total_hours = get_number_per_slot(self.solution1) / (60 // self.data['slot_length']) / (self.data['slot_length'] / 15)
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
        employees_total_duration = sum([v for i, v in self.efficiency.items() if i in employees_id])
        clients_total_duration = sum([v for i, v in self.efficiency.items() if i in clients_id])
        clients_total_availability = sum(self.availability["clients"].values())
        employees_total_availability = sum(self.availability["employees"].values())
        efficiency_data["total_employees_efficiency"] = round(employees_total_duration / employees_total_availability, 2)
        efficiency_data["total_clients_efficiency"] = round(clients_total_duration / clients_total_availability, 2)
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
        returned_arr = []
        objective_value = 0
        for _ in [self.data["objectiveactivity"]]:
            resources_used = []
            aut2 = Automate(resources_team, self.roles_hierarchy, data,resources_used, self.distance_matrix,self.solution1)
            aut2.solve_model(data2_team, self.time_constraints,self.event_pair)
            activity_list = aut2.find_ids_by_role(['Activity'])
            people_list = aut2.find_ids_by_role(['Employee'])
            people_appointments = {}
            for id in people_list:
                people_appointments[id] = []
            event_obj = {}
            teams_dict = {}
            if len(aut2.get_team_vals()) > 0:
                for k, v in aut2.get_team_vals().items():
                    teams_dict[k] = aut2.solver.Value(v)

            if aut2.printer.solution_count() != 0:
                for tup, event in aut2.resources1.slots.items():
                    if (aut2.solver.Value(event[0]) > 0 or (event[5] == True)):
                        resources_ids = tuple(list(tup)[3:])
                        first = tuple(list(tup)[:3])
                        if resources_ids in event_obj.keys():
                            event_obj[resources_ids].append(first)
                        else:
                            event_obj[resources_ids] = [first]
                del_arr = []


                for tup, slots in event_obj.items():
                    users = list(set(list(tup)))
                    for times in slots:
                        try:
                            str3 = times + tup
                            if str3 in aut2.resources1.slots.keys() and False == aut2.resources1.slots[str3][17]:
                                inte = aut2.solver.Value(aut2.resources1.slots[str3][0])
                                inte_start = aut2.solver.Value(aut2.resources1.slots[str3][3])
                                inte_end = aut2.solver.Value(aut2.resources1.slots[str3][4])
                                address = aut2.resources1.slots[str3][7]
                                loc_id = aut2.resources1.slots[str3][12]
                                loc_id2 = aut2.resources1.slots[str3][15]
                                scheduled = aut2.resources1.slots[str3][5]
                                delete_event = aut2.solver.Value(aut2.resources1.slots[str3][11])
                                update_event = aut2.solver.Value(aut2.resources1.slots[str3][16])
                                event_id = aut2.resources1.slots[str3][9]
                                delete_event_id = aut2.resources1.slots[str3][9]
                                try:
                                    if delete_event == 0 and update_event == 1:
                                        del_arr.append(delete_event_id)
                                        for del_event in aut2.deletable_events:
                                            if del_event["id"] == delete_event_id:
                                                type_delete = {"type": "delete"}
                                                some_dict_for_delete = find_from_resources(self.resources,del_event["resourceIds"])
                                                type_delete.update(del_event)
                                                type_delete.update(some_dict_for_delete)
                                                self.deletingEvents.append(type_delete)
                                                self.deleted_hours += calculate_time_difference(type_delete["start"],type_delete["end_real_time"])
                                except Exception as e:
                                    print("bazo_Error : ", e)
                                objective_best_bound = aut2.get_best_objective_bound()
                                sum_del_bol_array = aut2.solver.Value(aut2.del_bol_array)
                                self.best_bound = objective_best_bound - sum_del_bol_array
                                self.status_name = aut2.solver.StatusName()
                                objective_val = aut2.solver.ObjectiveValue()

                                start = slot_to_time(inte_start, data['slot_length'])
                                end = slot_to_time(inte_end,data['slot_length'])
                                start_date_original = datetime.datetime.strptime(date_original, "%Y-%m-%d")
                                start_day = math.floor(inte_start /(24 * 60 // data['slot_length'])) - datetime.datetime.strptime(date_original,'%Y-%m-%d').weekday() - 1
                                new_start = datetime.datetime.strftime(start_date_original + datetime.timedelta(days=start_day), "%Y-%m-%d")
                                new_end = datetime.datetime.strftime(start_date_original + datetime.timedelta(days=start_day + 1),"%Y-%m-%d")

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
                                        new_start
                                    })
                                people_ids = self.efficiency.keys()
                                if len(intersection(people_ids,users)) > 0:
                                    ids_of_intersection = intersection(people_ids, users)
                                    for id in ids_of_intersection:
                                        dur = round(int(inte) *self.data['slot_length'] / 60,2)
                                        self.efficiency[id] += dur
                                if (len(intersection(users, activity_list))> 0):
                                    activity = intersection(users, activity_list)[0]
                                    all_obj = object_for_return(new_start, new_end, start, end,users, activity, loc_id2, address)
                                    self.all_appointments.append(all_obj)
                                if not scheduled or update_event == 0:
                                    if (len(intersection(users, activity_list)) >0):
                                        activity = intersection(users, activity_list)[0]
                                        my_obj = object_for_return(new_start, new_end, start, end,users, activity, loc_id2,address)
                                        returned_arr.append(my_obj)
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
                                        self.created_hours += calculate_time_difference(
                                            my_obj["data"]["start"],
                                            my_obj["data"]["end"])
                                        self.created_events.append(my_obj)
                        except Exception as e:
                            print("bazo_error : ", e)
                self.deleted_appointments_list = del_arr + self.overlaped_ids
                self.deletingEvents = self.deletingEvents + [{"id":i,"type": "delete"} for i in self.overlaped_ids] + aut2.over_availability_events
            try :
                for id, arr in people_appointments.items():

                    arr_sorted = sorted(arr,key=lambda x: datetime.datetime.strptime(x['start'], "%Y-%m-%dT%H:%M:%S.000Z"),reverse=False)
                    for i in range(len(arr_sorted) - 1):
                        new_list = arr_sorted[i:i + 2]
                        if self.data["settings"]['driveTime']:
                            loc1 = aut2.solutions1.user_uuid_to_index[new_list[0]
                                                                    ['loc_id']]
                            loc2 = aut2.solutions1.user_uuid_to_index[new_list[1]
                                                                    ['loc_id']]
                            user1_id = aut2.solutions1.users[loc1]["id"]
                            user2_id = aut2.solutions1.users[loc2]["id"]
                            
                            branchId1 = 'd'
                            branchId2 = 's'
                            if loc1:
                                branchId1 = aut2.solutions1.users[loc1][
                                    'branches'][0]
                            if loc2:
                                branchId2 = aut2.solutions1.users[loc2][
                                    'branches'][0]

                            if len(branchId1) > 1 and len(
                                    branchId2
                            ) > 1 and loc1 and loc2 and loc1 != loc2:
                                drive_time = aut2.solutions1.branches[branchId1][
                                    'drivetime']
                                user_tuples = tuple(sorted([user1_id,user2_id]))
                                if user_tuples in aut2.drive_time_data.keys():
                                    drive_time_r = aut2.drive_time_data[user_tuples] / 60
                                else:
                                    drive_time_r = 0
                                if drive_time_r > 0 and drive_time_r <= 15:
                                    drive_time = 15
                                if drive_time_r > 15 and drive_time_r <= 30:
                                    drive_time = 30
                                if drive_time_r > 30 and drive_time_r <= 45:
                                    drive_time = 45
                                if drive_time == 0 or not drive_time:
                                    drive_time = 30
                                else:
                                    # print('snoofy', drive_time)
                                    pass
                                date_string = new_list[0]['end']
                                date_object = datetime.datetime.strptime(
                                    date_string, '%Y-%m-%dT%H:%M:%S.%fZ')
                                new_date = date_object + datetime.timedelta(
                                    minutes=drive_time)
                                new_date_string = new_date.strftime(
                                    '%Y-%m-%dT%H:%M:%S.%fZ')
                                myobj = {
                                    'data': {
                                        'start':
                                        new_list[0]['end'],
                                        'end':
                                        new_date_string,
                                        'users': [id,aut2.var_data["drive_id"]],
                                        "resourceIds" : [id,aut2.var_data["drive_id"]],
                                        "orange_sol":
                                        False,
                                        'scheduled':
                                        True,
                                        'activity0Id':
                                        aut2.var_data["drive_id"],
                                        'notes':
                                        '',
                                        'frequency':
                                        'Weekly',
                                        'startRecur':
                                        new_list[0]['startRecur'],
                                        'endRecur':
                                        new_list[0]['endRecur'],
                                        'interval':
                                        1,
                                        "type": "create",
                                        'daysOfWeek': [
                                            day_ids[(datetime.datetime.strptime(
                                                new_list[0]['new_start'],
                                                '%Y-%m-%d').weekday() + 1) % 7]
                                        ]
                                    }
                                }
                                resources_with_names = find_from_resources(
                                                    self.resources,
                                                    myobj["data"]["users"])
                                myobj["data"].update(
                                                    resources_with_names)

                                returned_arr.append(myobj)
                                self.creatingEvents.append(myobj["data"])
            except Exception as e:
                print('*** drive_time_error', e)
                traceback.print_exc()  # Print to console
                
        gc.collect()
        
        return {
            'returned_arr': returned_arr,
            'objective_value': objective_value,
            "status": "status",
            "created_events": self.created_events
        }

    def part_one(self):
        dd = self.data
        print("ok_part_one")
        try:
            self.rocket(dd)
        except Exception as e:
            print("bazo_error : ",e)
        print("ok_part_one_after")
        a = self.calculate_efficiency()
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
        a = self.calculate_efficiency()
        c = {
            "creatingEvents": self.creatingEvents,
            "deletingEvents": self.deletingEvents,
            "updatingEvents": self.updatingEvents,
            "statistics": a
        }
        return c

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
    sols = solution_getter(data)
    obj = {}
    result = []
    arr = []
    day_arr = []
    print("here_is_fine")
    for i in range(num_of_days):
        a = data.copy()
        a['start_date'] = sd
        a['end_date'] = sd
        sd = (d2 + datetime.timedelta(days=i + 1)).strftime("%Y-%m-%d")
        day = get_weekday_index(sd)
        day_arr.append(day)
        a['today_index'] = day
        x = {"data": a, "int": i}
        obj[sd] = []
        arr.append(x)
    for i in arr:
        i_data = i['data']
        if i_data["part1"]:
            i_data["sol_1"] = sols[0]
            i_data["sol_2"] = sols[1]
            i_data["sol_3"] = sols[2]
            i_data["percentage"] = 0
            print("bazo_data_ok : ",i_data)
            solver = Solver(i_data)
            result.append(solver.part_one())
            sols[0].created_events += solver.created_events
        else:
            i_data["sol_1"] = sols[0]
            i_data["sol_2"] = sols[1]
            i_data["sol_3"] = sols[2]
            i_data["sols_with_events"] = []
            solver = Solver(i_data)
            result.append(solver.part_two())
    return result


def solution_getter(a):
    # print("why_not : ", a)
    events_poss = []
    data_gatherer = []
    d1 = datetime.datetime.strptime(a['end_date'], "%Y-%m-%d")
    d2 = datetime.datetime.strptime(a['start_date'], "%Y-%m-%d")
    delta = d1 - d2
    start_date_original = datetime.datetime.strptime(a['start_date'],
                                                     "%Y-%m-%d")
    real_end_date = datetime.datetime.strftime(
        start_date_original + datetime.timedelta(days=int(delta.days) + 1),
        "%Y-%m-%d")
    data_gatherer = Data_Gatherer({
        **a, 'end_date': real_end_date,
        'is_events': True,
        "optimizer_sol": True

    })
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
    solutions2 = Solution_Generator(
        data_gatherer, {
            "is_orange": True,
            "is_session": False,
            "ignoreConstraintArray": a["uncheckOrangeSolutionConstraints"],
            "soft": True
        })

    events_poss = solutions1.main2()
    unmatch_poss_events = []
    unmatch_poss_events = solutions2.main2()
    unmatch_poss_events_new = []
    poss_events_obj = {}

    for event in events_poss:
        tup = tuple(event['resourceIds_r'])
        ev_now = set(
            solutions2.calc_availabilities(event['start'], event['end'],
                                           '%Y-%m-%dT%H:%M:%S.%fZ'))
        if tup in poss_events_obj.keys():
            poss_events_obj[tup] = poss_events_obj[tup].union(ev_now)
        else:
            poss_events_obj[tup] = ev_now

    for event in unmatch_poss_events:
        tup = tuple(event['resourceIds_r'])
        if tup in poss_events_obj.keys():
            ev_now = set(
                solutions2.calc_availabilities(
                    event['start'], event['end'],
                    '%Y-%m-%dT%H:%M:%S.%fZ')).difference(poss_events_obj[tup])
            detected = solutions2.detect_range(list(ev_now))
            for times in list(detected):
                start = solutions2.slot_to_time(times[0], 15)
                end = solutions2.slot_to_time(times[1], 15)
                start_date_original = datetime.datetime.strptime(
                    solutions2.start_date, "%Y-%m-%d")
                start_day = math.floor(
                    times[0] / (24 * 60 // 15)) - datetime.datetime.strptime(
                        solutions2.start_date, '%Y-%m-%d').weekday() - 1
                new_start = datetime.datetime.strftime(
                    start_date_original + datetime.timedelta(days=start_day),
                    "%Y-%m-%d")
                new_end = datetime.datetime.strftime(
                    start_date_original +
                    datetime.timedelta(days=start_day + 1), "%Y-%m-%d")

                full_start = f'{new_start}T{start}.000Z'
                full_end = f'{new_start}T{end}.000Z'

                obj = {**event, "start": full_start, "end": full_end}
                unmatch_poss_events_new.append(obj)
        else:
            unmatch_poss_events_new.append(event)
            
    a_orange = []
    for i in unmatch_poss_events_new:
        or_sol = i.copy()
        or_sol["orange_sol"] = True
        a_orange.append(or_sol)
    print("bazo_orange : ", len(events_poss),solutions1.events2)
    return [solutions1, solutions2, a_orange, events_poss]


def part1_part2_runner(data):
    print("yeah_bazo : ",data)
    data["optimizer_sol"] = True
    t1 = time.time()
    if data["part1"]:
        data["part2_in_part1"] = True
        data["percentage"] = 0
        data['is_orange'] == True
        data['max_time_in_seconds'] = 30.0
        res = []
        try:
            res = rocket_luncher2(data)
        except Exception as e:
            print("bazo_error: ",str(e))
        return res
    else:
        data["part2_in_part1"] = False
        data['max_time_in_seconds'] = 30.0
        data['is_orange'] == True
        data["percentage"] = 50
        res2 = rocket_luncher2(data)
        t2 = time.time()
        run_time = round(t2 - t1)
        for i in res2:
            i["statistics"]["run_time"] = run_time
        return res2




# Problem Idendification
    """
    1. Unnecessary commentted code needs to be removed --> False
    2. Functions and Classes need to be more clearly defined --> False
    3. Matches Frequency function needs to be refactored --> False
    4. Ortools needs proper upper limit for quick decisions --> False
    5. Avoid unnecessary variables,functions,classes and copy coding --> False
    """