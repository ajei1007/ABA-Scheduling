from ortools.sat.python import cp_model


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0

    def on_solution_callback(self):
        self.__solution_count += 1
        for v in self.__variables:
            print(f"{v}={self.Value(v)}", end=" ")
        print()

    def solution_count(self):
        return self.__solution_count


def earliness_tardiness_cost_sample_sat():
    """Encode the piecewise linear expression."""

    earliness_date = 5  # ed.
    earliness_cost = 8
    lateness_date = 15  # ld.
    lateness_cost = 12

    # Model.
    model = cp_model.CpModel()

    # Declare our primary variable.
    x = model.NewIntVar(0, 2000, "x")

    
    # Search for x values in increasing order.
    model.AddDecisionStrategy([x], cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE)

    # Create a solver and solve with a fixed search.
    solver = cp_model.CpSolver()

    # Force the solver to follow the decision strategy exactly.
    solver.parameters.search_branching = cp_model.FIXED_SEARCH
    # Enumerate all solutions.
    solver.parameters.enumerate_all_solutions = True

    # Search and print out all solutions.
    solution_printer = VarArraySolutionPrinter([x])
    solver.Solve(model, solution_printer)


earliness_tardiness_cost_sample_sat()

