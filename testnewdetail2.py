import random
import math
import numpy as np
from ortools.linear_solver import pywraplp
from external import haversine
import uuid
import json

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

def round_up_to_decimal(number, decimal_place):
    factor = 10 ** decimal_place
    return math.ceil(number * factor) / factor

def calculate_target_ratio(client):
    adder = math.floor(client/8) + 1
    emps = client + adder
    return emps

def create_centers_real(body, base_lat=32.8933106, base_lon=-96.9639305, center_radius=50, home_radius=10):
    data = body['data_after']
    branches_scrubbed = body['branches']
    users_scrubbed = body['users']
    centers = {}
    global_employee_index = 1
    employees_info = {}
    for i, obj in enumerate(data):
        # Center location
        bol_client = False
        center_id = obj['id']
        center_name = obj['name']
        deviation = 5000
        if 'latitude' in branches_scrubbed[center_id].keys() and 'longitude' in branches_scrubbed[center_id].keys() and branches_scrubbed[center_id]['latitude'] and branches_scrubbed[center_id]['longitude']:
            center_lat = branches_scrubbed[center_id]['latitude']
            center_lon = branches_scrubbed[center_id]['longitude']
        else:
            #continue
            center_lat = 0
            center_lon = 0
        bol = False
        for index, slot in enumerate(obj['data']):
            #if slot['x'] == '2:45p':
            if slot['x'] == '3:30p':
                bol = False
            #if slot['x'] == '10:30a' or bol:
            if slot['x'] == '8:00a' or bol:
                bol = True
                if slot['client_count'] == 0:
                    continue
                else:
                    bol_client =True
                actual_ratio_test = round_up_to_decimal(slot['emp_count'] / slot['client_count'],3)
                target_employees_test = calculate_target_ratio(slot['client_count'])
                if 'clientratio' in branches_scrubbed[center_id].keys() and 'employeeratio' in branches_scrubbed[center_id].keys() and branches_scrubbed[center_id]['clientratio'] is not None and branches_scrubbed[center_id]['clientratio'] != 0 and branches_scrubbed[center_id]['employeeratio'] is not None:
                    target_employees_test = math.ceil(slot['client_count'] / branches_scrubbed[center_id]['clientratio'] * branches_scrubbed[center_id]['employeeratio'])
                    print('sympton',target_employees_test)
                target_ratio_test = round_up_to_decimal(target_employees_test / slot['client_count'],4)
                print('hebrew',slot['x'],slot['client_count'],slot['emp_count'],center_name,actual_ratio_test - target_ratio_test,deviation)
                #if actual_ratio_test - target_ratio_test < deviation or slot['x'] == '10:30a':
                if actual_ratio_test - target_ratio_test < deviation or slot['x'] == '8:00a':
                    
                    clients = slot['client_count']
                    employees = slot['emp_count']
                    target_ratio = target_ratio_test
                    employee_multiplier = actual_ratio_test
                    deviation = actual_ratio_test - target_ratio_test
                    specific_employees = max(0, int(math.floor((employee_multiplier - target_ratio) * clients)))
                    if center_id == '411b31cb-6e21-4377-962a-68eb4072c8c4':
                        print('herewe',employee_multiplier,target_ratio,clients)

            

        if bol_client:
            #center_lat, center_lon = generate_random_coords(base_lat, base_lon, center_radius)
            print('lat',center_lat,'long',center_lon)
            # Number of clients and employees calculation
            #clients = random.randint(10, 30)
            # employee_multiplier = random.uniform(0.6, 2)
            # employees = int(clients * employee_multiplier)
            # target_employees = calculate_target_ratio(clients)
            # target_ratio = round_up_to_decimal(target_employees / clients,3)
            # specific_employees = max(0, int(math.floor((employee_multiplier - target_ratio) * clients)))
            # Employee homes
            employee_homes = []
            employee_names = []
            employee_ids = []
            employee_list = branches_scrubbed[center_id]['employees']
            num_to_sample = min(len(employee_list), specific_employees)
            random_employees = random.sample(employee_list, num_to_sample)
            for employee_id in random_employees:
                #home_lat, home_lon = generate_random_coords(center_lat, center_lon, home_radius)
                home_lat = center_lat
                home_lon = center_lon
                employee_name = users_scrubbed[employee_id]['name']
                employee_homes.append([home_lat, home_lon])
                employee_names.append(employee_name)
                employee_ids.append(employee_id)
                global_employee_index += 1
                employees_info[employee_id] = {'name':employee_name,'home':[home_lat, home_lon]}

            print('center_id', center_id, specific_employees)
            centers[center_id] = {
                'name':center_name,
                'clients': clients,
                'employees': employees,
                'specific_employees': specific_employees,
                'latitude': center_lat,
                'longitude': center_lon,
                'center_id': center_id,
                'employee_homes': employee_homes,
                'employee_ids': employee_ids,
                'employees_info': employees_info,
                'employee_names': employee_names,
                'target_ratio':target_ratio
            }
    return centers

def create_centers_simulate(num_centers, base_lat=32.8933106, base_lon=-96.9639305, center_radius=50, home_radius=10):
    centers = {}
    global_employee_index = 1
    employees_info = {}
    for i in range(1, num_centers + 1):
        # Center location
        center_lat, center_lon = generate_random_coords(base_lat, base_lon, center_radius)
        print('lat',center_lat,'long',center_lon)
        # Number of clients and employees calculation
        clients = random.randint(10, 30)
        employee_multiplier = random.uniform(0.6, 2)
        employees = int(clients * employee_multiplier)
        target_employees = calculate_target_ratio(clients)
        target_ratio = round_up_to_decimal(target_employees / clients,3)
        specific_employees = max(0, int(math.floor((employee_multiplier - target_ratio) * clients)))
        # Employee homes
        employee_homes = []
        employee_names = []
        employee_ids = []
        center_id = str(uuid.uuid4())
        for _ in range(specific_employees):
            home_lat, home_lon = generate_random_coords(center_lat, center_lon, home_radius)
            employee_name = create_employee_name(global_employee_index)
            employee_homes.append([home_lat, home_lon])
            employee_names.append(employee_name)
            employee_id = str(uuid.uuid4())
            employee_ids.append(employee_id)
            global_employee_index += 1
            employees_info[employee_id] = {'name':employee_name,'home':[home_lat, home_lon]}

        centers[f"Center{i}"] = {
            'clients': clients,
            'employees': employees,
            'specific_employees': specific_employees,
            'latitude': center_lat,
            'longitude': center_lon,
            'employee_homes': employee_homes,
            'employee_ids': employee_ids,
            'center_id': center_id,
            'employees_info': employees_info,
            'employee_names': employee_names,
            'target_ratio':target_ratio
        }
    return centers

def calculate_std_dev(centers, key):
    ratios = [center[key] / center['clients'] for center in centers.values()]
    return np.std(ratios)

def optimize_staff(info):
    num_centers = 10  # Set the number of centers
    #centers = create_centers_simulate(num_centers)
    print('keyboard',info)
    body = json.loads(info['body'])
    all_users = body['users']
    startDate = body['startDate']
    endDate = body['endDate']
    branches_scrubbed = body['branches']
    print('all_users',all_users)
    centers = create_centers_real(body)

    # Calculate initial standard deviation
    initial_std_dev = round_up_to_decimal(calculate_std_dev(centers, 'employees'),3)

    # Create the solver
    solver = pywraplp.Solver.CreateSolver('SCIP')

    # Variables for final employees at each center
    final_employees = {c: solver.NumVar(0, solver.infinity(), f'final_employees_{c}') for c in centers}

    # Variables for employees transfers between centers
    # Employee transfer variables
    transfers = {}
    transfers_received = {}
    distance_obj = {}
    for i in centers:
        for j in centers:
            if i != j:
                for index, emp_id in enumerate(centers[i]['employee_ids']):
                    bol = solver.BoolVar(f'transfer_{emp_id}_{i}_to_{j}')
                    transfers[(emp_id, i, j)] = bol
                    transfers_received[(emp_id, j, i)] = bol
                    #print('fooly')
                    emp_lat = centers[i]['employees_info'][emp_id]['home'][0]
                    emp_long = centers[i]['employees_info'][emp_id]['home'][1]
                    print('krillin',emp_lat,emp_long,centers[j]['latitude'],centers[j]['longitude'])
                    distance = round_up_to_decimal(haversine(emp_lat, emp_long, centers[j]['latitude'], centers[j]['longitude'], 'miles'),2)
                    print('limmy',distance, all_users[emp_id]['name'],branches_scrubbed[j]['name'])
                    employee_id = centers[i]['employee_ids'][index]
                    center_id = centers[j]['center_id']
                    centers[i]['employees_info'][employee_id]['distance'] = distance
                    distance_obj = {**distance_obj,(employee_id,center_id):distance}
                    # if emp_lat == 0 or emp_long == 0 or centers[j]['latitude'] == 0 or centers[j]['longitude']:
                    #     solver.Add(bol == 0)
                    if distance > 30:
                        print('too far')
                        solver.Add(bol == 0)
                    else:
                        print('not far')


    # Employee presence constraints
    print('limmy',transfers)
    for center in centers:
            # Ensure each employee is only at one center after transfer
        total_sent = solver.Sum(transfers[(emp_id,center, j)] for j in centers if j != center for emp_id in centers[center]['employee_ids'])
        total_received = solver.Sum(transfers[(emp_id,i, center)] for i in centers if i != center for emp_id in centers[i]['employee_ids'])
        print('simmer',centers[center]['specific_employees'])
        solver.Add(total_sent <= centers[center]['specific_employees'])
        if centers[center]['specific_employees'] > 0:
            solver.Add(total_received == 0)
        solver.Add(final_employees[center] == centers[center]['employees'] - total_sent + total_received)

    for center in centers:
        for emp_id in centers[center]['employee_ids']:
            solver.Add(solver.Sum(transfers[(emp_id, center, j)] for j in centers if j != center)<=1)
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


    # Variables to represent the buffer ratio at each center
    buffer_ratios = {c: solver.NumVar(1.0, solver.infinity(), f'buffer_ratio_{c}') for c in centers}
    shortfalls = {c: solver.NumVar(0, solver.infinity(), f'shortfall_{c}') for c in centers}  # Slack variables for shortfalls

    # Calculate the average buffer ratio
    average_buffer_ratio = solver.Sum(buffer_ratios[c] for c in centers) / len(centers)

    # Objective: Maximize the average buffer ratio while minimizing the deviation and penalties for not meeting targets
    deviations = {c: solver.NumVar(0, solver.infinity(), f'deviation_{c}') for c in centers}
    solver.Minimize(-average_buffer_ratio + solver.Sum(deviations[c] for c in centers) + solver.Sum(shortfalls[c] for c in centers))

    for c in centers:
        target_ratio = centers[c]['target_ratio']
        
        # Define buffer ratio variables, incorporating shortfalls
        solver.Add(buffer_ratios[c] * (centers[c]['clients'] * target_ratio) <= final_employees[c] + shortfalls[c])

        # Constraints to ensure the buffer ratio is at least 1 (meeting the target), considering shortfalls
        solver.Add(buffer_ratios[c] >= 1.0 - shortfalls[c] / (centers[c]['clients'] * target_ratio))

        # Deviations from the average buffer ratio
        solver.Add(deviations[c] >= buffer_ratios[c] - average_buffer_ratio)
        solver.Add(deviations[c] >= average_buffer_ratio - buffer_ratios[c])

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
    solver.SetTimeLimit(60000)
    status = solver.Solve()
    rows = []
    total_sent = 0
    optimal = 'Feasible'
    appropriately_staffed_before = 0
    appropriately_staffed_after = 0
    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        if status == 0:
            optimal = 'Optimal'
        final_std_dev = round_up_to_decimal(calculate_std_dev({c: {'clients': centers[c]['clients'], 'employees': final_employees[c].solution_value()} for c in centers}, 'employees'),3)
        print('\nOptimized Solution:')
        for center in centers:
            final_employees_count = round_up_to_decimal(final_employees[center].solution_value(),0)
            received = sum(transfers[(emp_id,i, center)].solution_value() for i in centers if i != center for emp_id in centers[i]['employee_ids'])
            sent = sum(transfers[(emp_id,center, j)].solution_value() for j in centers if j != center for emp_id in centers[center]['employee_ids'])
            total_sent = total_sent + sent
            target_ratio = round_up_to_decimal(centers[center]['target_ratio'],3)
            final_ratio = round_up_to_decimal(final_employees_count/centers[center]['clients'],3)
            initial_ratio = round_up_to_decimal(centers[center]['employees']/centers[center]['clients'],3)
            send_or_receive = 'Send'
            if received > 0:
                send_or_receive = 'Received'
            elif received == 0 and sent == 0:
                 send_or_receive = '-'
            final_ratio_difference = round_up_to_decimal(final_ratio - target_ratio,3)
            initial_ratio_difference = round_up_to_decimal(initial_ratio - target_ratio,3)
            if initial_ratio_difference >= 0:
                appropriately_staffed_before += 1
            if final_ratio_difference >= 0:
                appropriately_staffed_after += 1
            obj = {"type":send_or_receive,"final_ratio_difference":final_ratio_difference,"initial_ratio_difference":initial_ratio_difference,"original_center_id":center,"Original Center":branches_scrubbed[center]['name'], "Clients": centers[center]['clients'], "Initial Employees":centers[center]['employees'], "Final Employees": final_employees_count, "Initial Ratio":initial_ratio, "Target Ratio":target_ratio, "Final Ratio":final_ratio, "Sent":sent, "Received":received}
            users = []
            print(f"{center}: Initial_ratio = {initial_ratio} Final_ratio = {final_ratio} Target_ratio = {target_ratio} Clients = {centers[center]['clients']}, Initial Employees = {centers[center]['employees']}, Final Employees = {final_employees_count:.0f}, Sent = {sent:.0f}, Received = {received:.0f}")
            print(f"  Latitude = {centers[center]['latitude']}, Longitude = {centers[center]['longitude']}")
            if final_ratio - target_ratio < 0:
                print('loopy',final_ratio - target_ratio)
            else:
                print('happy')
            for j in centers:
                for index, emp_id in enumerate(centers[center]['employee_ids']):
                    bol = False
                    distance = '-'
                    if (emp_id,centers[j]['center_id']) in distance_obj.keys():
                        distance = distance_obj[(emp_id,centers[j]['center_id'])]
                    if center != j and transfers[(emp_id,center, j)].solution_value() > 0:
                        print(f"  {emp_id} transfered from {center} to {j}")
                        bol = True
                    if bol:
                        users.append({"emp_id":emp_id,"name":all_users[emp_id]['name'],"center":branches_scrubbed[j]['name'],"center_id":centers[j]['center_id'],"distance":distance})
                for index, emp_id in enumerate(centers[j]['employee_ids']):
                    bol = False
                    distance = '-'
                    if (emp_id,centers[center]['center_id']) in distance_obj.keys():
                        distance = distance_obj[(emp_id,centers[center]['center_id'])]
                    if center != j and transfers_received[(emp_id,center, j)].solution_value() > 0:
                        print(f"  {emp_id} Receive from {center} to {j}")
                        bol = True
                    if bol:
                        users.append({"emp_id":emp_id,"name":all_users[emp_id]['name'],"center":branches_scrubbed[j]['name'],"from_center_id":centers[j]['center_id'],"to_center":branches_scrubbed[center]['name'],"to_center_id":centers[center]['center_id'],"distance":distance})
            obj['users'] = users
            rows.append(obj)
        
        appropriately_staffed_after_percentage = round_up_to_decimal(appropriately_staffed_after/len(centers)*100,1)
        appropriately_staffed_before_percentage = round_up_to_decimal(appropriately_staffed_before/len(centers)*100,1)
        final_obj = {'startDate':startDate,'endDate':endDate,'rows':rows,'stats':[{'title':'Status','value':optimal},{'title':'Initial Ratio Deviation','value':initial_std_dev},{'title':'Final Ratio Deviation','value':final_std_dev},{'title':'Employees Transferred','value':total_sent},{'title':'# Appropriately Staffed Before','value':f"{appropriately_staffed_before} ({appropriately_staffed_before_percentage}%)"},{'title':'# Appropriately Staffed After','value':f"{appropriately_staffed_after} ({appropriately_staffed_after_percentage}%)"}]}
        print(f"Initial Standard Deviation of Ratios: {initial_std_dev:.2f}")
        print(f"Final Standard Deviation of Ratios: {final_std_dev:.2f}")
        print('lumy',final_obj)
        return final_obj
    else:
        print('The problem does not have an optimal solution.')
        return {'rows':[],'stats':{}}
