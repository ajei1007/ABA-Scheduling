# This file for abstracted functions.
import math
import time
import requests
import datetime
import itertools
import random
from ortools.sat.python import cp_model
from itertools import combinations
import pytz

day_ids = {
    0: '20770718-a98e-499f-ae8b-c395f0f743bb',
    1: '2d0599e7-2729-49ee-acbe-ede6de8ad9b7',
    2: '3260c7e7-c57b-4144-803f-7db9cf88393c',
    3: '56cbe76a-0cf6-4647-8a49-2ef9fd102079',
    4: '6d92706c-9bb1-447e-bf74-572609066663',
    5: 'ecd70b60-3fef-4d43-9181-2f9db60e19fe',
    6: 'fa2adb44-e5ba-4586-ae19-5f1e1767228d',
}


def haversine(lat1, lon1, lat2, lon2, unit='km'):
    # Earth radius in kilometers or miles
    radius = 6371 if unit == 'km' else 3959
    
    # Convert latitude and longitude from degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Difference in coordinates
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    
    # Haversine formula
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = radius * c
    
    return distance

def random_point_within_radius(latitude, longitude, distance, unit='km'):
    # Convert latitude and longitude from degrees to radians
    lat_rad = math.radians(latitude)
    lon_rad = math.radians(longitude)
    
    # Earth radius in kilometers or miles
    earth_radius = 6371.01 if unit == 'km' else 3958.76
    
    # Random distance within the given distance
    random_distance = random.uniform(0, distance)
    
    # Random bearing (direction) in radians
    random_bearing = random.uniform(0, 2 * math.pi)
    
    # Calculate the new latitude in radians
    new_lat_rad = math.asin(math.sin(lat_rad) * math.cos(random_distance / earth_radius) +
                            math.cos(lat_rad) * math.sin(random_distance / earth_radius) * math.cos(random_bearing))
    
    # Calculate the new longitude in radians
    new_lon_rad = lon_rad + math.atan2(math.sin(random_bearing) * math.sin(random_distance / earth_radius) * math.cos(lat_rad),
                                       math.cos(random_distance / earth_radius) - math.sin(lat_rad) * math.sin(new_lat_rad))
    
    # Convert the new latitude and longitude back to degrees
    new_latitude = math.degrees(new_lat_rad)
    new_longitude = math.degrees(new_lon_rad)
    
    return new_latitude, new_longitude

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

def round_to_nearest_interval(time, interval):
    """
    Rounds the time to the nearest multiple of 'interval'. If the time is within the first 30%
    of the interval, it rounds down; otherwise, it rounds up.

    :param time: The number to be rounded.
    :param interval: The interval to round to.
    :return: The rounded number.
    """
    # Calculate the remainder when 'time' is divided by 'interval'
    remainder = time % interval
    
    # Calculate the threshold for rounding down (30% of the interval)
    threshold = 0.333 * interval
    
    # Determine whether to round up or down based on the remainder
    print('thimmy',remainder,threshold,time)
    if remainder <= threshold:
        # Round down
        print('sooly1',time - remainder)
        if (time - remainder) == 0:
            return interval
        return time - remainder
    else:
        # Round up
        print('sooly2',time + interval - remainder)
        return time + interval - remainder


def intersection(lst1, lst2):
    return [value for value in lst1 if value in lst2]


# This function is converter for class Automate
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
    # if data["scheduled"]:
    #     print([interval_start, duration, interval_end])
    return [interval_start, duration, interval_end, weekday_number]


def min_session_array(minute_interval, min_minute):
    return [i for i in range(1, 60) if i * minute_interval < min_minute]


def days_arr(minute_interval):
    array = [1]
    slot_length = 60 // minute_interval
    for i in range(7):
        array.append((i + 1) * 24 * slot_length)
    return array


def create_bypass(x, incr):
    rx = []

    for id, array in x.items():
        inc = incr
        for j in array:
            a = {
                "id": "50c3a08d-6565-4d08-a62a-cc56c0a2a73b" + str(inc),
                "resourceIds": [id, "452bb872-180c-48f6-ae93-6ebb259597e9"],
                "title": "ByPass Activity",
                "canceledId": "",
                "address": "",
                "reasons": [],
                "people_drive_times": {
                    "start": {},
                    "end": {}
                },
                "distances_all": [],
                "times_all": [],
                "reasons_l": '',
                "priority": '',
                "start": j[0],
                "end": j[1],
                'scheduled': True
            }
            inc = inc + 1
            rx.append(a)
    return rx


def detect_range2(l):
    l.sort()
    ranges = []
    for i, j in itertools.groupby(enumerate(l), lambda x: x[1] - x[0]):
        j = list(j)
        ranges.append((j[0][1], j[-1][1]+1))
    return ranges


def gap_calc(array_of_start_end, minutes):
    x = []
    arr = []
    day = array_of_start_end[0]["start"][:10]
    for i in array_of_start_end:
        k, v = i["start"], i["end"]
        k = datetime.datetime.strptime(k, '%Y-%m-%dT%H:%M:%S.%fZ')
        s = time_to_slot(k.strftime('%H:%M:%S'), 1, minutes, "start")
        v = datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%fZ')
        e = time_to_slot(v.strftime('%H:%M:%S'), 1, minutes, "end")
        for tt in range(s, e + 1):
            arr.append(tt)
    r = detect_range2(sorted(list(set(arr))))
    # if len(r) == 1:
    for j in range(len(r) - 1):
        x.append([
            day + "T" + slot_to_time(r[j][1], minutes) + ".000Z",
            day + "T" + slot_to_time(r[j + 1][0], minutes) + ".000Z"
        ])
    return x


def gap_filler_2(arr, resources, some_minutes):
    people = []
    x_res = []
    for i in resources:
        if 'Person' in i['roles']:
            people.append(i['id'])
    inc = 0
    for i in arr:
        dict_people_availability = {}
        filler = []
        for id in people:
            dict_people_availability[id] = []
        for j in i:
            res_ids = [
                x[:-1] for x in j["resourceIds"] if j["scheduled"] == False
            ]
            for id in intersection(res_ids, people):
                dict_people_availability[id] = dict_people_availability[id] + [
                    {
                        'start': j["start"],
                        'end': j["end"]
                    }
                ]
        for k, v in dict_people_availability.items():
            if not dict_people_availability[k] == []:
                dict_people_availability[k] = gap_calc(
                    dict_people_availability[k], some_minutes)
        x_res.append(create_bypass(dict_people_availability, inc))
        inc = inc + 1

    return x_res


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
        'start':
        start_time_str,
        'end':
        end_time_str,
        'users':
        list(set(users)),
        'resourceIds':
        list(set([i for i in users if i != loc_id and i != activity and len(i) > 1])),
        'activity0Id':
        activity,
        'address':
        address,
        'notes':
        '',
        'frequency':
        'Weekly',
        'startRecur':
        f'{payload_start}',
        #f'{new_start}T{start}.000Z',
        'endRecur':
        f'{payload_end}',
        #f'{new_end}T{end}.000Z',
        'interval':
        1,
        # 'sandboxMode': True,
        "orange_sol":
        False,
        'scheduled':
        True,
        "type":
        "create",
        'daysOfWeek': [
            day_ids[(datetime.datetime.strptime(payload_start,
                                                '%Y-%m-%d').weekday() + 1) % 7]
        ]
    }
    # if "7bd835c3-7855-4855-a73e-f6b40b5b0dc4" in activity:
    #     print('jooly', loc_id, obj)

    if loc_id and len(loc_id) > 0:
        obj = {
            **obj,
            "location0Id": loc_id,
            "loc_id": loc_id,
        }
    # else:
    #     obj = {**obj, "location0Id": "7bd835c3-7855-4855-a73e-f6b40b5b0dc4", "loc_id":
    #            loc_id, }

    my_obj = {'data': obj}

    return my_obj


def convert_date_to_timezone(timezone_str,date):
    # Convert string to datetime
    date_start_final = datetime.datetime.strptime(date, "%Y-%m-%d")

    # Set timezone
    timezone = pytz.timezone(timezone_str)
    date_with_timezone = timezone.localize(date_start_final)
    # Format date with timezone offset
    formatted_date = date_with_timezone.isoformat()
    return formatted_date


def detect_range(l):
    l.sort()
    for i, j in itertools.groupby(enumerate(l), lambda x: x[1] - x[0]):
        j = list(j)
        yield j[0][1], j[-1][1] + 1


def ceil_to_multiple(number, multiple):
    return multiple * math.ceil(number / multiple)


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
        print("wkdb : ",[i["start"], i["end"]])
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


admin_act_id = "f472a7cf-39bf-44a0-9ddf-e30b67f7bd2c"  # it is for Blue Sprig


def all_combination(start_slot, end_slot, min_session, max_session):
    if end_slot - start_slot == 0:
        return []
    if end_slot - start_slot < min_session:
        return False

    arr = []

    for i in range(min_session, max_session + 1):
        res = all_combination(start_slot + i, end_slot, min_session,
                              max_session)
        if type(res) == list:
            if res == []:
                arr.append([(start_slot, start_slot + i)])
            else:
                for a in res:
                    arr.append([(start_slot, start_slot + i), *a])
    return arr


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
            # print('googy', n, solver.Value(n))
            resum += solver.Value(n)
        # print('real_slim', resum // 2, actual_max_hours // 2)
        for id in group_vars.keys():
            result[id] = solver.Value(group_vars[id])
            # print('looly', id, result[id])

        result_new = {}
        for key, value in result.items():
            result_new[key + "a"] = value
        return result_new

    return None
    # for key, val in cumulate_clients.items():
    #     if key in actual_counted_obj.keys():
    #         # print()
    #         print('loomy1', actual_counted_obj[key], val, len(val))
    #         actual_number = min(actual_counted_obj[key], len(val))
    #         model.Add(sum(val) >= actual_number)
    #     else:
    #         model.Add(sum(val) == 0)

    # for key, val in cumulate_employees.items():
    #     if key in actual_counted_obj.keys():
    #         print('loomy2', actual_counted_obj[key], val, len(val))
    #         actual_number = min(actual_counted_obj[key], len(val))
    #         model.Add(sum(val) >= actual_number)
    #     else:
    #         model.Add(sum(val) == 0)
    # model.Minimize(sum(solution_arr) - sum(arr_big)*1000)
    # solver = cp_model.CpSolver()
    # solver.parameters.log_search_progress = True
    # solver.parameters.num_search_workers = 8
    # solver.parameters.max_time_in_seconds = 60
    # # solver.log_callback = print
    # status = solver.Solve(model)
    # arr = []
    # for index, num in enumerate(solution_arr):
    #     print('answer', index, solver.Value(num))
    #     # arr.append(solver.Value(num))
    #     if solver.Value(num) == 1:
    #         arr.append(1)
    #     else:
    #         arr.append(0)
    return actual_max_hours


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
            model.Add(sum(arr) < 10)
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
    for key, val in cumulate_clients.items():
        if key in actual_counted_obj.keys():
            # print()
            # print('loomy1', actual_counted_obj[key], val, len(val))
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
    # model.Minimize(sum(solution_arr) - sum(arr_big)*1000)
    # solver = cp_model.CpSolver()
    # solver.parameters.log_search_progress = True
    # solver.parameters.num_search_workers = 8
    # solver.parameters.max_time_in_seconds = 60
    # # solver.log_callback = print
    # status = solver.Solve(model)
    # arr = []
    # for index, num in enumerate(solution_arr):
    #     print('answer', index, solver.Value(num))
    #     # arr.append(solver.Value(num))
    #     if solver.Value(num) == 1:
    #         arr.append(1)
    #     else:
    #         arr.append(0)
    return actual_max_hours


def create_blocks(selfie):
    # print('hooky1')
    # print('hooky2', selfie.var_data['true_team'])
    user_availabilities_general = selfie.solutions1.user_availabilities_general
    client_ids = list(
        set(selfie.find_ids_by_role(["Client"])).intersection(
            set(selfie.var_data['true_team'])))
    slot_length = selfie.var_data["slot_length"]
    ratio = slot_length // 15
    min_session = int(selfie.var_data['min_session_dur'] // slot_length)
    max_session = int(selfie.var_data["max_session_length"] // slot_length)
    # min_session = int(selfie.var_data['min_session_dur'])
    # max_session = int(selfie.var_data["max_session_length"])
    # print('liver5', selfie.var_data['min_session_dur'],
    #       int(selfie.var_data["max_session_length"]), min_session, max_session,
    #       slot_length)
    model = cp_model.CpModel()
    sum_to_minimize = 0
    block_obj = {}
    max_appointment_duration = max_session - min_session
    total_durations = []
    total_time = 0
    person_events = {}
    final_person_blocks = {}
    final_person_blocks2 = {}
    total_block_arr_all = []
    for id in client_ids:
        person_events[id] = {}
        final_person_blocks[id] = []
        final_person_blocks2[id] = []
        client_appointments = []
        # print('liver6', id, user_availabilities_general[id])
        total_block_arr = []
        for i in user_availabilities_general[id]:

            start = int(list(i)[0] // ratio)
            end = int(list(i)[1] // ratio)
            # block_arr = all_combination(start, end, min_session, max_session)
            block_arr = all_combination(start, end, 2, max_session)
            # print('sminty', start, end, min_session, max_session, id,
            #       block_arr)
            av_duration = end - start
            total_time += av_duration
            for b in block_arr:
                bol_block = model.NewBoolVar('f')
                obj = {"bol_block": bol_block, "b": b}
                total_block_arr.append(bol_block)
                total_block_arr_all.append(bol_block)
                b_arr = []
                for t in b:
                    start_b = int(list(t)[0])
                    end_b = int(list(t)[1])
                    time_tup = tuple([start_b, end_b])
                    if time_tup in block_obj.keys():
                        bol = block_obj[time_tup]['bol']
                        block_obj[time_tup]['num'] += av_duration
                    else:
                        bol = model.NewBoolVar('f')
                        block_obj[time_tup] = {"bol": bol, "num": av_duration}
                    b_arr.append(bol)
                # print('goohy', bol_block, b_arr)
                model.AddMinEquality(bol_block, b_arr)
                final_person_blocks[id].append(obj)
        # print('jooby', id, total_block_arr)
        model.Add(sum(total_block_arr) <= 3)

        # bol_appointment = model.NewBoolVar('f')
        # print('sirrah2')
        # duration_int = model.NewIntVar(
        #     0, new_end-new_start, f'session length')
        # print('sirrah3')
        # event_interval = model.NewOptionalIntervalVar(
        #     new_start, duration_int, new_end, bol_appointment, 't')
        # print('sirrah4')
        # tup_time = tuple([new_start, new_end])
        # person_events[id][tup_time] = bol_appointment
        # model.Add(duration_int == 0).OnlyEnforceIf(
        #     bol_appointment.Not())
        # print('sirrah5')
        # model.Add(duration_int == new_end -
        #             new_start).OnlyEnforceIf(bol_appointment)
        # print('sirrah6')
        # model.Add(bol_appointment ==
        #             0).OnlyEnforceIf(bol.Not())
        # model.Add(bol ==
        #             1).OnlyEnforceIf(bol_appointment)
        # total_durations.append(duration_int)
        # client_appointments.append(event_interval)
        # print('sirrah7')

        # print('gliffer8')
        # model.AddNoOverlap(client_appointments)
    # print('gliffer1', total_time)
    # # model.Add(sum(total_durations) >= total_time)
    # # model.Add(sum(total_durations) > 18)
    # print('gliffer2')
    tot = model.NewIntVar(0, 10000000, 'f')
    model.Add(sum(total_block_arr_all) == tot)
    # print('gliffer5')
    arr = []
    # HERE
    # for time_tup, value in block_obj.items():
    #     tot2 = model.NewIntVar(0, 10000000, 'f')
    #     model.Add(tot2 == value['num']).OnlyEnforceIf(value['bol'])
    #     model.Add(tot2 == 0).OnlyEnforceIf(value['bol'].Not())
    #     arr.append(tot2)
    # print('gliffer6')

    # tot2 = model.NewIntVar(0, 10000000, 'f')
    # model.Add(tot2 == sum(arr))
    # tot3 = model.NewIntVar(0, 10000000, 'f')
    # model.AddMultiplicationEquality(tot3, [tot, tot2])
    # print('gliffer7')
    # HERE
    # model.Minimize(sum(block_obj.values()))
    my_arr = []
    tup_arr = {}
    # print('loopy1')
    for id, val in final_person_blocks.items():
        for obj in val:
            for t in obj['b']:
                # print('loopy2', t, obj)
                if t in tup_arr.keys():
                    # print('loopy3')
                    tup_arr[t].append(obj["bol_block"])
                else:
                    # print('loopy4', obj, obj["bol_block"])
                    tup_arr[t] = [obj["bol_block"]]
    # print('loopy5')
    for tup, arr in tup_arr.items():
        b = model.NewBoolVar('f')
        my_arr.append(b)
        # print('loopy6')
        model.AddMaxEquality(b, arr)
        # print('loopy7')
    model.Maximize(tot * 1000 - sum(my_arr))
    # print('gliffer3', total_time)
    # Solve the model
    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.num_search_workers = 8
    solver.parameters.max_time_in_seconds = 60
    # solver.log_callback = print
    status = solver.Solve(model)
    # print('piver8', status, cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model)

    tup_arr = []

    # app = selfie.get_appointments([client_ids])
    if True or status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        result = {}

        for id in client_ids:
            for i in final_person_blocks[id]:
                if solver.Value(i['bol_block']) == 1:
                    final_person_blocks2[id].append(i['b'])

        # for id in client_ids:
        #     final_person_blocks[id] = []
        #     for tup, bol in person_events[id].items():
        #         if solver.Value(bol) == 1:
        #             final_person_blocks[id].append(tup)
        # print(f'Maximum of objective function : {solver.ObjectiveValue()}\n')
        # print('liver3')
        for tup, bol in block_obj.items():
            # print('floppy', solver.Value(bol['bol']))
            if solver.Value(bol['bol']) == 1:
                tup_arr.append(tup)
                # print('sniffer', tup)

    # print('stove', final_person_blocks2)

    return [total_time, tup_arr, final_person_blocks2]


# def create_blocks(selfie):
#     print('hooky1')
#     print('hooky2', selfie.var_data['true_team'])
#     user_availabilities_general = selfie.solutions1.user_availabilities_general
#     client_ids = list(set(selfie.find_ids_by_role(
#         ["Client"])).intersection(set(selfie.var_data['true_team'])))
#     slot_length = selfie.var_data["slot_length"]
#     ratio = slot_length // 15
#     min_session = int(selfie.var_data['min_session_dur'] // slot_length)
#     max_session = int(selfie.var_data["max_session_length"] // slot_length)
#     # min_session = int(selfie.var_data['min_session_dur'])
#     # max_session = int(selfie.var_data["max_session_length"])
#     print('liver5', selfie.var_data['min_session_dur'], int(
#         selfie.var_data["max_session_length"]), min_session, max_session, slot_length)
#     model = cp_model.CpModel()
#     sum_to_minimize = 0
#     block_obj = {}
#     max_appointment_duration = max_session-min_session
#     total_durations = []
#     total_time = 0
#     person_events = {}
#     final_person_blocks = {}
#     for id in client_ids:
#         person_events[id] = {}
#         final_person_blocks[id] = []
#         client_appointments = []
#         print('liver6', id, user_availabilities_general[id])
#         for i in user_availabilities_general[id]:

#             start = int(list(i)[0] // ratio)
#             end = int(list(i)[1] // ratio)
#             block_arr = all_combination(start,end,min_session,max_session)
#             for b in block_arr:
#                 bol_block = model.NewBoolVar('f')
#                 b_arr = []
#                 for t in b:
#                     start_b = int(list(t)[0])
#                     end_b = int(list(t)[1])
#                     time_tup = tuple([start_b, end_b])
#                     if time_tup in block_obj.keys():
#                         bol = block_obj[time_tup]
#                     else:
#                         bol = model.NewBoolVar('f')
#                         block_obj[time_tup] = bol
#                     b_arr.append(bol)
#                 model.AddMultiplicationEquality(bol_block,b_arr)

#             av_duration = end - start
#             total_time += av_duration
#             for dur in range(av_duration+1):
#                 print('liver7')
#                 new_start = start+dur
#                 print('floory2', new_start, end, start, dur)
#                 if new_start < end:
#                     print('floory1', end, min_session, max_session+1)
#                     for dur2 in range(min_session, max_session+1):
#                         print('liver8')
#                         new_end = new_start+dur2
#                         if new_end <= end:
#                             print('liver9')
#                             time_tup = tuple([new_start, new_end])
#                             print('liver111')
#                             if time_tup in block_obj.keys():
#                                 bol = block_obj[time_tup]
#                             else:
#                                 bol = model.NewBoolVar('f')
#                                 block_obj[time_tup] = bol
#                             print('sirrah1')
#                             bol_appointment = model.NewBoolVar('f')
#                             print('sirrah2')
#                             duration_int = model.NewIntVar(
#                                 0, new_end-new_start, f'session length')
#                             print('sirrah3')
#                             event_interval = model.NewOptionalIntervalVar(
#                                 new_start, duration_int, new_end, bol_appointment, 't')
#                             print('sirrah4')
#                             tup_time = tuple([new_start, new_end])
#                             person_events[id][tup_time] = bol_appointment
#                             model.Add(duration_int == 0).OnlyEnforceIf(
#                                 bol_appointment.Not())
#                             print('sirrah5')
#                             model.Add(duration_int == new_end -
#                                       new_start).OnlyEnforceIf(bol_appointment)
#                             print('sirrah6')
#                             model.Add(bol_appointment ==
#                                       0).OnlyEnforceIf(bol.Not())
#                             model.Add(bol ==
#                                       1).OnlyEnforceIf(bol_appointment)
#                             total_durations.append(duration_int)
#                             client_appointments.append(event_interval)
#                             print('sirrah7')

#         print('gliffer8')
#         model.AddNoOverlap(client_appointments)
#     print('gliffer1', total_time)
#     model.Add(sum(total_durations) == total_time)
#     # model.Add(sum(total_durations) > 18)
#     print('gliffer2')
#     model.Minimize(sum(block_obj.values()))
#     print('gliffer3', total_time)
#     # Solve the model
#     solver = cp_model.CpSolver()
#     solver.parameters.log_search_progress = True
#     solver.parameters.max_time_in_seconds = 60
#     solver.log_callback = print
#     status = solver.Solve(model)
#     print('piver8', status, cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model)

#     tup_arr = []

#     # app = selfie.get_appointments([client_ids])
#     if True or status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
#         result = {}
#         for id in client_ids:
#             final_person_blocks[id] = []
#             for tup, bol in person_events[id].items():
#                 if solver.Value(bol) == 1:
#                     final_person_blocks[id].append(tup)
#         print(f'Maximum of objective function : {solver.ObjectiveValue()}\n')
#         print('liver3')
#         for tup, bol in block_obj.items():
#             print('floppy', solver.Value(bol))
#             if solver.Value(bol) == 1:
#                 tup_arr.append(tup)
#                 print('sniffer', tup)

#     print('stove', final_person_blocks)

#     return [total_time, tup_arr, final_person_blocks]


def create_groups2(arr, m, persons):
    model = cp_model.CpModel()

    n = len(persons)
    # groups = max(n // m, 2)
    groups = 4
    m = n // 4

    group_vars = {}

    for id in persons:
        person_var = model.NewIntVar(0, groups - 1, f'group{id}')
        group_vars[id + "a"] = person_var

    bool_vars = []
    group_sums = [[]] * groups
    for info in arr:
        start_time = datetime.datetime.fromisoformat(info['start'].replace(
            'Z', '+00:00'))
        end_time = datetime.datetime.fromisoformat(info['end'].replace(
            'Z', '+00:00'))
        time_difference = end_time - start_time

        # Convert difference to seconds
        time_difference_seconds = time_difference.total_seconds()
        index = arr.index(info)
        people = intersection(info["resourceIds"], persons)
        if len(people) == 2:
            id1 = group_vars[people[0]]
            id2 = group_vars[people[1]]
            equality = model.NewBoolVar(f"eq{index}")
            model.Add(id1 == id2).OnlyEnforceIf(equality)
            model.Add(id1 != id2).OnlyEnforceIf(equality.Not())
            bool_vars.append(equality * int(time_difference_seconds))
            # for i in range(groups):
            #     bool_of_id = model.NewBoolVar("eq12345678")
            #     new_bool = model.NewBoolVar("new_bool")
            #     model.Add(i == id1).OnlyEnforceIf(bool_of_id)
            #     model.AddMultiplicationEquality(new_bool,
            #                                     [bool_of_id, equality])
            #     group_sums[i].append(equality * time_difference_seconds)

    # abs_arr = []
    # for i in range(groups - 1):
    #     abs_diff = model.NewIntVar(0, 10_000_000_00, 'abs_diff')
    #     model.AddAbsEquality(abs_diff, group_sums[i] - group_sums[i + 1])
    #     abs_arr.append(abs_diff)

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

    for i in range(groups):
        pass

    # Add objective function
    model.Maximize(sum(bool_vars))

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        result = {}
        for id in group_vars.keys():
            result[id] = solver.Value(group_vars[id])
        return result

    return None


def create_groups(arr, m, persons):
    model = cp_model.CpModel()

    n = len(persons)
    # groups = max(n // m, 2)
    groups = 1
    m = n // 1

    group_vars = {}

    for id in persons:
        person_var = model.NewIntVar(0, groups - 1, f'group{id}')
        group_vars[id + "a"] = person_var

    bool_vars = []
    group_sums = [[]] * groups
    for info in arr:
        start_time = datetime.datetime.fromisoformat(info['start'].replace(
            'Z', '+00:00'))
        end_time = datetime.datetime.fromisoformat(info['end'].replace(
            'Z', '+00:00'))
        time_difference = end_time - start_time

        # Convert difference to seconds
        time_difference_seconds = time_difference.total_seconds()
        index = arr.index(info)
        people = intersection(info["resourceIds"], persons)
        if len(people) == 2:
            id1 = group_vars[people[0]]
            id2 = group_vars[people[1]]
            equality = model.NewBoolVar(f"eq{index}")
            model.Add(id1 == id2).OnlyEnforceIf(equality)
            model.Add(id1 != id2).OnlyEnforceIf(equality.Not())
            bool_vars.append(equality * int(time_difference_seconds))
            # for i in range(groups):
            #     bool_of_id = model.NewBoolVar("eq12345678")
            #     new_bool = model.NewBoolVar("new_bool")
            #     model.Add(i == id1).OnlyEnforceIf(bool_of_id)
            #     model.AddMultiplicationEquality(new_bool,
            #                                     [bool_of_id, equality])
            #     group_sums[i].append(equality * time_difference_seconds)

    # abs_arr = []
    # for i in range(groups - 1):
    #     abs_diff = model.NewIntVar(0, 10_000_000_00, 'abs_diff')
    #     model.AddAbsEquality(abs_diff, group_sums[i] - group_sums[i + 1])
    #     abs_arr.append(abs_diff)

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

    for i in range(groups):
        pass

    # Add objective function
    model.Maximize(sum(bool_vars))

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        result = {}
        for id in group_vars.keys():
            result[id] = solver.Value(group_vars[id])
        return result

    return None


def get_groups_array(event_possibly, max_number, persons_ids, arr_poss):
    result = get_number_per_slot2(event_possibly, max_number, persons_ids)
    # print('foogly1', result)
    # result = create_groups(arr_poss, max_number, persons_ids)
    # print('foogly2', result)
    # result = get_number_per_slot2(event_possibly, max_number, persons_ids)
    groups = []
    for i in range(max_number):
        var_ids = []
        for k, v in result.items():
            if v == i:
                var_ids.append(k)
        if var_ids != []:
            groups.append(var_ids)
    return groups


# def create_groups_for_part2(arr, persons):
#     model = cp_model.CpModel()

#     n = len(persons)
#     groups = 2
#     m = n // 2

#     group_vars = {}

#     for id in persons:
#         person_var = model.NewIntVar(0, groups - 1, f'group{id}')
#         group_vars[id + "a"] = person_var

#     bool_vars = []
#     for info in arr:
#         index = arr.index(info)
#         people = intersection(info["resourceIds"], persons)
#         if len(people) == 2:
#             if info["scheduled"]:
#                 people = [i + "a" for i in people]
#             # print(f"Bug for this {index} index : ", people, group_vars)
#             id1 = group_vars[people[0]]
#             id2 = group_vars[people[1]]
#             equality = model.NewBoolVar(f"eq{index}")
#             model.Add(id1 == id2).OnlyEnforceIf(equality)
#             model.Add(id1 != id2).OnlyEnforceIf(equality.Not())
#             bool_vars.append(equality)

#     for i in range(groups):
#         equal_distribution = []
#         for var in group_vars.values():
#             temp = model.NewBoolVar("temp")
#             model.Add(var == i).OnlyEnforceIf(temp)
#             model.Add(var != i).OnlyEnforceIf(temp.Not())
#             equal_distribution.append(temp)
#         model.Add(sum(equal_distribution) <= m + 5)
#         model.Add(sum(equal_distribution) >= m - 5)

#     for i in range(groups):
#         pass

#     # Add objective function
#     model.Maximize(sum(bool_vars))

#     # Solve the model
#     solver = cp_model.CpSolver()
#     status = solver.Solve(model)

#     if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
#         result = {}
#         for id in group_vars.keys():
#             result[id] = solver.Value(group_vars[id])
#         print("i_am_ok : ", {})
#         return result
#     print("i_am_ok : ", {})
#     return {}

# def get_part2_groups(event_possibly, persons_ids):
#     result = create_groups_for_part2(event_possibly, persons_ids)
#     groups = []
#     for i in range(2):
#         var_ids = []
#         for k, v in result.items():
#             if v == i:
#                 var_ids.append(k)
#         if var_ids != []:
#             groups.append(var_ids)
#     print("######################################final_par2_group : ", groups)
#     return groups


def find_from_resources(resources, users_arr):
    d = {"activity": "Accelerate"}
    for one_info in resources:
        if one_info["id"] in users_arr:
            d[one_info["type"].lower()] = one_info["name"]
    return d


def generate_time_slots(data, slot_length):
    start_time = datetime.datetime.fromisoformat(data['start'])
    end_time = datetime.datetime.fromisoformat(data['end'])

    # Calculate the time difference between start and end
    time_difference = end_time - start_time

    # Convert slot_length to timedelta object
    slot_duration = datetime.timedelta(minutes=slot_length)

    # Initialize the array to store the time slots
    time_slots = []

    # Loop through the time range and generate slots
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


def optimal_weights(input_data, priority_data, pairs):
    model = cp_model.CpModel()

    vars = {}

    # Create variables
    for var in priority_data.keys():

        vars[var] = model.NewIntVar(1, 1000_000, f"{var}")

    # Define constraints

    multiplied_vars = {}

    for k, v in pairs.items():
        multiplied_vars[k] = vars[k] * input_data[v]

    for comb in list(combinations(multiplied_vars.keys(), 2)):
        if priority_data[comb[0]] < priority_data[comb[1]]:
            model.Add(multiplied_vars[comb[0]] > multiplied_vars[comb[1]])
        else:
            model.Add(multiplied_vars[comb[0]] < multiplied_vars[comb[1]])

    # Objective function

    model.Minimize(sum(vars.values()))

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        result = {}
        for id in vars.keys():
            result[id] = solver.Value(vars[id])
        return result

    return None


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


def adjust_end_date(data):
    start_str = data['start']
    end_str = data['end']

    # Ensure that start and end have the same length and type
    if len(start_str) != len(end_str) or type(start_str) != type(end_str):
        raise ValueError("start and end must have the same length and type")

    # Convert the date strings to datetime objects
    start_date = datetime.datetime.fromisoformat(start_str)
    end_date = datetime.datetime.fromisoformat(end_str)

    # Check if end < start
    if end_date < start_date:
        # Increment end by 1 day
        end_date += datetime.timedelta(days=1)

    # Convert the adjusted end date back to ISO format
    adjusted_end_str = end_date.isoformat()

    # Update the data dictionary
    data['end'] = adjusted_end_str[:-6] + ".000Z"

    return data


def solution_divider(t, m):
    arr = []
    for i in range(t[0], t[1] - m, m):
        arr.append((i, i + m))

    arr.append((t[1] - m, t[1]))
    return arr


# import datetime
# from dateutil import parser


# def solution_divider_time(t, m):
#     arr = []

#     # Convert the input strings to datetime objects
#     start_time = parser.parse(t[0])
#     end_time = parser.parse(t[1])

#     while start_time < end_time:
#         next_time = start_time + datetime.timedelta(minutes=m)
#         if next_time < end_time:
#             arr.append((start_time.isoformat()[:-3] + 'Z',
#                         next_time.isoformat()[:-3] + 'Z'))
#             start_time = next_time
#         else:
#             break
#     before_end = end_time - datetime.timedelta(minutes=m)
#     arr.append(
#         (before_end.isoformat()[:-3] + 'Z', end_time.isoformat()[:-3] + 'Z'))

#     return arr


# def filter_solutions(constraints_data, user_data, slot_length,gaps_dict,flags_data):
#     res_arr = []
#     # print("tothemoon : ",constraints_data)
#     for c_data in constraints_data:
#         if c_data["type"] == "frequency":
#             # print("ConWon")
#             inter = intersection(list(flags_data.keys()),user_data["resourceIds"])
#             if inter == []: continue
#             # print("bazo_inter")
#             for i in inter:
#                 # print("helloL1 : ",i)
#                 if not "constraints" in flags_data[i].keys():
#                     continue
#                 for cons in flags_data[i]["constraints"]:
#                     # print("now_here : ",cons)
#                     if "usertouser" != cons["constraintType"]:
#                         continue
#                     if cons["all"]["userNumber"] >= c_data["max"]:
#                         user_data["new_type"] = "orange"
#                         user_data.update({'colorType': 'orange', 'backgroundColor_real': 'orange'})
#                         user_data["reasons"] = [[]]
#                         break
#         if c_data["type"] == "session":

#             inter = intersection(list(flags_data.keys()),user_data["resourceIds"])
#             if inter == []: continue
#             for i in inter:
#                 if not "constraints" in flags_data[i].keys():
#                     continue
#                 for cons in flags_data[i]["constraints"]:
#                     if "usertosession" != cons["constraintType"]:
#                         continue
#                     if len(cons["each"]["consequenceUsers"])>= c_data["max"]:
#                         user_data["new_type"] = "orange"
#                         user_data.update({'colorType': 'orange', 'backgroundColor_real': 'orange'})
#                         user_data["reasons"] = [[]]
#                         break
#         if c_data["type"] == "time":

#             inter = intersection(list(flags_data.keys()),user_data["resourceIds"])
#             if inter == []: continue
#             for i in inter:
#                 if not "constraints" in flags_data[i].keys():
#                     continue
#                 for cons in flags_data[i]["constraints"]:
#                     if "time" != cons["constraintType"]:
#                         continue
#                     if cons["consequenceTypeEachOrAll"] == "all":
#                         if cons["all"]["actual"] >= c_data["max"]:
#                             user_data["new_type"] = "orange"
#                             user_data.update({'colorType': 'orange', 'backgroundColor_real': 'orange'})
#                             user_data["reasons"] = [[]]
#                             break
                        
#                     if sum([i["actual"] for i in cons["each"]["consequenceUsers"]])>= c_data["max"]:
#                         user_data["new_type"] = "orange"
#                         user_data.update({'colorType': 'orange', 'backgroundColor_real': 'orange'})
#                         user_data["reasons"] = [[]]
#                         break 
#     for c_data in constraints_data:
#         if "new_type" in user_data.keys():
#             continue
#         if c_data["type"] != "gaps":
#             continue
#         inter = intersection(list(gaps_dict.keys()),user_data["resourceIds"])
#         # print("bazo_x :",gaps_dict,inter)
#         # print("bazo_x1 :",list(gaps_dict.keys()),user_data["resourceIds"])
#         if  inter != []:
#             if c_data["maxSeconds"] / 60 < gaps_dict[inter[0]]:
#                 # print("bazo_y")
#                 user_data["new_type"] = "orange"
#                 user_data.update({'colorType': 'orange', 'backgroundColor_real': 'orange'})
#                 user_data["reasons"] = [[]]
#     for c_data in constraints_data:
        
#         if c_data["type"] != "sessionlength":
#             continue
#         user_a = intersection(c_data["users_antecedent"],
#                               user_data['resourceIds_r'])
#         user_c = intersection(c_data["users_consequence"],
#                               user_data['resourceIds_r'])
        
#         if len(user_a) > 0 and len(user_c) > 0:

#             max_sessionlength = (c_data["maxSeconds"] // 60) // slot_length
#             min_sessionlength = (c_data["minSeconds"] // 60) // slot_length
#             max_minutes = (c_data["maxSeconds"] // 60)
#             start_r = user_data["start_r"]
#             end_r = user_data["end_r"]
#             start = user_data["start"]
#             end = user_data["end"]
#             if (end_r - start_r <= max_sessionlength) and (end_r - start_r >=
#                                                            min_sessionlength):
#                 res_arr.append(user_data)
#                 continue
#             if (end_r - start_r < min_sessionlength):
#                 continue
#             divider_slot = solution_divider((start_r, end_r),
#                                             max_sessionlength)
#             divider_time = solution_divider_time((str(start), str(end)),
#                                                  max_minutes)
#             # print(divider_slot)
#             for i in range(len(divider_time)):
#                 temp = user_data.copy()
#                 temp["start_r"] = divider_slot[i][0]
#                 temp["end_r"] = divider_slot[i][0]
#                 # print("bazo_mk : ",divider_time[i][0],divider_time[i][1])
#                 temp["start"] = divider_time[i][0][:-4] + ".000Z"
#                 temp["end"] = divider_time[i][1][:-4] + ".000Z"
#                 res_arr.append(temp)
#     if res_arr == []:
#         return [user_data]
#     return res_arr

def get_day_index(date_string):
    try:
        # Remove milliseconds and 'Z' from the input string
        date_string = date_string[:10]
        date_obj = datetime.datetime.fromisoformat(date_string)
        day_index = date_obj.weekday()
        return day_index
    except ValueError:
        return None


def organize_events(events,user_ids,extra_str = ""):
    # print("bazo_org : ",events,user_ids)
    organized_events = {}
    for id in user_ids:
        organized_events[id]={}
    for user_id in user_ids:
        for i in range(7):
            organized_events[user_id][i] = []
    for user_id in user_ids:
        for i in events:
            if user_id+extra_str in i["resourceIds"]:
                day_index = get_day_index(i["start"])
                # print("day_index : ",day_index)
                organized_events[user_id][day_index].append(i)
    return organized_events

def calculate_total_gaps(time_intervals):
    # Convert the ISO 8601 date-time strings to datetime objects
    intervals = [(datetime.datetime.fromisoformat(interval['start'].replace("Z","")), datetime.datetime.fromisoformat(interval['end'].replace("Z",""))) for interval in time_intervals]

    # Sort the intervals by their start times
    intervals.sort(key=lambda interval: interval[0])

    total_gaps = 0
    end_time = intervals[0][1]

    for start, end in intervals[1:]:
        if start > end_time:
            total_gaps += (start - end_time).total_seconds()
        end_time = max(end_time, end)
    return total_gaps/60

def filter_gaps(events_data,solution_data,user_ids):
    d = {}
    for id in user_ids:
        for i in range(7):
            if events_data[id][i] ==[] or solution_data[id][i] == []:
                continue
            arr = events_data[id][i]+solution_data[id][i]
            sol_user_id  =id+"a"
            d[sol_user_id] = calculate_total_gaps(arr)
    # print("Total : ",d) 
    return d

def dict_priority(custom_constraints):
    # print("bazo_priority : ",custom_constraints)
    res = {}
    print('terry',custom_constraints)
    for c in custom_constraints:
        if c["type"] != "priority":
            continue
        print("bazo_priority : ",custom_constraints)
        if len(list(c["users_antecedent"])) == 0:
            continue
        #k = list(c["users_antecedent"])[0]
        for k in list(c["users_antecedent"]):
            if k in res.keys():
                res[k] += list(c["users_consequence"])
            else:
                res[k] = list(c["users_consequence"])
    print('adam_here ',res)
    return res

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
        print("bazo_time_diff : ",time_difference.total_seconds()//60)
        intersected_people = set_people.intersection(set(event["resourceIds"]))
        intersected_activity = set_activity.intersection(set(event["resourceIds"]))
        for i in intersected_people:
            for j in intersected_activity:
                dict_data_for_weekly_events[i][j] += int(time_difference.total_seconds()//60)
    return dict_data_for_weekly_events

def debug_mode():
    '''This function will return a dictionary for debug mode {"main_function_name":boolean}'''
    return {
        "main_drive_time" : True,
    }

def find_overlapping_events(events):
    print("bazo_ww : ",events)
    overlaps = []
    graph = {}
    
    # Build the graph with overlapping events
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
    
    # Perform DFS to find groups of overlapping events
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
    
    # Convert group indices to actual events
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

    # Sort events by start time
    sorted_events = sorted(events, key=lambda x: x['start'])

    merged_intervals = [sorted_events[0]]

    for event in sorted_events[1:]:
        last_merged = merged_intervals[-1]
        if event['start'] <= last_merged['end']:
            last_merged['end'] = max(last_merged['end'], event['end'])
        else:
            merged_intervals.append(event)
    
    return merged_intervals
    # temp = merged_intervals+events
    # res = []
    # for i in temp:
    #     if id in i[""]:
    #         i[""].remove(id)
    #         res.append(i)
    # return res

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
        print("bb_ids: ",users_overlap[usr])
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
    # for i in clients:
    #     res_clients[i] = []
    # for event in events_data:
    #     if events_ids_dict[event["id"]]:
    #         ddd={"fake_overlap":False}
    #         event.update(ddd)
    #         res_events.append(event)
    #     else:
    #         a_inter = set_people.intersection(set(event["resourceIds"]))
    #         if len(a_inter) > 0:
    #             ddd = {"fake_overlap":True}
    #             event.update(ddd)
    #             res_clients[list(a_inter)[0]].append(event)
    #             res_clients_arr.append(event)               
    # for event in events_data:
    #     if event["fake_overlap"]:
    #         a_inter = set(clients).intersection(set(event["resourceIds"]))
    #         if len(a_inter) == 0:
    #             continue
    #         users_overlap[list(a_inter)[0]]['fakes'].append(event)
    
    print("bazo_fake_event_list0 : ",events_by_user_ids)
    print("bazo_fake_event_list1 : ",res_events)
    print("bazo_fake_event_list2 : ",users_overlap)  
    print("bazo_fake_event_list3 : ",res_clients)  
    print("bazo_fake_event_list4 : ",res_clients_arr)  
    return [res_events,users_overlap,res_clients,res_clients_arr,list(delete_ids)]


def get_weekday_index(date_string):
    date = datetime.datetime.strptime(date_string, "%Y-%m-%d")
    return date.weekday()

def calculate_duration_in_minutes(data_info,user_anti_id,user_cons_id,act_id,loc_id):
    durations = 0
    temp_data = []
    for i in data_info:
        temp_data += i
    for item in temp_data:
        # print("my_item : ",item)
        if not user_anti_id in item["resourceIds"]:
            continue
        if not user_cons_id in item["resourceIds"]:
            continue
        if not act_id in item["resourceIds"] and not act_id is None:
            continue
        if not loc_id in item["resourceIds"] and not loc_id is None:
            continue
        start_time = datetime.datetime.fromisoformat(item['start'][:-1])
        end_time = datetime.datetime.fromisoformat(item['end'][:-1])
        duration = (end_time - start_time).total_seconds() / 60
        durations += duration
    return durations

def get_week_start_end(date_str):
    print("bbazzo : ",date_str)
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    start_of_week = date - datetime.timedelta(days=date.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=4)
    week_dates = [(start_of_week + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6)]
    start_of_week_str = start_of_week.strftime("%Y-%m-%d")
    end_of_week_str = end_of_week.strftime("%Y-%m-%d")
    
    return {"start":start_of_week_str, "end":end_of_week_str,"week_dates":week_dates}

def calculate_total_hours(intervals):
    if len(intervals) == 0:
        return 0
    print("calcalcal : ",intervals)
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

def calculate_duration_hours(interval):
    start_time = datetime.datetime.fromisoformat(interval["start"].replace('Z', '+00:00'))
    end_time = datetime.datetime.fromisoformat(interval["end"].replace('Z', '+00:00'))
    duration_seconds = (end_time - start_time).total_seconds()
    weekday_index = start_time.weekday()
    duration_hours = duration_seconds / 3600
    return duration_hours,weekday_index