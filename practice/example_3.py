# Bazarbay Halmedov
# A scheduling problem
from ortools.sat.python import cp_model

# Problem Link
# https://www.youtube.com/watch?v=hBxCUMgrZi8&t=5s

# Here is Problem

# St. Tatiana Hospital is aiming to design a schedule for day-shift nurses that minimizes the total number of nurses employed

# Each nurse works 3 consecutive day shifts and then has 4 days off

# The minimum number of nurses required for each day of a week given down below:
# [day_of_week,nurses_required] = [('Monday', 16),
#                                   ('Tuesday', 12),
#                                   ('Wednesday', 18),
#                                   ('Thursday', 13),
#                                   ('Friday', 15),
#                                   ('Saturday', 9),
#                                   ('Sunday', 7)]

# [shift,work_days] = [(1, 'Monday,Tuesday,Wednesday'),
#                      (2, 'Tuesday,Wednesday,Thursday'),
#                      (3, 'Wednesday,Thursday,Friday'),
#                      (4, 'Thursday,Friday,Saturday'),
#                      (5, 'Friday,Saturday,Sunday'),
#                      (6, 'Saturday,Sunday,Monday'),
#                      (7, 'Sunday,Monday,Tuesday')]

# Minimize the total number of nurses

# Lets the number of nurses at i'th shift are Xi then we are trying to minimize this equation
# X1 + X2 + X3 + X4 + X5 + X6 + X7


def main():
    # Creates model
    model = cp_model.CpModel()

    # Creates variables
    X1 = model.NewIntVar(0, 49, 'X1')
    X2 = model.NewIntVar(0, 49, 'X2')
    X3 = model.NewIntVar(0, 49, 'X3')
    X4 = model.NewIntVar(0, 49, 'X4')
    X5 = model.NewIntVar(0, 49, 'X5')
    X6 = model.NewIntVar(0, 49, 'X6')
    X7 = model.NewIntVar(0, 49, 'X7')
