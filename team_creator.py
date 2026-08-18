from ortools.sat.python import cp_model
from collections import defaultdict
import math


def run_team_creator(
    events_poss=[], users={}, num_of_teams=4, usersPerTeam=15, part1=True
):
    """
    Assign each resource to exactly one of `num_of_teams` teams so as to
    maximize:
      (1) The number of (resource, time-slot) assignments that occur in an
          event whose resources are all in the same team (controlled by all_bols).
      (2) Keep the per-slot differences (clients - employees) small (minimize sum of squares).
      (3) Keep each team's *total* (clients - employees) close to the average
          across all teams (i.e. minimize the variance across teams).
    """

    # -----------------------------
    # 1) PREPARE DATA
    # -----------------------------
    # Collect all candidate resources
    all_resource_indices = set()
    mapped_events = []
    for e_idx, ev in enumerate(events_poss):
        filtered_users = []
        for r in ev["resourceIds_r"]:
            roles = users[r]["roles"]
            # Only consider certain roles in the team logic
            if "Client" in roles or "Employee" in roles:
                filtered_users.append(r)
                all_resource_indices.add(r)
        if filtered_users:
            mapped_events.append(
                {
                    "start_r": ev["start_r"],
                    "end_r": ev["end_r"],
                    "resources": filtered_users,
                }
            )
    all_resource_indices = sorted(list(all_resource_indices))
    if not part1:
        final_teams_ids = [users[r]["id"] for r in all_resource_indices]
        return {"team_ids": [final_teams_ids]}

    model = cp_model.CpModel()

    num_of_teams = math.ceil(len(all_resource_indices) / usersPerTeam)
    print("actual number of teams", num_of_teams)
    # -----------------------------
    # 2) TEAM ASSIGNMENT VARIABLES
    # -----------------------------
    # For each resource r, we assign it to an integer team in [0..num_of_teams-1].
    team_vars = {}
    for i, r in enumerate(all_resource_indices):
        team_vars[r] = model.NewIntVar(0, num_of_teams - 1, f"team_r{r}")
        if i == 0:
            model.Add(team_vars[r] == 0)

    # -----------------------------
    # 3) TEAM SIZE CONSTRAINTS
    # -----------------------------
    total_resources = len(all_resource_indices)
    desired_team_size = total_resources // num_of_teams
    remainder = total_resources % num_of_teams

    # Each team gets either desired_team_size or desired_team_size+1
    team_size_bounds = [
        desired_team_size + 1 if i < remainder else desired_team_size
        for i in range(num_of_teams)
    ]

    # For each team, sum the booleans "is resource r in team i?" to match the team_size_bounds
    all_resource_teams = {}
    for r in all_resource_indices:
        all_resource_teams[r] = [None] * num_of_teams

    for team in range(num_of_teams):
        is_in_team = []
        for r in all_resource_indices:
            is_in_team_r = model.NewBoolVar(f"is_r{r}_in_team{team}")
            model.Add(team_vars[r] == team).OnlyEnforceIf(is_in_team_r)
            model.Add(team_vars[r] != team).OnlyEnforceIf(is_in_team_r.Not())
            is_in_team.append(is_in_team_r)
            # Store
            all_resource_teams[r][team] = is_in_team_r

        # We allow a slight tolerance of +/-4 in the code below, but typically
        # you'd do "model.Add(sum(is_in_team) == team_size_bounds[team])".
        team_count = model.NewIntVar(
            team_size_bounds[team] - 4, team_size_bounds[team] + 4, f"team{team}_count"
        )
        model.Add(team_count == sum(is_in_team))

    # -----------------------------
    # 4) EVENT "ALL RESOURCES SAME TEAM" VARIABLES
    # -----------------------------
    # For each event, define a bool "is_event_same_team" that is 1 iff
    # all resources in that event share the same team.
    resource_bools = {r: {} for r in all_resource_indices}

    for e_idx, ev in enumerate(mapped_events):
        event_resources = ev["resources"]
        start_t = ev["start_r"]
        end_t = ev["end_r"]

        is_event_same_team = model.NewBoolVar(f"is_event_{e_idx}_same_team")
        min_team = model.NewIntVar(0, num_of_teams - 1, f"minTeam_e{e_idx}")
        max_team = model.NewIntVar(0, num_of_teams - 1, f"maxTeam_e{e_idx}")

        # min_team == min of team_vars for event resources
        model.AddMinEquality(min_team, [team_vars[r] for r in event_resources])
        # max_team == max of team_vars for event resources
        model.AddMaxEquality(max_team, [team_vars[r] for r in event_resources])

        # If all in same team => min_team == max_team
        model.Add(min_team == max_team).OnlyEnforceIf(is_event_same_team)
        model.Add(min_team != max_team).OnlyEnforceIf(is_event_same_team.Not())

        # For each time slot in [start_t, end_t), define booleans that mirror is_event_same_team
        for i in range(start_t, end_t):
            for r in event_resources:
                bol = model.NewBoolVar(f"r{r}_t{i}_e{e_idx}")
                model.Add(bol == 1).OnlyEnforceIf(is_event_same_team)
                model.Add(bol == 0).OnlyEnforceIf(is_event_same_team.Not())

                # Collect in resource_bools for (r, i)
                if i not in resource_bools[r]:
                    resource_bools[r][i] = []
                resource_bools[r][i].append(bol)

    # -----------------------------
    # 5) OBJECTIVE PREP: MAXIMIZE (resource-time coverage)
    #    + Calculate client/employee difference arrays
    # -----------------------------
    # a) We create a new IntVar "max_int" for each (resource, time)
    #    to track if *any* event covering that (r, i) was same-team => 1
    #    Then we'll sum these to measure coverage.
    client_team_array = defaultdict(lambda: defaultdict(list))
    employee_team_array = defaultdict(lambda: defaultdict(list))

    all_max_ints = []
    for r, time_dict in resource_bools.items():
        for i, bool_list in time_dict.items():
            max_int = model.NewIntVar(0, 1, f"max_r{r}_t{i}")
            model.AddMaxEquality(max_int, bool_list)
            all_max_ints.append(max_int)

            # Now track team membership in client_team_array or employee_team_array
            for team in range(num_of_teams):
                team_bol = all_resource_teams[r][team]
                if "Client" in users[r]["roles"]:
                    # Team "team" has a client at time i if team_bol=1
                    client_team_array[team][i].append(team_bol)
                elif "Employee" in users[r]["roles"]:
                    # Team "team" has an employee at time i if team_bol=1
                    employee_team_array[team][i].append(team_bol)

    # -----------------------------
    # 6) CREATE PER-SLOT DIFFERENCES + SQUARES + SIGN BOOLS
    # -----------------------------
    myDifferenceIntSquared_all = []
    all_bols = []

    # We'll also store these difference Vars to sum them up to get each team's total difference.
    difference_vars_by_team = [[] for _ in range(num_of_teams)]

    for team in range(num_of_teams):
        for i, val in client_team_array[team].items():
            if len(val) > 0:
                myDifferenceInt = model.NewIntVar(
                    -1000000, 1000000, f"diff_t{team}_i{i}"
                )
                # myDifferenceIntSquared = model.NewIntVar(
                #     0, 10**12, f"diffSq_t{team}_i{i}"
                # )
                # myDifferenceIntSquared_all.append(myDifferenceIntSquared)

                myClientInt = model.NewIntVar(0, 1000000, f"clientSum_t{team}_i{i}")
                myEmployeeInt = model.NewIntVar(0, 1000000, f"employeeSum_t{team}_i{i}")

                # Sum of clients (list of BoolVars) => an integer
                model.Add(myClientInt == sum(val))

                # If there's a parallel employee array for (team, i)
                if (
                    i in employee_team_array[team]
                    and len(employee_team_array[team][i]) > 0
                ):
                    model.Add(myEmployeeInt == sum(employee_team_array[team][i]))
                else:
                    model.Add(myEmployeeInt == 0)

                # difference
                model.Add(myDifferenceInt == myClientInt - myEmployeeInt)

                # A bool to indicate sign (<= 0 or > 0)
                myBol = model.NewBoolVar(f"diffPositive_t{team}_i{i}")
                # If difference <= 0 => enforce myBol
                model.Add(myDifferenceInt <= 0).OnlyEnforceIf(myBol)
                # If difference > 0 => enforce myBol.Not()
                model.Add(myDifferenceInt > 0).OnlyEnforceIf(myBol.Not())
                all_bols.append(myBol)

                # Square the difference
                # model.AddMultiplicationEquality(
                #     myDifferenceIntSquared, [myDifferenceInt, myDifferenceInt]
                # )

                # Keep track for team-level total difference
                difference_vars_by_team[team].append(myDifferenceInt)

    # -----------------------------
    # 7) TEAM-LEVEL SD:
    #    Sum each team's differences across all time i,
    #    then penalize deviation from mean.
    # -----------------------------
    team_total_diff_vars = []
    for team in range(num_of_teams):
        tdiff = model.NewIntVar(-(10**7), 10**7, f"teamTotalDiff_{team}")
        model.Add(tdiff == sum(difference_vars_by_team[team]))
        team_total_diff_vars.append(tdiff)

    # Sum of all teams' total differences
    sum_team_diffs = model.NewIntVar(-(10**7), 10**7, "sum_team_diffs")
    model.Add(sum_team_diffs == sum(team_total_diff_vars))

    # Deviations from mean (scaled by num_of_teams)
    dev_sq_vars = []
    T = num_of_teams

    for team in range(num_of_teams):
        # dev = T * team_total_diff - sum_team_diffs
        dev_var = model.NewIntVar(-(10**8), 10**8, f"dev_{team}")
        model.Add(dev_var == T * team_total_diff_vars[team] - sum_team_diffs)

        dev_sq = model.NewIntVar(0, 10**16, f"devSq_{team}")
        model.AddMultiplicationEquality(dev_sq, [dev_var, dev_var])
        dev_sq_vars.append(dev_sq)

    # -----------------------------
    # 8) OBJECTIVE
    # -----------------------------
    # We combine:
    # - sum(all_bols) => we want to maximize
    # - sum(myDifferenceIntSquared_all) => we want to minimize
    # - sum(dev_sq_vars) => we want to minimize
    # Because the solver only supports a single objective, we do:
    #    Maximize( W1*sum(all_bols) - W2*sum(slot_diff_sq) - W3*sum(team_deviation_sq) )
    # Tweak weights as you prefer.
    weight_bols = 10000
    weight_slot_diff_sq = 1
    weight_team_sd = 1

    model.Maximize(
        weight_bols * sum(all_bols)
        # - weight_slot_diff_sq * sum(myDifferenceIntSquared_all)
        - weight_team_sd * sum(dev_sq_vars)
    )

    # -----------------------------
    # 9) SOLVE
    # -----------------------------
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20.0
    solver.parameters.log_search_progress = True
    status = solver.Solve(model)

    # -----------------------------
    # 10) EXTRACT RESULTS
    # -----------------------------
    final_teams = [[] for _ in range(num_of_teams)]
    final_teams_names = [[] for _ in range(num_of_teams)]
    final_teams_ids = [[] for _ in range(num_of_teams)]
    objective_value = 0

    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        objective_value = solver.ObjectiveValue()
        for r in all_resource_indices:
            t = solver.Value(team_vars[r])
            final_teams[t].append(r)
            final_teams_names[t].append(users[r]["name"])
            final_teams_ids[t].append(users[r]["id"])

        print("Objective Value:", objective_value)
        print("Teams distribution:", final_teams_names)

        # Optional: Print the team total difference + dev for debugging
        for team in range(num_of_teams):
            tdiff_val = solver.Value(team_total_diff_vars[team])
            print(f"Team {team} total difference: {tdiff_val}")

    else:
        print("No feasible solution found. Status =", status)

    return {
        "teams": final_teams,
        "team_names": final_teams_names,
        "team_ids": final_teams_ids,
        "objective_value": objective_value,
    }
