import datetime
from get_data import Get_Data
from abstract_inputs import header
import time
import requests
from helper_functions import create_bypass, detect_range2

direct_activity_id = '2faf27ca-9120-486c-9738-83714f0ee50d'
lunch_activity_id = '7bd835c3-7855-4855-a73e-f6b40b5b0dc4'
supervision_activity_id = 'f39d479c-ea0f-4dcf-86e1-3e47c19328c7'
break_activity_id = 'f6e9b38f-00d3-4556-bdc6-c87ba796caa4'
drive_activity_id = 'dbc2840e-362f-40cc-aa47-e37196f15cd1'


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


def calculate_duration_hours(data):
    start_recur = datetime.datetime.fromisoformat(data["start"].replace(
        'Z', '+00:00'))
    end_recur = datetime.datetime.fromisoformat(data["end"].replace(
        'Z', '+00:00'))
    duration_hours = (end_recur - start_recur).total_seconds() / 3600
    return duration_hours


def get_week_dates(date_str):
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    monday = date - datetime.timedelta(days=date.weekday())
    dates = [monday + datetime.timedelta(days=d) for d in range(8)]
    return dates


def time_to_slot(t, day, minutes):
    x = time.strptime(t, '%H:%M:%S')
    output = datetime.timedelta(
        hours=x.tm_hour, minutes=x.tm_min,
        seconds=x.tm_sec).total_seconds() / 60 / minutes
    output = int(day * 24 * 60 / minutes + output)
    return output


def calc_availabilities(start_time, end_time):
    start = datetime.datetime.strptime(start_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    end = datetime.datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
    interval_start = time_to_slot(start.strftime('%H:%M:%S'),
                                  (start.weekday() + 1) % 7, 30)
    interval_end = time_to_slot(end.strftime('%H:%M:%S'),
                                (end.weekday() + 1) % 7, 30)
    return [i for i in range(interval_start, interval_end + 1)]


def intersection(lst1, lst2):  # gets intersection of two lists
    return [value for value in lst1 if value in lst2]


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


some_date = get_week_dates("2022-10-10")
num_of_days = some_date[-1] - some_date[0]

a = {
    'start_date': str(some_date[0]),
    'end_date': str(some_date[-1]),
    'branch': '1ca63c9a-4926-40e4-a2e5-16c580fa82de',
    'daily': False,
    'blocks': False,
    'is_Multi': False,
    'is_lunch': False,
    'is_break': False,
    'is_orange': False,
    'is_events': True,
    "header": header,
    "objectiveactivity": direct_activity_id,
    "lunch_id": lunch_activity_id,
    "break_id": break_activity_id,
    "drive_id": drive_activity_id,
    "num_of_days": num_of_days.days + 1,
    "host": "http://localhost:8080/api"
}


class Time_Constraint_Handler:
    def __init__(self, given_data):
        self.data = given_data

    def get_week_dates_arr(self):
        return get_week_dates(self.data["start_date"])

    def get_all_data(self):
        data_1 = self.data
        data_1["start_date"] = str(self.get_week_dates_arr()[0])
        data_1["end_date"] = str(self.get_week_dates_arr()[-1])
        return Get_Data(data_1)

    def get_people_ids(self):
        people = []
        for i in self.get_all_data().get_resources():
            if 'Person' in i['roles']:
                people.append(i['id'])
        return people

    def get_activity_ids(self):
        act_ids = []
        for i in self.get_all_data().get_resources():
            if 'Activity' in i['roles']:
                act_ids.append(i['id'])
        return act_ids

    def data_for_stats(self):
        return {
            "people": "|".join(self.get_activity_ids()),
            "people2": "|".join(self.get_people_ids()),
            "activities": None,
            "totalType": "total",
            "bol1": True,
            "bol2": True,
            "level": 5,
            "resources": self.get_all_data().get_resources(),
            "offset": 360,
            "totalType": "total"
        }

    def get_statistics(self):
        s = str(self.get_week_dates_arr()[0])
        e = str(self.get_week_dates_arr()[-3])
        ss = parse_date_string(s)
        sst = " ".join([str(i) for i in ss])
        ee = parse_date_string(e)
        eet = " ".join([str(i) for i in ee])
        brn = self.data["branch"]
        hst = self.data["host"]
        response = requests.post(
            f"{hst}/scheduler/statistics?start={sst}&end={eet}",
            headers=self.data["header"],
            json=self.data_for_stats())
        return response.json()["individual"]["users"]

    def get_people_availabilities(self, s):
        arr_people_availability = []
        gap_filler = []
        for i in self.get_all_data().get_direct_activities():
            just_date = ""
            dict_people_availability = {}
            filler = []
            for id in self.get_people_ids():
                dict_people_availability[id] = []
            for j in i:
                res_ids = [x[:-1] for x in j["resourceIds"]]
                just_date = j["start"][:10]
                for id in intersection(res_ids, self.get_people_ids()):
                    dict_people_availability[id] = list(
                        set(dict_people_availability[id] +
                            calc_availabilities(j["start"], j["end"])))
            for k, v in dict_people_availability.items():
                for xy in s:
                    filler = filler + create_bypass(
                        xy, dict_people_availability[k])
                dict_people_availability[k] = round(len(v) / 4, 2)
            gap_filler.append(filler)
            arr_people_availability.append(dict_people_availability)
        return [arr_people_availability, gap_filler]

    def get_time_cons_arr(self):
        x = self.get_statistics()
        sts = convert_millisecond_to_hour(remove_tally(x))
        time_cons = []
        result = []
        for i in self.get_all_data().get_time_constraints():
            if i["frequency"] == "Total":
                if i["unit"] == "Units":
                    i["frequency"] = "Weekly"
                    i["unit"] = "Hours"
                    i["max"] = round(((float(i["max"]) / 4) /
                                      days_in_between(i["dateRange"])) * 7, 2)
                    time_cons.append(i)
                else:
                    i["frequency"] = "Weekly"
                    i["max"] = round(
                        ((float(i["max"])) / days_in_between(i["dateRange"])) *
                        7, 2)
            else:
                time_cons.append(i)
        for i in time_cons:
            if i["user_id"] in sts:
                if i["activity_id"] in sts[i["user_id"]]["activities"]:
                    i["max"] = i["max"] - sts[i["user_id"]]["activities"][
                        i["activity_id"]]

        return time_cons
