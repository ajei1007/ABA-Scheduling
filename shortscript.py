import math

def round_up_to_decimal(number, decimal_place):
    factor = 10 ** decimal_place
    return math.ceil(number * factor) / factor

for i in range(1,50):
    adder = math.floor(i/8) + 1
    emps = i + adder
    print(i,emps,round_up_to_decimal(emps/i,3))