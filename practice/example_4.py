from ortools.sat.python import cp_model

# Create a model.
model = cp_model.CpModel()

# Create an interval variable with a start time of 0, an end time of 10, and a duration of 5.

interval = model.NewIntervalVar(0, 5, 10, 'interval')

# Solve the model.
solver = cp_model.CpSolver()
status = solver.Solve(model)

if status == cp_model.FEASIBLE:
    # Get the start and end times of the interval variable.
    start = solver.Start(interval)
    end = solver.End(interval)
    print(f'Interval starts at {start} and ends at {end}.')
else:
    print('No solution found.')
