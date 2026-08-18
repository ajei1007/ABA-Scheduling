data = {
    'start_date': '2023-06-19',
    'end_date': '2023-06-19',
    'branch': '85f80da7-bdbf-4be4-81bb-3b5cefb9fe35',
    # 'teams': ['b8c08c4b-03b6-4210-9f22-fb4e98fa9f6f'],
    # 'daily': False,
    # 'blocks': False,
    # 'is_Multi': True,
    # 'is_lunch': False,
    # 'is_break': False,
    # 'is_orange': False,
    # 'is_events': True,
    # 'percentage': 15,
    # 'objective_role': ['RBT'],
    # 'insert_data_role': 'Person',
    # 'slot_length': 30,
    # 'max_time_in_seconds': 400.0,
    # 'num_search_workers': 8,
    # 'min_session_dur': 120,
    # 'max_session_length': 240.0,
    # 'no_gap_role': 'Person',
    # 'overlap_role': 'Person',
    # 'team_bounds': {
    #     'num_of_teams': 5,
    #     'r': 4,
    #     'min_people_per_team': 5
    # },
    # 'lunch_role': 'Employee',
    # 'lunch_length': 2,
    # 'break_role': 'Employee',
    # 'break_length': 1,
    # 'part1': False,
    # 'is_time_constraint': False,
    # 'is_drive_constraint': False,
    # 'is_lunch_constraint': False,
    # 'is_break_constraint': False,
    # 'is_team_constraint': False,
    # 'is_overlap_constraint': True,
    # 'is_minSession_constraint': True,
    # 'is_noGap_constraint': True,
    # 'is_delete': False,
    # 'optimize_current': False,
    'host': 'http://localhost:8080/api',
    # 'all_or_nothing': False,
    # 'break_id': 'not found',
    # 'drive_id': 'not found',
    # 'lunch_id': '64d1ba19-f8fa-4404-af94-3017229b93ef',
    # 'objectiveactivity': ['a2d2f210-831c-4429-be87-fe3c1e3e0df8'],
    # 'billable': ['a2d2f210-831c-4429-be87-fe3c1e3e0df8'],
    # 'nonbillable': [],
    'expanded_resources': ['a2d2f210-831c-4429-be87-fe3c1e3e0df8'],
    'uncheckWhiteSolutionConstraints': [],
    'uncheckOrangeSolutionConstraints': [],
    'settings': {
        'subgroupsFilterLabels': None,
        'resourceFilterLabels': None,
        'hideCancelations': False,
        'isolateCanceled': False,
        'locationQuantity': 2,
        'branchDefault': None,
        'totalCustom': 'total',
        'timeConstraintUpperBuffer': None,
        'timeConstraintLowerBuffer': None,
        'timeconstraints': False,
        'defaultActivity': None,
        'defaultLocation': None,
        'overbooking': False,
        'noGaps': False,
        'driveTime': False,
        'weekends': False,
        'teamSeparation': False,
        'blocks': False,
        'orange': False,
        'driveDistanceMax': False,
        'driveDistanceMaxQuantity': None,
        'driveDistanceMaxUnit': None,
        'timeInterval': 15,
        'driveTimeQuantity': None,
        'driveTimeUnit': 'Minutes',
        'stats_on': True
    },
    'companyId': '02691328-b72f-45fa-8092-f1be06ab5384',
    'header': {
        'Authorization':
        'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiMGQzY2EwYjAtMDU4MC00NjI4LWE2NDktNTkzMTJkYjVjOTE0IiwiZW1haWwiOiJhZGFtQGFiYXNjaGVkdWxlcy5jb20ifSwiaWF0IjoxNjg3NDQyMDM2LCJleHAiOjIzMjg3NDQyMDM2fQ.967POHoixkOl6cZuSJzwa80gu8DFe1ncF7gCsFWwI1c'
    },
    'part1_new': False,
    'is_session_for_part2': True
}

data2 = {
    'host': 'http://localhost:8080/api',
    'header': {
        'Authorization':
        'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiMGQzY2EwYjAtMDU4MC00NjI4LWE2NDktNTkzMTJkYjVjOTE0IiwiZW1haWwiOiJhZGFtQGFiYXNjaGVkdWxlcy5jb20ifSwiaWF0IjoxNjg3NDQyMDM2LCJleHAiOjIzMjg3NDQyMDM2fQ.967POHoixkOl6cZuSJzwa80gu8DFe1ncF7gCsFWwI1c'
    },
    'start_date': '2023-06-19',
    'end_date': '2023-06-20',
    'branch': '85f80da7-bdbf-4be4-81bb-3b5cefb9fe35',
    'expanded_resources': ['a2d2f210-831c-4429-be87-fe3c1e3e0df8'],
    'uncheckWhiteSolutionConstraints': [],
    'uncheckOrangeSolutionConstraints': [],
    'investigate': [],
    'settings': {
        'subgroupsFilterLabels': None,
        'resourceFilterLabels': None,
        'hideCancelations': False,
        'isolateCanceled': False,
        'locationQuantity': 2,
        'branchDefault': None,
        'totalCustom': 'total',
        'timeConstraintUpperBuffer': None,
        'timeConstraintLowerBuffer': None,
        'timeconstraints': False,
        'defaultActivity': None,
        'defaultLocation': None,
        'overbooking': False,
        'noGaps': False,
        'driveTime': False,
        'weekends': False,
        'teamSeparation': False,
        'blocks': False,
        'orange': False,
        'driveDistanceMax': False,
        'driveDistanceMaxQuantity': None,
        'driveDistanceMaxUnit': None,
        'timeInterval': 15,
        'driveTimeQuantity': None,
        'driveTimeUnit': 'Minutes',
        'stats_on': True
    }
}

from automation_inbloom import solution_getter
import requests
from solve import Solution_Generator, Data_Gatherer
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
from testing import hard_coded_data

print(len(solution_getter(data)[3]))


{'start': '2024-03-27T13:00:00.000Z', 'end': '2024-03-27T15:00:00.000Z', 'users': ['3', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9', '4a789fb8-b9ef-44ca-b686-1f37edf0c357', 'a2d2f210-831c-4429-be87-fe3c1e3e0df8', '3ada3d57-c8c1-4a77-b8cb-372efe55a8d1', '87588ea5-79ec-423c-b1d6-08f8893ff300'], 'resourceIds': ['4a789fb8-b9ef-44ca-b686-1f37edf0c357', '3ada3d57-c8c1-4a77-b8cb-372efe55a8d1', '87588ea5-79ec-423c-b1d6-08f8893ff300', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'], 'activity0Id': 'a2d2f210-831c-4429-be87-fe3c1e3e0df8', 'address': 'Gainesville, FL, USA', 'notes': '', 'frequency': 'Weekly', 'startRecur': '2024-03-27T13:00:00.000Z', 'endRecur': '2024-03-28T15:00:00.000Z', 'interval': 1, 'orange_sol': False, 'scheduled': True, 'type': 'create', 'daysOfWeek': ['56cbe76a-0cf6-4647-8a49-2ef9fd102079'], 'location0Id': '5aa92eb1-2f5f-46f3-9377-15841e5b3b54', 'loc_id': '5aa92eb1-2f5f-46f3-9377-15841e5b3b54', 'activity': 'Direct', 'funder': 'BCBS/Anthem', 'location': 'Home', 'client': 'Malcolm Payne', 'employee': 'Warkiris Sanchez'}


{'start': '2024-03-27T20:00:00.000Z', 'end': '2024-03-27T22:00:00.000Z', 'users': ['3', '46c3b666-975e-4305-bbd2-ff0e5e4e32fa', '4a789fb8-b9ef-44ca-b686-1f37edf0c357', '6cd405c5-8723-4c74-b429-ca8f4813a510', 'a2d2f210-831c-4429-be87-fe3c1e3e0df8', '87588ea5-79ec-423c-b1d6-08f8893ff300'], 'resourceIds': ['46c3b666-975e-4305-bbd2-ff0e5e4e32fa', '6cd405c5-8723-4c74-b429-ca8f4813a510', '87588ea5-79ec-423c-b1d6-08f8893ff300', '4a789fb8-b9ef-44ca-b686-1f37edf0c357'], 'activity0Id': 'a2d2f210-831c-4429-be87-fe3c1e3e0df8', 'address': 'Gainesville, FL, USA', 'notes': '', 'frequency': 'Weekly', 'startRecur': '2024-03-27T20:00:00.000Z', 'endRecur': '2024-03-28T22:00:00.000Z', 'interval': 1, 'orange_sol': False, 'scheduled': True, 'type': 'create', 'daysOfWeek': ['56cbe76a-0cf6-4647-8a49-2ef9fd102079'], 'location0Id': '5aa92eb1-2f5f-46f3-9377-15841e5b3b54', 'loc_id': '5aa92eb1-2f5f-46f3-9377-15841e5b3b54', 'activity': 'Direct', 'employee': 'Adam Silver', 'client': 'Bazarbay Hamdele', 'funder': 'BCBS/Anthem', 'location': 'Home'}