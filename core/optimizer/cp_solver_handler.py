import json
import base64
import traceback
from ortools.sat.python import cp_model
from core.shared.utils import serialize_instance, deserialize_instance


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0

    def OnSolutionCallback(self):
        self.__solution_count += 1
        for v in self.__variables:
            print("%s = %i" % (v, self.Value(v)), end=" ")
        print()

    def solution_count(self):
        return self.__solution_count


def extract_all_solver_values(solver, model):
    variable_values = {}
    print("available variables:", model.variables)
    for var in model.variables:
        var_name = var.name
        var_value = solver.Value(var)
        variable_values[var_name] = var_value
    return variable_values


def cp_solver_lambda_handler(event, context):
    try:
        encoded_model = event["model"]
        print("encoded model:", encoded_model)
        decoded_model = deserialize_instance(encoded_model)
        print("raw model:", decoded_model)
        print("max_time_parameter:", event["parameters"]["max_time_in_seconds"])

        solver = cp_model.CpSolver()
        # solver.parameters.search_branching = cp_model.FIXED_SEARCH
        solver.parameters.max_time_in_seconds = event["parameters"][
            "max_time_in_seconds"
        ]
        solver.parameters.log_search_progress = True
        solver.parameters.num_search_workers = event["parameters"]["num_search_workers"]
        solver.log_callback = print
        solver.parameters.random_seed = 42
        solution_printer = VarArraySolutionPrinter([])
        printer = solution_printer
        print("Starting solver...", flush=True)
        status = solver.Solve(decoded_model, solution_printer)
        print(f"Solver finished with status: {solver.StatusName(status)}", flush=True)
        print("solver structure:", solver)

        variable_values = extract_all_solver_values(solver, decoded_model)
        print("extracted variable value:", variable_values)

        encoded_printer = serialize_instance(printer)
        print("seriaclized printer:", encoded_printer)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "variable_values": variable_values,
                    "printer": encoded_printer,
                    "status": status,
                    "status_name": solver.StatusName(status),
                    "best_objective_bound": solver.BestObjectiveBound(),
                }
            ),
        }
    except Exception as e:
        print("An error occurred:", str(e))
        print(traceback.format_exc())
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
