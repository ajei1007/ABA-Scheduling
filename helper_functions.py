import math
import time
import random
import requests
import datetime
import itertools


def days_arr(minute_interval):
    array = [1]
    slot_length = 60 // minute_interval
    for i in range(7):
        array.append((i + 1) * 24 * slot_length)
    return array


def delete_multiple_events(arr, host, header):
    for j in range(len(arr)):
        response = requests.post(f'{host}/events/remove/multiple',
                                 headers=header,
                                 json=[arr[j]['id']])


def remove_randomly(arr, act_id, percent):
    target = [d for d in arr if act_id in d.get('resourceIds')]
    random_numbers = random.sample(range(1, len(target)),
                                   int(len(target) * percent // 100))
    deleted = []
    for i in random_numbers:
        x = target[i]
        arr.remove(x)
        deleted.append(x)
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


def time_to_slot(t, day, minutes):
    x = time.strptime(t, '%H:%M:%S')
    output = datetime.timedelta(
        hours=x.tm_hour, minutes=x.tm_min,
        seconds=x.tm_sec).total_seconds() / 60 / minutes
    output = int(day * 24 * 60 / minutes + output)
    print(day * 24 * 60 / minutes + output)
    return output


def detect_range2(l):
    l.sort()
    ranges = []
    for i, j in itertools.groupby(enumerate(l), lambda x: x[1] - x[0]):
        j = list(j)
        ranges.append((j[0][1], j[-1][1]))
    return ranges


def intersection(lst1, lst2):
    return [value for value in lst1 if value in lst2]


def format_date_range(start, end, tz_offset=-6):
    start_date = datetime.datetime.strptime(start, '%Y-%m-%d')
    end_date = datetime.datetime.strptime(end, '%Y-%m-%d')
    tz = datetime.timezone(datetime.timedelta(hours=tz_offset))
    start_date_tz = start_date.replace(tzinfo=tz)
    end_date_tz = end_date.replace(tzinfo=tz)
    start_date_str = start_date_tz.strftime('%a %b %d %Y %H:%M:%S %Z%z')
    end_date_str = end_date_tz.strftime('%a %b %d %Y %H:%M:%S %Z%z')
    return f'start= {start_date_str}&end= {end_date_str}'


def parse_date_string(date_string):
    date_obj = datetime.datetime.strptime(date_string, '%Y-%m-%d')
    day_of_week = date_obj.strftime('%a')
    month_abbr = date_obj.strftime('%b')
    day_of_month = date_obj.strftime('%d')
    year = date_obj.year
    return [day_of_week, month_abbr, day_of_month, year]


def days_in_between(s_date):
    s = s_date.split(" - ")
    d1 = datetime.datetime.strptime(s[1], '%m/%d/%Y')
    d2 = datetime.datetime.strptime(s[0], '%m/%d/%Y')
    diff = d1 - d2
    return diff.days + 1


def get_week_dates(date_str):
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    monday = date - datetime.timedelta(days=date.weekday())
    dates = [monday + datetime.timedelta(days=d) for d in range(8)]
    return dates


def calc_availabilities(start_time, end_time, s_length):
    start = datetime.datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    end = datetime.datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    interval_start = time_to_slot(start.strftime('%H:%M:%S'),
                                  (start.weekday() + 1) % 7, s_length)
    interval_end = time_to_slot(end.strftime('%H:%M:%S'),
                                (end.weekday() + 1) % 7, s_length)
    return [i for i in range(interval_start, interval_end + 1)]


def gap_calc(array_of_start_end, minutes):
    x = []
    arr = []
    day = array_of_start_end[0]["start"][:10]
    for i in array_of_start_end:
        k, v = i["start"], i["end"]
        k = datetime.datetime.strptime(k, '%Y-%m-%dT%H:%M:%S.%fZ')
        s = time_to_slot(k.strftime('%H:%M:%S'), 1, minutes)
        v = datetime.datetime.strptime(v, '%Y-%m-%dT%H:%M:%S.%fZ')
        e = time_to_slot(v.strftime('%H:%M:%S'), 1, minutes)
        for tt in range(s, e + 1):
            arr.append(tt)
    r = detect_range2(sorted(list(set(arr))))
    if len(r) == 1:
        print("")
    for j in range(len(r) - 1):
        x.append([
            day + "T" + slot_to_time(r[j][1], minutes) + ".000Z",
            day + "T" + slot_to_time(r[j + 1][0], minutes) + ".000Z"
        ])
    return x


def remove_tally(d):
    for key in d:
        del d[key]['tally']
    return d


def convert_millisecond_to_hour(d):
    for key in d:
        d[key]['total'] = round(d[key]['total'] / 3600_000, 2)
        for k in d[key]["activities"]:
            d[key]["activities"][k] = round(d[key]["activities"][k] / 3600_000,
                                            2)
    return d


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


def gap_filler_2(arr, resources, some_minutes):
    print("gapper : ", arr)
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
            print("dict_data : ", dict_people_availability[k])
            if not dict_people_availability[k] == []:
                dict_people_availability[k] = gap_calc(
                    dict_people_availability[k], some_minutes)
        print("filler : ", dict_people_availability)
        x_res.append(create_bypass(dict_people_availability, inc))
        inc = inc + 1

    return x_res


a = [{
    'start': '2023-07-13T17:45:00.000Z',
    'end': '2023-07-13T18:15:00.000Z'
}, {
    'start': '2023-07-13T15:00:00.000Z',
    'end': '2023-07-13T18:15:00.000Z'
}, {
    'start': '2023-07-13T13:00:00.000Z',
    'end': '2023-07-13T14:15:00.000Z'
}, {
    'start': '2023-07-13T17:45:00.000Z',
    'end': '2023-07-13T18:15:00.000Z'
}]
