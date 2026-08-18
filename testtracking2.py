import random
import numpy as np
from ortools.linear_solver import pywraplp
from geopy.distance import geodesic

# Base location
base_location = (32.8933106, -96.9639305)

def random_location(base, radius_miles):
    # Random angle in degrees and distance
    angle = random.uniform(0, 360)
    distance = random.uniform(0, radius_miles)
    return geodesic(miles=distance).destination(base, bearing=angle)

def create_centers(num_centers):
    centers = {}
    for i in range(1, num_centers + 1):
        center_location = random_location(base_location, 150)
        clients = random.randint(10, 30)
        employee_multiplier = random.uniform(0.7, 2.1)
        employees = int(clients * employee_multiplier)
        ratio = employees / clients
        centers[f"Center{i}"] = {
            'clients': clients,
            'employees': employees,
            'location': center_location,
            'initial_ratio': ratio
        }
    return centers

num_centers = 5
centers = create_centers(num_centers)

# Initialize the solver
solver = pywraplp.Solver.CreateSolver('SCIP')

# Variables for total employees at each center after potential transfers
final_employees = {center: solver.IntVar(0, centers[center]['employees'], f'final_employees_{center}') for center in centers}

# Create transfer variables between centers where applicable
transfers = {}
for src in centers:
    for dst in centers:
        if src != dst:
            transfers[(src, dst)] = solver.IntVar(0, centers[src]['employees'], f'transfer_{src}_to_{dst}')

# Ensure the total number of employees remains consistent
for center in centers:
    solver.Add(final_employees[center] == centers[center]['employees'] - solver.Sum(transfers[(center, dst)] for dst in centers if (center, dst) in transfers) + solver.Sum(transfers[(src, center)] for src in centers if (src, center) in transfers))

# Objective: Minimize the maximum deviation from the average ratio
average_ratio = solver.Sum(final_employees[center] / centers[center]['clients'] for center in centers) / num_centers
max_deviation = solver.NumVar(0, solver.infinity(), 'max_deviation')
for center in centers:
    solver.Add(max_deviation >= final_employees[center] / centers[center]['clients'] - average_ratio)
    solver.Add(max_deviation >= average_ratio - final_employees[center] / centers[center]['clients'])
solver.Minimize(max_deviation)

# Solve the model
status = solver.Solve()
response = []
if status == pywraplp.Solver.OPTIMAL:
    print('\nOptimized Solution:')
    for center in centers:
        final_count = final_employees[center].solution_value()
        obj = {"Original Center":centers[center]['location'], "Clients": centers[center]['clients'], "Initial Employees":centers[center]['employees'], "Initial Ratio":centers[center]['initial_ratio']}
        print(f"{center}: Location = {centers[center]['location']}, Initial Clients = {centers[center]['clients']}, Initial Employees = {centers[center]['employees']}, Initial Ratio = {centers[center]['initial_ratio']:.2f}")
        print(f"  Final Clients = {centers[center]['clients']}, Final Employees = {final_count:.0f}, Final Ratio = {final_count / centers[center]['clients']:.2f}")
        for src, dst in transfers:
            if src == center or dst == center:
                print(f"  Transfers {'from' if src == center else 'to'} {dst if src == center else src}: {transfers[(src, dst)].solution_value():.0f}")
    final_std_dev = np.std([final_employees[center].solution_value() / centers[center]['clients'] for center in centers])
    print(f"Final Standard Deviation of Ratios: {final_std_dev:.2f}")
else:
    print('The problem does not have an optimal solution.')
