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
    total_employees = 0
    for i in range(1, num_centers + 1):
        center_location = random_location(base_location, 150)
        clients = random.randint(10, 30)
        employee_multiplier = random.uniform(0.7, 2.1)
        employees = int(clients * employee_multiplier)
        employee_locations = [random_location(center_location, 12) for _ in range(employees)]
        centers[f"Center{i}"] = {'clients': clients, 'employees': employees, 'location': center_location, 'employee_locations': employee_locations}
        total_employees += employees
    return centers, total_employees

num_centers = 15  # Number of centers
centers, total_employees = create_centers(num_centers)

# Initialize the solver
solver = pywraplp.Solver.CreateSolver('SCIP')

# Variables for tracking each employee at each center
employee_vars = {}
index = 0
for center in centers:
    for i in range(centers[center]['employees']):
        employee_vars[index] = {}
        for other_center in centers:
            distance = geodesic(centers[center]['employee_locations'][i], centers[other_center]['location']).miles
            if distance <= 35:
                employee_vars[index][other_center] = solver.BoolVar(f'employee_{index}_at_{other_center}')
        index += 1

# Constraint: Each employee can only work at one center
for i in employee_vars:
    solver.Add(solver.Sum(employee_vars[i][other_center] for other_center in employee_vars[i]) == 1)

# Constraints for initial employees per center and total employees per center after assignment
for center in centers:
    centers[center]['final_employees'] = solver.Sum(employee_vars[i][center] for i in employee_vars if center in employee_vars[i])

# Minimize the maximum deviation from the average ratio
average_ratio = solver.Sum(centers[center]['final_employees'] / centers[center]['clients'] for center in centers) / num_centers
max_deviation = solver.NumVar(0, solver.infinity(), 'max_deviation')
for center in centers:
    current_ratio = centers[center]['final_employees'] / centers[center]['clients']
    solver.Add(max_deviation >= current_ratio - average_ratio)
    solver.Add(max_deviation >= average_ratio - current_ratio)
solver.Minimize(max_deviation)

# Solve the model
status = solver.Solve()
if status == pywraplp.Solver.OPTIMAL:
    print('\nOptimized Solution:')
    for i in employee_vars:
        for center in employee_vars[i]:
            if employee_vars[i][center].solution_value() > 0:
                print(f"Employee {i} is assigned to {center}")
    for center in centers:
        final_count = centers[center]['final_employees'].solution_value()
        print(f"{center}: Location = {centers[center]['location']}, Clients = {centers[center]['clients']}, Final Employees = {final_count:.0f}")
    final_std_dev = np.std([centers[center]['final_employees'].solution_value() / centers[center]['clients'] for center in centers])
    print(f"Final Standard Deviation of Ratios: {final_std_dev:.2f}")
else:
    print('The problem does not have an optimal solution.')
