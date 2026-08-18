import time
import datetime
import requests
import itertools
import pickle
import base64
from ortools.sat.python import cp_model

day_ids = {
    0: '20770718-a98e-499f-ae8b-c395f0f743bb',
    1: '2d0599e7-2729-49ee-acbe-ede6de8ad9b7',
    2: '3260c7e7-c57b-4144-803f-7db9cf88393c',
    3: '56cbe76a-0cf6-4647-8a49-2ef9fd102079',
    4: '6d92706c-9bb1-447e-bf74-572609066663',
    5: 'ecd70b60-3fef-4d43-9181-2f9db60e19fe',
    6: 'fa2adb44-e5ba-4586-ae19-5f1e1767228d',
}

def intersection(lst1, lst2):
    return [value for value in lst1 if value in lst2]

def time_to_slot(t, day, minutes, s=None):
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

def slot_to_time(slot, slot_interval):
    slots_per_day = 24 * 60 // slot_interval
    slots_per_hour = 60 // slot_interval
    hours = str((slot % slots_per_day) // slots_per_hour).zfill(2)
    minutes = str(
        (slot % slots_per_day % slots_per_hour) * slot_interval).zfill(2)
    seconds = '00'
    return hours + ':' + minutes + ':' + seconds

def get_user_ids(self, role_name, type_str='roles'):
    indexes = set()
    for i, user in enumerate(self.users):
        if role_name in user[type_str]:
            indexes.add(i)
    return indexes

def get_weekday_index(date_string):
    date = datetime.datetime.strptime(date_string, "%Y-%m-%d")
    return date.weekday()

def get_week_start_end(date_str):
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    start_of_week = date - datetime.timedelta(days=date.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=4)
    week_dates = [(start_of_week + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6)]
    start_of_week_str = start_of_week.strftime("%Y-%m-%d")
    end_of_week_str = end_of_week.strftime("%Y-%m-%d")
    
    return {"start":start_of_week_str, "end":end_of_week_str,"week_dates":week_dates}

def intersection(lst1, lst2):
    return [value for value in lst1 if value in lst2]

def calculate_total_hours(intervals):
    if len(intervals) == 0:
        return 0
    intervals = [
        {"start": datetime.datetime.fromisoformat(interval["start"]), "end": datetime.datetime.fromisoformat(interval["end"])}
        for interval in intervals
    ]
    intervals.sort(key=lambda x: x["start"])
    merged_intervals = []
    current_interval = intervals[0]

    for interval in intervals[1:]:
        if interval["start"] <= current_interval["end"]:
            current_interval["end"] = max(current_interval["end"], interval["end"])
        else:
            merged_intervals.append(current_interval)
            current_interval = interval
    
    merged_intervals.append(current_interval)
    total_duration = sum((interval["end"] - interval["start"]).total_seconds() for interval in merged_intervals)
    total_hours = total_duration / 3600
    
    return total_hours

def availabilities(host, header, start, end, branch):
    print('limoz',start,end)
    resource = requests.get(f'{host}/scheduler/resources?branches={branch}&start={start}&end={end}',
                            headers=header)
    res = requests.get(
        f'{host}/scheduler/availabilities?start={start}&end={end}&branches={branch}',
        headers=header)
    people = []
    clients = []
    employees = []
    for i in resource.json():
        if "Person" in i["roles"]:
            people.append(i["id"])
        if "Client" in i["roles"]:
            clients.append(i["id"])
        if "Employee" in i["roles"]:
            employees.append(i["id"])
    a = {}
    b = {}
    c = {"employee_ids": employees, "client_ids": clients}
    d = {}
    final_hours_dict = {}
    test_data = res.json()
    for i in people:
        b[i] = 0
        d[i] = []
        final_hours_dict[i] = 0
    employees_dict = {}
    clients_dict = {}
    for i in res.json():
        start = datetime.datetime.fromisoformat(i["start"].replace(
            'Z', '+00:00'))
        end = datetime.datetime.fromisoformat(i["end"].replace('Z', '+00:00'))
        duration_hours = (end - start).total_seconds() / 3600
        _id = intersection(people, i["resourceIds"])
        if len(_id) > 0:
            if _id[0] in employees:
                d[_id[0]].append({"start" : i["start"][:-6],"end" : i["end"][:-6]})
                if _id[0] in employees_dict.keys():
                    employees_dict[_id[0]] += duration_hours
                else:
                    employees_dict[_id[0]] = duration_hours
            else:
                if _id[0] in clients_dict.keys():
                    clients_dict[_id[0]] += duration_hours
                else:
                    clients_dict[_id[0]] = duration_hours
            a[_id[0]] = duration_hours
    
    for k,v in d.items():
        final_hours_dict[k] = calculate_total_hours(v)
    return [{
        "employees": employees_dict,
        "clients": clients_dict
    }, b, test_data, c,final_hours_dict]

def generate_time_slots(data, slot_length):
    start_time = datetime.datetime.fromisoformat(data['start'])
    end_time = datetime.datetime.fromisoformat(data['end'])

    time_difference = end_time - start_time

    slot_duration = datetime.timedelta(minutes=slot_length)

    time_slots = []

    current_time = start_time
    while current_time + slot_duration <= end_time:
        time_slots.append(int(current_time.timestamp()))
        current_time += slot_duration

    return time_slots

def max_possible_total_hours(raw_input, ids_dict, slot_length):
    employees_array = []
    clients_array = []
    for i in raw_input:
        if i["resourceIds"][0] in ids_dict["employee_ids"]:
            employees_array = employees_array + generate_time_slots(
                i, slot_length)
        elif i["resourceIds"][0] in ids_dict["client_ids"]:
            clients_array = clients_array + generate_time_slots(i, slot_length)
    abs_min = min(min(employees_array), min(clients_array))
    abs_max = max(max(employees_array), max(clients_array))
    dict_count_employees = {i: 0 for i in range(abs_min, abs_max + 1)}
    dict_count_clients = {i: 0 for i in range(abs_min, abs_max + 1)}

    for i in employees_array:
        dict_count_employees[i] += 1

    for i in clients_array:
        dict_count_clients[i] += 1

    res = 0

    for i in dict_count_clients.keys():
        res += min(dict_count_clients[i], dict_count_employees[i])

    return res / (60 // slot_length)

def find_overlapping_events(events):
    overlaps = []
    graph = {}
    
    for i in range(len(events)):
        graph[i] = []
        for j in range(len(events)):
            if i != j:
                event1 = events[i]
                event2 = events[j]
                start1 = event1['start']
                end1 = event1['end']
                start2 = event2['start']
                end2 = event2['end']
                if (start1 <= end2 and start2 <= start1) or (end1 <= end2 and start2 <= end1) or (start2 <= end1 and start1 <= start2) or (end2 <= end1 and start1 <= end2):
                    graph[i].append(j)
    
    visited = set()
    
    def dfs(node, group):
        if node in visited:
            return
        visited.add(node)
        group.append(node)
        for neighbor in graph[node]:
            dfs(neighbor, group)
    
    for i in range(len(events)):
        if i not in visited:
            group = []
            dfs(i, group)
            overlaps.append(group)
    
    grouped_overlaps = []
    for group in overlaps:
        grouped_events = [events[i] for i in group]
        grouped_overlaps.append(grouped_events)
    
    res = {"ids":set(),"fakes":[]}
    x_count = 1000
    for i in grouped_overlaps:
        
        if len(i) > 1:
            for j in i:
                _idd = x_count
                if "id"  in j.keys():
                    _idd = j["id"]
                res["ids"].add(_idd)
            res["fakes"].append({"start":min([x["start"] for x in i]),
                                 "end":max([x["end"] for x in i]),
                                 "resourceIds":[],
                                 "title":"fake",
                                 "scheduled":True,
                                 "loc_id" : None,
                                 "address":""
                                 })        
    return res

def merge_overlapping_events(events,id):
    if not events:
        return []

    sorted_events = sorted(events, key=lambda x: x['start'])
    merged_intervals = [sorted_events[0]]

    for event in sorted_events[1:]:
        last_merged = merged_intervals[-1]
        if event['start'] <= last_merged['end']:
            last_merged['end'] = max(last_merged['end'], event['end'])
        else:
            merged_intervals.append(event)
    
    return merged_intervals

def events_overlap(events_data,resources):
    overlaped_events_ids = []
    people = []
    clients = []
    for i in resources:
        if "Person" in i["roles"]:
            people.append(i["id"])
        if "Client" in i["roles"]:
            clients.append(i["id"])
    events_by_user_ids = {}
    for _id in people:
        events_by_user_ids[_id] = []
    set_people = set(people)
    set_events_ids = set()
    for event in events_data:
        set_events_ids.add(event["id"])
        for res_id in set_people.intersection(set(event["resourceIds"])):
            events_by_user_ids[res_id].append(event)
    delete_ids = []
    users_overlap = {}
    for usr in events_by_user_ids.keys():
        users_overlap[usr] = find_overlapping_events(events_by_user_ids[usr])
    for usr in users_overlap.keys():
        delete_ids += list(users_overlap[usr]["ids"])
    delete_ids = set(delete_ids)
    events_ids_dict = {i:True for i in set_events_ids}
    delete_ids_dict = {i:False for i in delete_ids}
    events_ids_dict.update(delete_ids_dict)
    res_events = []
    res_clients = {}
    res_clients_arr = []
    for event in events_data:
        if not events_ids_dict[event["id"]]:
            inters = list(set_people.intersection(set(event["resourceIds"])))
            for i in inters:
                users_overlap[i]["fakes"].append(event)
        else:
            res_events.append(event)
    for id in people:
        temp = users_overlap[id]["fakes"]
        users_overlap[id]["fakes"] = merge_overlapping_events(users_overlap[id]["fakes"],id)
        ress = []
        for i in temp:
            if id in i["resourceIds"]:
                i["resourceIds"].remove(id)
                ress.append(i)
        for ev_index in range(len(users_overlap[id]["fakes"])):
            users_overlap[id]["fakes"][ev_index]["resourceIds"].append(id)
        users_overlap[id]["fakes"] += ress
    return [res_events,users_overlap,res_clients,res_clients_arr,list(delete_ids)]

def weekly_events(events_data,resources):
    
    people = []
    activity = []
    for i in resources:
        if "Person" in i["roles"]:
            people.append(i["id"])
        if "Activity" in i["roles"]:
            activity.append(i["id"])
    dict_data_for_weekly_events = {}
    for i in people:
        dict_data_for_weekly_events[i] = {a:0 for a in activity}
    
    set_people = set(people)
    set_activity = set(activity)
    for event in events_data:
        
        start_time_str = event["start"]
        end_time_str = event["end"]
        start_time = datetime.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        end_time = datetime.datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        time_difference = end_time - start_time
        intersected_people = set_people.intersection(set(event["resourceIds"]))
        intersected_activity = set_activity.intersection(set(event["resourceIds"]))
        for i in intersected_people:
            for j in intersected_activity:
                dict_data_for_weekly_events[i][j] += int(time_difference.total_seconds()//60)
    return dict_data_for_weekly_events

def get_number_per_slot2(solution1, m, persons):
    model = cp_model.CpModel()
    n = len(persons)

    # groups = max(n // m, 2)
    groups = 1
    m = n // 1
    # print('simple', len(persons), m, persons)

    group_vars = {}

    for id in persons:
        person_var = model.NewIntVar(0, groups - 1, f'group{id}')
        group_vars[id] = person_var

    employees = []
    clients = []
    solution_arr = []
    slot_dict = {}
    users_slots_dict = {}
    employee_counted_obj = {}
    client_counted_obj = {}

    employee_counted_obj_ortools = {}
    client_counted_obj_ortools = {}
    for user in solution1.users:
        users_slots_dict = {**users_slots_dict, user['id']: []}
        if "Employee" in user['roles']:
            employees.append(user['id'])
        elif "Client" in user['roles']:
            clients.append(user['id'])
    for index, solution in enumerate(solution1.events_poss):
        people = intersection([i[:-1] for i in solution["resourceIds"]],
                              persons)

        if len(people) == 2:
            id1 = group_vars[people[0]]
            id2 = group_vars[people[1]]
            bol = model.NewBoolVar('f')
            model.Add(id1 == id2).OnlyEnforceIf(bol)
            model.Add(id1 != id2).OnlyEnforceIf(bol.Not())
            solution_arr.append(bol)
            for i in range(solution['start_r'], solution['end_r']):
                for res in solution['resourceIds']:
                    res1 = res[:-1]
                    if res1 in users_slots_dict.keys():
                        bol2 = model.NewBoolVar('f')
                        model.Add(bol2 == 1).OnlyEnforceIf(bol)
                        model.Add(bol2 == 0).OnlyEnforceIf(bol.Not())
                        # if i in users_slots_dict[res1]:
                        #     pass
                        # else:
                        if res1 in employees:
                            if i in employee_counted_obj.keys():
                                if i not in users_slots_dict[res1]:
                                    employee_counted_obj[i] += 1
                                if res1 in employee_counted_obj_ortools.keys():
                                    if i in employee_counted_obj_ortools[
                                            res1].keys():
                                        employee_counted_obj_ortools[res1][
                                            i].append(bol2)
                                    else:
                                        employee_counted_obj_ortools[res1] = {
                                            **employee_counted_obj_ortools[res1], i:
                                            [bol2]
                                        }
                                else:
                                    employee_counted_obj_ortools = {
                                        **employee_counted_obj_ortools, res1: {
                                            i: [bol2]
                                        }
                                    }
                            else:
                                # employee_counted_obj_ortools[i] = [bol2]
                                employee_counted_obj_ortools = {
                                    **employee_counted_obj_ortools, res1: {
                                        i: [bol2]
                                    }
                                }
                                if i not in users_slots_dict[res1]:
                                    employee_counted_obj = {
                                        **employee_counted_obj, i: 1
                                    }
                        elif res1 in clients:
                            if i in client_counted_obj.keys():
                                # client_counted_obj_ortools[i].append(bol2)
                                if i not in users_slots_dict[res1]:
                                    client_counted_obj[i] += 1
                                if res1 in client_counted_obj_ortools.keys():
                                    if i in client_counted_obj_ortools[
                                            res1].keys():
                                        client_counted_obj_ortools[res1][
                                            i].append(bol2)
                                    else:
                                        client_counted_obj_ortools[res1] = {
                                            **client_counted_obj_ortools[res1], i:
                                            [bol2]
                                        }
                                else:
                                    client_counted_obj_ortools = {
                                        **client_counted_obj_ortools, res1: {
                                            i: [bol2]
                                        }
                                    }
                            else:
                                # client_counted_obj_ortools[i] = [bol2]
                                client_counted_obj_ortools = {
                                    **client_counted_obj_ortools, res1: {
                                        i: [bol2]
                                    }
                                }
                                if i not in users_slots_dict[res1]:
                                    client_counted_obj = {
                                        **client_counted_obj, i: 1
                                    }
                        if i not in users_slots_dict[res1]:
                            users_slots_dict[res1].append(i)

    if groups > 1:
        for i in range(groups):
            equal_distribution = []
            for var in group_vars.values():
                temp = model.NewBoolVar("temp")
                model.Add(var == i).OnlyEnforceIf(temp)
                model.Add(var != i).OnlyEnforceIf(temp.Not())
                equal_distribution.append(temp)
            model.Add(sum(equal_distribution) <= m + 1)
            model.Add(sum(equal_distribution) >= m - 1)

    # print('emp_thing', employee_counted_obj)
    # print('client_thing', client_counted_obj)
    actual_counted_obj = {}
    actual_counted_obj_mckenna = {}

    cumulate_clients = {}
    cumulate_employees = {}

    for key, val in employee_counted_obj_ortools.items():
        for i, arr in val.items():
            bol = model.NewBoolVar('f')
            model.AddMaxEquality(bol, arr)

            if i in cumulate_employees.keys():
                cumulate_employees[i].append(bol)
            else:
                cumulate_employees = {**cumulate_employees, i: [bol]}

    arr_big = []

    for key, val in client_counted_obj_ortools.items():
        for i, arr in val.items():
            bol = model.NewBoolVar('f')
            model.AddMaxEquality(bol, arr)
            # bol2 = model.NewBoolVar('f')
            arr_big = [*arr_big, *arr]
            # model.Add(sum(arr) < 10)
            # model.Add(sum(arr) >= 10).OnlyEnforceIf(bol2)
            # model.Add(sum(arr) < 10).OnlyEnforceIf(bol2.Not())
            # arr_big.append(bol2)
            if i in cumulate_clients.keys():
                cumulate_clients[i].append(bol)
            else:
                cumulate_clients = {**cumulate_clients, i: [bol]}

    for key, val in client_counted_obj.items():
        if key in employee_counted_obj.keys():
            actual_counted_obj[key] = min(employee_counted_obj[key],
                                          client_counted_obj[key])
            actual_counted_obj_mckenna[key] = employee_counted_obj[key] - \
                client_counted_obj[key]

    actual_max_hours = 0
    for n in actual_counted_obj.values():
        actual_max_hours += n

    # print('herro', actual_counted_obj)
    # print('herro_mckenna', actual_counted_obj_mckenna)

    new_sol_arr = []
    for key, val in cumulate_clients.items():
        # print('sloofy2')
        if key in cumulate_employees.keys():
            # print('sloofy3')
            val2 = cumulate_employees[key]
            emp_int = model.NewIntVar(0, 10000, 'f')
            client_int = model.NewIntVar(0, 10000, 'f')
            # print('sloofy4')
            model.Add(sum(val) == client_int)
            model.Add(sum(val2) == emp_int)
            min_int = model.NewIntVar(0, 10000, 'f')
            new_sol_arr.append(min_int)
            # print('sloofy5')
            model.AddMinEquality(min_int, [emp_int, client_int])

    # Solve the model
    # print('sloofy6', actual_max_hours)
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    status = solver.Solve(model)
    model.Maximize(sum(new_sol_arr))
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        result = {}
        resum = 0
        for n in new_sol_arr:
            resum += solver.Value(n)
        for id in group_vars.keys():
            result[id] = solver.Value(group_vars[id])

        result_new = {}
        for key, value in result.items():
            result_new[key + "a"] = value
        return result_new

    return None

def get_number_per_slot(solution1):
    employees = []
    clients = []
    model = cp_model.CpModel()
    solution_arr = []
    slot_dict = {}
    users_slots_dict = {}
    employee_counted_obj = {}
    client_counted_obj = {}

    employee_counted_obj_ortools = {}
    client_counted_obj_ortools = {}
    for user in solution1.users:
        users_slots_dict = {**users_slots_dict, user['id']: []}
        if "Employee" in user['roles']:
            employees.append(user['id'])
        elif "Client" in user['roles']:
            clients.append(user['id'])
    for index, solution in enumerate(solution1.events_poss):
        bol = model.NewBoolVar('f')
        solution_arr.append(bol)

        for i in range(solution['start_r'], solution['end_r']):
            for res in solution['resourceIds']:
                res1 = res[:-1]
                if res1 in users_slots_dict.keys():
                    bol2 = model.NewBoolVar('f')
                    model.Add(bol2 == 1).OnlyEnforceIf(bol)
                    model.Add(bol2 == 0).OnlyEnforceIf(bol.Not())
                    # if i in users_slots_dict[res1]:
                    #     pass
                    # else:

                    if res1 in employees:
                        if i in employee_counted_obj.keys():
                            if i not in users_slots_dict[res1]:
                                employee_counted_obj[i] += 1
                            if res1 in employee_counted_obj_ortools.keys():
                                if i in employee_counted_obj_ortools[
                                        res1].keys():
                                    employee_counted_obj_ortools[res1][
                                        i].append(bol2)
                                else:
                                    employee_counted_obj_ortools[res1] = {
                                        **employee_counted_obj_ortools[res1], i:
                                        [bol2]
                                    }
                            else:
                                employee_counted_obj_ortools = {
                                    **employee_counted_obj_ortools, res1: {
                                        i: [bol2]
                                    }
                                }
                        else:
                            # employee_counted_obj_ortools[i] = [bol2]
                            employee_counted_obj_ortools = {
                                **employee_counted_obj_ortools, res1: {
                                    i: [bol2]
                                }
                            }
                            if i not in users_slots_dict[res1]:
                                employee_counted_obj = {
                                    **employee_counted_obj, i: 1
                                }
                    elif res1 in clients:
                        if i in client_counted_obj.keys():
                            # client_counted_obj_ortools[i].append(bol2)
                            if i not in users_slots_dict[res1]:
                                client_counted_obj[i] += 1
                            if res1 in client_counted_obj_ortools.keys():
                                if i in client_counted_obj_ortools[res1].keys(
                                ):
                                    client_counted_obj_ortools[res1][i].append(
                                        bol2)
                                else:
                                    client_counted_obj_ortools[res1] = {
                                        **client_counted_obj_ortools[res1], i:
                                        [bol2]
                                    }
                            else:
                                client_counted_obj_ortools = {
                                    **client_counted_obj_ortools, res1: {
                                        i: [bol2]
                                    }
                                }
                        else:
                            # client_counted_obj_ortools[i] = [bol2]
                            client_counted_obj_ortools = {
                                **client_counted_obj_ortools, res1: {
                                    i: [bol2]
                                }
                            }
                            if i not in users_slots_dict[res1]:
                                client_counted_obj = {
                                    **client_counted_obj, i: 1
                                }
                    if i not in users_slots_dict[res1]:
                        users_slots_dict[res1].append(i)
    actual_counted_obj = {}
    actual_counted_obj_mckenna = {}

    cumulate_clients = {}
    cumulate_employees = {}

    for key, val in employee_counted_obj_ortools.items():
        for i, arr in val.items():
            bol = model.NewBoolVar('f')
            model.AddMaxEquality(bol, arr)

            if i in cumulate_employees.keys():
                cumulate_employees[i].append(bol)
            else:
                cumulate_employees = {**cumulate_employees, i: [bol]}

    arr_big = []

    for key, val in client_counted_obj_ortools.items():
        for i, arr in val.items():
            bol = model.NewBoolVar('f')
            model.AddMaxEquality(bol, arr)
            arr_big = [*arr_big, *arr]
            model.Add(sum(arr) < 10)
            if i in cumulate_clients.keys():
                cumulate_clients[i].append(bol)
            else:
                cumulate_clients = {**cumulate_clients, i: [bol]}

    for key, val in client_counted_obj.items():
        if key in employee_counted_obj.keys():
            actual_counted_obj[key] = min(employee_counted_obj[key],
                                          client_counted_obj[key])
            actual_counted_obj_mckenna[key] = employee_counted_obj[key] - \
                client_counted_obj[key]

    actual_max_hours = 0
    for n in actual_counted_obj.values():
        actual_max_hours += n
    for key, val in cumulate_clients.items():
        if key in actual_counted_obj.keys():
            actual_number = min(actual_counted_obj[key], len(val))
            model.Add(sum(val) >= actual_number)
        else:
            model.Add(sum(val) == 0)

    for key, val in cumulate_employees.items():
        if key in actual_counted_obj.keys():
            # print('loomy2', actual_counted_obj[key], val, len(val))
            actual_number = min(actual_counted_obj[key], len(val))
            model.Add(sum(val) >= actual_number)
        else:
            model.Add(sum(val) == 0)
    return actual_max_hours

def get_number_per_slot_2(solution1):
    employees = []
    clients = []
    model = cp_model.CpModel()
    solution_arr = []
    slot_dict = {}
    users_slots_dict = {}
    employee_counted_obj = {}
    client_counted_obj = {}

    employee_counted_obj_ortools = {}
    client_counted_obj_ortools = {}
    for user in solution1["users"]:
        users_slots_dict = {**users_slots_dict, user['id']: []}
        if "Employee" in user['roles']:
            employees.append(user['id'])
        elif "Client" in user['roles']:
            clients.append(user['id'])
    for index, solution in enumerate(solution1["events_poss"]):
        bol = model.NewBoolVar('f')
        solution_arr.append(bol)

        for i in range(solution['start_r'], solution['end_r']):
            for res in solution['resourceIds']:
                res1 = res[:-1]
                if res1 in users_slots_dict.keys():
                    bol2 = model.NewBoolVar('f')
                    model.Add(bol2 == 1).OnlyEnforceIf(bol)
                    model.Add(bol2 == 0).OnlyEnforceIf(bol.Not())
                    # if i in users_slots_dict[res1]:
                    #     pass
                    # else:

                    if res1 in employees:
                        if i in employee_counted_obj.keys():
                            if i not in users_slots_dict[res1]:
                                employee_counted_obj[i] += 1
                            if res1 in employee_counted_obj_ortools.keys():
                                if i in employee_counted_obj_ortools[
                                        res1].keys():
                                    employee_counted_obj_ortools[res1][
                                        i].append(bol2)
                                else:
                                    employee_counted_obj_ortools[res1] = {
                                        **employee_counted_obj_ortools[res1], i:
                                        [bol2]
                                    }
                            else:
                                employee_counted_obj_ortools = {
                                    **employee_counted_obj_ortools, res1: {
                                        i: [bol2]
                                    }
                                }
                        else:
                            # employee_counted_obj_ortools[i] = [bol2]
                            employee_counted_obj_ortools = {
                                **employee_counted_obj_ortools, res1: {
                                    i: [bol2]
                                }
                            }
                            if i not in users_slots_dict[res1]:
                                employee_counted_obj = {
                                    **employee_counted_obj, i: 1
                                }
                    elif res1 in clients:
                        if i in client_counted_obj.keys():
                            # client_counted_obj_ortools[i].append(bol2)
                            if i not in users_slots_dict[res1]:
                                client_counted_obj[i] += 1
                            if res1 in client_counted_obj_ortools.keys():
                                if i in client_counted_obj_ortools[res1].keys(
                                ):
                                    client_counted_obj_ortools[res1][i].append(
                                        bol2)
                                else:
                                    client_counted_obj_ortools[res1] = {
                                        **client_counted_obj_ortools[res1], i:
                                        [bol2]
                                    }
                            else:
                                client_counted_obj_ortools = {
                                    **client_counted_obj_ortools, res1: {
                                        i: [bol2]
                                    }
                                }
                        else:
                            # client_counted_obj_ortools[i] = [bol2]
                            client_counted_obj_ortools = {
                                **client_counted_obj_ortools, res1: {
                                    i: [bol2]
                                }
                            }
                            if i not in users_slots_dict[res1]:
                                client_counted_obj = {
                                    **client_counted_obj, i: 1
                                }
                    if i not in users_slots_dict[res1]:
                        users_slots_dict[res1].append(i)
    actual_counted_obj = {}
    actual_counted_obj_mckenna = {}

    cumulate_clients = {}
    cumulate_employees = {}

    for key, val in employee_counted_obj_ortools.items():
        for i, arr in val.items():
            bol = model.NewBoolVar('f')
            model.AddMaxEquality(bol, arr)

            if i in cumulate_employees.keys():
                cumulate_employees[i].append(bol)
            else:
                cumulate_employees = {**cumulate_employees, i: [bol]}

    arr_big = []

    for key, val in client_counted_obj_ortools.items():
        for i, arr in val.items():
            bol = model.NewBoolVar('f')
            model.AddMaxEquality(bol, arr)
            arr_big = [*arr_big, *arr]
            model.Add(sum(arr) < 10)
            if i in cumulate_clients.keys():
                cumulate_clients[i].append(bol)
            else:
                cumulate_clients = {**cumulate_clients, i: [bol]}

    for key, val in client_counted_obj.items():
        if key in employee_counted_obj.keys():
            actual_counted_obj[key] = min(employee_counted_obj[key],
                                          client_counted_obj[key])
            actual_counted_obj_mckenna[key] = employee_counted_obj[key] - \
                client_counted_obj[key]

    actual_max_hours = 0
    for n in actual_counted_obj.values():
        actual_max_hours += n
    for key, val in cumulate_clients.items():
        if key in actual_counted_obj.keys():
            actual_number = min(actual_counted_obj[key], len(val))
            model.Add(sum(val) >= actual_number)
        else:
            model.Add(sum(val) == 0)

    for key, val in cumulate_employees.items():
        if key in actual_counted_obj.keys():
            # print('loomy2', actual_counted_obj[key], val, len(val))
            actual_number = min(actual_counted_obj[key], len(val))
            model.Add(sum(val) >= actual_number)
        else:
            model.Add(sum(val) == 0)
    return actual_max_hours


def get_groups_array(event_possibly, max_number, persons_ids, arr_poss):
    result = get_number_per_slot2(event_possibly, max_number, persons_ids)
    groups = []
    for i in range(max_number):
        var_ids = []
        for k, v in result.items():
            if v == i:
                var_ids.append(k)
        if var_ids != []:
            groups.append(var_ids)
    return groups

def days_arr(minute_interval):
    array = [1]
    slot_length = 60 // minute_interval
    for i in range(7):
        array.append((i + 1) * 24 * slot_length)
    return array

def time_to_int(data, slot_interval):
    start = datetime.datetime.strptime(data['start'], '%Y-%m-%dT%H:%M:%S.%fZ')
    weekday_number = start.strftime('%w')
    end = datetime.datetime.strptime(data['end'], '%Y-%m-%dT%H:%M:%S.%fZ')
    duration = int(
        (end - start).total_seconds() / 3600 * (60 // slot_interval))
    interval_start = time_to_slot(start.strftime('%H:%M:%S'),
                                  (start.weekday() + 1) % 7, slot_interval,
                                  "start")
    interval_end = time_to_slot(end.strftime('%H:%M:%S'),
                                (start.weekday() + 1) % 7, slot_interval,
                                "end")
    if interval_end < interval_start:
        interval_end = int(interval_end + 24*(60//slot_interval))
    return [interval_start, duration, interval_end, weekday_number]

def min_session_array(minute_interval, min_minute):
    return [i for i in range(1, 60) if i * minute_interval < min_minute]

def find_from_resources(resources, users_arr):
    d = {"activity": "Accelerate"}
    for one_info in resources:
        if one_info["id"] in users_arr:
            d[one_info["type"].lower()] = one_info["name"]
    return d

def calculate_time_difference(start, end):

    start_time = datetime.datetime.fromisoformat(
        start[:-1])  # Remove the trailing 'Z' and parse the timestamp
    end_time = datetime.datetime.fromisoformat(
        end[:-1])  # Remove the trailing 'Z' and parse the timestamp

    time_difference = end_time - start_time
    hours_difference = time_difference.total_seconds(
    ) / 3600  # Convert to hours

    return float(hours_difference)

def find_gaps(intervals):
    # Sort the intervals by their start values
    intervals.sort(key=lambda x: x[0])

    gaps = []
    prev_end = intervals[0][1]

    for interval in intervals[1:]:
        if interval[0] > prev_end:
            gap = (prev_end, interval[0])
            gaps.append(gap)
        prev_end = max(prev_end, interval[1])

    return {
        "gap_length": sum([i[1] - i[0] for i in gaps]),
        "gap_intervals": gaps
    }

def round_to_nearest_interval(time, interval):
    remainder = time % interval
    threshold = 0.333 * interval
    
    if remainder <= threshold:
        if (time - remainder) == 0:
            return interval
        return time - remainder
    else:
        return time + interval - remainder
    
def calculate_duration_hours(interval):
    start_time = datetime.datetime.fromisoformat(interval["start"].replace('Z', '+00:00'))
    end_time = datetime.datetime.fromisoformat(interval["end"].replace('Z', '+00:00'))
    duration_seconds = (end_time - start_time).total_seconds()
    weekday_index = start_time.weekday()
    duration_hours = duration_seconds / 3600
    return duration_hours,weekday_index

def object_for_return(new_start, new_end, start, end, users, activity, loc_id,
                      address, payload_start='',payload_end=''):
    start_time_str = f'{new_start}T{start}.000Z'
    end_time_str = f'{new_start}T{end}.000Z'
    start_time = datetime.datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
    end_time = datetime.datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
    if end_time < start_time:
        end_time += datetime.timedelta(days=1)
        end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')[:-3] + 'Z'
    
    date_obj = datetime.datetime.strptime(payload_start, "%Y-%m-%d")

    # Add one day to the datetime object
    new_date_obj = date_obj + datetime.timedelta(days=1)

    # Convert the new datetime object back to a string
    payload_end = new_date_obj.strftime("%Y-%m-%d")
    obj = {
        'start': start_time_str,
        'end': end_time_str,
        'users': list(set(users)),
        'resourceIds': list(set([i for i in users if i != loc_id and i != activity and len(i) > 1])),
        'activity0Id': activity,
        'address': address,
        'notes': '',
        'frequency': 'Weekly',
        'startRecur': f'{new_start}',
        # f'{payload_start}',
        'endRecur': f'{new_end}',
        # f'{payload_end}',
        'interval': 1,
        # 'sandboxMode': True,
        "orange_sol": False,
        'scheduled': True,
        "type": "create",
        'daysOfWeek': [
            day_ids[(datetime.datetime.strptime(new_start,
                                                '%Y-%m-%d').weekday() + 1) % 7]
        ]
    }

    if loc_id and len(loc_id) > 0:
        obj = {
            **obj,
            "location0Id": loc_id,
            "loc_id": loc_id,
        }

    my_obj = {'data': obj}

    return my_obj

def detect_range2(l):
    l.sort()
    ranges = []
    for i, j in itertools.groupby(enumerate(l), lambda x: x[1] - x[0]):
        j = list(j)
        ranges.append((j[0][1], j[-1][1]+1))
    return ranges

def serialize_instance(instance):
    binary_data = pickle.dumps(instance)
    return base64.b64encode(binary_data).decode("utf-8")


def deserialize_instance(serialized_data):
    binary_data = base64.b64decode(serialized_data)
    return pickle.loads(binary_data)

def normalize_time(timestamp):
    """Converts timestamp string to a standard format for comparison."""
    try:
        return datetime.datetime.strptime(timestamp.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f").strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.datetime.strptime(timestamp.replace("Z", ""), "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%dT%H:%M:%S")
    
def strip_microseconds(date_str):
    if '.' in date_str:
        date_str = date_str.split('.')[0]
    if date_str.endswith('Z'):
        date_str = date_str[:-1]
    return date_str