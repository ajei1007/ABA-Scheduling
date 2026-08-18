import googlemaps
import requests
import datetime
import numpy as np

API_KEY = 'AIzaSyDCObA9hIjPPHlcRHUsE0nhv7y9LQwI8ZQ'
Headers = {'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiMGQzY2EwYjAtMDU4MC00NjI4LWE2NDktNTkzMTJkYjVjOTE0IiwiZW1haWwiOiJhZGFtQGFiYXNjaGVkdWxlcy5jb20ifSwiaWF0IjoxNzAyNDAyNzUxLCJleHAiOjIzMzAyNDAyNzUxfQ.NsWz7IjJIRrGskZi9r_U-Jd1DlpOLI6VWWGn8jmLY8A'}

example_data = {
    "data" : {
        "duration": 512,
        "distance": 2000,
        "user1" : "cb8c33b9-3866-4999-bd5a-7bd9c201ea25",
        "user2" : "28576e59-7459-419e-bbd0-b1ec60f8f386"
        }
    }

# def calculate_distance_pairs(addr1, addr2,api_key='AIzaSyDCObA9hIjPPHlcRHUsE0nhv7y9LQwI8ZQ', dep_time = ''):
#     gmaps = googlemaps.Client(key=api_key)

#     try:
#         print("bb_google_maps_run")
#         if dep_time != "":
#             departure_time = datetime.datetime.fromisoformat(dep_time[:-1])
#             print("departure_time : ",departure_time)
#             print("bazo_adresses : ",addr1,"----",addr2 )
#             if addr1 is None or addr2 is None:
#                 return [0,0]
#             result = gmaps.distance_matrix(origins=[addr1], destinations=[addr2], mode="driving", units="metric",departure_time=departure_time
#                                            #,traffic_model="pessimistic"
#                                            )
#             # print("bazo_distance_matrix_error : ",result)
#             if result is None or result['rows'][0]['elements'][0]["status"] == "NOT_FOUND":
#                 return [0,0]
#             distance = result['rows'][0]['elements'][0]['distance']['value']
#             duration = result['rows'][0]['elements'][0]['duration_in_traffic']['value']
#         else:
#             result = gmaps.distance_matrix(origins=[addr1], destinations=[addr2], mode="driving", units="metric")
#             if result is None:
#                 return [0,0]
#             distance = result['rows'][0]['elements'][0]['distance']['value']
#             duration = result['rows'][0]['elements'][0]['duration']['value']
#         return [distance, duration]
#     except Exception as e:
#         print(f"Error: {e}")

def calculate_distance_pairs(addr1, addr2,api_key='AIzaSyDFfpe9hOdznMJkNwmor6ljrrBFWjlXLPM', dep_time = 12,minutes=0):
    gmaps = googlemaps.Client(key=api_key)
    try:
        now = datetime.datetime.now()
        days_until_next_monday = (7 - now.weekday() + 0) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7  # Ensure it's the next Monday, not today if today is Monday

        # Calculate the next Monday at 9:00 AM
        next_monday_at_9am = now.replace(hour=dep_time, minute=minutes, second=0, microsecond=0) + datetime.timedelta(days=days_until_next_monday)

        # Convert to timestamp
        departure_time_seconds = int(next_monday_at_9am.timestamp())
        print("bazo_adresses : ",addr1,"----",addr2 )
        if addr1 is None or addr2 is None:
            return [0,0]
        result = gmaps.distance_matrix(origins=[addr1], destinations=[addr2], mode="driving", units="metric",departure_time=departure_time_seconds
                                        #,traffic_model="pessimistic"
                                        )
        # print("bazo_distance_matrix_error : ",result)
        if result is None or result['rows'][0]['elements'][0]["status"] == "NOT_FOUND":
            return [0,0]
        distance = result['rows'][0]['elements'][0]['distance']['value']
        duration = result['rows'][0]['elements'][0]['duration_in_traffic']['value']
        return [distance, duration]
    except Exception as e:
        print(f"Error: {e}")

def get_drive_time_data(header,host):
    res = requests.get(f"{host}/distancematrix/", headers=header)
    dict_data = {}
    # print("bazo_res : ",res)
    for d in res.json()["rows"]:
        if(d["address1"] is not None and d["address2"] is not None):
            dict_data[tuple([d["address1"],d["address2"]])] = {"early": d["duration_early"],"mid":d["duration"],"late":d["duration_late"]}
    # print('doofy',dict_data)
    return dict_data

def post_drive_time_data(header,actual_data,host):
    res = requests.post(f"{host}/distancematrix/", headers=header,json=actual_data)
    return res.status_code


def convert_drive_time(d_time):
    if type(d_time) == str:
        return [i.split(",") for i in d_time.split("|")]
    if type(d_time) == list:
        return "|".join([",".join([str(j) for j in i]) for i in d_time])

def calc_approx_time(arr,X):
    # X = "1:35"
    # arr = [(8,14),(9,17)...]
    x = [int(i) for i in X.split(":")]
    del_x = x[0]+ x[1]/60
    len_arr = len(arr)
    for i,v in enumerate(arr):
        if v[0] == x[0]:
            if i < len_arr-1:
                return round(arr[i][1]+ (del_x-arr[i][0])*(arr[i+1][1]-arr[i][1])/(arr[i+1][0]-arr[i][0]),2)
            else:
                return arr[-1][1]
    return None  


def return_ten_time():
    def get_tomorrow_date_with_time(hours):
        # Get the current date and time
        current_datetime = datetime.datetime.utcnow()

        # Calculate the date for tomorrow
        tomorrow_date = current_datetime + datetime.timedelta(days=1)

        # Set the specified hours for tomorrow
        tomorrow_datetime_with_hours = tomorrow_date.replace(hour=hours, minute=0, second=0, microsecond=0)

        # Format the datetime as a string in the desired format
        formatted_datetime = tomorrow_datetime_with_hours.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        return formatted_datetime

    # Example usage with specified hours [8,9,10,11,12,13,14,15,16,17,18]
    specified_hours = [12]
    res = []
    for hour in specified_hours:
        result = get_tomorrow_date_with_time(hour)
        res.append(result)
    return res

def return_interval_drive_time(addr1,addr2,hour,minutes):
    print('foojy',addr1,addr2,hour,minutes)
    res = calculate_distance_pairs(addr1,addr2,dep_time=hour,minutes=minutes)
    # dis ,dur_time = res[0][0],int(max([i[1] for i in res]))
    print('simmy',res)
    dis ,dur_time = res[0],res[1]
    # print("bazo_min_max_time : ",int(min([i[1] for i in res])),int(max([i[1] for i in res])),dis)
    # print("bb_drive_res : ",[i[1] for i in res])
    return [dis,dur_time]
    return res

# aa=return_interval_drive_time("400 NW 1st Ave, Gainesville, FL 32601","1222 NW 7th St, Gainesville, FL 32601",return_ten_time())
# print(aa)
aa = [[1522, 208], [1522, 201], [1522, 215], [1522, 216], [1522, 230], [1522, 262], [1522, 268], [1522, 265], [1522, 280], [1522, 301], [1522, 323]]
# print(aa)
# print(calculate_distance_pairs("Ayasofya Meydanı, Sultanahmet, Fatih, Istanbul, Turkey"," Bereketzade, Galata Kulesi, Beyoğlu, Istanbul, Turkey ",dep_time='2023-12-20T19:30:00.000Z')) # this is for testing purposes
# print(calculate_distance_pairs("400 NW 1st Ave, Gainesville, FL 32601","1222 NW 7th St, Gainesville, FL 32601 ")) # this is for testing purposes
# print(calculate_distance_pairs("400 NW 1st Ave, Gainesville, FL 32601","7400 SW Archer Rd, Gainesville, FL 32608  ")) # this is for testing purposes
# print(calculate_distance_pairs("400 NW 1st Ave, Gainesville, FL 32601","4320 SW 35th Blvd, Gainesville, FL 32608 ")) # this is for testing purposes
# print(calculate_distance_pairs("400 NW 1st Ave, Gainesville, FL 32601","1400 NW 16th Ave, Gainesville, FL 32603 ")) # this is for testing purposes
# print(calculate_distance_pairs("400 NW 1st Ave, Gainesville, FL 32601","4500 SE Hawthorne Rd, Gainesville, FL 32608")) # this is for testing purposes
# print(calculate_distance_pairs("400 NW 1st Ave, Gainesville, FL 32601","12100 NE 23rd Ave, Gainesville, FL 32609 ")) # this is for testing purposes
    



# # print(post_drive_time_data(Headers,example_data))
# print(get_drive_time_data(Headers))

# Example data (replace with your actual data points)
def return_cofficients_of_polinomial(x_values, y_values):
    x = np.array(x_values)
    y = np.array(y_values)
    coefficients = np.polyfit(x, y, 2)
    return [int(i) for i in list(coefficients)]
    pass
# x = np.array([i+5 for i in [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]])  # x-coordinates
# y = np.array([i[1] for i in aa])  # y-coordinates

# # Fit a 3rd degree polynomial
# coefficients = np.polyfit(x, y, 2)

# # The coefficients are in descending order: [a, b, c, d]
# a, b, c= coefficients
# print([int(i*1000) for i in list(coefficients)])
# # You can also create a polynomial function with these coefficients
# polynomial_function = np.poly1d(coefficients)

# print([int(i*1000) for i in [a, b, c]],polynomial_function)

# Now you can use polynomial_function(x) to get y values



# Ideas

# 1. 

# dict_keys([('1043eecf-0e24-4455-9e5a-2d7ce65adb83', '4eb6efcd-b5df-4d1f-acc9-4123285d1016'), ('187f65d2-910b-4841-95bc-406cb594ae15', '4eb6efcd-b5df-4d1f-acc9-4123285d1016'), ('1043eecf-0e24-4455-9e5a-2d7ce65adb83', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'), ('4eb6efcd-b5df-4d1f-acc9-4123285d1016', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'), ('187f65d2-910b-4841-95bc-406cb594ae15', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'), ('62537fb5-3366-41ae-ba80-bf129a57d298', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'), ('4eb6efcd-b5df-4d1f-acc9-4123285d1016', '62537fb5-3366-41ae-ba80-bf129a57d298'), ('1043eecf-0e24-4455-9e5a-2d7ce65adb83', '62537fb5-3366-41ae-ba80-bf129a57d298'), ('1043eecf-0e24-4455-9e5a-2d7ce65adb83', '187f65d2-910b-4841-95bc-406cb594ae15'), ('187f65d2-910b-4841-95bc-406cb594ae15', '62537fb5-3366-41ae-ba80-bf129a57d298'), ('28576e59-7459-419e-bbd0-b1ec60f8f386', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'), ('28576e59-7459-419e-bbd0-b1ec60f8f386', '4eb6efcd-b5df-4d1f-acc9-4123285d1016'), ('28576e59-7459-419e-bbd0-b1ec60f8f386', '62537fb5-3366-41ae-ba80-bf129a57d298'), ('4eb6efcd-b5df-4d1f-acc9-4123285d1016', '9acf23af-b592-4a57-ac76-ee313fb95be1'), ('187f65d2-910b-4841-95bc-406cb594ae15', '28576e59-7459-419e-bbd0-b1ec60f8f386'), ('1043eecf-0e24-4455-9e5a-2d7ce65adb83', '28576e59-7459-419e-bbd0-b1ec60f8f386'), ('46c3b666-975e-4305-bbd2-ff0e5e4e32fa', '4eb6efcd-b5df-4d1f-acc9-4123285d1016'), ('1043eecf-0e24-4455-9e5a-2d7ce65adb83', '9acf23af-b592-4a57-ac76-ee313fb95be1'), ('9acf23af-b592-4a57-ac76-ee313fb95be1', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'), ('187f65d2-910b-4841-95bc-406cb594ae15', '9acf23af-b592-4a57-ac76-ee313fb95be1'), ('62537fb5-3366-41ae-ba80-bf129a57d298', '9acf23af-b592-4a57-ac76-ee313fb95be1'), ('46c3b666-975e-4305-bbd2-ff0e5e4e32fa', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'), ('1043eecf-0e24-4455-9e5a-2d7ce65adb83', '46c3b666-975e-4305-bbd2-ff0e5e4e32fa'), ('28576e59-7459-419e-bbd0-b1ec60f8f386', '46c3b666-975e-4305-bbd2-ff0e5e4e32fa'), ('46c3b666-975e-4305-bbd2-ff0e5e4e32fa', '62537fb5-3366-41ae-ba80-bf129a57d298'), ('187f65d2-910b-4841-95bc-406cb594ae15', '46c3b666-975e-4305-bbd2-ff0e5e4e32fa'), ('09b1c15f-8a5b-4fea-bcd5-795e03ccd289', 'df95edd2-f019-4ee5-bfeb-7bf05f232af9'), ('09b1c15f-8a5b-4fea-bcd5-795e03ccd289', '4eb6efcd-b5df-4d1f-acc9-4123285d1016'), ('46c3b666-975e-4305-bbd2-ff0e5e4e32fa', '9acf23af-b592-4a57-ac76-ee313fb95be1'), ('09b1c15f-8a5b-4fea-bcd5-795e03ccd289', '62537fb5-3366-41ae-ba80-bf129a57d298'), ('09b1c15f-8a5b-4fea-bcd5-795e03ccd289', '28576e59-7459-419e-bbd0-b1ec60f8f386'), ('09b1c15f-8a5b-4fea-bcd5-795e03ccd289', '187f65d2-910b-4841-95bc-406cb594ae15'), ('09b1c15f-8a5b-4fea-bcd5-795e03ccd289', '1043eecf-0e24-4455-9e5a-2d7ce65adb83'), ('09b1c15f-8a5b-4fea-bcd5-795e03ccd289', '46c3b666-975e-4305-bbd2-ff0e5e4e32fa'), ('09b1c15f-8a5b-4fea-bcd5-795e03ccd289', '9acf23af-b592-4a57-ac76-ee313fb95be1'), ('28576e59-7459-419e-bbd0-b1ec60f8f386', '9acf23af-b592-4a57-ac76-ee313fb95be1')])

# {'id': '5fd041e3-3fd4-4fb9-ace0-cfaf1689253b', 'title': 'Cigna  - Parahat Iljanov - Tyson Blue - Direct  - Home ', 'startNow': '2024-01-19T13:00:00Z', 'endNow': '2024-01-20', 'roles_list': {'Employee': ['Tyson Blue'], 'Client': ['Parahat Iljanov'], 'Activity': ['Direct ']}, 'activity': 'Direct', 'ap': None, 'start_real': '2024-01-19T13:00:00.000Z', 'end_real_time': '2024-01-19T16:00:00.000Z', 'end_real': '2024-01-21', 'duration': {'seconds': 10800}, 'duration_real': {'seconds': 10800}, 'startTime': '08:00', 'endTime': '11:00', 'resourceIds': ['1a92ae33-a4ae-46a1-a59f-ae29ffc2d042', '28576e59-7459-419e-bbd0-b1ec60f8f386', '86dcbb8b-139b-4c8f-8de0-21b0b437f77d', 'a2d2f210-831c-4429-be87-fe3c1e3e0df8', '4a789fb8-b9ef-44ca-b686-1f37edf0c357'], 'calendar': 'Personal', 'backgroundColor': 'blueviolet', 'backgroundColor2': None, 'borderColor2': None, 'color_obj': {}, 'colorBorder_obj': {}, 'newColor': 'blueviolet', 'activity0Id': 'a2d2f210-831c-4429-be87-fe3c1e3e0df8', 'location0Id': '4a789fb8-b9ef-44ca-b686-1f37edf0c357', 'daysOfWeek': [5], 'deletedAt': None, 'bysetpos': None, 'visible': False, 'borderLocationColor': 'navy', 'daysOfWeek_real': [5], 'clients_canceled': '', 'employees_canceled': '', 'reason_canceled': '', 'user_canceled': '', 'canceledId': '', 'startRecur1': '2024-01-19', 'endRecur1': '2024-01-20', 'startRecur': '2024-01-19', 'endRecur': '2024-01-20', 'cancelPending': [], 'createdById': '0d3ca0b0-0580-4628-a649-59312db5c914', 'updatedById': '0d3ca0b0-0580-4628-a649-59312db5c914', 'createdAt': '2024-01-19T15:39:11.000Z', 'updatedAt': '2024-01-19T15:39:17.000Z', 'notes': None, 'address': 'Gainesville, FL, USA', 'actual_users': [{'id': '1a92ae33-a4ae-46a1-a59f-ae29ffc2d042', 'roles': [{'id': '121bb921-96b4-4a89-86da-bf596b3d6ca2', 'name': 'Funder'}]}, {'id': '28576e59-7459-419e-bbd0-b1ec60f8f386', 'roles': [{'id': '8668600d-d670-4da7-baa0-64ee907c4770', 'name': 'ABA'}]}, {'id': '86dcbb8b-139b-4c8f-8de0-21b0b437f77d', 'roles': [{'id': '9707532a-dd9f-4cb7-aacb-06d21f25e8c0', 'name': 'RBT'}]}, {'id': 'a2d2f210-831c-4429-be87-fe3c1e3e0df8'}, {'id': '4a789fb8-b9ef-44ca-b686-1f37edf0c357'}], 'users': ['28576e59-7459-419e-bbd0-b1ec60f8f386', '86dcbb8b-139b-4c8f-8de0-21b0b437f77d', '4a789fb8-b9ef-44ca-b686-1f37edf0c357', '1a92ae33-a4ae-46a1-a59f-ae29ffc2d042', 'a2d2f210-831c-4429-be87-fe3c1e3e0df8'], 'users_names': ['Parahat Iljanov', 'Tyson Blue', 'Home ', 'Cigna ', 'Direct '], 'interval': 1, 'frequency': 'Weekly', 'sandboxMode': False}