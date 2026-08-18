# Bazarbay Halmedov
from ortools.sat.python import cp_model


def main():
    model = cp_model.CpModel()  # Creates the model

    # Create the variables
    var_upper_bound = max(50, 45, 37)
    x = model.NewIntVar(0, var_upper_bound, 'x')
    y = model.NewIntVar(0, var_upper_bound, 'y')
    z = model.NewIntVar(0, var_upper_bound, 'z')

    # Creates Constraints
    model.Add(2 * x + 7 * y + 3 * z <= 50)
    model.Add(3 * x - 5 * y + 7 * z <= 48)
    model.Add(5 * x + 2 * y - 6 * z <= 37)

    # Objective
    model.Maximize(2 * x + 2 * y + 3 * z)

    # Creates a solver and solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # Prints Solution
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        print(f'Maximum of objective function : {solver.ObjectiveValue()}\n')
        print(f'x = {solver.Value(x)}')
        print(f'y = {solver.Value(y)}')
        print(f'z = {solver.Value(z)}')
    else:
        print('No solution found.')

    # Statistics
    print('\nStatistics')
    print(f'  status        : {solver.StatusName(status)}')
    print(f'  conflicts     : {solver.NumConflicts()}')
    print(f'  branches      : {solver.NumBranches()}')
    print(f'  wall time     : {solver.WallTime()}')


if __name__ == '__main__':
    main()
