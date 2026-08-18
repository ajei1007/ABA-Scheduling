import math
from flask import Flask, request
# automation file
import copy
# from automation_v2 import rocket_luncher
from controller import rocket_luncher
import sys
from utils.getBackendURL import getBackendURL
from flask_cors import CORS, cross_origin
from solve import Solution_Generator, Data_Gatherer
import time
# import sentry_sdk
from flask import Flask
import numpy as np
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
import lambda2
# from sentry_sdk.integrations.flask import FlaskIntegration

app = Flask(__name__)
CORS(app, support_credentials=True)
app.config['CORS_HEADERS'] = 'Content-Type'

logging.basicConfig(level=logging.DEBUG)


def data_converter(d):
    obj = {
        'start_date': d['startdate'],  #
        'end_date': d['enddate'],  #
        'branch': d['branches'][0],
        'teams': d['teams'],
        'daily': False,
        'blocks': False,  #
        'is_Multi': True,
        'is_lunch': False,
        'is_break': d['breaktime'],
        'is_orange': True,
        'is_events': True,
        'percentage': d["percentignore"],  # percentage
        # 'objective_role': 'R/BT',
        'objective_role': d["objectiverole"],
        'insert_data_role': 'Person',
        'slot_length': 15,
        'max_time_in_seconds': 100.0,
        'num_search_workers': d['workers'],
        'min_session_dur': d['minsession'],  # [1]
        'max_session_length': float(d['maxsession']),
        'no_gap_role': "Person",
        'overlap_role': 'Person',
        'team_bounds': {
            'num_of_teams': 5,
            'r': 4,
            'min_people_per_team': 5
        },
        'lunch_role': 'Employee',
        'lunch_length': 2,
        'break_role': 'Employee',
        'break_length': 1,
        'part1': d['part1'],
        'is_time_constraint': False,
        'is_drive_constraint': False,
        'is_lunch_constraint': d['constraintlunch'],
        'is_break_constraint': d['breaktime'],
        'is_team_constraint': False,
        'is_overlap_constraint': True,
        'is_minSession_constraint': True,
        'is_noGap_constraint': True,
        'is_delete': False,
        'optimize_current': False,
        'host': str(getBackendURL()),
        'all_or_nothing': d["all_or_nothing"],
        "break_id": d["break_id"],
        "drive_id": d["drive_id"],
        "lunch_id": d["lunch_id"],
        "objectiveactivity": d["objectiveactivity"],
        "billable": d["billable"],
        "nonbillable": d["nonbillable"],
        # For Solution_Generator:
        "expanded_resources": d["objectiveactivity"],
        "uncheckWhiteSolutionConstraints":
        d["uncheckWhiteSolutionConstraints"],
        "uncheckOrangeSolutionConstraints":
        d["uncheckOrangeSolutionConstraints"],
        "settings": d["settings"],
        "companyId": d["companyId"]
    }
    if obj['is_lunch']:
        obj["expanded_resources"] = [
            *obj["expanded_resources"], obj["lunch_id"]
        ]
    if obj['is_break']:
        obj["expanded_resources"] = [
            *obj["expanded_resources"], obj["break_id"]
        ]
    return obj


@app.route("/")
def hello_world():
    return f'Successfully deployed using CI/CD by ABA Schedules Team, Backend API: {getBackendURL()}'


@app.route('/test', methods=['POST'])
@cross_origin(supports_credentials=True)
def test_api():
    data = request.json
    print("***** Data : ", data)
    return {'data': data}


@app.route('/solution_generator', methods=['POST'])
@cross_origin(supports_credentials=True)
def solution_generator():
    data = request.json
    # print("***** Data : ", data)
    header = request.headers
    a = {}
    b = {
        'host': str(getBackendURL()),
        'header': {
            'Authorization': header['Authorization']
        }
    }
    a.update(b)
    a.update(data["data"])
    print('soompy', a)
    start1 = time.time()
    data_gatherer = Data_Gatherer(a)
    start2 = time.time()
    print('stopwatch data_gatherer: ', start2 - start1)
    solutions1 = Solution_Generator(
        data_gatherer, {
            "is_orange": False,
            "ignoreConstraintArray": a["uncheckWhiteSolutionConstraints"],
            'investigate': [],
            "soft": False
        })
    solutions2 = Solution_Generator(
        data_gatherer, {
            "is_orange": True,
            "ignoreConstraintArray": a["uncheckOrangeSolutionConstraints"],
            'investigate': a['investigate'],
            "soft": True
        })
    # solutions1.time_to_slot()
    format = '%Y-%m-%d'

    start = datetime.datetime.strptime(solutions1.start_date, format)
    end = datetime.datetime.strptime(solutions1.end_date, format)

    interval_start = solutions1.time_to_slot(start.strftime('%H:%M:%S'),
                                             (start.weekday() + 1) % 7, 15)
    interval_end = solutions1.time_to_slot(end.strftime('%H:%M:%S'),
                                           (end.weekday() + 1) % 7, 15)

    # fake_list = np.arange(interval_start, interval_end, math.floor(
    #     (interval_end-interval_start)/10)).tolist()
    # actual_list = []
    # for index, i in enumerate(fake_list):
    #     if index != len(fake_list)-1:
    #         actual_list.append([i, fake_list[index+1]])

    # print('foogy', actual_list, interval_start, interval_end, start, end)
    # solutions_orange = Solution_Generator(data_gatherer, {"is_orange": True})
    # arr = [[100, 130], [130, 160], [160, 190], [190, 220]]
    real_results = []
    # with ThreadPoolExecutor() as executor:
    #     results = executor.map(solutions1.main2, actual_list)
    #     for result in results:
    #         real_results = [*real_results, *result]
    #         print('multi_res : ', result)
    # events_poss = real_results

    events_poss = solutions1.main2()
    start3 = time.time()
    print('stopwatch events_poss_main2 ', start3 - start2)
    events_poss = solutions1.main3()
    start4 = time.time()
    print('stopwatch events_poss_main3 ', start4 - start3)
    events_poss_white = []
    events_poss_orange = []
    # for event in events_poss:
    #     if len(event['reasons']) == 0:
    #         events_poss_white.append(event)
    #     else:
    #         events_poss_orange.append(event)
    unmatch_poss_events = []
    # unmatch_poss_events = solutions2.main2()
    unmatch_poss_events = solutions2.main2()
    start5 = time.time()
    print('stopwatch unmatch_events_poss_main2 ', start5 - start4)
    unmatch_poss_events = solutions2.main3()
    start6 = time.time()
    print('stopwatch events_poss_main3 ', start6 - start5)
    # events_poss = solutions1.main_drive_time()
    # unmatch_poss_events = solutions2.main_drive_time()
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

    print('smeezer', poss_events_obj)

    # unmatch_poss_events = solutions_orange.main2()
    print("e_po :", events_poss)
    print("une_po :", unmatch_poss_events_new)

    return {
        'intersections': [],
        'poss_events': events_poss,
        'unmatch_poss_events': unmatch_poss_events_new
        # 'poss_events': events_poss_white,
        # 'unmatch_poss_events': events_poss_orange
    }


@app.route("/optimizer", methods=['POST'])
@cross_origin(supports_credentials=True)
def optimizer():
    data = request.get_json()
    print(data)


@app.route("/automation", methods=['POST'])
@cross_origin(supports_credentials=True)
def automate():
    start_time = time.time()
    data = request.json
    header = request.headers
    print('Hello world - sys.stderr', file=sys.stderr)
    app.logger.info('Hello world - app.logger.info')
    # print('data ', data)
    print('header: ', header)
    a = data_converter(data['data'])
    d1 = datetime.datetime.strptime(a['end_date'], "%Y-%m-%d")
    d2 = datetime.datetime.strptime(a['start_date'], "%Y-%m-%d")

    delta = d1 - d2
    b = {'header': {'Authorization': header['Authorization']}}
    a.update(b)
    a["part1_new"] = copy.copy(a["part1"])
    print("json_data : ", a)
    if delta.days > 7:
        return {'status': "Day range should be less than or equal to 7 days"}
    a["objectiveactivity"] = a['billable']
    a["expanded_resources"] = a['billable']
    if a['is_lunch']:
        a["expanded_resources"] = [*a["expanded_resources"], a["lunch_id"]]
    if a['is_break']:
        a["expanded_resources"] = [*a["expanded_resources"], a["break_id"]]
    print('somethig_def_wrong', a)

    result = rocket_luncher(a)

    # a["is_lunch_constraint"] = False
    # a["is_lunch"] = False
    # # a['min_session_dur'] = 15
    # # a["max_session_length"] = 480
    # a['part1'] = True
    # a["objectiveactivity"] = a['nonbillable']
    # a["expanded_resources"] = a['nonbillable']
    # print('bazarbay', a)
    # if a["part1_new"] and a["objectiveactivity"] != []:
    #     result = rocket_luncher(a)
    end_time = time.time()
    print(end_time - start_time)
    return {'status': result}


# Montoring
# sentry_sdk.init(
#     dsn=
#     "https://826ec27f09bc49debd0f7268a0386ad7@o4504678950174720.ingest.sentry.io/4504724317011968",
#     integrations=[
#         FlaskIntegration(),
#     ],
#     traces_sample_rate=1.0,
#     _experiments={
#         "profiles_sample_rate": 1.0,
#     })

if __name__ == '__name__':
    app.run(debugger=True)
