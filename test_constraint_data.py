y_a = [10,10,30,40,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,100,0,0,0,0,0,0]
x_a = list(range(len(y_a))) 

from ortools.sat.python import cp_model

def solve_xy(x_array, y_array):
    model = cp_model.CpModel()
    x_min = min(x_array)
    x_max = max(x_array)
    variables = []

    for i in x_array:
        bool_x = model.NewBoolVar(f"index_{i}")
        start = model.NewIntVar(x_min, x_max, f"start_{i}")
        end = model.NewIntVar(x_min, x_max, f"end_{i}")
        duration = model.NewIntVar(0, x_max-x_min, f"duration_{i}")
        interval = model.NewOptionalIntervalVar(start, duration, end, bool_x, f"intervals_{i}")
        variables.append([start, duration, end, bool_x, interval])
        model.Add(duration > 20).OnlyEnforceIf(bool_x)
        model.Add(duration == 0).OnlyEnforceIf(bool_x.Not())
        model.Add(start <= end)
    model.AddNoOverlap([i[-1] for i in variables])

    objective_array = []
    xy_dict = {}

    for i in range(len(variables)):
        xy_dict[i] = []

    inc = 0

    for j,y in enumerate(y_array):
        for i, v in enumerate(variables):
            abc = model.NewBoolVar(f"abc-{inc}")
            bool_y = model.NewBoolVar(f"bool_y_{inc}")
            inc += 1
            model.Add(v[0] <= x_array[j]).OnlyEnforceIf(bool_y)
            model.Add(v[2] >= x_array[j]).OnlyEnforceIf(bool_y)
            # model.Add(abc == 1).OnlyEnforceIf(bool_y)
            # model.Add(v[1] > 20).OnlyEnforceIf(bool_y)
            model.AddMultiplicationEquality(abc,[bool_y,v[3]])
            objective_array.append(y * abc)
            xy_dict[i].append(y * abc)

    for val in list(xy_dict.values()):
        print(val)
        model.Add(sum(val) < 300)
    
    model.Maximize(sum(objective_array))

    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        result = []
        for i in variables:
            if solver.Value(i[3]) != 0:
                result.append([solver.Value(i[0]), solver.Value(i[2])])
        return result
    else:
        return "INFEASIBLE"



['ee79aee1-85fa-4d2a-b42b-6a8e2cc87bcf', '692d1ef0-35f8-4b24-83a3-aca43a5709f2', 'ea8c2627-c3b9-4413-9a48-234aaa8fa890', '66efb010-c869-4ec9-ba0d-06fc1723d869', '33ef53a6-d0c5-4b43-91d3-62dddc039bca', '40067b4b-7a49-41c0-9286-17d686d7daa8', 'bc42bdf0-69a7-48e5-853d-5458e24ca04e', 'd8e63ae2-3d5f-4218-bfaa-086fdbc1d2c2', 'e4808766-220e-49db-8357-02d138b82556', 'cbaafb10-a320-4a05-9706-cbf3729ba755', '3280fe37-68ef-40eb-af41-5aa9a063271c', 'd00789d1-180f-45d9-8795-8ace9bc1534d', '661650b0-c24a-4234-a0ab-1e7c879dfc0c', 'd6744cdd-8eea-4b5e-b09c-1f97e6fdefd8', 'c1b14b24-422f-4e3e-a27d-70a57eb87bf7', 'd9a28d76-773d-4eb6-99b3-dd7aefff7d3b', '070611e9-a19b-4759-8b44-9c56f33eae62', '2b928324-b875-4ecc-a0fa-27f55bf382cd', '3516f630-0908-457d-b4b2-7c6c84f71a75', '3f8bb4f9-a77d-4cb9-8c0c-a2ebaeb01c8a', '3f1fa9c4-90e9-412a-9f79-a3e12370369c', '5f4119e1-cc71-4cd5-82fa-dff11768457d', '0ed331d2-a876-44a2-90e0-9c46cb1ad062', 'c22290c9-442a-4fc9-9150-ab54943c218a', 'c23f0e7a-e1a8-4ba1-8389-b9ead6afefdf', 'bf2e03ef-620a-472f-ac4b-25a0769ee00a', 'c2c8fa42-d7dd-41df-b210-b66e2ff90650', 'f234b08c-a6a1-47de-aaef-3973bbbe1054', '985c4f88-8c00-4dd1-814b-8d5600da6f13', '80df2a7b-12e3-42b7-bbdd-f4eef85d47ed', '802b4f0c-3858-480f-88d4-e155661a0e4c', '999c041d-a1a0-4fe8-9754-00940e3c94e7', 'd5bb71a6-e744-47b1-93b7-20fc7d874b1b', 'c57882bf-578b-4f63-86f4-8176d8504973', '6034662a-9ace-4ff4-84d3-01b4e4a8a96c', '90d2536d-63db-46bd-8e33-e7b554d7b291', 'e1d2aac4-4b90-4b12-8495-5667492ec845', '4214716f-6d8f-4b2d-9e08-b961be0377f8', '3c329e01-14f5-4f1d-ac2a-1f7d465e347f', '7a7f4ff8-a5a8-406a-a88f-adc8e96528c7', '040efd76-cd7a-4a52-bd65-369b37ee68d4', '967de35e-f327-4583-ba62-a83fb4e3408f', '8feef26c-3e60-4970-978f-d9c1867dd321', '8095f445-d403-4477-b9c2-e291e312af2e', '2faf27ca-9120-486c-9738-83714f0ee50d', 'dbc2840e-362f-40cc-aa47-e37196f15cd1', '236c0b14-e1a8-4984-9b5a-a76b8b841c6c', '995522be-5cd3-41d9-b32c-ec047c937345', '37bf5802-b892-48f5-b33b-032a7c5251a8', 'dae5dcd4-af4d-486e-b0f9-9166577b8250', 'c4d6082a-7681-45d6-b12f-45b3a00a05d9', '32bf33d8-b776-4d0b-8907-6b126bbdcd0b', 'a327d46f-96c8-4b5f-aaa9-3f943f1b8fda', 'b0b552ce-79b7-4d34-a964-2d059447c582', '69388a96-c175-4528-b3fa-6516c1166588', '934a1362-7f8e-493a-a90f-f46a7f8f26c4', '5b6b8e8e-d606-4e61-9ca1-e938f05565a4', '379427c4-df36-46dd-a7b1-2d734f09fae4', 'e248cd92-eb6c-4134-b2c8-bac94c49c4a3', 'cfedf369-fd9d-4264-9d9d-6967f74a5bcb', '52cc1b31-3884-47f2-b291-44d50d572e78', '56814218-3400-447f-8117-1e7748f83878', 'd5ef872a-3d32-4f8f-a5ae-dac295e29cbe', '26815132-3ed4-4c65-806b-d456afa5025c', 'a9ba5910-3723-4d52-bfcf-e9081c04d581', 'd916b342-df1c-438e-95f2-9cbb9ab4cbdf', '554f0f78-0acb-4aa4-b3a9-313ef3c91f6b', '7bd835c3-7855-4855-a73e-f6b40b5b0dc4', '243ee178-9360-44c3-bbc2-f98137afefe2', 'b9880286-5ca9-410c-9de4-77c98cfe4066', 'c7004807-c362-48e5-badf-5467a3880f50', '4cee76e2-ca88-4343-b53c-e4a554f1ff75', '8b391ac3-cfbd-4acd-917e-df6308be8faf', '2075924d-f113-43f8-b2b7-e0bda7eb763a', 'e06a3867-d990-415a-94fe-be1fc18f4257', 'd20bce9a-0f2f-46a1-9781-b1c230768f7c', '1bbf7eab-5341-42fb-ab8c-ca3912937103', 'd84a2985-52c0-4684-b8dc-faf84bf65c15', '72936f60-77cb-48e1-ac27-258303514ff0', 'e9c1cf43-07cb-42ed-85da-8e8664504e74', 'b0be04a3-a252-44f0-8f12-c8da743c7a82', 'e2c0eb48-1473-46fd-8511-03c51d5068d3', '96c9e717-0cc8-4e3a-b47d-0920dfc151a7', '4cea7ccf-cef2-4d36-bcb4-f006776aab89', '83f13ae2-a504-441d-ac9c-72afbe85c61a', '607e0ebe-8e61-454c-a3a3-b8913fa268f7', '5f92504c-2651-4c00-97a4-1588d7771c4c', 'a330ea2f-4ded-40da-91f8-51e80550b815', '696c44f3-a037-4acb-aee3-29551c0859a2', 'f5263be2-c4b4-43f4-8fe5-ab7b7e9d66bd', '68622b18-fe70-4366-bd13-124355e6aa55', '24655a8e-2c1a-4180-aefe-d8703e533828', '17a2801a-6df6-4c7e-a2d9-69c9d4e506fc', '84aee335-ab4d-41e4-8b7f-7a25026627fe', '42fd3851-8944-4888-93e0-33a2fd953835', '2985d60d-fd4e-4308-8867-e3c43c429a9a', 'c61117dc-87c2-4b00-9805-acda3093597b', '2e3a5bbb-dc2f-4ba5-9c34-16d28966609d', '9b20723e-d21e-49f6-919a-d60b28bb59d5', '5656c42a-98e2-499f-aa4d-83421c13521c', '9e27b945-8408-4851-a9f0-d1392bd4f714', 'f39d479c-ea0f-4dcf-86e1-3e47c19328c7', 'd4cdaade-a14f-4309-b0ae-56aef58fdbcb', '6a010f26-ca70-42aa-a44b-196e1a31322a', '54112161-98f6-4c37-9f78-89b230073333', 'fda57f92-e14d-43c1-96bc-7593b7760b6e', 'e7414ab1-26a0-4c76-bf75-877e354c627c', '0468c2d7-59d8-4034-85e1-68c5c2b9fbb2', '75e58110-6972-4be9-b66f-dac5361f53cd', '8b87bb3f-3861-42d6-a0e0-1b48d16d0f69', '3d518d60-034d-44ec-865a-796bda64ee3c', 'e2c71ed8-aa86-4449-8304-2bde8c7b4f16', '3f5edc11-afeb-4d0c-af21-f049fc53d5a0']


# get_data list of minimum required data

'''
1. get_availability
    ENDPOINT :/scheduler/availabilities?start={self.start_date}&end={self.end_date}&branches={self.branches_id}
    REQUIRED : header
    RETURN : [
        {
        "av" : dict() 
        }
        ...
    ]
2. get_funders_fake -> not needed
    ENDPOINT : nothing
    REQUIRED : nothing
    RETURN : []
4. get_capacities
    ENDPOINT :/capacityconstraints?page=1&capacityconstraints=
    RETURN : [
        {
            "user1" : {
                "id" : uuid
                ...
            },
            "disabled" : True/False
        }
        ...
    ]
5. get_groupings -> not needed
    ENDPOINT :/groupings?page=1&groupings=
    REQUIRED : header
    RETURN : [
        {
            "role1" : [
                {
                    "name" : "NAME"
                    ...
                }],
            "role2" : [
                {
                    "name" : "NAME",
                    ...
                }
            ]
        }
        ...
    ]
6. get_subgroups
    ENDPOINT : /scheduler/subgroups?branches={self.branches_id}&all={True}
    REQUIRED : header
    RETURN : [
        {
            "user" : {
                "id" : uuid,
                ...
            }
        }
    ]
7. get_person_raw_data -> not needed
    ENDPOINT : /users/resources/Person?bol2=true&branches={self.branches_id}
    REQUIRED : header
    RETURN : [
        {
            "id" : uuid,
            "credentialFunders" : {
                "firstName" : "First Name",
                ...
            }
        }
    ]
8. get_location_raw_data -> not needed
    ENDPOINT : /users/resources/Location?bol2=true&branches={self.branches_id}
    REQUIRED : header
    RETURN : [
        {
            "id" : ID,
            "roomparent" : room_parent,
            "rooms" : [
                {
                    "id" :  ID
                }
                ...
            ]
        }
    ]
9. get_subgroups_raw_data 
    ENDPOINT : /subgroups?branches={self.branches_id}
    REQUIRED : header
    RETURN : [
        {
            "user" : {
                "id" : uuid,
                "name" : NAME 
                ...
            }
        }
    ]
10. get_custom_constraints 
    ENDPOINT : newconstraintgenerator
    REQUIRED : header
    RETURN : [
        {
            "id" : ID,
            "constraintType" : TYPE,
            "antecedentType" : TYPE,
            "antecedentTypeUsers_filtered" : [...],
            "antecedentTypeRoles_filtered" : [...],
            "antecedentTypeSubgroups_filtered" : [...],  
            "antecedentTypeBranches_filtered" : [...],
            "consequenceType" : TYPE,
            "consequenceTypeUsers_filtered" : [...],
            "consequenceTypeRoles_filtered" : [...],
            "consequenceTypeSubgroups_filtered" : [...],
            "consequenceTypeBranches_filtered" : [...],
            "consequenceTypeDaySelection" : [...],
            "consequenceTypeWeekDays_filtered" : [...],
            "antecedentTypeDaySelection" : TYPE,
            "antecedentTypeWeekDays_filtered" : [...],
            "min" : INT,
            "max" : INT, 
            "minSeconds" : INT,
            "maxSeconds" : INT,
            "all" : STRING,
            "weight" : INT,
            "start" : DATE, 
            "end" : DATE,
            "frequency" : TYPE
            "consequenceTypeEachOrAll" : TYPE,
            "grouping_filtered" : [...],      
            "noLimit" : LIMIT,
            "disabled" : BOOLEAN           
            "soft": [] / BOOLEAN
            "antecedentTypeEachOrAll" : TYPE
        }
    ]
11. get_branches -> not needed
    ENDPOINT : /branches/optimizer'
    REQUIRED : header
    RETURN : ALL
12. get_branch_structure
    ENDPOINT : /scheduler/branch_structure'
    REQUIRED : header
    RETURN : [
        {},{}
    ]
13. get_event_pair
    ENDPOINT : /event_pair
    REQUIRED : header
    RETURN : [
        {
            "role1" : {
                "name" : NAME
            },
            "role2" : {
                "name" : NAME
            },
            "activity1Id" : uuid,
            "activity2Id" : uuid
        }
    ]
14. get_events2
    ENDPOINT : /scheduler/events?locations={locations}&start={str(start_date)}&end={str(end_date)}&branches={branch}
    REQUIRED : header,json={"people" : "uuid|uuid ....."}
    RETURN : [
        {
            "id": uuid,
            "resourceIds": [uuid,...],
            "title": string,
            "canceledId": BOOLEAN,
            "address": ADDRESS,
            "duration": {
                "seconds" : INT/FLOAT,
                },
            "start_real": DATE,
            'end_real_time': DATE,
            "end": DATE,
            'location0Id': uuid,
        
        }
        ...
    ]
'''


# 16 
# 20 20

# 2 12
# 7 12
# 8 6
# 3 6
# 3 5
# 5 5
# 3 12
# 3 7
# 5 7
# 2 6
# 3 2
# 4 2
# 3 4
# 4 4
# 9 2
# 11 2

data = {
    "number_of_rectangles": 16,
    "big_rectangle": [20,20],
    "small_rectangles": [(2, 12), (7, 12), (8, 6), (3, 6), (3, 5), (5, 5), (3, 12), (3, 7), (5, 7), (2, 6), (3, 2), (4, 2), (3, 4), (4, 4), (9, 2), (11, 2)]
}
from ortools.sat.python import cp_model

def solve_place_rectangles_optimal(input_data):
    model = cp_model.CpModel()
    # number_of_rectangles = input_data["number_of_rectangles"]
    big_rectangle = input_data["big_rectangle"]
    small_rectangles = input_data["small_rectangles"]
    
    vars_data = {}
    max_length = max(big_rectangle)
    for i,v in enumerate(small_rectangles):
        # Variables
        is_exist = model.NewBoolVar(f"is_exist-{i}")
        bool_w_l = model.NewBoolVar(f"bool-{i}")
        x_1 = model.NewIntVar(0,max_length,f"x_1-{i}")
        x_2 = model.NewIntVar(0,max_length,f"x_2-{i}")
        y_1 = model.NewIntVar(0,max_length,f"y_1-{i}")
        y_2 = model.NewIntVar(0,max_length,f"y_2-{i}")
        x_length = model.NewIntVar(0,max(v),f"x_length-{i}")
        y_length = model.NewIntVar(0,max(v),f"y_length-{i}")
        x_interval = model.NewOptionalIntervalVar(x_1,x_length,x_2,is_exist,f"x_interval-{i}")
        y_interval = model.NewOptionalIntervalVar(y_1,y_length,y_2,is_exist,f"y_interval-{i}")
        
        vars_data[i] = [v[0],v[1],x_1,x_2,y_1,y_2,is_exist,x_interval,y_interval]
        
        # Constraints
        model.Add(x_1 <= x_2)
        model.Add(y_1 <= y_2)
        model.Add(x_length == v[0]).OnlyEnforceIf(bool_w_l)
        model.Add(x_length == v[1]).OnlyEnforceIf(bool_w_l.Not())
        model.Add(y_length == v[1]).OnlyEnforceIf(bool_w_l)
        model.Add(y_length == v[0]).OnlyEnforceIf(bool_w_l.Not())
    x_interval_array = [i[7] for i in vars_data.values()]
    y_interval_array = [i[8] for i in vars_data.values()]
    model.AddNoOverlap2D(x_interval_array,y_interval_array)
        
    # Objective
    model.Maximize(sum([i[0]*i[1]*i[6] for i in vars_data.values()]))

    solver = cp_model.CpSolver()
    solver.parameters.log_search_progress = True
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_workers = 2
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        result = []
        for i in list(vars_data.values()):
            if solver.Value(i[6]) == 1:
                result.append([solver.Value(i[2]),solver.Value(i[3]),solver.Value(i[4]),solver.Value(i[5])])
        return result
    else:
        return "No solution found!"

print(solve_place_rectangles_optimal(data))
print(sum([i[0]*i[1] for i in data["small_rectangles"]]))

