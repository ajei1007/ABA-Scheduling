from testing import data_1, data_2, emp

import datetime

admin_act_id = "f472a7cf-39bf-44a0-9ddf-e30b67f7bd2c"


def get_overlap(dict_arr, array):
    output = []
    # Parsing datetime strings to datetime objects
    for dict_data in dict_arr:
        dict_start = datetime.datetime.strptime(dict_data['start'],
                                                '%Y-%m-%dT%H:%M:%S.%fZ')
        dict_end = datetime.datetime.strptime(dict_data['end'],
                                              '%Y-%m-%dT%H:%M:%S.%fZ')

        for element in array:
            element_start = datetime.datetime.strptime(
                element['start'], '%Y-%m-%dT%H:%M:%S.%fZ')
            element_end = datetime.datetime.strptime(element['end'],
                                                     '%Y-%m-%dT%H:%M:%S.%fZ')

            # Check if element start and end is between dict start and end
            if dict_start <= element_start and dict_end >= element_end:

                output.append(element)

    return output


def yellow_overlap(event_array, orange_array, employee_array, admin_id):
    result = []
    for emp_id in employee_array:
        ev = []
        ids_not_repeat = []
        orange_with_id = []

        for event in event_array:
            if admin_id in event['resourceIds']:
                if emp_id in event['resourceIds']:
                    if not event["id"] in ids_not_repeat:
                        ev.append(event)
                        ids_not_repeat.append(event["id"])

        for data in orange_array:
            if emp_id + "a" in data['resourceIds']:
                orange_with_id.append(data)
        result.append([ev, orange_with_id])
    return result


ar1 = yellow_overlap([data_2[0]], data_1, emp, admin_act_id)

for i in ar1:
    print(ar1.index(i), " : ", i[0])
    print(len(get_overlap(i[0], i[1])))

xz = 0
for i in data_1:
    if "ov" in i.keys():
        print(i["ov"])
        xz += 1
print(xz)