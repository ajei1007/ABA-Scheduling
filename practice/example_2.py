# Bazarbay Halmedov
from ortools.sat.python import cp_model

# Problem and solution Link
# https://www.youtube.com/watch?v=EmDiD5a9CE8

# Here is problem

# [day_of_week,workers_required] = [('Sunday', 18),
#                                   ('Monday', 27),
#                                   ('Tuesday', 22),
#                                   ('Wednesday', 26),
#                                   ('Thursday', 25),
#                                   ('Friday', 21),
#                                   ('Saturday', 19)]

# [shift,days_off,wage] = [(1, 'Sunday & Monday', 680),
#                          (2, 'Monday & Tuesday', 705),
#                          (3, 'Tuesday & Wednesday', 705),
#                          (4, 'Wednesday & Thursday', 705),
#                          (5, 'Thursday & Friday', 705),
#                          (6, 'Friday & Saturday', 680),
#                          (7, 'Saturday & Sunday', 655)]

# Minimize the total wage

# Lets the number of worker at i'th shift are Xi then we are trying to minimize this equation
# X1*680 + X2*705 + X3*705 + X4*705 + X5*705 + X6*680 + X7*655


def main():
    model = cp_model.CpModel()  # Creates the model

    #Creates variables
    upper_bound = max(17, 18, 19, 20, 21, 22, 27)
    X1 = model.NewIntVar(0, upper_bound, 'X1')
    X2 = model.NewIntVar(0, upper_bound, 'X2')
    X3 = model.NewIntVar(0, upper_bound, 'X3')
    X4 = model.NewIntVar(0, upper_bound, 'X4')
    X5 = model.NewIntVar(0, upper_bound, 'X5')
    X6 = model.NewIntVar(0, upper_bound, 'X6')
    X7 = model.NewIntVar(0, upper_bound, 'X7')

    wage = model.NewIntVar(0, 10000000, 'wage')

    # Creates Constraints
    model.Add(X2 + X3 + X4 + X5 + X6 >= 18)
    model.Add(X3 + X4 + X5 + X6 + X7 >= 18)
    model.Add(X1 + X4 + X5 + X6 + X7 >= 19)
    model.Add(X1 + X2 + X5 + X6 + X7 >= 20)
    model.Add(X1 + X2 + X3 + X6 + X7 >= 21)
    model.Add(X1 + X2 + X3 + X4 + X7 >= 22)
    model.Add(X1 + X2 + X3 + X4 + X5 >= 23)

    model.Add(X1 * 600 + X2 * 620 + X3 * 640 + X4 * 580 + X5 * 500 + X6 * 420 +
              X7 * 630 == wage)

    # Objective
    model.Minimize(wage)

    # Creates a solver and solve the model.
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # Prints solution
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f'Minimum of objective function : {solver.ObjectiveValue()}\n')
        print(f'Total value of the wage is : {solver.Value(wage)}')
        print(f'X1 = {solver.Value(X1)}')
        print(f'X2 = {solver.Value(X2)}')
        print(f'X3 = {solver.Value(X3)}')
        print(f'X4 = {solver.Value(X4)}')
        print(f'X5 = {solver.Value(X5)}')
        print(f'X6 = {solver.Value(X6)}')
        print(f'X7 = {solver.Value(X7)}')
    else:
        print('No solution found')

    # Statistics
    print('\nStatistics:')
    print(f'    status      : {solver.StatusName(status)}')
    print(f'    conflicts   : {solver.NumConflicts()}')
    print(f'    branches    : {solver.NumBranches()}')
    print(f'    wall time   : {solver.WallTime()}')


if __name__ == '__main__':
    main()