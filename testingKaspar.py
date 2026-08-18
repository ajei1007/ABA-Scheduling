from datetime import datetime


def slot_to_time(slot, slot_interval):
    # slot : int , 0 < slot_interval : int <= 60
    slots_per_day = 24 * 60 // slot_interval
    slots_per_hour = 60 // slot_interval
    hours = str((slot % slots_per_day) // slots_per_hour).zfill(2)
    minutes = str((slot % slots_per_day % slots_per_hour) * slot_interval).zfill(2)
    seconds = "00"
    timer = hours + ":" + minutes + ":" + seconds
    time_obj = datetime.strptime(timer, "%H:%M:%S")
    time_12_hour = time_obj.strftime("%I:%M %p")
    formatted_time = time_12_hour.lstrip("0")
    return formatted_time


def group_slot(slots):
    for slot in slots:
        slot0 = str(slot_to_time(slot[0], 15))
        slot1 = str(slot_to_time(slot[1], 15))
        print(str(slot) + ": " + slot0 + ", " + slot1)


# slotty = [
#     [152, 166],
#     [148, 160],
#     [148, 164],
#     [177, 188],
#     [160, 168],
#     [148, 164],
#     [180, 188],
#     [164, 180],
#     [180, 188],
#     [166, 177],
#     [164, 180],
#     [162, 176],
# ]

# slotty = [
#     [152, 170],
#     [162, 176],
#     [148, 168],
#     [172, 188],
#     [170, 188],
#     [148, 172],
#     [172, 188],
#     [148, 172],
# ]

# slotty = [[52, 76], [76, 92], [56, 74], [74, 92], [52, 76], [76, 92], [52, 72]]

# group_slot(slotty)
print(slot_to_time(176, 15))
