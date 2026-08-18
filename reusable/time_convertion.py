# Time convertion
import time
import datetime
from turtle import clear


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


# this function converts the day time to the slot (minutes interval)
def convert_to_time_slot(t, day, minutes):
    #print(t)
    x = time.strptime(t, '%H:%M:%S')
    output = datetime.timedelta(
        hours=x.tm_hour, minutes=x.tm_min,
        seconds=x.tm_sec).total_seconds() / 60 / minutes
    output = int(day * 24 * 60 / minutes + output)
    #print(day,'snippy',output)
    return output


def time_to_slot(t, day, slot_interval):
    x = time.strftime(t, '%H:%M:%S')
    output = datetime.timedelta(
        hours=x.tm_hour, minutes=x.tm_min,
        seconds=x.tm_sec).total_seconds() / 60 / slot_interval
    output = int(day * 24 * 60 / slot_interval + output)
    return output
