import random
from itertools import chain
from ortools.sat.python import cp_model

time_slot_def = 15


def run_interval_scheduler_with_global_caps(
    num_clients=30,
    max_appts=4,
    num_staff=25,
    horizon=600 // time_slot_def,
    time_slot=time_slot_def,
    min_appt_duration=120 // time_slot_def,
    max_appt_duration=240 // time_slot_def,
    include_lunch=True,
    lunch_min=240 // time_slot_def,  # 12:00 => 240
    lunch_max=330 // time_slot_def,  # 13:30 => 330,
    lunch_duration=30 // time_slot_def,
    seed=600,
    client_list={},
    id_name_dict={},
):
    """
    1) Each appointment is assigned to a single staff (staff_var in [0..num_staff-1]).
    2) Each staff has a mandatory non-zero lunch interval (no overlap with appointments).
    3) A global AddCumulative limit ensures concurrency <= num_staff.
    4) We also do per-staff no-overlap to handle lunches + appointments on that staff's schedule.
    """

    def get_property_from_c(c, key="name"):
        if not id_name_dict:
            return c
        client_key = list(client_list.keys())[c]
        return id_name_dict[client_key][key]

    # Scale horizon and durations by time_slot
    # horizon //= time_slot
    # min_appt_duration //= time_slot
    # max_appt_duration //= time_slot
    # lunch_min //= time_slot
    # lunch_max //= time_slot
    # lunch_duration //= time_slot

    if seed is not None:
        random.seed(seed)

    model = cp_model.CpModel()

    # ---------------------------------------------------------
    # 1) Generate or parse client availability windows
    # ---------------------------------------------------------
    earliest_starts = []
    latest_ends = []
    if not client_list:
        # random availabilities if client_list not provided
        for c in range(num_clients):
            availabilities = random.randint(2, 3)
            start_list = []
            end_list = []
            for _ in range(availabilities):
                s_rand = random.randint(0, horizon - 1)
                e_rand = random.randint(s_rand + 1, horizon)
                start_list.append(s_rand)
                end_list.append(e_rand)
            earliest_starts.append(start_list)
            latest_ends.append(end_list)
    else:
        # from your client_list
        for key, availabilities in client_list.items():
            s_list, e_list = [], []
            for a in availabilities:
                s_rand, e_rand = list(a)
                s_list.append(s_rand)
                e_list.append(e_rand)
            earliest_starts.append(s_list)
            latest_ends.append(e_list)

    print("Scaled horizon:", horizon, "time_slot:", time_slot)
    print("earliest_starts:", earliest_starts)
    print("latest_ends:", latest_ends)

    # ---------------------------------------------------------
    # 2) Build IntervalVarOptional + staff assignment
    # ---------------------------------------------------------
    intervals_per_client = []
    presence_per_client = []
    durations_matrix = []
    staff_assignment = []

    for c in range(num_clients):
        intervals_between_avails = []
        presence_between_avails = []
        durations_between_avails = []
        staff_between_avails = []

        cname = get_property_from_c(c, "name")

        # For each availability window
        for a in range(len(latest_ends[c])):
            intervals_c = []
            presence_c = []
            durations_c = []
            staff_vars_c = []

            previous_end = None
            previous_duration = None

            for i in range(max_appts):
                used_c_i = model.NewBoolVar(f"used_c{c}_a{a}_i{i}")
                # Appointment duration in scaled units
                appt_duration = model.NewIntVar(
                    0, max_appt_duration, f"dur_c{c}_a{a}_i{i}"
                )

                # Staff assignment: each appointment is assigned to exactly 1 staff
                staff_var = model.NewIntVar(0, num_staff - 1, f"staff_c{c}_a{a}_i{i}")

                # Interval end
                end_c_i = model.NewIntVar(
                    earliest_starts[c][a], latest_ends[c][a], f"end_c{c}_a{a}_i{i}"
                )

                if i == 0:
                    # first appointment in this window
                    start_c_i = model.NewIntVar(
                        earliest_starts[c][a],
                        latest_ends[c][a],
                        f"start_c{c}_a{a}_i{i}",
                    )
                else:
                    # subsequent appointment starts at the previous appointment's end
                    start_c_i = previous_end
                    # durations non-increasing
                    if previous_duration is not None:
                        model.Add(appt_duration <= previous_duration)

                previous_end = end_c_i
                previous_duration = appt_duration

                # If not used => appt_duration=0
                model.Add(appt_duration == 0).OnlyEnforceIf(used_c_i.Not())
                # If used => appt_duration >= min_appt_duration
                model.Add(appt_duration >= min_appt_duration).OnlyEnforceIf(used_c_i)

                # Build optional interval
                appt_iv = model.NewOptionalIntervalVar(
                    start_c_i,
                    appt_duration,
                    end_c_i,
                    used_c_i,
                    f"client{cname}_a{a}_appt{i}",
                )

                intervals_c.append(appt_iv)
                presence_c.append(used_c_i)
                durations_c.append(appt_duration)
                staff_vars_c.append(staff_var)

            intervals_between_avails.append(intervals_c)
            presence_between_avails.append(presence_c)
            durations_between_avails.append(durations_c)
            staff_between_avails.append(staff_vars_c)

        intervals_per_client.append(intervals_between_avails)
        presence_per_client.append(presence_between_avails)
        durations_matrix.append(durations_between_avails)
        staff_assignment.append(staff_between_avails)

    # ---------------------------------------------------------
    # 3) No-Overlap per client
    # ---------------------------------------------------------
    for c in range(num_clients):
        intervals_for_c = list(chain.from_iterable(intervals_per_client[c]))
        model.AddNoOverlap(intervals_for_c)

    # ---------------------------------------------------------
    # 4) Staff lunches (Mandatory Intervals)
    # ---------------------------------------------------------
    lunch_vars = []
    if include_lunch:
        # Force each staff to have a non-zero lunch
        for s in range(num_staff):
            # staff s lunch start in [lunch_min..(lunch_max-lunch_duration)]
            if lunch_max - lunch_duration < lunch_min:
                # If lunch window is too small, set them to exactly lunch_min
                lunch_start_var = model.NewIntVar(
                    lunch_min, lunch_min, f"lunch_start_s{s}"
                )
            else:
                lunch_start_var = model.NewIntVar(
                    lunch_min, lunch_max - lunch_duration, f"lunch_start_s{s}"
                )
            lunch_end_var = model.NewIntVar(0, horizon, f"lunch_end_s{s}")
            model.Add(lunch_end_var == lunch_start_var + lunch_duration)

            # Non-optional lunch interval
            lunch_iv = model.NewIntervalVar(
                lunch_start_var, lunch_duration, lunch_end_var, f"staff{s}_lunch"
            )
            lunch_vars.append(lunch_iv)

    # ---------------------------------------------------------
    # 5) Global Cumulative (capacity = num_staff)
    # ---------------------------------------------------------
    all_intervals = []
    all_demands = []

    for c in range(num_clients):
        for a, intervals_a in enumerate(intervals_per_client[c]):
            for i in range(max_appts):
                all_intervals.append(intervals_a[i])
                all_demands.append(1)

    if include_lunch:
        for lv in lunch_vars:
            all_intervals.append(lv)
            all_demands.append(1)

    model.AddCumulative(all_intervals, all_demands, num_staff)

    # ---------------------------------------------------------
    # 6) Per-Staff No-Overlap (Appointments + Lunch)
    # ---------------------------------------------------------
    for s in range(num_staff):
        intervals_for_staff = []
        # staff s lunch
        if include_lunch:
            intervals_for_staff.append(lunch_vars[s])

        # For each appointment, if assigned to staff s => we add an optional interval
        for c in range(num_clients):
            for a, staff_arr in enumerate(staff_assignment[c]):
                for i in range(max_appts):
                    staff_var = staff_arr[i]
                    used_var = presence_per_client[c][a][i]
                    interval_iv = intervals_per_client[c][a][i]

                    assigned_to_s = model.NewBoolVar(f"assign_s{s}_c{c}_a{a}_i{i}")
                    model.Add(staff_var == s).OnlyEnforceIf(assigned_to_s)
                    model.Add(staff_var != s).OnlyEnforceIf(assigned_to_s.Not())

                    staff_optional_iv = model.NewOptionalIntervalVar(
                        interval_iv.StartExpr(),
                        interval_iv.SizeExpr(),
                        interval_iv.EndExpr(),
                        assigned_to_s,
                        f"staff{s}_c{c}_a{a}_i{i}",
                    )
                    intervals_for_staff.append(staff_optional_iv)

        model.AddNoOverlap(intervals_for_staff)

    # ---------------------------------------------------------
    # 7) Objective: maximize total scheduled time (scaled)
    #               with a penalty for used intervals
    # ---------------------------------------------------------
    total_scheduled = model.NewIntVar(
        0, horizon * num_clients * max_appts, "total_scheduled"
    )
    total_used = model.NewIntVar(0, num_clients * max_appts, "total_used")

    sum_expr = []
    sum_used = []
    for c in range(num_clients):
        for a, durations_for_window in enumerate(durations_matrix[c]):
            for i in range(max_appts):
                sum_expr.append(durations_for_window[i])
                sum_used.append(presence_per_client[c][a][i])

    model.Add(total_scheduled == sum(sum_expr))
    model.Add(total_used == sum(sum_used))

    # Weighted objective: prefer maximizing total_scheduled, slightly penalize the # of intervals used
    model.Maximize(total_scheduled * 100 - total_used)
    model.AddDecisionStrategy(
        [*sum_expr], cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE
    )
    total_blocks = horizon
    staff_capacity = num_staff * total_blocks - num_staff
    model.Add(total_scheduled <= staff_capacity)

    # (b) Client capacity = sum of (latest_ends[c] - earliest_starts[c])
    total_client_capacity = 0
    for c in range(num_clients):
        for a, _ in enumerate(latest_ends[c]):
            total_client_capacity += latest_ends[c][a] - earliest_starts[c][a]
    model.Add(total_scheduled <= total_client_capacity)

    # ---------------------------------------------------------
    # 8) Solve
    # ---------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True

    print("\nSolving...\n")
    status = solver.Solve(model)
    print(f"Status: {solver.StatusName(status)}")

    all_appointments = {}
    lunch_appointments = {}

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        scaled_total = solver.Value(total_scheduled)
        used_count = solver.Value(total_used)
        print(f"Total scheduled (scaled) = {scaled_total}")
        print(f"Number of used intervals = {used_count}\n")

        # 1) Show lunches
        if include_lunch:
            print("Assigned Lunch Intervals:")
            for s in range(num_staff):
                lunch_iv = lunch_vars[s]
                ls_val = solver.Value(lunch_iv.StartExpr())
                le_val = solver.Value(lunch_iv.EndExpr())
                dur_lunch = le_val - ls_val
                lunch_appointments.setdefault(s, []).append(
                    {"start": ls_val, "end": le_val}
                )
                print(f"  Staff {s}: lunch from {ls_val} to {le_val}, dur={dur_lunch}")
            print()

        # 2) Show assigned appointments
        print("Assigned Appointments (with staff assignment):")
        num_of_appointments = 0
        for c in range(num_clients):
            cid = get_property_from_c(c, "id")
            cname = get_property_from_c(c, "name")
            for a, presence_array in enumerate(presence_per_client[c]):
                for i in range(max_appts):
                    if solver.Value(presence_array[i]) == 1:
                        interval_var = intervals_per_client[c][a][i]
                        s_val = solver.Value(interval_var.StartExpr())
                        e_val = solver.Value(interval_var.EndExpr())
                        dur_val = e_val - s_val

                        staff_var = staff_assignment[c][a][i]
                        staff_assigned = solver.Value(staff_var)

                        num_of_appointments += 1
                        all_appointments.setdefault(cid, []).append(
                            {
                                "start": s_val,
                                "end": e_val,
                                "staff": staff_assigned,
                                "clientName": cname,
                            }
                        )

                        print(
                            f"  Client {cname} Avail {a}, Appt {i}: "
                            f"start={s_val}, end={e_val}, dur={dur_val}, staff={staff_assigned}"
                        )

        print(f"Number of assigned appointments: {num_of_appointments}")

        return {
            "therapy_appointments": all_appointments,
            "lunch_appointments": lunch_appointments,
        }
    else:
        print("No feasible solution found.")
        return None


# Example usage (commented out so you can adapt):
if __name__ == "__main__":
    results = run_interval_scheduler_with_global_caps(
        num_clients=4,
        max_appts=3,
        num_staff=4,
        horizon=600 // time_slot_def,
        time_slot=time_slot_def,
        min_appt_duration=60 // time_slot_def,
        max_appt_duration=240 // time_slot_def,
        include_lunch=True,
        lunch_min=240 // time_slot_def,
        lunch_max=330 // time_slot_def,
        lunch_duration=30 // time_slot_def,
        seed=600,
        client_list={},  # or your custom availability
        id_name_dict={},  # or your custom mapping
    )
    if results:
        # do something with results['therapy_appointments']
        pass
