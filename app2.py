import copy
import datetime
import json
import os
import signal
import sys
import time
from flask import Flask, request, Response, send_file
from flask_cors import CORS, cross_origin
import logging
from controller import rocket_luncher
from automation_inbloom import rocket_luncher_inbloom
from core.optimizer.optimizer import runOptimizer
from api.utils import data_converter
from analyzer import Analyzer
from api.lambda_handler import handler
from core.optimizer.team_optimizer import lambda_handler

import signal
import sys
import traceback
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True)

logging.basicConfig(level=logging.DEBUG)


@app.route("/optimizer/test_insert", methods=["GET", "POST"])
@cross_origin(supports_credentials=True)
def test_insert():
    print("test_insert")
    event_str = {
        "body": '{"data":{"header":{"Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiOTJiMTg5N2YtYWMxYy00MWE5LWE1NDAtOTQ5OGJkZGI0MjYyIiwiZW1haWwiOiJEZW1vQWNjb3VudEBtYWlsLmNvbSJ9LCJpYXQiOjE3MTMzNjczMDAsImV4cCI6MjMzMTMzNjczMDB9.03m_u4crzLESP_-YzGAyum9-EJDOMZ3n6Wrj_GW-Dwg"},"start_date":"2024-04-22","end_date":"2024-04-23","branch":"1c0368e9-ec85-484c-b28b-b618271f8d49","expanded_resources":["ee9ecd25-4f88-40a9-a80e-7a4bbeb9c752"],"expanded_resources_filter":[],"resourceCombinationsExclude":[],"uncheckWhiteSolutionConstraints":[],"uncheckOrangeSolutionConstraints":[],"investigate":[],"settings":{"initialized":"no","statsDefault":[],"statsViewEnabled":false,"defaultActivity":"96b98026-42fa-4a21-86b8-d22ec679c3f7","defaultLocation":null,"noGaps":false,"driveTime":false,"weekends":false,"blocks":false,"orange":false,"overbooking":false,"emptyAvailability":false,"notAvailableBusy":false,"differentBranch":false,"hideCancelations":false,"subgroupsFilter":[],"roleFilter":[],"quickStatFilter":["Direct 1:1","Drive","Admin"],"isolatedResources":[],"businessStartTime":"2024-01-18T11:00:00.000Z","businessEndTime":"2024-01-19T02:00:00.000Z","backgroundColorRole":"Activity","borderColorRole":"Activity","timezone":"America/Chicago","subgroupsFilterLabels":null,"resourceFilterLabels":null,"isolateCanceled":false,"timeConstraintUpperBuffer":null,"timeConstraintLowerBuffer":null,"timeconstraints":false,"teamSeparation":1,"driveDistanceMax":false,"driveDistanceMaxQuantity":null,"driveDistanceMaxUnit":null,"driveTimeQuantity":null,"locationQuantity":2,"branchDefault":null,"totalCustom":"total","timeInterval":15,"driveTimeUnit":"Minutes"},"soft":[],"highPriority":["25992fb8-3ce6-451c-824c-d2012657e46d","ac7b0229-5ced-4e72-aacb-b40e5159d983"],"disabled":[],"hard":[]}}',
        "cookies": [],
        "headers": {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "1788",
            "Content-Type": "application/json",
            "Host": "127.0.0.1:5002",
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Forwarded-Port": "5002",
            "X-Forwarded-Proto": "http",
        },
        "isBase64Encoded": False,
        "pathParameters": {},
        "rawPath": "/test_insert",
        "rawQueryString": "",
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "1234567890",
            "domainName": "localhost",
            "domainPrefix": "localhost",
            "http": {
                "method": "POST",
                "path": "/test_insert",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "Custom User Agent String",
            },
            "requestId": "187cec2d-44d2-428b-8f51-0075919695e0",
            "routeKey": "POST /test_insert",
            "stage": "development",
            "time": "20/Apr/2024:23:26:39 +0000",
            "timeEpoch": 1713655599,
        },
        "routeKey": "POST /test_insert",
        "stageVariables": None,
        "version": "2.0",
    }
    body = event_str["body"]
    body_dict = json.loads(body)
    # return request.get_json()
    # print('see_bass', request.get_json())
    # body_dict['data']= request.get_json()['data']
    body_dict["data"] = request.get_json()
    event_str["body"] = json.dumps(body_dict)
    # return event_str

    response = handler(event_str)
    event_str["response"] = response
    return response["body"]


@app.route("/optimizer/solution_generator", methods=["GET", "POST"])
@cross_origin(supports_credentials=True)
def solution_generator():
    print("Solution generator")
    event_str = {
        "body": '{"data":{"header":{"Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiOTJiMTg5N2YtYWMxYy00MWE5LWE1NDAtOTQ5OGJkZGI0MjYyIiwiZW1haWwiOiJEZW1vQWNjb3VudEBtYWlsLmNvbSJ9LCJpYXQiOjE3MTMzNjczMDAsImV4cCI6MjMzMTMzNjczMDB9.03m_u4crzLESP_-YzGAyum9-EJDOMZ3n6Wrj_GW-Dwg"},"start_date":"2024-04-22","end_date":"2024-04-23","branch":"1c0368e9-ec85-484c-b28b-b618271f8d49","expanded_resources":["ee9ecd25-4f88-40a9-a80e-7a4bbeb9c752"],"expanded_resources_filter":[],"resourceCombinationsExclude":[],"uncheckWhiteSolutionConstraints":[],"uncheckOrangeSolutionConstraints":[],"investigate":[],"settings":{"initialized":"no","statsDefault":[],"statsViewEnabled":false,"defaultActivity":"96b98026-42fa-4a21-86b8-d22ec679c3f7","defaultLocation":null,"noGaps":false,"driveTime":false,"weekends":false,"blocks":false,"orange":false,"overbooking":false,"emptyAvailability":false,"notAvailableBusy":false,"differentBranch":false,"hideCancelations":false,"subgroupsFilter":[],"roleFilter":[],"quickStatFilter":["Direct 1:1","Drive","Admin"],"isolatedResources":[],"businessStartTime":"2024-01-18T11:00:00.000Z","businessEndTime":"2024-01-19T02:00:00.000Z","backgroundColorRole":"Activity","borderColorRole":"Activity","timezone":"America/Chicago","subgroupsFilterLabels":null,"resourceFilterLabels":null,"isolateCanceled":false,"timeConstraintUpperBuffer":null,"timeConstraintLowerBuffer":null,"timeconstraints":false,"teamSeparation":1,"driveDistanceMax":false,"driveDistanceMaxQuantity":null,"driveDistanceMaxUnit":null,"driveTimeQuantity":null,"locationQuantity":2,"branchDefault":null,"totalCustom":"total","timeInterval":15,"driveTimeUnit":"Minutes"},"soft":[],"highPriority":["25992fb8-3ce6-451c-824c-d2012657e46d","ac7b0229-5ced-4e72-aacb-b40e5159d983"],"disabled":[],"hard":[]}}',
        "cookies": [],
        "headers": {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "1788",
            "Content-Type": "application/json",
            "Host": "127.0.0.1:5002",
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Forwarded-Port": "5002",
            "X-Forwarded-Proto": "http",
        },
        "isBase64Encoded": False,
        "pathParameters": {},
        "rawPath": "/solution_generator",
        "rawQueryString": "",
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "1234567890",
            "domainName": "localhost",
            "domainPrefix": "localhost",
            "http": {
                "method": "POST",
                "path": "/solution_generator",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "Custom User Agent String",
            },
            "requestId": "187cec2d-44d2-428b-8f51-0075919695e0",
            "routeKey": "POST /solution_generator",
            "stage": "development",
            "time": "20/Apr/2024:23:26:39 +0000",
            "timeEpoch": 1713655599,
        },
        "routeKey": "POST /solution_generator",
        "stageVariables": None,
        "version": "2.0",
    }
    body = event_str["body"]
    body_dict = json.loads(body)
    request_data = request.get_json()
    data = request_data.get("data", {})
    tenant_id = request.headers.get("x-tenant-id")
    print("tenant_id", tenant_id, request.headers)
    body_dict["data"] = data
    event_str["body"] = json.dumps(body_dict)
    event_str["headers"]["X-Tenant-Id"] = tenant_id
    event_str["headers"]["x-tenant-id"] = tenant_id
    response = handler(event_str)
    event_str["response"] = response
    return response["body"]


@app.route("/optimizer/teams", methods=["GET", "POST"])
@cross_origin(supports_credentials=True)
def team_optimizer():
    try:
        print("Request Body:", request.get_json())
        event = {"body": json.dumps(request.get_json())}
        result = lambda_handler(event, None)
        return result
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/optimizer/staff_tracker", methods=["GET", "POST"])
@cross_origin(supports_credentials=True)
def staff_tracker():
    event_str = {
        "body": '{"data":{"header":{"Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiOTJiMTg5N2YtYWMxYy00MWE5LWE1NDAtOTQ5OGJkZGI0MjYyIiwiZW1haWwiOiJEZW1vQWNjb3VudEBtYWlsLmNvbSJ9LCJpYXQiOjE3MTMzNjczMDAsImV4cCI6MjMzMTMzNjczMDB9.03m_u4crzLESP_-YzGAyum9-EJDOMZ3n6Wrj_GW-Dwg"},"start_date":"2024-04-22","end_date":"2024-04-23","branch":"1c0368e9-ec85-484c-b28b-b618271f8d49","expanded_resources":["ee9ecd25-4f88-40a9-a80e-7a4bbeb9c752"],"expanded_resources_filter":[],"resourceCombinationsExclude":[],"uncheckWhiteSolutionConstraints":[],"uncheckOrangeSolutionConstraints":[],"investigate":[],"settings":{"initialized":"no","statsDefault":[],"statsViewEnabled":false,"defaultActivity":"96b98026-42fa-4a21-86b8-d22ec679c3f7","defaultLocation":null,"noGaps":false,"driveTime":false,"weekends":false,"blocks":false,"orange":false,"overbooking":false,"emptyAvailability":false,"notAvailableBusy":false,"differentBranch":false,"hideCancelations":false,"subgroupsFilter":[],"roleFilter":[],"quickStatFilter":["Direct 1:1","Drive","Admin"],"isolatedResources":[],"businessStartTime":"2024-01-18T11:00:00.000Z","businessEndTime":"2024-01-19T02:00:00.000Z","backgroundColorRole":"Activity","borderColorRole":"Activity","timezone":"America/Chicago","subgroupsFilterLabels":null,"resourceFilterLabels":null,"isolateCanceled":false,"timeConstraintUpperBuffer":null,"timeConstraintLowerBuffer":null,"timeconstraints":false,"teamSeparation":1,"driveDistanceMax":false,"driveDistanceMaxQuantity":null,"driveDistanceMaxUnit":null,"driveTimeQuantity":null,"locationQuantity":2,"branchDefault":null,"totalCustom":"total","timeInterval":15,"driveTimeUnit":"Minutes"},"soft":[],"highPriority":["25992fb8-3ce6-451c-824c-d2012657e46d","ac7b0229-5ced-4e72-aacb-b40e5159d983"],"disabled":[],"hard":[]}}',
        "cookies": [],
        "headers": {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "1788",
            "Content-Type": "application/json",
            "Host": "127.0.0.1:5002",
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Forwarded-Port": "5002",
            "X-Forwarded-Proto": "http",
        },
        "isBase64Encoded": False,
        "pathParameters": {},
        "rawPath": "/staff_tracker",
        "rawQueryString": "",
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "1234567890",
            "domainName": "localhost",
            "domainPrefix": "localhost",
            "http": {
                "method": "POST",
                "path": "/staff_tracker",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "Custom User Agent String",
            },
            "requestId": "187cec2d-44d2-428b-8f51-0075919695e0",
            "routeKey": "POST /staff_tracker",
            "stage": "development",
            "time": "20/Apr/2024:23:26:39 +0000",
            "timeEpoch": 1713655599,
        },
        "routeKey": "POST /staff_tracker",
        "stageVariables": None,
        "version": "2.0",
    }
    body = event_str["body"]
    body_dict = json.loads(body)
    body_dict["data"] = request.get_json()["data"]
    event_str["body"] = json.dumps(body_dict)
    response = handler(event_str)
    return response["body"]


@app.route("/optimizer/staff_equilibrium", methods=["GET", "POST"])
@cross_origin(supports_credentials=True)
def staff_equilibrium():
    print("limmy5")
    event_str_equilibrium = {
        "body": '{"data":{"header":{"Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiOTJiMTg5N2YtYWMxYy00MWE5LWE1NDAtOTQ5OGJkZGI0MjYyIiwiZW1haWwiOiJEZW1vQWNjb3VudEBtYWlsLmNvbSJ9LCJpYXQiOjE3MTMzNjczMDAsImV4cCI6MjMzMTMzNjczMDB9.03m_u4crzLESP_-YzGAyum9-EJDOMZ3n6Wrj_GW-Dwg"},"start_date":"2024-04-22","end_date":"2024-04-23","branch":"1c0368e9-ec85-484c-b28b-b618271f8d49","expanded_resources":["ee9ecd25-4f88-40a9-a80e-7a4bbeb9c752"],"expanded_resources_filter":[],"resourceCombinationsExclude":[],"uncheckWhiteSolutionConstraints":[],"uncheckOrangeSolutionConstraints":[],"investigate":[],"settings":{"initialized":"no","statsDefault":[],"statsViewEnabled":false,"defaultActivity":"96b98026-42fa-4a21-86b8-d22ec679c3f7","defaultLocation":null,"noGaps":false,"driveTime":false,"weekends":false,"blocks":false,"orange":false,"overbooking":false,"emptyAvailability":false,"notAvailableBusy":false,"differentBranch":false,"hideCancelations":false,"subgroupsFilter":[],"roleFilter":[],"quickStatFilter":["Direct 1:1","Drive","Admin"],"isolatedResources":[],"businessStartTime":"2024-01-18T11:00:00.000Z","businessEndTime":"2024-01-19T02:00:00.000Z","backgroundColorRole":"Activity","borderColorRole":"Activity","timezone":"America/Chicago","subgroupsFilterLabels":null,"resourceFilterLabels":null,"isolateCanceled":false,"timeConstraintUpperBuffer":null,"timeConstraintLowerBuffer":null,"timeconstraints":false,"teamSeparation":1,"driveDistanceMax":false,"driveDistanceMaxQuantity":null,"driveDistanceMaxUnit":null,"driveTimeQuantity":null,"locationQuantity":2,"branchDefault":null,"totalCustom":"total","timeInterval":15,"driveTimeUnit":"Minutes"},"soft":[],"highPriority":["25992fb8-3ce6-451c-824c-d2012657e46d","ac7b0229-5ced-4e72-aacb-b40e5159d983"],"disabled":[],"hard":[]}}',
        "cookies": [],
        "headers": {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "1788",
            "Content-Type": "application/json",
            "Host": "127.0.0.1:5002",
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Forwarded-Port": "5002",
            "X-Forwarded-Proto": "http",
        },
        "isBase64Encoded": False,
        "pathParameters": {},
        "rawPath": "/staff_equilibrium",
        "rawQueryString": "",
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "1234567890",
            "domainName": "localhost",
            "domainPrefix": "localhost",
            "http": {
                "method": "POST",
                "path": "/staff_equilibrium",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "Custom User Agent String",
            },
            "requestId": "187cec2d-44d2-428b-8f51-0075919695e0",
            "routeKey": "POST /staff_equilibrium",
            "stage": "development",
            "time": "20/Apr/2024:23:26:39 +0000",
            "timeEpoch": 1713655599,
        },
        "routeKey": "POST /staff_equilibrium",
        "stageVariables": None,
        "version": "2.0",
    }
    event_str_staff = {
        "body": '{"data":{"header":{"Authorization":"Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiOTJiMTg5N2YtYWMxYy00MWE5LWE1NDAtOTQ5OGJkZGI0MjYyIiwiZW1haWwiOiJEZW1vQWNjb3VudEBtYWlsLmNvbSJ9LCJpYXQiOjE3MTMzNjczMDAsImV4cCI6MjMzMTMzNjczMDB9.03m_u4crzLESP_-YzGAyum9-EJDOMZ3n6Wrj_GW-Dwg"},"start_date":"2024-04-22","end_date":"2024-04-23","branch":"1c0368e9-ec85-484c-b28b-b618271f8d49","expanded_resources":["ee9ecd25-4f88-40a9-a80e-7a4bbeb9c752"],"expanded_resources_filter":[],"resourceCombinationsExclude":[],"uncheckWhiteSolutionConstraints":[],"uncheckOrangeSolutionConstraints":[],"investigate":[],"settings":{"initialized":"no","statsDefault":[],"statsViewEnabled":false,"defaultActivity":"96b98026-42fa-4a21-86b8-d22ec679c3f7","defaultLocation":null,"noGaps":false,"driveTime":false,"weekends":false,"blocks":false,"orange":false,"overbooking":false,"emptyAvailability":false,"notAvailableBusy":false,"differentBranch":false,"hideCancelations":false,"subgroupsFilter":[],"roleFilter":[],"quickStatFilter":["Direct 1:1","Drive","Admin"],"isolatedResources":[],"businessStartTime":"2024-01-18T11:00:00.000Z","businessEndTime":"2024-01-19T02:00:00.000Z","backgroundColorRole":"Activity","borderColorRole":"Activity","timezone":"America/Chicago","subgroupsFilterLabels":null,"resourceFilterLabels":null,"isolateCanceled":false,"timeConstraintUpperBuffer":null,"timeConstraintLowerBuffer":null,"timeconstraints":false,"teamSeparation":1,"driveDistanceMax":false,"driveDistanceMaxQuantity":null,"driveDistanceMaxUnit":null,"driveTimeQuantity":null,"locationQuantity":2,"branchDefault":null,"totalCustom":"total","timeInterval":15,"driveTimeUnit":"Minutes"},"soft":[],"highPriority":["25992fb8-3ce6-451c-824c-d2012657e46d","ac7b0229-5ced-4e72-aacb-b40e5159d983"],"disabled":[],"hard":[]}}',
        "cookies": [],
        "headers": {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Content-Length": "1788",
            "Content-Type": "application/json",
            "Host": "127.0.0.1:5002",
            "Origin": "http://localhost:3000",
            "Referer": "http://localhost:3000/",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Forwarded-Port": "5002",
            "X-Forwarded-Proto": "http",
        },
        "isBase64Encoded": False,
        "pathParameters": {},
        "rawPath": "/staff_tracker",
        "rawQueryString": "",
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "1234567890",
            "domainName": "localhost",
            "domainPrefix": "localhost",
            "http": {
                "method": "POST",
                "path": "/staff_tracker",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "Custom User Agent String",
            },
            "requestId": "187cec2d-44d2-428b-8f51-0075919695e0",
            "routeKey": "POST /staff_tracker",
            "stage": "development",
            "time": "20/Apr/2024:23:26:39 +0000",
            "timeEpoch": 1713655599,
        },
        "routeKey": "POST /staff_tracker",
        "stageVariables": None,
        "version": "2.0",
    }
    body = event_str_staff["body"]
    body_dict = json.loads(body)
    body_dict["data"] = request.get_json()["data"]
    event_str_staff["body"] = json.dumps(body_dict)
    response = handler(event_str_staff)
    body = event_str_equilibrium["body"]
    body_dict_equilibrium = json.loads(body)
    body_dict_equilibrium["data"] = response
    event_str_equilibrium["body"] = json.dumps(body_dict_equilibrium)
    response = handler(event_str_equilibrium)
    return response["body"]


@app.route("/optimizer/automation", methods=["GET", "POST"])
@cross_origin(supports_credentials=True)
def automation():
    try:
        body = request.get_json()
        data = body.get("data", {})
        tenant_id = request.headers.get("X-Tenant-Id")
        data["header"]["X-Tenant-Id"] = tenant_id
        converted_data = data_converter(data)

        converted_data["part1_new"] = copy.copy(converted_data.get("part1", []))
        converted_data["objectiveactivity"] = converted_data.get(
            "activitiesRanking", []
        )
        converted_data["mode"] = converted_data.get("mode", "fast")
        converted_data["expanded_resources"] = converted_data.get(
            "activitiesRanking", []
        )

        try:
            start_date = datetime.datetime.strptime(
                converted_data["start_date"], "%Y-%m-%d"
            )
            end_date = datetime.datetime.strptime(
                converted_data["end_date"], "%Y-%m-%d"
            )
            if (end_date - start_date).days > 7:
                return {"status": "Day range should be less than or equal to 7 days"}
        except KeyError:
            return {"status": "Invalid date format or missing start_date/end_date"}

        if converted_data.get("is_lunch"):
            converted_data["expanded_resources"].append(converted_data.get("lunch_id"))
        if converted_data.get("is_break"):
            converted_data["expanded_resources"].append(converted_data.get("break_id"))

        if converted_data.get("analyzeMode"):
            analyzer = Analyzer(converted_data)
            final_data = analyzer.isNoGapRelatedIssues()
            result = runOptimizer(final_data)
        else:
            result = runOptimizer(converted_data)
        return json.dumps(result)

    except Exception as e:
        print("Automation Error:", e)
        traceback.print_exc()  # Log detailed error traceback
        return json.dumps({"error": "Something went wrong!"})


def shutdown_server(signum, frame):
    print("Shutting down the server...")
    # Add any cleanup code here
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown_server)
    app.run(host="0.0.0.0", port=80, debug=True)
