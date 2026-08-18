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
    # Calculate new coordinates based on base, angle, and distance
    return geodesic(miles=distance).destination(base, bearing=angle)

def create_centers(num_centers):
    centers = {}
    for i in range(1, num_centers + 1):
        center_location = random_location(base_location, 150)
        clients = random.randint(10, 30)
        employee_multiplier = random.uniform(0.7, 2.1)
        employees = int(clients * employee_multiplier)
        employee_locations = [random_location(center_location, 12) for _ in range(employees)]
        centers[f"Center{i}"] = {'clients': clients, 'employees': employees, 'location': center_location, 'employee_locations': employee_locations}
    return centers

num_centers = 5  # Number of centers
centers = create_centers(num_centers)

# Initialize the solver
solver = pywraplp.Solver.CreateSolver('SCIP')

print('hello')

# Variables for tracking each employee at each center
employee_vars = {}
for center in centers:
    employee_vars[center] = [solver.BoolVar(f'employee_{i}_at_{center}') for i in range(centers[center]['employees'])]

# Constraint: Each employee can only work at one center
for i in range(max(len(centers[c]['employee_locations']) for c in centers)):
    solver.Add(solver.Sum(employee_vars[c][i] for c in centers if i < len(employee_vars[c])) == 1)

# Variables for final number of employees at each center
final_employees = {c: solver.Sum(employee_vars[c]) for c in centers}

# Minimize the maximum deviation from the average ratio
average_ratio = solver.Sum(final_employees[c] / centers[c]['clients'] for c in centers) / num_centers
max_deviation = solver.NumVar(0, solver.infinity(), 'max_deviation')
for c in centers:
    solver.Add(max_deviation >= final_employees[c] / centers[c]['clients'] - average_ratio)
    solver.Add(max_deviation >= average_ratio - final_employees[c] / centers[c]['clients'])
solver.Minimize(max_deviation)

# Solve the model
status = solver.Solve()
if status == pywraplp.Solver.OPTIMAL:
    print('\nOptimized Solution:')
    for center in centers:
        print(f"{center}: Location = {centers[center]['location']}, Clients = {centers[center]['clients']}, Final Employees = {final_employees[center].solution_value():.0f}")
else:
    print('The problem does not have an optimal solution.')

# Additional printing and results processing...
