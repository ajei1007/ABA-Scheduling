import random
from itertools import chain
from ortools.sat.python import cp_model

time_slot_def = 15


def run_interval_scheduler_with_global_caps(
    num_clients=30,
    max_appts=5,
    num_staff=25,
    horizon=600 // time_slot_def,
    time_slot=time_slot_def,
    min_appt_duration=60 // time_slot_def,
    max_appt_duration=360 // time_slot_def,
    include_lunch=True,
    lunch_min=240 // time_slot_def,  # 12:00 => 240
    lunch_max=330 // time_slot_def,  # 13:30 => 330,
    lunch_duration=30 // time_slot_def,
    seed=600,
    client_list={},
    id_name_dict={},
):
    print("time_slot:", time_slot, "lunch_min:", lunch_min, "lunch_max:", lunch_max)

    """
    Demonstration with:
      - IntervalVarOptional for client appointments
      - AddNoOverlap to prevent a single client's appointments from overlapping
      - A Cumulative constraint to limit concurrency to 'num_staff'
      - Staff lunches restricted to 12:00–13:30
      - Global constraints on total_scheduled <= staff_capacity and client_capacity
      - Staff assignment to ensure each appointment can be mapped to a unique staff
    """

    def get_property_from_c(c, key="name"):
        """Retrieve property (like name/id) from id_name_dict if provided."""
        if not id_name_dict:
            return c
        # otherwise map from client_list's keys
        client_key = list(client_list.keys())[c]
        return id_name_dict[client_key][key]

    # Scale all the time-based inputs by time_slot
    # Already done in your function signature

    if seed is not None:
        random.seed(seed)

    model = cp_model.CpModel()

    # ---------------------------------------------------------
    # 1) Generate random or provided client availability windows
    # ---------------------------------------------------------
    earliest_starts = []
    latest_ends = []
    if not client_list:
        # random generation
        for c in range(num_clients):
            availabilities = random.randint(2, 3)
            availability_start_list = []
            availability_end_list = []
            for a in range(availabilities):
                start_rand = random.randint(0, horizon - 1)
                end_rand = random.randint(start_rand + 1, horizon)
                availability_start_list.append(start_rand)
                availability_end_list.append(end_rand)
            earliest_starts.append(availability_start_list)
            latest_ends.append(availability_end_list)
    else:
        # from client_list
        for key, availabilities in client_list.items():
            availability_start_list = []
            availability_end_list = []
            for a in availabilities:
                start_rand, end_rand = list(a)
                availability_start_list.append(start_rand)
                availability_end_list.append(end_rand)
            earliest_starts.append(availability_start_list)
            latest_ends.append(availability_end_list)

    print("earliest_starts:", earliest_starts)
    print("latest_ends:", latest_ends)

    print("Client availability windows (0..horizon in scaled time slots):")
    for c in range(num_clients):
        print(f"  Client {c}: earliest={earliest_starts[c]}, latest={latest_ends[c]}")

    # ---------------------------------------------------------
    # 2) Create IntervalVarOptional for each client appointment
    #    + Introduce staff assignment variable
    # ---------------------------------------------------------
    intervals_per_client = []
    presence_per_client = []
    durations_matrix = []
    assigned_staff = []  # new: assigned staff variables

    for c in range(num_clients):
        intervals_per_client_between = []
        presence_per_client_between = []
        durations_matrix_between = []
        staff_assignment_between = []

        name = get_property_from_c(c, "name")

        # For each availability window "a"
        for a in range(len(latest_ends[c])):
            intervals_c = []
            presence_c = []
            durations_c = []
            staff_assign_c = []

            previous_end = None
            previous_duration = None

            for i in range(max_appts):
                # appt_duration in scaled time slots
                appt_duration = model.NewIntVar(
                    0, max_appt_duration, f"duration_c{c}_a{a}_i{i}"
                )

                used_c_i = model.NewBoolVar(f"used_c{c}_a{a}_i{i}")
                end_c_i = model.NewIntVar(
                    earliest_starts[c][a], latest_ends[c][a], f"end_c{c}_a{a}_i{i}"
                )

                # staff assignment variable
                staff_var = model.NewIntVar(0, num_staff - 1, f"staff_c{c}_a{a}_i{i}")

                if i == 0:
                    start_c_i = model.NewIntVar(
                        earliest_starts[c][a],
                        latest_ends[c][a],
                        f"start_c{c}_a{a}_i{i}",
                    )
                else:
                    # subsequent appointment starts at previous end
                    start_c_i = previous_end
                    model.Add(appt_duration <= previous_duration)

                # update for next iteration
                previous_end = end_c_i
                previous_duration = appt_duration

                # if not used => appt_duration=0
                model.Add(appt_duration == 0).OnlyEnforceIf(used_c_i.Not())
                model.Add(appt_duration >= min_appt_duration).OnlyEnforceIf(used_c_i)

                # define optional interval
                appt_iv = model.NewOptionalIntervalVar(
                    start_c_i, appt_duration, end_c_i, used_c_i, f"client{name}_appt{i}"
                )

                intervals_c.append(appt_iv)
                presence_c.append(used_c_i)
                durations_c.append(appt_duration)
                staff_assign_c.append(staff_var)

            intervals_per_client_between.append(intervals_c)
            presence_per_client_between.append(presence_c)
            durations_matrix_between.append(durations_c)
            staff_assignment_between.append(staff_assign_c)

        intervals_per_client.append(intervals_per_client_between)
        presence_per_client.append(presence_per_client_between)
        durations_matrix.append(durations_matrix_between)
        assigned_staff.append(staff_assignment_between)

    # ---------------------------------------------------------
    # 3) No-Overlap per client
    # ---------------------------------------------------------
    for c in range(num_clients):
        # Flatten intervals across all availability windows
        intervals_for_client = list(chain.from_iterable(intervals_per_client[c]))
        model.AddNoOverlap(intervals_for_client)

    # ---------------------------------------------------------
    # 4) Staff lunches
    # ---------------------------------------------------------
    lunch_intervals = []
    if include_lunch:
        if lunch_max > horizon:
            lunch_max = horizon

        for s in range(num_staff):
            lunch_start_var = model.NewIntVar(
                lunch_min,
                max(lunch_min, lunch_max - lunch_duration),
                f"lunch_start_s{s}",
            )
            lunch_end_var = model.NewIntVar(0, horizon, f"lunch_end_s{s}")
            model.Add(lunch_end_var == lunch_start_var + lunch_duration)

            lunch_iv = model.NewIntervalVar(
                lunch_start_var, lunch_duration, lunch_end_var, f"staff{s}_lunch"
            )
            lunch_intervals.append(lunch_iv)

    # ---------------------------------------------------------
    # 5) Cumulative Resource: capacity = num_staff
    # ---------------------------------------------------------
    all_intervals = []
    all_demands = []

    for c in range(num_clients):
        for a, _ in enumerate(intervals_per_client[c]):
            for i in range(max_appts):
                all_intervals.append(intervals_per_client[c][a][i])
                all_demands.append(1)

    if include_lunch:
        for lunch_iv in lunch_intervals:
            all_intervals.append(lunch_iv)
            all_demands.append(1)

    model.AddCumulative(all_intervals, all_demands, num_staff)

    # ---------------------------------------------------------
    # 6) Per-Staff NoOverlap
    #    So each staff doesn't get double-booked
    # ---------------------------------------------------------
    for s in range(num_staff):
        staff_specific_intervals = []
        for c in range(num_clients):
            for a, staff_array in enumerate(assigned_staff[c]):
                for i in range(max_appts):
                    # This is a boolean that indicates "this interval is assigned to staff s"
                    assigned_to_s = model.NewBoolVar(
                        f"assigned_to_s{c}_a{a}_i{i}_stf{s}"
                    )

                    # If used, staff_var == s
                    model.Add(staff_array[i] == s).OnlyEnforceIf(assigned_to_s)
                    model.Add(staff_array[i] != s).OnlyEnforceIf(assigned_to_s.Not())

                    # If "assigned_to_s" is true, we add the interval to that staff's set
                    # We create an "OptionalIntervalVar" link for staff-level no-overlap
                    interval_var = intervals_per_client[c][a][i]
                    # We'll create a staff-specific optional interval
                    staff_opt_iv = model.NewOptionalIntervalVar(
                        interval_var.StartExpr(),
                        interval_var.SizeExpr(),
                        interval_var.EndExpr(),
                        assigned_to_s,
                        f"staff{s}_c{c}_a{a}_i{i}",
                    )
                    staff_specific_intervals.append(staff_opt_iv)

        # Now, no overlap among intervals assigned to staff s
        model.AddNoOverlap(staff_specific_intervals)

    # ---------------------------------------------------------
    # 7) Objective: maximize total scheduled minutes
    #               secondary objective: fewer appointments
    # ---------------------------------------------------------
    total_scheduled = model.NewIntVar(
        0, horizon * num_clients * max_appts, "total_scheduled"
    )
    total_used = model.NewIntVar(0, num_clients * max_appts, "total_used")

    sum_expr = []
    sum_used = []
    for c in range(num_clients):
        for a, durations_array in enumerate(durations_matrix[c]):
            for i in range(max_appts):
                sum_expr.append(durations_array[i])
                sum_used.append(presence_per_client[c][a][i])

    model.Add(total_scheduled == sum(sum_expr))
    model.Add(total_used == sum(sum_used))

    # Weighted objective: maximize total_scheduled - small penalty for usage
    model.Maximize(total_scheduled * 100 - total_used)

    # ---------------------------------------------------------
    # 8) Solve
    # ---------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 3
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True

    print("\nSolving...\n")
    status = solver.Solve(model)
    print(f"Status: {solver.StatusName(status)}")

    all_appointments = {}
    lunch_appointments = {}

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"Total scheduled (scaled) = {solver.Value(total_scheduled)}")
        print(f"Number of used intervals = {solver.Value(total_used)}\n")

        # Print staff lunches
        if include_lunch:
            print("Staff Lunch Intervals:")
            for s in range(num_staff):
                ls_val = solver.Value(lunch_intervals[s].StartExpr())
                le_val = solver.Value(lunch_intervals[s].EndExpr())
                print(
                    f"  Staff {s}: lunch from {ls_val} to {le_val} (dur={le_val - ls_val})"
                )
                lunch_appointments.setdefault(s, []).append(
                    {"start": ls_val, "end": le_val}
                )
            print()

        print("Assigned Appointments (with staff assignment):")
        num_of_appointments = 0

        for c in range(num_clients):
            cid = get_property_from_c(c, "id")
            cname = get_property_from_c(c, "name")
            for a, presence_array in enumerate(presence_per_client[c]):
                for i in range(max_appts):
                    if solver.Value(presence_array[i]) == 1:
                        num_of_appointments += 1
                        interval_var = intervals_per_client[c][a][i]
                        start_val = solver.Value(interval_var.StartExpr())
                        end_val = solver.Value(interval_var.EndExpr())
                        staff_var = assigned_staff[c][a][i]
                        assigned_s = solver.Value(staff_var)
                        dur_val = end_val - start_val
                        # Store it
                        all_appointments.setdefault(cid, []).append(
                            {
                                "start": start_val,
                                "end": end_val,
                                "staff": assigned_s,
                                "clientName": cname,
                            }
                        )
                        print(
                            f"  Client {cname} Avail {a}, Appt {i}: "
                            f"start={start_val}, end={end_val}, dur={dur_val}, staff={assigned_s}"
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
        max_appts=5,
        num_staff=4,
        horizon=600 // time_slot_def,
        time_slot=time_slot_def,
        min_appt_duration=60 // time_slot_def,
        max_appt_duration=360 // time_slot_def,
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
