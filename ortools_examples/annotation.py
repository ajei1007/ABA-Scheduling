# Annotations about ortools-examples

# ! About bus_driver_scheduling_flow_sat.py
"""This model implements a bus driver scheduling problem.
Constraints:
- max driving time per driver <= 9h
- max working time per driver <= 12h
- min working time per driver >= 6.5h (soft)
- 30 min break after each 4h of driving time per driver
- 10 min preparation time before the first shift
- 15 min cleaning time after the last shift
- 2 min waiting time after each shift for passenger boarding and alighting
"""

libraries = {
    'argparse':
    """The argparse module makes it easy to write user-friendly command-line interfaces. The program defines what arguments it requires, and argparse will figure out how to parse those out of sys.argv. The argparse module also automatically generates help and usage messages. The module will also issue errors when users give the program invalid arguments.""",
}