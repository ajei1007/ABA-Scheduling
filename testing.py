import random
import numpy as np
from ortools.linear_solver import pywraplp

def create_centers(num_centers):
    centers = {}
    for i in range(1, num_centers + 1):
        clients = random.randint(5, 15)
        employee_multiplier = random.uniform(0.7, 2.1)
        employees = int(clients * employee_multiplier)
        specific_employees = max(0,int(round((employee_multiplier-1.125)*clients)))
        centers[f"Center{i}"] = {'clients': clients, 'employees': employees, 'specific_employees':specific_employees}
    return centers

def calculate_std_dev(centers, key):
    ratios = [center[key] / center['clients'] for center in centers.values()]
    return np.std(ratios)

num_centers = 5  # Set the number of centers
centers = create_centers(num_centers)

# Calculate initial standard deviation
initial_std_dev = calculate_std_dev(centers, 'employees')

# Print initial data
print("Initial Centers' Data and Ratios:")
for center, data in centers.items():
    ratio = data['employees'] / data['clients']
    print(f"{center}: Clients = {data['clients']}, Employees = {data['employees']}, Specific_Employees = {data['specific_employees']}, Ratio = {ratio:.2f}")
print(f"Initial Standard Deviation of Ratios: {initial_std_dev:.2f}")

# Create the solver
solver = pywraplp.Solver.CreateSolver('SCIP')

# Variables for final employees at each center
final_employees = {c: solver.NumVar(0, solver.infinity(), f'final_employees_{c}') for c in centers}

# Variables for employees transferred between centers
transferred = {}
for i in centers:
    for j in centers:
        if i != j:
            transferred[(i, j)] = solver.IntVar(0, centers[i]['employees'], f'transfer_{i}_to_{j}')

# Constraints for employee transfers
for center in centers:
    total_sent = solver.Sum(transferred[(center, j)] for j in centers if j != center)
    total_received = solver.Sum(transferred[(i, center)] for i in centers if i != center)
    solver.Add(final_employees[center] == centers[center]['employees'] - total_sent + total_received)

    # Add constraints that enforce non-simultaneous sending and receiving
    can_send = solver.BoolVar(f'can_send_{center}')
    can_receive = solver.BoolVar(f'can_receive_{center}')
    solver.Add(total_sent <= centers[center]['employees'] * can_send)
    solver.Add(total_received <= centers[center]['employees'] * can_receive)
    solver.Add(can_send + can_receive <= 1)  # A center can either send or receive, not both

# Ensure total number of employees remains constant
solver.Add(solver.Sum(final_employees[c] for c in centers) == solver.Sum(centers[c]['employees'] for c in centers))

# Objective: Minimize the maximum deviation from the average ratio
average_ratio = solver.Sum(final_employees[c] / centers[c]['clients'] for c in centers) / num_centers
max_deviation = solver.NumVar(0, solver.infinity(), 'max_deviation')
for c in centers:
    solver.Add(max_deviation >= final_employees[c] / centers[c]['clients'] - average_ratio)
    solver.Add(max_deviation >= average_ratio - final_employees[c] / centers[c]['clients'])
solver.Minimize(max_deviation)

# Solve the model
status = solver.Solve()
if status == pywraplp.Solver.OPTIMAL:
    final_centers = {center: {'clients': centers[center]['clients'], 'employees': final_employees[center].solution_value()} for center in centers}
    final_std_dev = calculate_std_dev(final_centers, 'employees')
    print('\nOptimized Solution:')
    for center in final_centers:
        final_employees_count = final_centers[center]['employees']
        received = sum(transferred[(i, center)].solution_value() for i in centers if i != center)
        sent = sum(transferred[(center, j)].solution_value() for j in centers if j != center)
        final_ratio = final_employees_count / centers[center]['clients']
        print(f"{center}: Initial Employees = {centers[center]['employees']}, Final Employees = {final_employees_count:.0f}")
        print(f"  Clients = {centers[center]['clients']}, Sent = {sent:.0f}, Received = {received:.0f}")
        print(f"  Initial Ratio = {centers[center]['employees'] / centers[center]['clients']:.2f}, Final Ratio = {final_ratio:.2f}")
    print(f"Final Standard Deviation of Ratios: {final_std_dev:.2f}")
else:
    print('The problem does not have an optimal solution.')
