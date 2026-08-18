import random
import math
import numpy as np
from ortools.linear_solver import pywraplp
from geopy.distance import geodesic
from external import haversine

def generate_random_coords(lat, lon, distance):
    # Convert latitude and longitude from degrees to radians
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)

    # Earth's radius in miles
    earth_radius = 3958.8

    # Random distance in miles
    random_distance = random.random() * distance

    # Random bearing (direction in radians)
    random_bearing = random.random() * 2 * math.pi

    # Calculate the new latitude
    lat_new_rad = math.asin(math.sin(lat_rad) * math.cos(random_distance / earth_radius) +
                            math.cos(lat_rad) * math.sin(random_distance / earth_radius) * math.cos(random_bearing))

    # Calculate the new longitude
    lon_new_rad = lon_rad + math.atan2(math.sin(random_bearing) * math.sin(random_distance / earth_radius) * math.cos(lat_rad),
                                       math.cos(random_distance / earth_radius) - math.sin(lat_rad) * math.sin(lat_new_rad))

    # Convert the new latitude and longitude back to degrees
    lat_new = math.degrees(lat_new_rad)
    lon_new = math.degrees(lon_new_rad)

    return lat_new, lon_new

def create_employee_name(index):
    return f"Employee{index}"

def create_centers(num_centers, base_lat=32.8933106, base_lon=-96.9639305, center_radius=50, home_radius=10):
    centers = {}
    global_employee_index = 1
    for i in range(1, num_centers + 1):
        # Center location
        center_lat, center_lon = generate_random_coords(base_lat, base_lon, center_radius)
        print('lat',center_lat,'long',center_lon)
        # Number of clients and employees calculation
        clients = random.randint(10, 30)
        employee_multiplier = random.uniform(0.6, 2)
        employees = int(clients * employee_multiplier)
        specific_employees = max(0, int(round((employee_multiplier - 1.125) * clients)))

        # Employee homes
        employee_homes = []
        employee_names = []
        for _ in range(specific_employees):
            home_lat, home_lon = generate_random_coords(center_lat, center_lon, home_radius)
            employee_name = create_employee_name(global_employee_index)
            employee_homes.append([home_lat, home_lon])
            employee_names.append(employee_name)
            global_employee_index += 1

        centers[f"Center{i}"] = {
            'clients': clients,
            'employees': employees,
            'specific_employees': specific_employees,
            'latitude': center_lat,
            'longitude': center_lon,
            'employee_homes': employee_homes,
            'employee_names': employee_names
        }
    return centers

def calculate_std_dev(centers, key):
    ratios = [center[key] / center['clients'] for center in centers.values()]
    return np.std(ratios)

num_centers = 50  # Set the number of centers
centers = create_centers(num_centers)

# Calculate initial standard deviation
initial_std_dev = calculate_std_dev(centers, 'employees')

# Create the solver
solver = pywraplp.Solver.CreateSolver('SCIP')

# Variables for final employees at each center
final_employees = {c: solver.NumVar(0, solver.infinity(), f'final_employees_{c}') for c in centers}

# Variables for employees transfers between centers
# Employee transfer variables
transfers = {}
for i in centers:
    for j in centers:
        if i != j:
            for index, emp_name in enumerate(centers[i]['employee_names']):
                bol = solver.BoolVar(f'transfer_{emp_name}_{i}_to_{j}')
                transfers[(emp_name, i, j)] = bol
                #print('fooly')
                distance = haversine(centers[i]['employee_homes'][index][0], centers[i]['employee_homes'][index][1], centers[j]['latitude'], centers[j]['longitude'], 'miles')
                #print('limmy',distance)
                if distance > 30:
                    print('too far')
                    solver.Add(bol == 0)
                else:
                    print('not far')


# Employee presence constraints
print('limmy',transfers)
for center in centers:
        # Ensure each employee is only at one center after transfer
    total_sent = solver.Sum(transfers[(emp_name,center, j)] for j in centers if j != center for emp_name in centers[center]['employee_names'])
    total_received = solver.Sum(transfers[(emp_name,i, center)] for i in centers if i != center for emp_name in centers[i]['employee_names'])
    print('simmer',centers[center]['specific_employees'])
    solver.Add(total_sent <= centers[center]['specific_employees'])
    if centers[center]['specific_employees'] > 0:
        solver.Add(total_received == 0)
    solver.Add(final_employees[center] == centers[center]['employees'] - total_sent + total_received)

for center in centers:
    for emp_name in centers[center]['employee_names']:
        solver.Add(solver.Sum(transfers[(emp_name, center, j)] for j in centers if j != center)<=1)
    # solver.Add(solver.Sum(transfers[(emp_name, center, j)] for j in centers if j != center for emp_name in centers[center]['employee_names']) +
    #             solver.Sum(transfers[(emp_name, i, center)] for i in centers if i != center for emp_name in centers[i]['employee_names']) <= 1)

# Constraints for employee transfers
# for center in centers:
#     total_sent = solver.Sum(transfers[(center, j)] for j in centers if j != center)
#     total_received = solver.Sum(transfers[(i, center)] for i in centers if i != center)
#     solver.Add(final_employees[center] == centers[center]['employees'] - total_sent + total_received)

# Ensure total number of employees remains constant
solver.Add(solver.Sum(final_employees[c] for c in centers) == solver.Sum(centers[c]['employees'] for c in centers))

# for center in centers:
#     received = sum(transfers[(i, center)] for i in centers if i != center)
#     sent = sum(transfers[(center, j)] for j in centers if j != center)
#     solver.Add(sent <= centers[center]['specific_employees'])
#     if centers[center]['specific_employees'] > 0:
#         solver.Add(received == 0)


###TRYING
# Define the target midpoint for the ratios
target_ratio = 1.14

# Variables for deviations from the target ratio
deviations = {c: solver.NumVar(0, solver.infinity(), f'deviation_{c}') for c in centers}

# Constraints to calculate deviations
for c in centers:
    solver.Add(deviations[c] >= final_employees[c] / centers[c]['clients'] - target_ratio)
    solver.Add(deviations[c] >= target_ratio - final_employees[c] / centers[c]['clients'])

# Objective: Minimize the sum of deviations from the target ratio
solver.Minimize(solver.Sum(deviations[c] for c in centers))
###TRYING

###THIS WORKS
# Objective: Minimize the maximum deviation from the average ratio
# average_ratio = solver.Sum(final_employees[c] / centers[c]['clients'] for c in centers) / num_centers
# max_deviation = solver.NumVar(0, solver.infinity(), 'max_deviation')
# for c in centers:
#     solver.Add(max_deviation >= final_employees[c] / centers[c]['clients'] - average_ratio)
#     solver.Add(max_deviation >= average_ratio - final_employees[c] / centers[c]['clients'])
# solver.Minimize(max_deviation)
###THIS WORKS

# Solve the model
status = solver.Solve()
if status == pywraplp.Solver.OPTIMAL:
    final_std_dev = calculate_std_dev({c: {'clients': centers[c]['clients'], 'employees': final_employees[c].solution_value()} for c in centers}, 'employees')
    print('\nOptimized Solution:')
    for center in centers:
        final_employees_count = final_employees[center].solution_value()
        received = sum(transfers[(emp_name,i, center)].solution_value() for i in centers if i != center for emp_name in centers[i]['employee_names'])
        sent = sum(transfers[(emp_name,center, j)].solution_value() for j in centers if j != center for emp_name in centers[center]['employee_names'])
        print(f"{center}: Initial_ratio = {centers[center]['employees']/centers[center]['clients']} Final_ratio = {final_employees_count/centers[center]['clients']} Clients = {centers[center]['clients']}, Initial Employees = {centers[center]['employees']}, Final Employees = {final_employees_count:.0f}, Sent = {sent:.0f}, Received = {received:.0f}")
        print(f"  Latitude = {centers[center]['latitude']}, Longitude = {centers[center]['longitude']}")
        for j in centers:
            for emp_name in centers[center]['employee_names']:
                if center != j and transfers[(emp_name,center, j)].solution_value() > 0:
                    pass
                    print(f"  {emp_name} transfered from {center} to {j}")
    print(f"Initial Standard Deviation of Ratios: {initial_std_dev:.2f}")
    print(f"Final Standard Deviation of Ratios: {final_std_dev:.2f}")
else:
    print('The problem does not have an optimal solution.')
