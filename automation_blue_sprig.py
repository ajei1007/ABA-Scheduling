# ABA Scheduling Automation Script
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
        self.constraint_bols = []
        self.delete_bool = []

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
                    if len(
                            intersection(
                                roles,
                                self.roles_hierarchy[resource_role])) > 0:
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

    def objective(self, id):
        days_arrays = days_arr(self.var_data['slot_length'])
        index = self.var_data['today_index']
        print('guru_guru', index)
        val = self.get_appointments([
            self.find_ids_by_role(self.var_data['objective_role']),
            self.var_data["objectiveactivity"]
        ])
        undeleted_appointments = []
        del_bol_array = []

        for i in val.values():
            if i[5]:
                undeleted_appointments.append(i[0])
                del_bol_array.append(i[11])
        if self.var_data["percentage"] != 0:
            self.model.Add(
                sum(del_bol_array) >= int((
                    (100 - self.var_data["percentage"]) / 100) *
                                          len(del_bol_array)))

        if self.var_data["percentage"] == 0:
            self.model.Add(sum(del_bol_array) == len(del_bol_array))

        del_bol_array = self.delete_bool
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
        for i in map(lambda num: num, val.values()):
            target = self.model.NewIntVar(0, 1000000, f"target{j}")
            self.model.AddMultiplicationEquality(target, [i[0], i[0]])
            arr.append(target)
            if i[10]:
                orange_array.append(target)
                normal_orange_array.append(i[0])
                normal_orange_array.append(i[14])
            else:
                white_array.append(target)
                normal_white_array.append(i[0])
                normal_white_array.append(i[14])
            j += 1
        # self.model.Maximize(
        #     sum(arr) + sum(del_bol_array)
        #     + sum(self.constraint_bols)
        # )

        # self.model.Maximize(2 * sum(white_array) + sum(orange_array) +
        #                     sum(del_bol_array)
        #                     # + sum(self.constraint_bols)
        #
        #                      )
        if self.var_data["part1"]:
            self.model.Maximize(
                2 * sum(white_array) + sum(orange_array) + sum(del_bol_array) +
                sum(self.constraint_bols) +
                (sum(normal_white_array) + sum(normal_orange_array)) * 10000)

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
        #     c_dict[k] = int(1 * max_week * v / weekly_avb[k])
        # print('guru_guru', "success3")
        # for k, v in c_dict.items():
        #     therapy_val = self.get_appointments(
        #         [[k], self.var_data["objectiveactivity"],
        #          list(range(days_arrays[index], days_arrays[index + 1]))])
        #     total_sum.append(
        #         v * sum(map(lambda num: num[0], therapy_val.values())))

        # ## 3rd objective function
        # print("guru_bug_1")
        # new_obj = []
        # c_total_hours = 0
        # for k, v in mm_week["clients"].items():
        #     c_total_hours += v
        # c_total_hours = c_total_hours // self.var_data["slot_length"]
        # clients_ids = clients = self.find_ids_by_role(['Client'])
        # for client_id in clients_ids:
        #     client_val = self.get_appointments(
        #         [[client_id], self.var_data["objectiveactivity"],
        #          list(range(days_arrays[index], days_arrays[index + 1]))])
        #     new_obj.append(sum(map(lambda num: num[0], client_val.values())))
        # greater_than_zero = []
        # for i in list(map(lambda num: num[0], val.values())):
        #     gtb = self.model.NewBoolVar("gtb")
        #     self.model.Add(i > 0).OnlyEnforceIf(gtb)
        #     self.model.Add(i == 0).OnlyEnforceIf(gtb.Not())
        #     greater_than_zero.append(gtb)
        # self.model.Minimize(c_total_hours - sum(new_obj))
        # print("guru_bug_2")
        # ## End of 3rd objective function

        # self.model.Maximize(
        #     sum(map(lambda num: num[0], val.values())) + sum(del_bol_array))

        # self.model.Maximize(sum(total_sum) + sum(self.constraint_bols))
        # self.model.Maximize(
        #     sum(arr) + sum(del_bol_array) + sum(self.constraint_bols))
        if not self.var_data["part1"]:
            bl_arr = []
            for i in list(map(lambda num: num[0], val.values())):
                bl = self.model.NewBoolVar("bl")
                self.model.Add(i != 0).OnlyEnforceIf(bl)
                self.model.Add(i == 0).OnlyEnforceIf(bl.Not())
                bl_arr.append(bl)

            self.model.Maximize(
                sum(map(lambda num: num[0], val.values())) * 3 +
                sum(del_bol_array) + sum(self.constraint_bols))

    def solve(self):
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.var_data[
            'max_time_in_seconds']
        self.solver.parameters.log_search_progress = True
        self.solver.parameters.num_search_workers = 8
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
        waitlist_count = 1
        event_ids = []
        bug_arr = []
        # people = self.find_ids_by_role([self.var_data['insert_data_role']])
        people = self.find_ids_by_role(['Resource'])
        print('404_not_found : ', self.var_data["gg"])
        data_arr = data + self.created_events + self.var_data["gg"]

        if not self.var_data["part1"]:
            print('lalava', data_arr)

        priority_arr = []
        for info in data_arr:
            if 'priority' in info.keys():
                if type(info['priority']) == int:
                    priority = info['priority']
                    if priority not in priority_arr:
                        priority_arr.append(priority)
        priority_arr.sort(reverse=True)
        print('slifter', priority_arr)
        for info in data_arr:
            print('loohy', info)
            weight = 0
            if 'priority' in info.keys() and type(info['priority']) == int:
                weight += priority_arr.index(info['priority']) * 10000

            if "fdb7ccda-0062-4fdd-88e9-4fff4691e9ada" in info["resourceIds"]:
                print("break_found")
            if "fdb7ccda-0062-4fdd-88e9-4fff4691e9ad" in info["resourceIds"]:
                print("break_found2")

            "fdb7ccda-0062-4fdd-88e9-4fff4691e9ada"

            slots = time_to_int(info, self.var_data['slot_length'])
            interval_start = slots[0]
            duration = slots[1]
            interval_end = slots[2]
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
            resource_list_all = resource_list
            resource_list_people = intersection(resource_list, people)
            for r in list(combinations(resource_list_all, 2)):
                res1, res2 = r[0], r[1]
                if res1 in self.resources1.resources.keys(
                ) and res2 in self.resources1.resources.keys():
                    if res2 not in self.resources1.resources[res1].matches:
                        bol_match = self.model.NewBoolVar('hi')
                        self.resources1.resources[res1].matches[
                            res2] = bol_match
                        self.resources1.resources[res2].matches[
                            res1] = bol_match
                    if res2 not in self.resources1.resources[res1].matches2:
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
                            self.resources1.resources[res1].matches2_durations[
                                res2][i] = int_duration
                            self.resources1.resources[res2].matches2_durations[
                                res1][i] = int_duration
                            self.resources1.resources[res1].matches2_sessions[
                                res2][i] = int_session
                            self.resources1.resources[res2].matches2_sessions[
                                res1][i] = int_session
            if not info["scheduled"]:

                duration_int = self.model.NewIntVar(0, duration,
                                                    'session length')
                start_int = self.model.NewIntVar(interval_start, interval_end,
                                                 'start')
                end_int = self.model.NewIntVar(interval_start, interval_end,
                                               'end')
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
                        res1, res2 = r[0], r[1]
                        if self.resources1.resources[res1].waitlisted:
                            waitlist_count = waitlist_count - 1
                        if self.resources1.resources[res2].waitlisted:
                            waitlist_count = waitlist_count - 1
                        self.model.Add(duration_int == 0).OnlyEnforceIf(
                            self.resources1.resources[res1].matches[res2].Not(
                            ))
                        self.resources1.slots[
                            tuple([interval_start]) + tuple(resource_list)] = [
                                duration_int, self.resources1.resources[res1].
                                matches[res2].Not(), event_interval, start_int,
                                end_int, False, bol_appointment, address,
                                waitlist_count, info["id"], info["orange_sol"],
                                2, loc_id, yellow_sol, weight
                            ]

                else:
                    self.resources1.slots[tuple([interval_start]) +
                                          tuple(resource_list)] = [
                                              duration_int, 1, event_interval,
                                              start_int, end_int, False,
                                              bol_appointment, address,
                                              waitlist_count, info["id"],
                                              info["orange_sol"], 2, loc_id,
                                              yellow_sol, weight
                                          ]

            if info['scheduled']:
                orange_sol = False
                if "orange_sol" in info.keys():
                    orange_sol = info["orange_sol"]
                del_bol = self.model.NewBoolVar("del_bol")
                resource_list = list(set(info['resourceIds']))
                resource_list = [res for res in sorted(resource_list)]
                print(
                    'froohy',
                    duration,
                    resource_list,
                )
                duration_int = self.model.NewIntVar(0, duration, "some_dur")
                start_int = self.model.NewConstant(interval_start)
                end_int = self.model.NewConstant(interval_start + duration)
                event_interval = self.model.NewOptionalIntervalVar(
                    start_int, duration_int, end_int, del_bol, 'interval')

                if self.var_data['percentage'] == 0:
                    self.model.Add(duration_int == duration)
                else:
                    self.model.Add(
                        duration_int == duration).OnlyEnforceIf(del_bol)
                    self.model.Add(duration_int == 0).OnlyEnforceIf(
                        del_bol.Not())
                self.direct_events_sum += duration
                if info["id"] in event_ids:
                    continue
                else:
                    self.resources1.slots[tuple([interval_start]) +
                                          tuple(resource_list)] = [
                                              duration_int, 1, event_interval,
                                              start_int, end_int, True, 1,
                                              address, waitlist_count,
                                              info["id"], orange_sol, del_bol,
                                              loc_id, yellow_sol, weight
                                          ]
                    self.delete_bool.append(del_bol)

                event_ids.append(info["id"])
                event_ids = list(set(event_ids))

    def min_session(self):
        val = self.get_appointments([self.var_data["objectiveactivity"]])
        val = list(filter(lambda num: not num[5], val.values()))
        durations = list(map(lambda num: num[0], val))
        min_session_arr = min_session_array(self.var_data['slot_length'],
                                            self.var_data['min_session_dur'])
        max_slot = self.var_data["max_session_length"] // self.var_data[
            "slot_length"]
        print('flicky1', max_slot, min_session_arr)
        for dur in durations:
            for i in min_session_arr:
                self.model.Add(dur != i)
            print('flicky2', max_slot, dur)
            self.model.Add(dur <= max_slot)

    # def no_overlap(self, e_pair):
    #     for id in list(
    #             set(self.find_ids_by_role([self.var_data['overlap_role']]))):
    #         val = self.get_appointments([[id],
    #                                      self.find_ids_by_role(['Activity'])])
    #         if id == "e301d14c-10e3-4b52-a01b-8cd4d1d60a5b":
    #             print("Jenna_Roddey", val.values())
    #         if len(val) > 0:
    #             arr = val.values()
    #             flimp = list((map(lambda num: num[2], arr)))
    #             self.model.AddNoOverlap(flimp)

    def no_overlap(self, e_pair):
        for id in list(set(self.find_ids_by_role(["Client"]))):
            val = self.get_appointments([[id],
                                         self.find_ids_by_role(['Activity'])])

            if len(val) > 0:
                arr = val.values()
                flimp = list((map(lambda num: num[2], arr)))
                self.model.AddNoOverlap(flimp)
        for id in list(set(self.find_ids_by_role(["Employee"]))):
            val = self.get_appointments([[id],
                                         self.find_ids_by_role(['Activity'])])

            if len(val) > 0:
                arr = val.values()
                over_yellow = []
                over_normal = []
                for i in arr:
                    if i[13]:
                        print("Overlap_Found_Luckily_Bug")
                        over_yellow.append(i)
                    else:
                        over_normal.append(i)
                flimp1 = list((map(lambda num: num[2], over_yellow)))
                flimp2 = list((map(lambda num: num[2], over_normal)))
                self.model.AddNoOverlap(flimp1)
                self.model.AddNoOverlap(flimp2)

    def no_gap(self):
        days_arrays = days_arr(self.var_data['slot_length'])
        employees = self.find_ids_by_role(['Employee'])
        clients = self.find_ids_by_role(['Client'])
        for emp_id in clients:
            if self.resources1.resources[emp_id].firstName == 'Luis':
                pass
            for index, x in enumerate(days_arrays[1:]):
                # val = self.get_appointments(
                #     [[emp_id], clients,
                #      #  list(range(days_arrays[index - 1],
                #      #              x)),
                #      self.find_ids_by_role(['Activity'])])
                val = self.get_appointments(
                    [[emp_id], ['68d018cf-31db-4e76-9769-e04ddf12830c']])

                durations = list(map(lambda num: num[0], val.values()))
                # if len(durations) > 0:
                #     self.model.Add(sum(durations) <= 4)
        # for index, x in enumerate(days_arrays[1:]):
        #     print('doothy', index, x, list(range(days_arrays[1:][index - 1],
        #                                          x)))

        for index, x in enumerate(days_arrays):
            if index == self.var_data['today_index']:
                # if index != 0 and index < len(days_arrays)-2:
                for person_id in self.find_ids_by_role(
                    [self.var_data['no_gap_role']]):
                    pp = False
                    if person_id == "2995143d-5778-4ced-945b-81b9907a0d57":
                        pp = True
                    ok_gap_value = 0
                    max_value = 0
                    try:
                        if person_id in list(self.var_data['max_hours']
                                             ["employees"].keys()):
                            max_value = self.var_data["max_hours"]["employees"][
                                person_id] * 60 // self.var_data["slot_length"]
                        else:
                            max_value = self.var_data["max_hours"]["clients"][
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
                        [[person_id],
                         list(range(days_arrays[index],
                                    days_arrays[index + 1])),
                         self.find_ids_by_role(['Activity'])])
                    if val:
                        arr4 = []
                        arr5 = []
                        for e in list(map(lambda num: num, val.values())):
                            b3 = self.model.NewBoolVar('f')
                            target = self.model.NewIntVar(
                                0, 1000000000, 'snip1')
                            target2 = self.model.NewIntVar(
                                0, 1000000000, 'snip2')
                            target3 = self.model.NewIntVar(
                                0, 1000000000, 'snip3')
                            target4 = self.model.NewIntVar(
                                0, 1000000000, 'snip4')
                            self.model.Add(e[0] > 0).OnlyEnforceIf(b3)
                            self.model.Add(e[0] == 0).OnlyEnforceIf(b3.Not())
                            self.model.Add(target3 == 1).OnlyEnforceIf(b3)
                            self.model.Add(target4 == 1).OnlyEnforceIf(b3)
                            self.model.Add(target3 == 1000000).OnlyEnforceIf(
                                b3.Not())
                            self.model.Add(target4 == 0).OnlyEnforceIf(
                                b3.Not())
                            self.model.AddMultiplicationEquality(
                                target, [e[3], target3])
                            self.model.AddMultiplicationEquality(
                                target2, [e[4], target4])
                            arr4.append(target)
                            arr5.append(target2)

                        min = self.model.NewIntVar(0, 10000000000, 'snip5')
                        max = self.model.NewIntVar(0, 1000000000, 'snip6')
                        min_array = list(map(lambda num: num[3], val.values()))
                        max_array = list(map(lambda num: num[4], val.values()))
                        durations = list(map(lambda num: num[0], val.values()))
                        self.model.Add(sum(durations) <= int(max_value) + 1)
                        # self.model.AddMinEquality(min, min_array)
                        # self.model.AddMaxEquality(max, max_array)
                        self.model.AddMinEquality(min, arr4)
                        self.model.AddMaxEquality(max, arr5)

                        bol = self.model.NewBoolVar(f'{person_id}')
                        if True:
                            pass
                        if person_id in employees:
                            self.model.Add(sum(durations) >= max - min -
                                           8).OnlyEnforceIf(bol)
                            self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                                bol.Not())

                        elif person_id in clients:
                            self.model.Add(sum(durations) == max -
                                           min).OnlyEnforceIf(bol)
                            self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                                bol.Not())

    def lunch_constraints(self):
        days_arrays = days_arr(self.var_data['slot_length'])
        lunch_length = 30 // self.var_data['slot_length']
        for index, x in enumerate(days_arrays[1:]):
            if index == self.var_data['today_index']:
                for id in self.find_ids_by_role([self.var_data['lunch_role']]):
                    val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         [self.var_data["lunch_id"]]])
                    therapy_val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         self.var_data["objectiveactivity"]])
                    xy = self.model.NewBoolVar('hello')
                    dur_lunch = sum(map(lambda num: num[0], val.values()))
                    bol_lunch = sum(map(lambda num: num[6], val.values()))
                    self.model.Add(bol_lunch <= 1)

                    dur_therapy = sum(
                        map(lambda num: num[0], therapy_val.values()))

                    if (len(val) > 0):
                        self.model.Add(
                            dur_lunch == lunch_length).OnlyEnforceIf(xy)
                        self.model.Add(
                            dur_lunch + dur_therapy >= (30 + 360) //
                            self.var_data["slot_length"]).OnlyEnforceIf(xy)
                        self.model.Add(dur_lunch == 0).OnlyEnforceIf(xy.Not())
                        self.model.Add(
                            dur_therapy < 360 //
                            self.var_data["slot_length"]).OnlyEnforceIf(
                                xy.Not())

    def break_constraints(self):
        days_arrays = days_arr(self.var_data['slot_length'])
        break_length = 15 // self.var_data['slot_length']
        for index, x in enumerate(days_arrays[1:]):
            if index == self.var_data['today_index']:
                for id in self.find_ids_by_role([self.var_data['break_role']]):
                    break_val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         [self.var_data["break_id"]]])
                    therapy_val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         self.var_data["objectiveactivity"]])

                    dur_break = sum(map(lambda num: num[0],
                                        break_val.values()))
                    bol_break = sum(map(lambda num: num[6],
                                        break_val.values()))
                    # self.model.Add(bol_break <= 2)

                    b_bol1 = self.model.NewBoolVar("bol1")
                    b_bol2 = self.model.NewBoolVar("bol2")

                    arr_exists_bool = []

                    for break_data in list(
                            map(lambda num: num, break_val.values())):
                        m_bol = self.model.NewBoolVar("m_bol")
                        max_bool_arr = []
                        min_bool_arr = []
                        for info in list(
                                map(lambda num: num, therapy_val.values())):
                            d_bol_se = self.model.NewBoolVar("d_bol_se")
                            d_bol_es = self.model.NewBoolVar("d_bol_es")
                            not_zero = self.model.NewBoolVar("not_zero")

                            self.model.Add(
                                info[0] != 0).OnlyEnforceIf(not_zero)
                            self.model.Add(info[0] == 0).OnlyEnforceIf(
                                not_zero.Not())

                            target1 = self.model.NewBoolVar("target1")
                            target2 = self.model.NewBoolVar("target2")

                            self.model.Add(break_data[3] ==
                                           info[4]).OnlyEnforceIf(d_bol_se)
                            self.model.Add(
                                break_data[3] != info[4]).OnlyEnforceIf(
                                    d_bol_se.Not())
                            self.model.Add(break_data[4] ==
                                           info[3]).OnlyEnforceIf(d_bol_es)
                            self.model.Add(
                                break_data[4] != info[3]).OnlyEnforceIf(
                                    d_bol_es.Not())

                            self.model.AddMultiplicationEquality(
                                target1, [d_bol_es, not_zero])
                            self.model.AddMultiplicationEquality(
                                target2, [d_bol_se, not_zero])

                            max_bool_arr.append(target1)
                            min_bool_arr.append(target2)
                        self.model.Add(
                            sum(max_bool_arr) == 1).OnlyEnforceIf(m_bol)
                        self.model.Add(
                            sum(min_bool_arr) == 1).OnlyEnforceIf(m_bol)
                        arr_exists_bool.append(m_bol)

                    dur_therapy = sum(
                        map(lambda num: num[0], therapy_val.values()))

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

                    print("buggy_ford : ", break_val)
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

                            self.model.Add(break_data[0] == break_length
                                           ).OnlyEnforceIf(exist_bool)

                            self.model.Add(break_data[0] == 0).OnlyEnforceIf(
                                exist_bool.Not())

                            self.model.Add(
                                dur_therapy >= int(3.25 * 60 //
                                                   self.var_data['slot_length']
                                                   )).OnlyEnforceIf(exist_bool)

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
        constraint_drive = self.distance_matrix
        # drive_keys = constraint_drive.keys()
        days_arrays = days_arr(self.var_data['slot_length'])
        for index, x in enumerate(days_arrays):
            if index != 0:

                for id in self.find_ids_by_role(['Employee']):
                    val = self.get_appointments(
                        [[id],
                         list(range(days_arrays[index - 1], x)),
                         self.find_ids_by_role(['Activity'])])
                    for r in list(
                            combinations(map(lambda num: num, val.values()),
                                         2)):
                        res1 = r[0]
                        res2 = r[1]
                        address1 = res1[7]
                        address2 = res2[7]
                        loc1 = self.solutions1.user_uuid_to_index[res1[12]]
                        loc2 = self.solutions1.user_uuid_to_index[res2[12]]
                        # print('swoofy',loc1,loc2)
                        branchId1 = 'd'
                        branchId2 = 's'
                        if loc1:
                            # print('skooky',loc1,self.solutions1.users[loc1])
                            branchId1 = self.solutions1.users[loc1][
                                'branches'][0]
                        if loc2:
                            # print('skooky2',loc2,self.solutions1.users[loc2])
                            branchId2 = self.solutions1.users[loc2][
                                'branches'][0]
                        # print('sloofy',branchId1)
                        if len(branchId1) > 1 and len(
                                branchId2
                        ) > 1 and loc1 and loc2 and loc1 != loc2:

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
                                drive_time = self.solutions1.branches[
                                    branchId1]['drivetime']
                                if drive_time == 0 or not drive_time:
                                    drive_time = 30
                                else:
                                    print('snoofy', drive_time)
                                drive_time_slot = int(
                                    drive_time // self.var_data['slot_length'])
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

                                print('sloofy', end1, end2, start1, start2,
                                      duration1, duration2)

                                self.model.Add(newInt1 == max_end - min_end -
                                               duration2 - duration1)
                                self.model.Add(newInt1 >= drive_time_slot
                                               ).OnlyEnforceIf(newBol)
        print("OK_WITH : DRIVE_CONS")

    def matches_frequency(self):
        people = self.find_ids_by_role(["Resource"])
        days_arrays = days_arr(self.var_data['slot_length'])
        for person_id in people:
            # val = self.get_appointments([[person_id]])
            for person_id2 in self.resources1.resources[
                    person_id].matches2.keys():
                # val2 = self.get_appointments([[person_id2]], False, val)

                for index, x in enumerate(days_arrays):
                    if index == self.var_data['today_index']:
                        print('hello7', index, x,
                              list(range(days_arrays[index - 1], x)))
                        # val3 = self.get_appointments(
                        #     [list(range(days_arrays[index - 1], x))], False,
                        #     val2)
                        val3 = self.get_appointments([[person_id],
                                                      [person_id2]])
                        #  list(range(days_arrays[index - 1], x))])
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
                            # self.model.Add(sum(durations) == 0).OnlyEnforceIf(
                            #     matching_bol.Not())
                            # self.model.Add(
                            #     sum(durations) > 0).OnlyEnforceIf(matching_bol)
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
                    if c['frequency'] == 'session':
                        for index, x in enumerate(days_arrays):
                            if index == self.var_data['today_index']:
                                for user_c in c['users_consequence']:
                                    user_c_id = self.solutions1.resources1.resources[
                                        user_c].id
                                    val = self.get_appointments([[user_c_id],
                                                                 [user_a_id]])
                                    durations = list(
                                        map(lambda num: num[0], val.values()))
                                    for dur in durations:
                                        bol = self.model.NewBoolVar('y')
                                        inte = self.model.NewIntVar(
                                            0, 10000000000, 'snip1')
                                        # self.constraint_bols.append(bol)
                                        self.model.Add(
                                            inte == 1000).OnlyEnforceIf(bol)
                                        self.model.Add(
                                            inte == 0).OnlyEnforceIf(bol.Not())
                                        self.constraint_bols.append(inte)
                                        self.model.Add(dur <= c['max'] *
                                                       4).OnlyEnforceIf(bol)
                                        self.model.Add(dur >= c['min'] *
                                                       4).OnlyEnforceIf(bol)

                    if c["each_or_all_users"] == 'each':
                        if c['frequency'] == 'day':
                            for index, x in enumerate(days_arrays):
                                if index == self.var_data['today_index']:
                                    # if index != 0:
                                    for user_c in c['users_consequence']:
                                        print('lifterz5')
                                        bol = self.model.NewBoolVar('y')
                                        self.constraint_bols.append(bol)
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
                                        bol = self.model.NewBoolVar('y')
                                        inte = self.model.NewIntVar(
                                            0, 10000000000, 'snip1')
                                        # self.constraint_bols.append(bol)
                                        self.model.Add(inte == c['weight']
                                                       ).OnlyEnforceIf(bol)
                                        self.model.Add(
                                            inte == 0).OnlyEnforceIf(bol.Not())
                                        self.constraint_bols.append(inte)
                                        # self.constraint_bols.append(bol)
                                        self.model.Add(
                                            sum(arr) <= c['max'] *
                                            4).OnlyEnforceIf(bol)
                                        self.model.Add(
                                            sum(arr) >= c['min'] *
                                            4).OnlyEnforceIf(bol)
                                        self.model.Add(
                                            sum(arr) == 0).OnlyEnforceIf(
                                                bol.Not())

                        elif c['frequency'] == 'week':
                            for user_c in c['users_consequence']:
                                arr = []
                                for index, x in enumerate(days_arrays):
                                    if index == self.var_data['today_index']:
                                        # if index != 0:
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
                                bol = self.model.NewBoolVar('y')
                                self.constraint_bols.append(bol)
                                self.model.Add(sum(arr) <= c['max'] *
                                               4).OnlyEnforceIf(bol)
                                self.model.Add(sum(arr) >= c['min'] *
                                               4).OnlyEnforceIf(bol)
                                self.model.Add(sum(arr) == 0).OnlyEnforceIf(
                                    bol.Not())
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
                                    if len(arr) > 0:
                                        pass

                                        # newBol = self.model.NewBoolVar('l')
                                        self.model.Add(
                                            sum(arr) <= c['max'] * 4)
                                        # self.model.Add(sum(arr) == 0).OnlyEnforceIf(newBol.Not())

                                        self.model.Add(
                                            sum(arr) >= c['min'] * 4)
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
                                        elif user_c_id in self.resources1.resources.keys(
                                        ) and user_a_id in self.resources1.resources[
                                                user_c_id].matches2_durations.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_c_id].matches2_durations[
                                                    user_a_id][index - 1]
                                            arr.append(int_duration)
                            self.model.Add(sum(arr) <= c['max'] * 4)
                            self.model.Add(sum(arr) >= c['min'] * 4)

            elif c['type'] == 'session':
                for user_a in c['users_antecedent']:
                    user_a_id = self.solutions1.resources1.resources[user_a].id
                    if c['frequency'] == 'day':
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
                                    for user_c in c['users_consequence']:
                                        user_c_id = self.solutions1.resources1.resources[
                                            user_c].id
                                        if user_a_id in self.resources1.resources.keys(
                                        ) and user_c_id in self.resources1.resources[
                                                user_a_id].matches2_sessions.keys(
                                                ):
                                            int_duration = self.resources1.resources[
                                                user_a_id].matches2_sessions[
                                                    user_c_id][index - 1]
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

    def solve_model(self, data, timeconstraints, e_pair):

        self.data_insert(data)
        if self.var_data['is_minSession_constraint']:
            self.min_session()
        # if self.var_data['is_time_constraint']:
        #     self.time_constraints(timeconstraints)
        # if self.var_data['is_drive_constraint']:
        #     self.drive_constraints()
        if self.var_data['is_lunch_constraint']:
            self.lunch_constraints()
        if self.var_data['is_break_constraint']:
            self.break_constraints()
        # if self.var_data['is_team_constraint']:
        #     self.team_constraints(self.var_data['team_bounds'])
        if self.var_data['is_overlap_constraint']:
            self.no_overlap(e_pair)
        # if True:
        #     self.matches_frequency()
        # if True:
        #     self.constraint_drive()
        if self.var_data['is_noGap_constraint']:
            self.no_gap()

        self.objective(self.var_data["objectiveactivity"])
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
        self.availability.update(stat[0])
        max_h = {"max_hours": stat[0]}
        self.data.update(max_h)
        self.efficiency = stat[1]

        some_data = Get_Data(d)
        self.resources = some_data.res()
        employee_ids = []
        persons_ids = []
        for e in self.resources:
            if "Employee" in e["roles"]:
                employee_ids.append(e["id"])
            if "Person" in e["roles"]:
                persons_ids.append(e["id"])
        print("my_fav_person", persons_ids)
        # solution to
        print("some_emp_ids:", employee_ids)
        # self.events = some_data.get_events()
        self.events = self.solution1.events2

        self.gap_filler = []
        # self.event_possibly = some_data.get_direct_activities()
        # self.event_possibly = self.solution1.events_poss
        arr_poss = []
        print('ploort', len(self.solution1.events_poss), len(self.orange_data))
        for i in random.sample(
                self.solution1.events_poss, len(
                    self.solution1.events_poss)) + random.sample(
                        self.orange_data,
                        len(self.orange_data) // 1):
            if data["start_date"] == i["new_start"]:
                arr_poss.append(i)
        event_arr = []
        # if data['is_orange']:
        #     for i in self.solution2.events_poss:
        #         if data["start_date"] == i["new_start"]:
        #             arr_poss.append(i)

        self.event_possibly = arr_poss
        gg = gap_finder(arr_poss, stat[2])

        if len(data["teams"]) <= 1 and data[
                "branch"] == "85f80da7-bdbf-4be4-81bb-3b5cefb9fe35":
            data["teams"] = get_groups_array(arr_poss, 20, persons_ids)

        for i in self.solution1.events2:
            if str(data["start_date"]) == i["start"][:10]:
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
        if self.data['part1'] and False:
            some_arr_of_data = []
            for team in self.data['teams']:
                resources_team = []
                resource_id_team = []
                resource_id_team_not = []
                data2_team = []
                for res in self.resources:
                    if 'Person' not in res['roles'] or team in res['branches']:
                        resources_team.append(res)
                for res in self.resources:
                    if 'Person' in res['roles'] and team in res['branches']:
                        resource_id_team.append(f'{res["id"]}a')
                    if 'Person' in res['roles'] and team not in res['branches']:
                        resource_id_team_not.append(f'{res["id"]}a')
                for dat in testing_data['actual_data']:
                    # if len(
                    #         intersection(dat['resourceIds'],
                    #                      resource_id_team_not)) == 0:

                    #     data2_team.append(dat)
                    if self.data["lunch_id"] in dat['resourceIds']:
                        data2_team.append(dat)
                    if len(intersection(dat['resourceIds'], team)) == 2:

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
                some_arr_of_data.append(d)
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
                    if 'Person' in res['roles'] and True:
                        resource_id_team_not.append(f'{res["id"]}a')
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
        efficiency_data = {
            "total_efficiency": 0.0,
            "total_employees_efficiency": 0.0,
            "total_clients_efficiency": 0.0,
            "employees_efficiency": {},
            "clients_efficiency": {},
            "upper_bound": 0,
            "founded_solution": 0,
            "status": "",
            "orange_solution_ratio": 0.0,
            "deleted_appointments": [],
            "deleted_appointments_number": 0,
        }
        total_availability = 0
        # print("inside_calc : ", self.availability)
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
        clients_total_availability = sum(self.availability["clients"].values())
        employees_total_availability = sum(
            self.availability["employees"].values())
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
        efficiency_data['upper_bound'] = self.best_bound
        efficiency_data["founded_solution"] = self.founded
        # print("eff_cal : ", efficiency_data)
        self.response = efficiency_data
        return efficiency_data

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
        for act_id in [self.data["objectiveactivity"]]:
            day = 0
            resources_used = []
            aut2 = Automate(resources_team, self.roles_hierarchy, data,
                            resources_used, self.distance_matrix,
                            self.solution1)
            aut2.solve_model(data2_team, self.time_constraints,
                             self.event_pair)
            # resources_used += aut2.resources_yes
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
                        resources_ids = tuple(list(tup)[1:])
                        slot = list(tup)[0]
                        if resources_ids in event_obj.keys():
                            event_obj[resources_ids].append(slot)
                        else:
                            event_obj[resources_ids] = [slot]
                del_arr = []
                for tup, slots in event_obj.items():

                    users = list(set(list(tup)))
                    for times in detect_range(list(sorted(set(slots)))):
                        inte = aut2.solver.Value(
                            aut2.resources1.slots[tuple([int(times[0])]) +
                                                  tup][0])
                        inte_start = aut2.solver.Value(
                            aut2.resources1.slots[tuple([int(times[0])]) +
                                                  tup][3])
                        inte_end = aut2.solver.Value(
                            aut2.resources1.slots[tuple([int(times[0])]) +
                                                  tup][4])
                        address = aut2.resources1.slots[tuple([int(times[0])])
                                                        + tup][7]
                        loc_id = aut2.resources1.slots[tuple([int(times[0])]) +
                                                       tup][12]
                        scheduled = aut2.resources1.slots[
                            tuple([int(times[0])]) + tup][5]
                        delete_event = aut2.solver.Value(
                            aut2.resources1.slots[tuple([int(times[0])]) +
                                                  tup][11])

                        delete_event_id = aut2.resources1.slots[
                            tuple([int(times[0])]) + tup][9]
                        if delete_event == 0:
                            del_arr.append(delete_event_id)

                        objective_best_bound = aut2.get_best_objective_bound()

                        sum_del_bol_array = aut2.solver.Value(
                            aut2.del_bol_array)

                        self.best_bound = objective_best_bound - sum_del_bol_array

                        self.status_name = aut2.solver.StatusName()

                        objective_val = aut2.solver.ObjectiveValue()

                        self.founded = objective_val - sum_del_bol_array

                        start = slot_to_time(inte_start, data['slot_length'])
                        end = slot_to_time(inte_end, data['slot_length'])
                        start_date_original = datetime.datetime.strptime(
                            date_original, "%Y-%m-%d")
                        start_day = math.floor(
                            inte_start / (24 * 60 // data['slot_length'])
                        ) - datetime.datetime.strptime(
                            date_original, '%Y-%m-%d').weekday() - 1
                        new_start = datetime.datetime.strftime(
                            start_date_original +
                            datetime.timedelta(days=start_day), "%Y-%m-%d")
                        new_end = datetime.datetime.strftime(
                            start_date_original +
                            datetime.timedelta(days=start_day + 1), "%Y-%m-%d")

                        for peep_id in intersection(users, people_list):
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
                        if len(intersection(people_ids, users)) > 0:
                            ids_of_intersection = intersection(
                                people_ids, users)
                            for id in ids_of_intersection:
                                dur = round(
                                    int(inte) * self.data['slot_length'] / 60,
                                    2)
                                self.efficiency[id] += dur
                        if not scheduled:
                            if (len(intersection(users, activity_list)) > 0):
                                activity = intersection(users,
                                                        activity_list)[0]
                                my_obj = object_for_return(
                                    new_start, new_end, start, end, users,
                                    activity, loc_id, address)
                                returned_arr.append(my_obj)
                                if not data['optimize_current']:
                                    host = data['host']
                                    response = requests.post(
                                        f'{host}/events',
                                        headers=data['header'],
                                        json=my_obj)
                                self.created_events.append(my_obj)
                self.deleted_appointments_list = del_arr
                response = requests.post(f'{host}/events/remove/multiple',
                                         headers=data['header'],
                                         json={
                                             "toBeDeletedIds": del_arr,
                                             "pushNotification": {
                                                 "send": False,
                                                 "message": "",
                                                 "to": []
                                             }
                                         })
            distance_matrix_keys = aut2.distance_matrix.keys()
            # print('sneebler1', people_appointments)
            # for id, arr in people_appointments.items():
            #     arr_sorted = sorted(arr,
            #                         key=lambda x: datetime.datetime.strptime(
            #                             x['start'], "%Y-%m-%dT%H:%M:%S.000Z"),
            #                         reverse=False)
            #     # print('sneebler5', people_appointments)
            #     for i in range(len(arr_sorted) - 1):
            #         new_list = arr_sorted[i:i + 2]
            #         address1 = new_list[0]['address']
            #         address2 = new_list[1]['address']
            #         # print('sloofyer5', new_list[0]['loc_id'],
            #         #       new_list[1]['loc_id'])
            #         # if new_list[0]['loc_id'] in aut2.solutions1.user_uuid_to_index.keys() and new_list[1]['loc_id'] in aut2.solutions1.user_uuid_to_index.keys():
            #         if True:
            #             loc1 = aut2.solutions1.user_uuid_to_index[new_list[0]
            #                                                       ['loc_id']]
            #             loc2 = aut2.solutions1.user_uuid_to_index[new_list[1]
            #                                                       ['loc_id']]

            #             branchId1 = 'd'
            #             branchId2 = 's'
            #             if loc1:
            #                 print('skooky')
            #                 branchId1 = aut2.solutions1.users[loc1][
            #                     'branches'][0]
            #             if loc2:
            #                 print('skooky2')
            #                 branchId2 = aut2.solutions1.users[loc2][
            #                     'branches'][0]

            #             if len(branchId1) > 1 and len(
            #                     branchId2) > 1 and loc1 and loc2 and len(
            #                         loc1) > 1 and len(
            #                             loc2) > 1 and loc1 != loc2:

            #                 # if (address1 and address2 and len(address2) > 0
            #                 #         and len(address1) > 0
            #                 #         and address1 in distance_matrix_keys):
            #                 #     if (address2 in aut2.distance_matrix[address1].keys()
            #                 #             and
            #                 #             aut2.distance_matrix[address1][address2][1]):
            #                 drive_time = aut2.solutions1.branches[branchId1][
            #                     'drivetime']
            #                 if drive_time == 0 or not drive_time:
            #                     drive_time = 30
            #                 else:
            #                     print('snoofy', drive_time)
            #                 drive_time_slot = int(drive_time //
            #                                       aut2.var_data['slot_length'])
            #                 # drive_time = ceil_to_multiple(
            #                 #     aut2.distance_matrix[address1][address2][1] /
            #                 #     60.0, data['slot_length'])
            #                 # drive_time_slot = int(drive_time //
            #                 #                     data['slot_length'])
            #                 date_string = new_list[0]['end']
            #                 date_object = datetime.datetime.strptime(
            #                     date_string, '%Y-%m-%dT%H:%M:%S.%fZ')
            #                 new_date = date_object + datetime.timedelta(
            #                     minutes=drive_time)
            #                 new_date_string = new_date.strftime(
            #                     '%Y-%m-%dT%H:%M:%S.%fZ')
            #                 print('hiffy', aut2.var_data["drive_id"])

            #                 myobj = {
            #                     'data': {
            #                         'start':
            #                         new_list[0]['end'],
            #                         'end':
            #                         new_date_string,
            #                         'users': [id],
            #                         'activity0Id':
            #                         aut2.var_data["drive_id"],
            #                         'notes':
            #                         '',
            #                         'frequency':
            #                         'Weekly',
            #                         'startRecur':
            #                         new_list[0]['startRecur'],
            #                         'endRecur':
            #                         new_list[0]['endRecur'],
            #                         'interval':
            #                         1,
            #                         'daysOfWeek': [
            #                             day_ids[(datetime.datetime.strptime(
            #                                 new_list[0]['new_start'],
            #                                 '%Y-%m-%d').weekday() + 1) % 7]
            #                         ]
            #                     }
            #                 }
            #                 returned_arr.append(myobj)
            #                 print('herro1')
            #                 if not data['optimize_current']:
            #                     print('herro2', myobj)
            #                     host = data['host']
            #                     response = requests.post(
            #                         f'{host}/events',
            #                         headers=data['header'],
            #                         json=myobj)
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

        return a

    def part_two(self):
        dd = self.data

        self.rocket(dd)
        a = self.calculate_efficiency()
        return a

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
    sols = solution_getter(data)
    av = availabilities(data["host"], data["header"], s, e, data["branch"])

    nested_dict = av[0]

    combined_dict = {
        k: v
        for sub_dict in nested_dict.values() for k, v in sub_dict.items()
    }

    obj = {}
    result = []
    arr = []
    day_arr = []
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

    # for i in solution1:
    #     if i["new_start"] in obj.keys():
    #         obj[i["new_start"]].append(i)
    e_arr = []
    for i in arr:
        i_data = i['data']
        if i_data["part1"]:
            i_data["sol_1"] = sols[0]
            i_data["sol_2"] = sols[1]
            i_data["sol_3"] = []

            # i_data['today_index'] = day
            i_data["weekly_avb"] = combined_dict
            i_data["percentage"] = 0
            solver = Solver(i_data)
            result.append(solver.part_one())
            sols[0].created_events += solver.created_events
            # i_data['is_orange'] == True
            # i_data["sol_3"] = sols[2]
            # i_data['part1'] = False
            # solver = Solver(i_data)
            # result.append(solver.part_one())
            sols[0].created_events += solver.created_events
        else:
            i_data["part1"] = False
            i_data["is_lunch_constraint"] = True
            i_data["is_lunch"] = True
            # i_data['is_events'] = False
            # sols = solution_getter(i_data)
            i_data["weekly_avb"] = combined_dict
            # i_data['today_index'] = day
            i_data["sol_1"] = sols[0]
            i_data["sol_2"] = sols[1]
            i_data["sol_3"] = sols[2]
            print("wakavu_data : ", i_data)
            solver = Solver(i_data)
            result.append(solver.part_two())
    return result


def solution_getter(a):
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
    data_gatherer = Data_Gatherer({
        **a, 'end_date': real_end_date,
        'is_events': True
        # a['part1']
    })
    # print('sooty', data_gatherer.events)
    solutions1 = Solution_Generator(
        data_gatherer, {
            "is_orange": False,
            "is_session": False,
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

    # solutions2 = Solution_Generator(data_gatherer, {"is_orange": True})
    # events_poss = solutions1.main2()
    # events_poss = solutions1.main3()
    # print('simily4')
    solutions1.all_main()
    # events_poss = solutions1.events_poss

    events_poss_white = []
    events_poss_orange = []
    # for event in events_poss:
    #     if len(event['reasons']) == 0:
    #         events_poss_white.append(event)
    #     else:
    #         events_poss_orange.append(event)
    unmatch_poss_events = []
    # unmatch_poss_events = solutions2.main2()
    # print('simily1')
    unmatch_poss_events = solutions2.main2()
    # print('simily2')
    unmatch_poss_events = solutions2.main3()
    # print('simily3')
    unmatch_poss_events_new = []
    poss_events_obj = {}
    unmatch_poss_events_obj = {}
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

    # events_poss_orange = solutions2.main2()
    # events_poss_orange = solutions2.main3()
    # print('baz_bug', events_poss)
    # events_poss = solutions1.main3()
    ######
    events_poss_obj = {
        'intersections': [],
        'poss_events': events_poss,
        'unmatch_poss_events': unmatch_poss_events_new
        # 'poss_events': events_poss_white,
        # 'unmatch_poss_events': events_poss_orange
    }
    a_orange = []
    for i in unmatch_poss_events_new:
        or_sol = i.copy()
        or_sol["orange_sol"] = True
        a_orange.append(or_sol)
    print("my_fav_arr : ", solutions1.events_poss + unmatch_poss_events_new)
    # print("debug_orange_2 : ", solutions1.events_poss)
    # print("debug_orange_3 : ", a_orange)

    return [solutions1, solutions2, a_orange]


def rocket_luncher_blue_sprig(data):
    if data["part1"]:

        data['is_orange'] == False
        data['max_time_in_seconds'] = 120.0
        res = rocket_luncher2(data)
        data["part1"] = False
        data['is_orange'] == True
        data["percentage"] = 10
        data['max_time_in_seconds'] = 150.0
        return rocket_luncher2(data)
        # return res
    else:
        return rocket_luncher2(data)
