import googlemaps
import requests
import datetime
import numpy as np

API_KEY = "AIzaSyDFfpe9hOdznMJkNwmor6ljrrBFWjlXLPM"
Headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyIjp7ImlkIjoiMGQzY2EwYjAtMDU4MC00NjI4LWE2NDktNTkzMTJkYjVjOTE0IiwiZW1haWwiOiJhZGFtQGFiYXNjaGVkdWxlcy5jb20ifSwiaWF0IjoxNzAyNDAyNzUxLCJleHAiOjIzMzAyNDAyNzUxfQ.NsWz7IjJIRrGskZi9r_U-Jd1DlpOLI6VWWGn8jmLY8A"
}

example_data = {
    "data": {
        "duration": 512,
        "distance": 2000,
        "user1": "cb8c33b9-3866-4999-bd5a-7bd9c201ea25",
        "user2": "28576e59-7459-419e-bbd0-b1ec60f8f386",
    }
}


def calculate_distance_pairs(
    addr1,
    addr2,
    api_key="AIzaSyDFfpe9hOdznMJkNwmor6ljrrBFWjlXLPM",
    dep_time=12,
    minutes=0,
):
    gmaps = googlemaps.Client(key=api_key)
    try:
        now = datetime.datetime.now()
        days_until_next_monday = (7 - now.weekday() + 0) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = (
                7  # Ensure it's the next Monday, not today if today is Monday
            )

        next_monday_at_9am = now.replace(
            hour=dep_time, minute=minutes, second=0, microsecond=0
        ) + datetime.timedelta(days=days_until_next_monday)

        departure_time_seconds = int(next_monday_at_9am.timestamp())
        print("bazo_adresses : ", addr1, "----", addr2)
        if addr1 is None or addr2 is None:
            return [0, 0]
        result = gmaps.distance_matrix(
            origins=[addr1],
            destinations=[addr2],
            mode="driving",
            units="metric",
            departure_time=departure_time_seconds,
            # ,traffic_model="pessimistic"
        )
        if result is None or result["rows"][0]["elements"][0]["status"] == "NOT_FOUND":
            return [0, 0]
        distance = result["rows"][0]["elements"][0]["distance"]["value"]
        duration = result["rows"][0]["elements"][0]["duration_in_traffic"]["value"]
        return [distance, duration]
    except Exception as e:
        print(f"Error: {e}")


def get_drive_time_data(header, host):
    res = requests.get(f"{host}/distancematrix/", headers=header)
    dict_data = {}
    for d in res.json()["rows"]:
        if d["address1"] is not None and d["address2"] is not None:
            dict_data[tuple([d["address1"], d["address2"]])] = {
                "early": d["duration_early"],
                "mid": d["duration"],
                "late": d["duration_late"],
            }
    return dict_data


def post_drive_time_data(header, actual_data, host):
    res = requests.post(f"{host}/distancematrix/", headers=header, json=actual_data)
    return res.status_code


def convert_drive_time(d_time):
    if type(d_time) == str:
        return [i.split(",") for i in d_time.split("|")]
    if type(d_time) == list:
        return "|".join([",".join([str(j) for j in i]) for i in d_time])


def calc_approx_time(arr, X):
    x = [int(i) for i in X.split(":")]
    del_x = x[0] + x[1] / 60
    len_arr = len(arr)
    for i, v in enumerate(arr):
        if v[0] == x[0]:
            if i < len_arr - 1:
                return round(
                    arr[i][1]
                    + (del_x - arr[i][0])
                    * (arr[i + 1][1] - arr[i][1])
                    / (arr[i + 1][0] - arr[i][0]),
                    2,
                )
            else:
                return arr[-1][1]
    return None


def return_ten_time():
    def get_tomorrow_date_with_time(hours):
        current_datetime = datetime.datetime.utcnow()

        tomorrow_date = current_datetime + datetime.timedelta(days=1)

        tomorrow_datetime_with_hours = tomorrow_date.replace(
            hour=hours, minute=0, second=0, microsecond=0
        )

        formatted_datetime = tomorrow_datetime_with_hours.strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )

        return formatted_datetime

    specified_hours = [12]
    res = []
    for hour in specified_hours:
        result = get_tomorrow_date_with_time(hour)
        res.append(result)
    return res


def return_interval_drive_time(addr1, addr2, hour, minutes):
    print("foojy", addr1, addr2, hour, minutes)
    res = calculate_distance_pairs(addr1, addr2, dep_time=hour, minutes=minutes)
    print("simmy", res)
    dis, dur_time = res[0], res[1]
    return [dis, dur_time]
    return res


aa = [
    [1522, 208],
    [1522, 201],
    [1522, 215],
    [1522, 216],
    [1522, 230],
    [1522, 262],
    [1522, 268],
    [1522, 265],
    [1522, 280],
    [1522, 301],
    [1522, 323],
]


def return_cofficients_of_polinomial(x_values, y_values):
    x = np.array(x_values)
    y = np.array(y_values)
    coefficients = np.polyfit(x, y, 2)
    return [int(i) for i in list(coefficients)]
    pass
