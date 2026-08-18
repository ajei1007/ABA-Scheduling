import requests
import datetime
from helper_functions import slot_to_time, intersection
import time
import math
from itertools import combinations, product

header = {
    'Authorization':
    'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiZmIzYWE1YzYtNTgzYS00YWU0LWI0NTEtYjkzOWJlNjZmYWMwIiwiZW1haWwiOiJibHVlLnNwcmlnQG1haWwuY29tIn0sImlhdCI6MTY4MTgzMzExNSwiZXhwIjoyMzI4MTgzMzExNX0.JVT-as6w4HVlb3h2a9tOoKJHrcHRf-Ts2txBUxRHIm4'
}

# response = requests.get(
#     f'http://localhost:8080/api/scheduler/resources?branches=1ca63c9a-4926-40e4-a2e5-16c580fa82de',
#     headers=header)

# res = requests.get(
#     'http://localhost:8080/api/scheduler/availabilities?start=2023-04-18&end=2023-04-19&branches=1ca63c9a-4926-40e4-a2e5-16c580fa82de',
#     headers=header)

# people = []

# for i in response.json():
#     if "Person" in i["roles"]:
#         people.append(i["id"])

# a = {}

# for i in res.json():
#     start = datetime.datetime.fromisoformat(i["start"].replace('Z', '+00:00'))
#     end = datetime.datetime.fromisoformat(i["end"].replace('Z', '+00:00'))
#     duration_hours = (end - start).total_seconds() / 3600
#     _id = intersection(people, i["resourceIds"])
#     if len(_id) > 0:
#         print(len(_id))
#         a[_id[0]] = duration_hours

# print(a)


def availabilities(host, header, start, end, branch):
    resource = requests.get(f'{host}/scheduler/resources?branches={branch}',
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
    for i in people:
        b[i] = 0
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
                employees_dict[_id[0]] = duration_hours
            else:
                clients_dict[_id[0]] = duration_hours
            a[_id[0]] = duration_hours
    return [{"employees": employees_dict, "clients": clients_dict}, b]


print(
    availabilities("http://localhost:8080/api", header, "2023-04-18",
                   "2023-04-19", "52df4747-a144-4ca4-8ae8-ba0d2d1b0f2d"))

# def time_to_slot(t, day, minutes, s):
#     x = time.strptime(t, '%H:%M:%S')
#     output = datetime.timedelta(
#         hours=x.tm_hour, minutes=x.tm_min,
#         seconds=x.tm_sec).total_seconds() / 60 / minutes
#     if s == "start":
#         print(round(output))
#         if int(output) < output:
#             output = int(output) + 1
#     if s == "end":
#         print(int(output))
#         output = int(output)
#     output = int(day * 24 * 60 / minutes + output)

#     return output

# arr = []
# roles = [['Employee', 'Client'], ['super']]
# subgroups = [['Team Blue']]
# branches = [[]]

# # p = list(product(*roles))
# # if len(p) > 0:
# #     arr.append(p)
# # t = list(product(*subgroups))
# # if len(t) > 0:
# #     arr.append(t)
# # o = list(product(*branches))
# # if len(o) > 0:
# #     arr.append(o)

# p = list(product(*roles))
# if len(p) > 0:
#     for v in p:
#         arr.append(v)
# t = list(product(*subgroups))
# if len(t) > 0:
#     arr.append(t)
# o = list(product(*branches))
# if len(o) > 0:
#     arr.append(o)

# b = list(product(*p, *t, *o))

# print('neever', b)
