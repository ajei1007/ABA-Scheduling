import random
from itertools import chain
from ortools.sat.python import cp_model

time_slot_def = 15


def run_interval_scheduler_with_global_caps(
    num_clients=30,
    max_appts=3,
    num_staff=25,
    horizon=600 // time_slot_def,
    time_slot=time_slot_def,
    min_appt_duration=30 // time_slot_def,
    max_appt_duration=240 // time_slot_def,
    include_lunch=True,
    lunch_min=240 // time_slot_def,  # 12:00 => 240
    lunch_max=330 // time_slot_def,  # 13:30 => 330,
    lunch_duration=30 // time_slot_def,
    seed=600,
    client_list={},
    id_name_dict={},
):
    print("time_slot", time_slot, lunch_min, lunch_max)

    """
    Demonstration with:
      - IntervalVarOptional for client appointments
      - AddNoOverlap to prevent a single client's appointments from overlapping
      - A Cumulative constraint to limit concurrency to 'num_staff'
      - Staff lunches restricted to 12:00–13:30
      - Global constraints on total_scheduled <= staff_capacity and client_capacity
    """

    def get_property_from_c(c, key="name"):
        return c if not id_name_dict else id_name_dict[list(client_list.keys())[c]][key]

    if seed is not None:
        random.seed(seed)

    model = cp_model.CpModel()

    # ---------------------------------------------------------
    # 1) Generate random client availability windows
    # ---------------------------------------------------------
    earliest_starts = []
    latest_ends = []
    if not client_list:
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
        for key, availabilities in client_list.items():
            availability_start_list = []
            availability_end_list = []
            for a in availabilities:
                list_a = list(a)
                start_rand = list_a[0]
                end_rand = list_a[1]
                availability_start_list.append(start_rand)
                availability_end_list.append(end_rand)
            earliest_starts.append(availability_start_list)
            latest_ends.append(availability_end_list)

    print("earliest_starts", earliest_starts)
    print("latest_ends", latest_ends)
    # print()
    # for c_id, value in client_list.items():
    #     pass

    print("Client availability windows (0..horizon minutes):")
    for c in range(num_clients):
        print(f"  Client {c}: earliest={earliest_starts[c]}, latest={latest_ends[c]}")

    # ---------------------------------------------------------
    # 2) Create IntervalVarOptional for each client appointment
    # ---------------------------------------------------------
    intervals_per_client = []
    presence_per_client = []
    durations_matrix = []

    for c in range(num_clients):
        intervals_per_client_between = []
        presence_per_client_between = []
        durations_matrix_between = []
        name = get_property_from_c(c, "name")
        for a in range(len(latest_ends[c])):
            intervals_c = []
            presence_c = []
            durations_c = []
            previous_end = None
            previous_duration = None
            for i in range(max_appts):
                # appt_duration = random.randint(min_appt_duration, max_appt_duration)
                appt_duration = model.NewIntVar(
                    0, max_appt_duration, f"end_c{c}_a{a}_i{i}"
                )

                used_c_i = model.NewBoolVar(f"used_c{c}_i{i}")
                end_c_i = model.NewIntVar(
                    earliest_starts[c][a], latest_ends[c][a], f"end_c{c}_a{a}_i{i}"
                )
                if i == 0:
                    start_c_i = model.NewIntVar(
                        earliest_starts[c][a],
                        latest_ends[c][a],
                        f"start_c{c}_a{a}_i{i}",
                    )
                else:
                    start_c_i = previous_end
                    model.Add(appt_duration <= previous_duration)
                previous_end = end_c_i
                previous_duration = appt_duration
                model.Add(appt_duration == 0).OnlyEnforceIf(used_c_i.Not())
                model.Add(appt_duration >= min_appt_duration).OnlyEnforceIf(used_c_i)

                appt_iv = model.NewOptionalIntervalVar(
                    start_c_i, appt_duration, end_c_i, used_c_i, f"client{name}_appt{i}"
                )

                intervals_c.append(appt_iv)
                presence_c.append(used_c_i)
                durations_c.append(appt_duration)

            intervals_per_client_between.append(intervals_c)
            presence_per_client_between.append(presence_c)
            durations_matrix_between.append(durations_c)

        intervals_per_client.append(intervals_per_client_between)
        presence_per_client.append(presence_per_client_between)
        durations_matrix.append(durations_matrix_between)

    # ---------------------------------------------------------
    # 3) No-Overlap per client
    # ---------------------------------------------------------
    for c in range(num_clients):
        model.AddNoOverlap(list(chain.from_iterable(intervals_per_client[c])))

    # ---------------------------------------------------------
    # 4) Staff lunches restricted to 12:00–13:30 (converted to [240..330])
    # ---------------------------------------------------------
    lunch_intervals = []
    if include_lunch:
        if lunch_max > horizon:
            lunch_max = horizon

        for s in range(num_staff):
            lunch_start_var = model.NewIntVar(
                lunch_min, lunch_max - lunch_duration, f"lunch_start_s{s}"
            )
            lunch_end_var = model.NewIntVar(0, horizon, f"lunch_end_s{s}")
            model.Add(lunch_end_var == lunch_start_var + lunch_duration)

            lunch_iv = model.NewIntervalVar(
                lunch_start_var, lunch_duration, lunch_end_var, f"staff{s}_lunch"
            )
            lunch_intervals.append((lunch_start_var, lunch_end_var, lunch_iv))

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
        for s in range(num_staff):
            (_, _, lunch_iv) = lunch_intervals[s]
            all_intervals.append(lunch_iv)
            all_demands.append(1)

    model.AddCumulative(all_intervals, all_demands, num_staff)

    # ---------------------------------------------------------
    # 6) Objective: maximize total scheduled minutes
    # ---------------------------------------------------------
    total_scheduled = model.NewIntVar(
        0, horizon * num_clients * max_appts, "total_scheduled"
    )
    total_used = model.NewIntVar(0, num_clients * max_appts, "total_used")
    sum_expr = []
    sum_used = []
    for c in range(num_clients):
        for a, _ in enumerate(durations_matrix[c]):
            for i in range(max_appts):
                sum_expr.append(durations_matrix[c][a][i])
                sum_used.append(presence_per_client[c][a][i])
    model.Add(total_scheduled == sum(sum_expr))
    model.Add(total_used == sum(sum_used))
    ##minimize number appointments as secondary constraint, maybe just do decision strategy to start with largest durations first?
    model.Maximize(total_scheduled * 100 - total_used)
    # model.Maximize(total_scheduled)
    # model.AddDecisionStrategy(
    #     [*sum_expr], cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE
    # )

    # ---------------------------------------------------------
    # 7) Global Capacity Constraints
    # ---------------------------------------------------------
    # (a) Staff capacity (approx). Let's interpret each "block" as 1 minute => total_blocks = horizon
    # each staff is 1-lunch => staff_capacity = num_staff*horizon - num_staff
    # total_blocks = horizon
    # staff_capacity = num_staff * total_blocks - num_staff
    # model.Add(total_scheduled <= staff_capacity)

    # # (b) Client capacity = sum of (latest_ends[c] - earliest_starts[c])
    # total_client_capacity = 0
    # for c in range(num_clients):
    #     for a, _ in enumerate(latest_ends[c]):
    #         total_client_capacity += latest_ends[c][a] - earliest_starts[c][a]
    # model.Add(total_scheduled <= total_client_capacity)

    # ---------------------------------------------------------
    # 8) Solve
    # ---------------------------------------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = True

    print("\nSolving...\n")
    status = solver.Solve(model)
    print(f"Status: {solver.StatusName(status)}")

    all_appointments = {}
    lunch_appointments = {}

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"Total scheduled minutes = {solver.Value(total_scheduled)}\n")

        # Print staff lunches
        if include_lunch:
            print("Staff Lunch Intervals (12:00–13:30 only):")
            for s in range(num_staff):
                lunch_start_var, lunch_end_var, lunch_iv = lunch_intervals[s]
                ls = solver.Value(lunch_start_var)
                le = solver.Value(lunch_end_var)
                lunch_appointments.setdefault(s, []).append({"start": ls, "end": le})
                print(f"  Staff {s}: lunch from {ls} to {le} (duration={le - ls})")
            print()

        print("Assigned Appointments:")
        num_of_appointments = 0
        for c in range(num_clients):
            id = get_property_from_c(c, "id")
            name = get_property_from_c(c, "name")
            for a, _ in enumerate(presence_per_client[c]):
                for i in range(max_appts):
                    if solver.Value(presence_per_client[c][a][i]) == 1:
                        num_of_appointments = num_of_appointments + 1
                        start_val = solver.Value(
                            intervals_per_client[c][a][i].StartExpr()
                        )
                        end_val = solver.Value(intervals_per_client[c][a][i].EndExpr())
                        all_appointments.setdefault(id, []).append(
                            {"start": start_val, "end": end_val, "name": name}
                        )
                        print(
                            f"  Client {name}, Avail {a}, Appt {i}: start={start_val}, end={end_val}, "
                            f"dur={end_val - start_val}"
                        )
        print("number of appointments: ", num_of_appointments)
        return {
            "therapy_appointments": all_appointments,
            "lunch_appointments": lunch_appointments,
        }
    else:
        print("No feasible solution found.")


# if __name__ == "__main__":
#     run_interval_scheduler_with_global_caps(
#         num_clients=30,
#         max_appts=5,
#         num_staff=25,
#         horizon=600//time_slot_def,
#         time_slot = time_slot_def,
#         min_appt_duration=120//time_slot_def,
#         max_appt_duration=240//time_slot_def,
#         include_lunch=True,
#         lunch_min = 240//time_slot_def,  # 12:00 => 240
#         lunch_max = 330//time_slot_def,  # 13:30 => 330,
#         lunch_duration = 30//time_slot_def,
#         seed=600,
#         client_list={},
#         id_name_dict={}
#     )
