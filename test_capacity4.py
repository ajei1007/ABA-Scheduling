import random
from itertools import chain
from ortools.sat.python import cp_model

time_slot_def = 15


def run_interval_scheduler_with_global_caps(
    num_clients=5,
    max_appts=2,
    num_staff=5,
    horizon=600,  # Total time horizon (in "time-slot" units)
    min_appt_duration=4,
    max_appt_duration=20,
    include_lunch=True,
    lunch_min=10,
    lunch_max=20,
    lunch_duration=2,
    seed=123,
):
    """
    1) Exactly one optional interval per client appointment (no staff duplication).
    2) staff_var in [0..num_staff-1] for each appointment => which staff is assigned if used.
    3) Mandatory lunch for each staff as a normal IntervalVar => staff can't do appointments then.
    4) Global AddCumulative => total concurrency <= num_staff.
    5) Per-staff no-overlap => staff's lunch + assigned appointments do not overlap.
    """

    if seed is not None:
        random.seed(seed)

    model = cp_model.CpModel()

    # ---------------------------
    # 1) Random client availability
    # ---------------------------
    earliest_starts = []
    latest_ends = []
    for c in range(num_clients):
        # Each client has 1 availability window for simplicity
        start_rand = random.randint(0, horizon - 5)
        end_rand = random.randint(start_rand + 1, horizon)
        earliest_starts.append([start_rand])  # list of lists
        latest_ends.append([end_rand])

    print("Client Availabilities:")
    for c in range(num_clients):
        print(f" Client {c}: earliest={earliest_starts[c]}, latest={latest_ends[c]}")

    # ---------------------------
    # 2) One optional interval per (client, availability, i)
    # ---------------------------
    intervals_per_client = []
    presence_per_client = []
    durations_per_client = []
    staff_per_client = []

    for c in range(num_clients):
        intervals_c = []
        presence_c = []
        durations_c = []
        staff_c = []

        # Each client has e.g. 1 availability window for demo
        for a in range(len(earliest_starts[c])):
            start_win = earliest_starts[c][a]
            end_win = latest_ends[c][a]

            # We'll create max_appts intervals in that window
            intervals_a = []
            presence_a = []
            durations_a = []
            staff_a = []

            for i in range(max_appts):
                used_var = model.NewBoolVar(f"used_c{c}_a{a}_i{i}")
                dur_var = model.NewIntVar(0, max_appt_duration, f"dur_c{c}_a{a}_i{i}")
                stf_var = model.NewIntVar(0, num_staff - 1, f"staff_c{c}_a{a}_i{i}")

                # Build start and end
                start_iv = model.NewIntVar(start_win, end_win, f"start_c{c}_a{a}_i{i}")
                end_iv = model.NewIntVar(start_win, end_win, f"end_c{c}_a{a}_i{i}")

                # If used => dur_var >= min_appt_duration
                model.Add(dur_var >= min_appt_duration).OnlyEnforceIf(used_var)
                # If not used => dur_var=0
                model.Add(dur_var == 0).OnlyEnforceIf(used_var.Not())

                # Interval
                appt_iv = model.NewOptionalIntervalVar(
                    start_iv, dur_var, end_iv, used_var, f"Client{c}_Avail{a}_Appt{i}"
                )

                # end_iv = start_iv + dur_var if used
                model.Add(end_iv == start_iv + dur_var).OnlyEnforceIf(used_var)

                intervals_a.append(appt_iv)
                presence_a.append(used_var)
                durations_a.append(dur_var)
                staff_a.append(stf_var)

            intervals_c.append(intervals_a)
            presence_c.append(presence_a)
            durations_c.append(durations_a)
            staff_c.append(staff_a)

        intervals_per_client.append(intervals_c)
        presence_per_client.append(presence_c)
        durations_per_client.append(durations_c)
        staff_per_client.append(staff_c)

    # ---------------------------
    # 3) Per-client NoOverlap
    # ---------------------------
    for c in range(num_clients):
        client_intervals = list(chain.from_iterable(intervals_per_client[c]))
        model.AddNoOverlap(client_intervals)

    # ---------------------------
    # 4) Staff lunches (mandatory)
    # ---------------------------
    lunch_intervals = []
    if include_lunch:
        for s in range(num_staff):
            # Staff s lunch
            if lunch_max - lunch_duration < lunch_min:
                # fallback
                lunch_start = model.NewIntVar(lunch_min, lunch_min, f"lunch_start_s{s}")
            else:
                lunch_start = model.NewIntVar(
                    lunch_min, lunch_max - lunch_duration, f"lunch_start_s{s}"
                )
            lunch_end = model.NewIntVar(0, horizon, f"lunch_end_s{s}")
            model.Add(lunch_end == lunch_start + lunch_duration)

            # Non-optional lunch
            lunch_iv = model.NewIntervalVar(
                lunch_start, lunch_duration, lunch_end, f"staff{s}_lunch"
            )
            lunch_intervals.append(lunch_iv)

    # ---------------------------
    # 5) Global AddCumulative (capacity = num_staff)
    # ---------------------------
    all_intervals = []
    all_demands = []

    # Add all client intervals
    for c in range(num_clients):
        for a, arr_a in enumerate(intervals_per_client[c]):
            for i in range(max_appts):
                all_intervals.append(arr_a[i])
                all_demands.append(1)

    # Add lunches
    if include_lunch:
        for lv in lunch_intervals:
            all_intervals.append(lv)
            all_demands.append(1)

    model.AddCumulative(all_intervals, all_demands, num_staff)

    # ---------------------------
    # 6) Per-Staff NoOverlap
    #    We do NOT create staff-level optional intervals for each appt.
    #    Instead, a minimal approach: We gather lunch + an "assigned to staff" approach
    # ---------------------------
    for s in range(num_staff):
        intervals_for_staff = []
        # That staff's lunch
        if include_lunch:
            intervals_for_staff.append(lunch_intervals[s])

        # For each appointment:
        for c in range(num_clients):
            for a, staff_array in enumerate(staff_per_client[c]):
                for i in range(max_appts):
                    staff_var = staff_array[i]
                    used_var = presence_per_client[c][a][i]
                    interval_iv = intervals_per_client[c][a][i]

                    assigned_to_s = model.NewBoolVar(f"assignStaff_s{s}_c{c}_a{a}_i{i}")

                    # If used => staff_var == s => assigned_to_s
                    model.Add(staff_var == s).OnlyEnforceIf(assigned_to_s)
                    # If not assigned => staff_var != s
                    model.Add(staff_var != s).OnlyEnforceIf(assigned_to_s.Not())
                    # Also, if not used => staff_var is irrelevant, but we ensure assigned_to_s=0
                    model.Add(assigned_to_s == 0).OnlyEnforceIf(used_var.Not())

                    # Then we build a minimal optional interval that references the same times
                    staff_opt_iv = model.NewOptionalIntervalVar(
                        interval_iv.StartExpr(),
                        interval_iv.SizeExpr(),
                        interval_iv.EndExpr(),
                        assigned_to_s,
                        f"staff{s}_c{c}_a{a}_i{i}",
                    )
                    intervals_for_staff.append(staff_opt_iv)

        model.AddNoOverlap(intervals_for_staff)

    # ---------------------------
    # 7) Objective
    # ---------------------------
    total_scheduled = model.NewIntVar(
        0, horizon * num_clients * max_appts, "total_scheduled"
    )
    sum_expr = []
    used_count_expr = []
    for c in range(num_clients):
        for a, dur_list in enumerate(durations_per_client[c]):
            for i in range(max_appts):
                sum_expr.append(dur_list[i])
                used_count_expr.append(presence_per_client[c][a][i])

    model.Add(total_scheduled == sum(sum_expr))

    total_used = model.NewIntVar(0, num_clients * max_appts, "total_used")
    model.Add(total_used == sum(used_count_expr))

    # Weighted objective: maximize sum of durations - small penalty for usage
    model.Maximize(total_scheduled * 100 - total_used)

    # ---------------------------
    # Solve
    # ---------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    solver.parameters.log_search_progress = True

    print("\nSolving...\n")
    status = solver.Solve(model)
    print(f"Status = {solver.StatusName(status)}")

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        scaled_total = solver.Value(total_scheduled)
        print(f"Total scheduled = {scaled_total} (scaled)")

        # Print lunches
        if include_lunch:
            print("\nStaff Lunches:")
            for s, lv in enumerate(lunch_intervals):
                ls = solver.Value(lv.StartExpr())
                le = solver.Value(lv.EndExpr())
                print(f"  Staff {s}: lunch from {ls} to {le}, dur={le - ls}")

        # Print assigned appointments
        print("\nAssigned Appointments:")
        for c in range(num_clients):
            for a, used_array in enumerate(presence_per_client[c]):
                for i, used_var in enumerate(used_array):
                    if solver.Value(used_var) == 1:
                        interval_iv = intervals_per_client[c][a][i]
                        st_val = solver.Value(interval_iv.StartExpr())
                        en_val = solver.Value(interval_iv.EndExpr())
                        staff_val = solver.Value(staff_per_client[c][a][i])
                        print(
                            f"  Client {c}, Avail {a}, Appt {i}: "
                            f"start={st_val}, end={en_val}, dur={en_val-st_val}, staff={staff_val}"
                        )
    else:
        print("No feasible solution found.")


# Example usage:
if __name__ == "__main__":
    run_interval_scheduler_with_global_caps(
        num_clients=4,
        max_appts=3,
        num_staff=4,
        horizon=600 // time_slot_def,
        # time_slot=time_slot_def,
        min_appt_duration=60 // time_slot_def,
        max_appt_duration=240 // time_slot_def,
        include_lunch=True,
        lunch_min=240 // time_slot_def,
        lunch_max=330 // time_slot_def,
        lunch_duration=30 // time_slot_def,
        seed=600,
        # client_list={},  # or your custom availability
        # id_name_dict={},  # or your custom mapping
    )
