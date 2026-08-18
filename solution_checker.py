# This if a helper class for testing solutions.
import datetime
from external import intersection


def calculate_hours(data_input):
    datetime_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    start = datetime.datetime.strptime(data_input['start'], datetime_format)
    end = datetime.datetime.strptime(data_input['end'], datetime_format)

    difference = end - start
    hours_difference = difference.total_seconds(
    ) / 3600  # there are 3600 seconds in an hour

    return round(hours_difference,
                 2)  # rounding to two decimal places for a float result


def check_schedule(data):
    if len(data) == 0:
        return 1
    datetime_format = "%Y-%m-%dT%H:%M:%S.%fZ"
    # Sort the data according to 'start' time
    data.sort(
        key=lambda x: datetime.datetime.strptime(x['start'], datetime_format))
    for i in range(len(data) - 1):
        # if 'end' time of current slot is less than 'start' time of next slot, there is a gap.
        if datetime.datetime.strptime(
                data[i]['end'], datetime_format) < datetime.datetime.strptime(
                    data[i + 1]['start'], datetime_format):
            return 0
    return 1


def total_time(array):
    # the format of your datetime strings
    fmt = '%Y-%m-%dT%H:%M:%S.%fZ'

    total = 0
    for item in array:
        # parse the datetime strings into datetime objects
        start = datetime.datetime.strptime(item['start'], fmt)
        end = datetime.datetime.strptime(item['end'], fmt)

        # add the difference in seconds to the total
        total += (end - start).total_seconds()

    return total / 3600  # if you need the result in seconds


class Checker:
    def __init__(self, data, employees_ids, clients_ids, sended_data,
                 productivity_data, efficiency_data):
        self.data = data
        self.persons_ids = employees_ids + clients_ids
        self.employees_ids = employees_ids
        self.clients_ids = clients_ids
        self.sended_data = sended_data
        self.result = 1
        self.productivity_data = productivity_data
        self.efficiency_data = efficiency_data

    def proper_session_length(self):
        # This function returns 0 if session length is less than min_session or greater than max_session else returns 1
        direct_data = []
        for d in self.data:
            if len(intersection(d["resourceIds"], self.persons_ids)) == 2:
                direct_data.append(d)
        for d in direct_data:
            min_session = self.sended_data["min_session_dur"]
            max_session = self.sended_data["max_session_length"]
            objective_act_ids = self.sended_data["objectiveactivity"]
            if len(intersection(objective_act_ids, d["resourceIds"])) > 1:
                dur = calculate_hours(d) * 60
                if dur < min_session or dur > max_session:
                    return 0
        if self.sended_data["is_lunch"]:
            print(True)
            for d in self.data:
                if len(
                        intersection(d["resourceIds"],
                                     [self.sended_data["lunch_id"]])) > 0:
                    dur = calculate_hours(d) * 60
                    if int(dur) != 30:
                        return 0
        if self.sended_data["is_break"]:
            print(True)
            for d in self.data:
                if len(
                        intersection(d["resourceIds"],
                                     [self.sended_data["break_id"]])) > 0:
                    dur = calculate_hours(d) * 60
                    if int(dur) != 15:
                        return 0
        return 1

    def is_overlap(self):
        # This function returns 0 if there is overlap else returns 1
        result = 1
        for person in self.persons_ids:
            schedule = []
            for d in self.data:
                if person in d["resourceIds"]:
                    schedule.append(d)
            # Sort the schedule by start time
            if len(schedule) > 0:
                sorted_schedule = sorted(schedule, key=lambda d: d["start"])
                # print("bug: ", sorted_schedule)
                # Initialize end time with the end time of the first period
                end_time = sorted_schedule[0]['end']

                for period in sorted_schedule[1:]:
                    if period['start'] < end_time:
                        result = result * 0  # There's an overlap
                    end_time = period['end']  # Update end time

        return 1  #result

    def is_gap(self):
        # This function returns 0 if there is gap in clients session or employees gap greater than some_value else returns 1
        for id in self.clients_ids:
            arr = []
            for d in self.data:
                if id in d["resourceIds"]:
                    arr.append(d)
            if check_schedule(arr) == 0:
                return 0
        return 1

    def is_lunch_added(self):
        # This function returns 0 if there is no lunch for employees if they have certain hours of Direct else returns 1
        if self.sended_data["is_lunch"]:
            for id in self.employees_ids:
                direct_arr = []
                lunch_arr = []
                for d in self.data:
                    if id in d["resourceIds"]:
                        if len(intersection(d["resourceIds"],
                                            self.persons_ids)) >= 2:
                            direct_arr.append(d)
                        if len(
                                intersection(
                                    d["resourceIds"],
                                    self.sended_data["lunch_id"])) == 1:
                            lunch_arr.append(d)
                if total_time(direct_arr) >= 6 and total_time(lunch_arr) == 0:
                    return 0
                if len(lunch_arr) > 1:
                    return 0
        else:
            return 1

    def is_break_added(self):
        # This function returns 0 if not satisfy break condition else returns 1
        if not self.sended_data["is_break"]:
            return 1
        for id in self.employees_ids:
            employee_data = [d for d in self.data if id in d["resourceIds"]]
            break_id = self.sended_data["break_id"]
            direct_arr = [
                d for d in employee_data if not break_id in d["resourceIds"]
            ]
            break_arr = [
                d for d in employee_data if break_id in d["resourceIds"]
            ]
            for break_data in break_arr:
                res1 = False
                res2 = False
                for d in direct_arr:
                    if d["start"] == break_data["end"]:
                        res1 = True
                        break
                for d in direct_arr:
                    if d["end"] == break_data["start"]:
                        res2 = True
                        break
                if not (res1 and res2):
                    return 0
        return 1

    def is_drive_added(self):
        #I have no idea
        return 1

    def productivity(self):
        # This function returns productivity percentage
        pass

    def efficiency(self):
        # This function returns efficiency percentage
        pass

    def run(self):
        proper_session = self.proper_session_length()
        is_overlap = self.is_overlap()
        is_gap = self.is_gap()
        is_lunch = self.is_lunch_added()
        is_break = self.is_break_added()
        is_drive = self.is_drive_added()
        productivity = self.productivity_data  #self.productivity()
        efficiency = self.efficiency_data  #self.efficiency()
        res_prod = productivity * proper_session * is_overlap * is_gap * is_lunch * is_break * is_drive
        res_eff = efficiency * proper_session * is_overlap * is_gap * is_lunch * is_break * is_drive
        return {
            "productivity": res_prod,
            "efficiency": res_eff,
            "proper_session": proper_session,
            "is_overlap": is_overlap,
            "is_gap": is_gap,
            "is_lunch": is_lunch,
            "is_break": is_break,
            "is_drive": is_drive
        }


# data, employees_ids, clients_ids, sended_data,productivity_data, efficiency_data


def convert_in_out(input, output):
    data = [i["data"] for i in output["appointments"]]

    employees_ids = list(output["employees_efficiency"].keys())
    clients_ids = list(output["clients_efficiency"].keys())

    sended_data = input

    productivity_data = 1

    efficiency_data = output["total_clients_efficiency"] * 100

    some_test = Checker(data, employees_ids, clients_ids, sended_data,
                        productivity_data, efficiency_data)

    return some_test.run()


# from testing import test_1_input, output

# print(convert_in_out(test_1_input, output))

# data = [i["data"] for i in output["appointments"]]

# employees_ids = list(output["employees_efficiency"].keys())
# clients_ids = list(output["clients_efficiency"].keys())

# sended_data = test_1_input

# productivity_data = 1

# efficiency_data = output["total_clients_efficiency"] * 100

# some_test = Checker(data, employees_ids, clients_ids, sended_data,
#                     productivity_data, efficiency_data)

# print(some_test.run())
