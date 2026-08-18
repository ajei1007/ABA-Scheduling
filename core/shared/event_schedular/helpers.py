from ortools.sat.python import cp_model


class VarArraySolutionPrinter(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables, limit):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__solution_count = 0
        self.all_solutions = {}
        self.all_priorities = {}
        self.all_blocks = {}
        self.all_solutions_constraints = {}
        self.__solution_limit = limit

    def on_solution_callback(self):
        self.__solution_count += 1
        arr = []
        arr_names = []
        assignments = self.__variables[0]
        slot = self.__variables[1]
        constraints = self.__variables[2]
        priority = self.__variables[3]
        block = self.__variables[4]
        users = self.__variables[5]
        constraints_values = []
        for key, v in assignments.items():
            pass
            value = self.Value(v)
            if value == 1:
                # print('%s=%i' % (v, value), end=' ')
                # print('%i' % (key), end=' ')
                # print(users[key]['name'])
                arr_names.append(users[key]['name'])
                arr.append(key)

        tuple_arr = tuple(arr)
        slot_value = self.Value(slot)

        priority_value = self.Value(priority)
        block_value = self.Value(block)
        #print(f'{tuple_arr} {priority_value} {arr_names}')
        if self.__solution_count >= self.__solution_limit:
            print(f"Stop search after {self.__solution_limit} solutions")
            self.StopSearch()
        for c in constraints:
            value = self.Value(c)
            if (value) == 1:
                # print('soomy', str(c))
                constraints_values.append({"reason": str(c)})
        if (tuple_arr in self.all_solutions.keys()):
            self.all_solutions[tuple_arr].append(slot_value)
            if (slot_value
                    in self.all_solutions_constraints[tuple_arr].keys()):
                self.all_solutions_constraints[tuple_arr][
                    slot_value] = constraints_values
            else:
                self.all_solutions_constraints[tuple_arr][
                    slot_value] = constraints_values

        else:
            self.all_solutions[tuple_arr] = [slot_value]
            self.all_priorities[tuple_arr] = priority_value
            self.all_blocks[tuple_arr] = block_value
            self.all_solutions_constraints[tuple_arr] = {
                slot_value: constraints_values
            }
        print()

    def solution_count(self):
        return self.__solution_count

class VarArraySolutionPrinter2(cp_model.CpSolverSolutionCallback):
    """Print intermediate solutions."""

    def __init__(self, variables, events_poss, events_poss_raw, resources1,
                 is_investigate):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.__variables = variables
        self.__events_poss = events_poss
        self.__solution_count = 0
        self.all_solutions = []
        self.events_poss_raw = events_poss_raw
        self.resources1 = resources1
        self.is_investigate = is_investigate

    def on_solution_callback(self):
        self.__solution_count += 1
        for key, v in enumerate(self.__variables):
            value = self.Value(v[5])
            if value == 1:
                self.all_solutions.append(self.__events_poss[key])
                print(key,self.__events_poss[key])
            elif self.is_investigate:
                info = self.events_poss_raw[key]
                resource_list = info["resourceIds"]
                start_int = info['start']
                reasons = self.resources1.slots[tuple([start_int]) +
                                                tuple(resource_list)][7]
                self.all_solutions.append({
                    **self.__events_poss[key], 'reasons':
                    [*reasons, *self.__events_poss[key]['reasons']]
                })

    def solution_count(self):
        return self.__solution_count