from datetime import datetime
from core.shared.utils import strip_microseconds

def parse_dt(s):
    try:
        print(f"inputed date: {s}")
        formatted_date = strip_microseconds(s)
        print(f"formatted date: {formatted_date}")
        return datetime.fromisoformat(formatted_date.replace('Z', '+00:00'))
    except Exception:
        return None

def is_matching_event(delete_evt, create_evt):
    activity = delete_evt.get("activity") or create_evt.get("activity")

    if activity == "Lunch":
        keys_to_match = ['employee', 'location']
    else:
        keys_to_match = ['client', 'employee', 'location', 'activity']

    for key in keys_to_match:
        if delete_evt.get(key) != create_evt.get(key):
            return False

    end1 = parse_dt(delete_evt.get('end'))
    end2 = parse_dt(create_evt.get('end'))
    start1 = parse_dt(delete_evt.get('start'))
    start2 = parse_dt(create_evt.get('start'))

    if start1 and start2 and end1 and end2:
        if start1 == start2 and end1 == end2:
            print(f"old event in matcher: {delete_evt}")
            print(f"new event in matcher: {create_evt}")
        return start1 == start2 and end1 == end2

    return False

def events_overlap(e1, e2):
    c1 = e1.get("client")
    c2 = e2.get("client")
    e1_emp = e1.get("employee")
    e2_emp = e2.get("employee")
    has_valid_client_match = c1 and c2 and c1 == c2
    has_valid_employee_match = e1_emp and e2_emp and e1_emp == e2_emp

    if has_valid_client_match or has_valid_employee_match:
        s1 = parse_dt(e1.get("start"))
        e1_end = parse_dt(e1.get("end"))
        s2 = parse_dt(e2.get("start"))
        e2_end = parse_dt(e2.get("end"))

        if not (s1 and e1_end and s2 and e2_end):
            return False

        return s1 < e2_end and s2 < e1_end
    
    return False
