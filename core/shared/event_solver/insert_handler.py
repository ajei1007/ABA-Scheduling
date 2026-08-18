import datetime
import math
import gc
import traceback
import json
from collections import defaultdict
from core.shared.utils import deserialize_instance
from core.shared.event_solver.automate import Automate
from core.shared.utils import (
    find_from_resources,
    calculate_time_difference,
    intersection,
    slot_to_time,
    object_for_return,
    round_to_nearest_interval,
    normalize_time,
)


def remove_duplicate_lunches(deletingEvents, creatingEvents):
    deleting_lunch_keys = {}
    for event in deletingEvents:
        if event.get("type") == "delete" and "Lunch" in event.get("title", ""):
            lunch_key = (
                frozenset(event["resourceIds"]),
                normalize_time(event["start"]),
                normalize_time(event["end"]),
            )
            deleting_lunch_keys[lunch_key] = event

    matched_keys = set()
    filtered_creatingEvents = []

    for event in creatingEvents:
        if "Lunch" in event.get("activity", ""):
            lunch_key = (
                frozenset(event["resourceIds"]),
                normalize_time(event["start"]),
                normalize_time(event["end"]),
            )

            for del_key in deleting_lunch_keys:
                if lunch_key[1:] == del_key[1:] and lunch_key[0].issubset(del_key[0]):
                    matched_keys.add(del_key)
                    break
            else:
                filtered_creatingEvents.append(event)
        else:
            filtered_creatingEvents.append(event)

    filtered_deletingEvents = [
        event
        for event in deletingEvents
        if not (
            "Lunch" in event.get("title", "")
            and (
                frozenset(event["resourceIds"]),
                normalize_time(event["start"]),
                normalize_time(event["end"]),
            )
            in matched_keys
        )
    ]

    return filtered_deletingEvents, filtered_creatingEvents


def merge_duration(intervals):
    """Merge overlapping [start, end) intervals."""
    merged = []
    for s, e in sorted(intervals):
        if not merged or s >= merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)
    return merged


def insert_handler(event, context):
    try:
        input_data = event
        serialized_start_date_original = input_data["start_date_original"]
        start_date_original = deserialize_instance(serialized_start_date_original)
        resources_team = input_data["resources_team"]
        data = input_data["data"]
        is_week = (
            datetime.datetime.strptime(data["end_date"], "%Y-%m-%d").date()
            - datetime.datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        ).days > 1
        try:
            drive_data = deserialize_instance(input_data["constraint_drive_data"])
        except Exception as e:
            print(f"Error deserializing 'constraint_drive_data': {e}")
        if "fake_user_starts_ends" in data:
            try:
                data["fake_user_starts_ends"] = deserialize_instance(
                    data["fake_user_starts_ends"]
                )
            except Exception as e:
                print(f"Error deserializing 'fake_user_starts_ends': {e}")
        date_original = input_data["date_original"]
        data2_team = input_data["data2_team"]
        aut_arr = input_data["aut_arr"]
        overlaped_ids = input_data["overlaped_ids"]
        resources = input_data["resources"]
        roles_hierarchy = input_data["roles_hierarchy"]
        distance_matrix = input_data["distance_matrix"]
        received_solution1 = input_data["solution1"]
        if "resources1" in received_solution1:
            if "frequency_constraints" in received_solution1["resources1"]:
                received_solution1["resources1"]["frequency_constraints"] = (
                    deserialize_instance(
                        received_solution1["resources1"]["frequency_constraints"]
                    )
                )

            if "resources" in received_solution1["resources1"]:
                received_solution1["resources1"]["resources"] = deserialize_instance(
                    received_solution1["resources1"]["resources"]
                )
        solution1 = {
            "events2": received_solution1.get("events2"),
            "users": received_solution1.get("users"),
            "created_events": received_solution1.get("created_events"),
            "user_availabilities_general": received_solution1.get(
                "user_availabilities_general"
            ),
            "resources1": received_solution1.get("resources1"),
            "user_uuid_to_index": received_solution1.get("user_uuid_to_index"),
            "branches": received_solution1.get("branches"),
            "events_poss": received_solution1.get("events_poss"),
            "flags": deserialize_instance(received_solution1.get("flags")),
        }
        efficiency = input_data["efficiency"]
        employees_ids = input_data["employees_ids"]
        availability_person = input_data["availability_person"]

        deletingEvents = []
        all_appointments = []
        updatingEvents = []
        creatingEvents = []
        created_events = []
        deleted_appointments_list = []
        created_hours = 0
        deleted_hours = 0
        best_bound = 0
        founded = 0
        status_name = ""
        loc_id_2 = None

        returned_arr = []
        objective_value = 0
        for act_id in [data["objectiveactivity"]]:
            resources_used = []
            aut2 = Automate(
                resources_team,
                roles_hierarchy,
                data,
                drive_data,
                resources_used,
                distance_matrix,
                solution1,
            )
            aut2.solve_model(data2_team, [], [])
            objective_value = aut2.objective_value
            disabled_constraints = aut2.disabled_constraints
            if aut2 is None:
                pass
            employees_ids = aut2.employees_ids
            availability_person = aut2.availability_persons
            activity_list = aut2.find_ids_by_role(["Activity"])
            people_list = aut2.find_ids_by_role(["Employee"])
            people_appointments = {}
            for id in people_list:
                people_appointments[id] = []
            event_obj = {}
            teams_dict = {}
            # print(f"people appointments: {people_appointments}")
            print(f"finished running solve_model of Automate")
            for t in aut2.see_here:
                print(
                    "see_here",
                    t[0],
                    aut2.solver.Value(t[1]),
                    aut2.solver.Value(t[2]),
                    aut2.solver.Value(t[3]),
                    aut2.solver.Value(t[4]),
                    aut2.solver.Value(t[5]),
                    t[6],
                )
            if len(aut2.get_team_vals()) > 0:
                for k, v in aut2.get_team_vals().items():
                    teams_dict[k] = aut2.solver.Value(v)
            print(f"optimzier printer solution count: {aut2.printer.solution_count()}")
            if aut2.printer.solution_count() != 0:
                # print(f"all generated slots: {aut2.resources1.slots.items()}")
                for tup, event in aut2.resources1.slots.items():
                    if aut2.solver.Value(event[0]) > 0 or (event[5] == True):

                        resources_ids = tuple(list(tup)[3:])
                        first = tuple(list(tup)[:3])
                        if resources_ids in event_obj.keys():
                            event_obj[resources_ids].append(first)
                        else:
                            event_obj[resources_ids] = [first]
                del_arr = []

                print(f"formatted event object: {event_obj.items()}")

                user_intervals = defaultdict(list)

                for tup, slots in event_obj.items():
                    users = list(set(list(tup)))

                    if len(users) == 1:
                        continue
                    for times in slots:
                        try:
                            str3 = times + tup
                            if (
                                str3 in aut2.resources1.slots.keys()
                                and False == aut2.resources1.slots[str3][17]
                            ):
                                # inte = aut2.solver.Value(aut2.resources1.slots[str3][0])
                                dur_slots = aut2.solver.Value(
                                    aut2.resources1.slots[str3][0]
                                )
                                start_slot = aut2.solver.Value(
                                    aut2.resources1.slots[str3][3]
                                )
                                end_slot = start_slot + dur_slots
                                inte_start = aut2.solver.Value(
                                    aut2.resources1.slots[str3][3]
                                )
                                inte_end = aut2.solver.Value(
                                    aut2.resources1.slots[str3][4]
                                )
                                address = aut2.resources1.slots[str3][7]
                                loc_id = aut2.resources1.slots[str3][12]
                                loc_id2 = aut2.resources1.slots[str3][15]
                                scheduled = aut2.resources1.slots[str3][5]
                                real_event_ids = []
                                for event in solution1["events2"]:
                                    real_event_ids.append(event["id"])
                                delete_event = aut2.solver.Value(
                                    aut2.resources1.slots[str3][11]
                                )
                                update_event = aut2.solver.Value(
                                    aut2.resources1.slots[str3][16]
                                )
                                event_id = aut2.resources1.slots[str3][9]
                                delete_event_id = aut2.resources1.slots[str3][9]
                                if (
                                    aut2.resources1.priorities[str3]["faker"]
                                    and delete_event == 0
                                ):
                                    continue
                                try:
                                    if delete_event == 0 and update_event == 0:
                                        pass
                                    if delete_event == 0 and update_event == 1:
                                        del_arr.append(delete_event_id)
                                        for del_event in aut2.deletable_events:
                                            if del_event["id"] == delete_event_id:
                                                type_delete = {"type": "delete"}

                                                some_dict_for_delete = (
                                                    find_from_resources(
                                                        resources,
                                                        del_event["resourceIds"],
                                                    )
                                                )
                                                type_delete.update(del_event)
                                                type_delete.update(some_dict_for_delete)
                                                deletingEvents.append(type_delete)
                                                deleted_hours += (
                                                    calculate_time_difference(
                                                        type_delete["start"],
                                                        type_delete["end_real_time"],
                                                    )
                                                )
                                            else:
                                                pass
                                except Exception as e:
                                    print("bazo_Error : ", e)

                                objective_best_bound = aut2.get_best_objective_bound()

                                sum_del_bol_array = aut2.solver.Value(
                                    aut2.del_bol_array
                                )

                                best_bound = objective_best_bound - sum_del_bol_array

                                status_name = aut2.solver.StatusName()

                                objective_val = aut2.solver.ObjectiveValue()

                                founded = objective_val - sum_del_bol_array

                                start = slot_to_time(inte_start, data["slot_length"])
                                end = slot_to_time(inte_end, data["slot_length"])
                                start_date_original = datetime.datetime.strptime(
                                    date_original, "%Y-%m-%d"
                                )
                                start_day = (
                                    math.floor(
                                        inte_start / (24 * 60 // data["slot_length"])
                                    )
                                    - datetime.datetime.strptime(
                                        date_original, "%Y-%m-%d"
                                    ).weekday()
                                    - 1
                                )
                                new_start = datetime.datetime.strftime(
                                    start_date_original
                                    + datetime.timedelta(days=start_day),
                                    "%Y-%m-%d",
                                )
                                new_end = datetime.datetime.strftime(
                                    start_date_original
                                    + datetime.timedelta(days=start_day + 1),
                                    "%Y-%m-%d",
                                )

                                intersecting_people = intersection(users, people_list)
                                for peep_id in intersecting_people:
                                    people_appointments[peep_id].append(
                                        {
                                            "start": f"{new_start}T{start}.000Z",
                                            "end": f"{new_start}T{end}.000Z",
                                            "startRecur": f"{new_start}T{start}.000Z",
                                            "endRecur": f"{new_end}T{end}.000Z",
                                            "address": address,
                                            "loc_id": loc_id,
                                            "new_start": new_start,
                                            "users": users,
                                            "start_time_r": start,
                                            "end_time_r": end,
                                        }
                                    )
                                intersecting_ids = intersection(
                                    efficiency.keys(), users
                                )
                                if is_week or tup[0] == str(
                                    start_date_original.weekday() + 1
                                ):
                                    for id in intersecting_ids:
                                        # dur = round(inte * data["slot_length"] / 60, 2)
                                        # efficiency[id] += dur
                                        user_intervals[id].append(
                                            (start_slot, end_slot)
                                        )

                                activity_users = intersection(users, activity_list)
                                if activity_users:
                                    activity = activity_users[0]
                                    all_obj = object_for_return(
                                        new_start,
                                        new_end,
                                        start,
                                        end,
                                        users,
                                        activity,
                                        loc_id,
                                        address,
                                        data["start_date"],
                                        data["end_date"],
                                    )
                                    all_appointments.append(all_obj)

                                if not scheduled or update_event == 0:
                                    activity_users = intersection(users, activity_list)
                                    if activity_users:
                                        activity = activity_users[0]

                                        if (
                                            data["drive_id"] in activity
                                            or data["drive_id"][:-1] in activity
                                        ):
                                            pass

                                        my_obj = object_for_return(
                                            new_start,
                                            new_end,
                                            start,
                                            end,
                                            users,
                                            activity,
                                            loc_id,
                                            address,
                                            data["start_date"],
                                            data["end_date"],
                                        )
                                        loc_id_2 = loc_id2
                                        returned_arr.append(my_obj)

                                        resources_with_names = find_from_resources(
                                            resources, my_obj["data"]["users"]
                                        )
                                        my_obj["data"].update(resources_with_names)
                                        my_obj["data"]["users"] = list(set(users))

                                        if update_event == 0:
                                            event_here = {
                                                **my_obj["data"],
                                                "id": event_id,
                                                "type": "update",
                                            }
                                            updatingEvents.append(
                                                {
                                                    **event_here,
                                                    "newEvent": {**event_here},
                                                    "oldEvent": {**event_here},
                                                }
                                            )
                                        else:
                                            creatingEvents.append(my_obj["data"])

                                        created_hours += calculate_time_difference(
                                            my_obj["data"]["start"],
                                            my_obj["data"]["end"],
                                        )
                                        created_events.append(my_obj)

                        except Exception as e:
                            print("bazo_error : ", e)
                deleted_appointments_list = (
                    del_arr
                    + overlaped_ids
                    + [i["id"] for i in aut2.over_availability_events]
                )
                deletingEvents = (
                    deletingEvents
                    + [{"id": i, "type": "delete"} for i in overlaped_ids]
                    + aut2.over_availability_events
                )
                for uid, intervals in user_intervals.items():
                    merged_ints = merge_duration(intervals)
                    total_slots = sum(e - s for s, e in merged_ints)
                    efficiency[uid] = round(total_slots * data["slot_length"] / 60, 2)
            arr_of_not_exist = []
            try:
                for id, arr in people_appointments.items():

                    arr_sorted = sorted(
                        arr,
                        key=lambda x: datetime.datetime.strptime(
                            x["start"], "%Y-%m-%dT%H:%M:%S.000Z"
                        ),
                        reverse=False,
                    )

                    for i in range(len(arr_sorted) - 1):
                        new_list = arr_sorted[i : i + 2]
                        address1 = new_list[0]["address"]
                        address2 = new_list[1]["address"]
                        users1 = new_list[0]["users"]
                        users2 = new_list[1]["users"]
                        check_inter1 = list(set([*users1]) & set(data["notWorking"]))
                        check_inter2 = list(set([*users2]) & set(data["notWorking"]))
                        if len(check_inter1) + len(check_inter2) > 1:
                            continue
                        if data["settings"]["driveTime"]:
                            if (
                                new_list[0]["loc_id"] is None
                                or new_list[1]["loc_id"] is None
                            ):
                                continue
                            loc1 = aut2.solutions1["user_uuid_to_index"][
                                new_list[0]["loc_id"]
                            ]
                            loc2 = aut2.solutions1["user_uuid_to_index"][
                                new_list[1]["loc_id"]
                            ]
                            if loc1 is None or loc2 is None:
                                continue

                            branchId1 = "d"
                            branchId2 = "s"
                            if loc1:
                                branchId1 = aut2.solutions1["users"][loc1]["branches"][
                                    0
                                ]
                            if loc2:
                                branchId2 = aut2.solutions1["users"][loc2]["branches"][
                                    0
                                ]

                            if True or (
                                len(branchId1) > 1
                                and len(branchId2) > 1
                                and loc1
                                and loc2
                                and loc1 != loc2
                            ):
                                if address1 and address2:
                                    drive_time = (
                                        aut2.solutions1["branches"]
                                        .get(branchId1, {})
                                        .get("drivetime", 0)
                                    )
                                    user_tuples = (address1, address2)

                                    drive_time_r = 0
                                    if user_tuples in aut2.drive_time_data:
                                        drive_time_r = round_to_nearest_interval(
                                            aut2.drive_time_data[user_tuples]["mid"]
                                            / 60,
                                            aut2.var_data["slot_length"],
                                        )

                                    drive_time = drive_time_r
                                    # if drive_time == 0:
                                    #     return

                                    # drive_time_slot = (
                                    #     drive_time // aut2.var_data["slot_length"]
                                    # )

                                    date_object = datetime.datetime.strptime(
                                        new_list[0]["end"], "%Y-%m-%dT%H:%M:%S.%fZ"
                                    )
                                    # new_date_string = (
                                    #     date_object
                                    #     + datetime.timedelta(minutes=drive_time)
                                    # ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                                    time_obj = datetime.datetime.strptime(
                                        new_list[0]["end_time_r"], "%H:%M:%S"
                                    )
                                    new_time_str = (
                                        time_obj
                                        + datetime.timedelta(minutes=drive_time)
                                    ).strftime("%H:%M:%S")

                                    if drive_time > 0:
                                        myobj = object_for_return(
                                            date_original,
                                            "",
                                            new_list[0]["end_time_r"],
                                            new_time_str,
                                            [id, aut2.var_data["drive_id"]],
                                            aut2.var_data["drive_id"],
                                            None,
                                            None,
                                            data["start_date"],
                                            data["end_date"],
                                        )

                                        resources_with_names = find_from_resources(
                                            resources, myobj["data"]["users"]
                                        )
                                        myobj["data"].update(resources_with_names)

                                        returned_arr.append(myobj)

                                        tuple_check = (
                                            id,
                                            myobj["data"]["start"],
                                            myobj["data"]["end"],
                                        )
                                        if tuple_check not in arr_of_not_exist:
                                            creatingEvents.append(myobj["data"])
                if deletingEvents:
                    deletingEvents, creatingEvents = remove_duplicate_lunches(
                        deletingEvents, creatingEvents
                    )
            except Exception as e:
                traceback.print_exc()
        gc.collect()
        response = {
            "employees_ids": employees_ids,
            "availability_person": availability_person,
            "deletingEvents": deletingEvents,
            "best_bound": best_bound,
            "status_name": status_name,
            "founded": founded,
            "all_appointments": all_appointments,
            "loc_id_2": loc_id_2,
            "updatingEvents": updatingEvents,
            "creatingEvents": creatingEvents,
            "created_hours": created_hours,
            "deleted_hours": deleted_hours,
            "deleted_appointments_list": deleted_appointments_list,
            "created_events": created_events,
            "returned_arr": returned_arr,
            "objective_value": objective_value,
            "efficiency": efficiency,
            "disabled_constraints": disabled_constraints,
            "status": "status",
        }
        import pprint

        print(f"response2 in the test insert handler: {response}")
        print(f"response3 in the test insert handler: {json.dumps(response)}")

        return {
            "statusCode": 200,
            # USES LOCAL
            # "body": response,
            # USES LOCAL
            # USES lambda
            "body": json.dumps(response),
            # #USES lambda
        }

    except Exception as e:
        print("An error occurred:", str(e))
        print(traceback.format_exc())
        return {
            "statusCode": 500,
            # #USES lambda
            "body": json.dumps({"error": str(e)}),
            # #USES lambda
            # USES LOCAL
            # "body": {"error": str(e)},
            # USES LOCAL
        }
