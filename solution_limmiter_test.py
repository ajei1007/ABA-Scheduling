from ortools.sat.python import cp_model

from ortools.sat.python import cp_model

# Create the CP-SAT solver
model = cp_model.CpModel()

# Define the variables
x = model.NewIntVar(0, 100, 'x')
y = model.NewIntVar(0, 100, 'y')
z = model.NewIntVar(0, 100, 'z')

# Create a list of variables that you want to consider for the minimum
variables_to_consider = [x, y, z]

# Create a list to store variables that are not equal to 0
variables_not_equal_to_zero = []

# Filter out variables that are equal to 0 and add not equal to 0 constraints
for var in variables_to_consider:
    not_equal_to_zero_var = model.NewBoolVar(f'{var.Name()}_not_equal_to_zero')
    model.Add(var != 0).OnlyEnforceIf(not_equal_to_zero_var)
    variables_not_equal_to_zero.append(var)

# Ensure that there are variables to consider
if variables_not_equal_to_zero:
    # Add constraints to set the selected variable to the minimum
    model.AddMinEquality(x, variables_not_equal_to_zero)

# Create the CP solver and solve the problem
solver = cp_model.CpSolver()
status = solver.Solve(model)

if status == cp_model.OPTIMAL:
    # Get the value of 'x' after the solver has run
    x_value = solver.Value(x)
    print(f"Value of 'x': {x_value}")
else:
    print("No solution found.")