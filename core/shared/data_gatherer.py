import datetime
import os
import time
from get_data import Get_Data
from concurrent.futures import ThreadPoolExecutor

# from utils.timing_utils import visualize_timings


class Data_Gatherer:
    def __init__(self, dict_data):
        self.dd_data = dict_data
        self.branch_id = dict_data.get("branch", "")
        self.start_date = dict_data.get("start_date", "")
        self.end_date = dict_data.get("end_date", "")
        self.sandboxMode = dict_data.get("sandboxMode", False)
        self.settings = dict_data.get("settings", {})
        self.isolatedResources = dict_data.get("isolatedResources", [])
        self.home_id = dict_data.get("home_id", "")
        self.expanded_resources = dict_data.get("expanded_resources", [])
        self.resourceCombinationsExclude = dict_data.get(
            "resourceCombinationsExclude", []
        )
        self.expanded_resources_filter = dict_data.get("expanded_resources_filter", [])
        self.onCall = dict_data.get("onCall", False)

        self.flags_data = {}
        self.distance_matrix = {}
        self.num_of_days = self._calculate_days()

        data_params = {
            "objectiveactivity": "",
            "lunch_id": "",
            "break_id": "",
            "num_of_days": self.num_of_days,
            "blocks": "",
            "is_lunch": "",
            "is_break": "",
            "is_orange": "",
            "is_events": "",
        }
        data_params.update(dict_data)

        self.some_data = Get_Data(data_params)
        self._fetch_all_data()

    def _calculate_days(self):
        if self.start_date and self.end_date:
            d1 = datetime.datetime.strptime(self.end_date, "%Y-%m-%d")
            d2 = datetime.datetime.strptime(self.start_date, "%Y-%m-%d")
            return (d1 - d2).days
        return 0

    def _fetch_all_data(self):
        """Fetch data concurrently using ThreadPoolExecutor."""
        method_names = [
            "get_availability",
            "get_capacities",
            "get_subgroups",
            "get_custom_constraints",
            "get_branch_structure",
            "get_event_pair",
            "get_events2",
            "get_branches",
            "get_location_raw_data",
            "get_activity_table",
        ]

        if self.dd_data.get("optimizer_sol", False):
            method_names.append("get_flags")

        timings = {}

        def timed_execution(method_name):
            """Execute a method and measure its execution time."""
            start_time = time.time()
            result = getattr(self.some_data, method_name)()
            elapsed_time = time.time() - start_time
            timings[method_name] = elapsed_time
            return result

        init_time = time.time()
        with ThreadPoolExecutor(max_workers=len(method_names)) as executor:
            results = list(executor.map(timed_execution, method_names))

        timings["total_time"] = time.time() - init_time
        print("execution time:", timings)
        # if True and os.getenv("ENV") == "development":
        #     visualize_timings(
        #         timings,
        #         title="Data Gathering Timings",
        #         save_path="benchmarking/fetch_all_data_timings.png",
        #     )

        self.availabilities = results[0]
        self.capacities = results[1]
        self.subgroups = results[2]
        self.custom_constraints = results[3]
        self.branch_structure = results[4]
        self.e_pair = results[5]
        self.branches = results[7]
        self.location_raw_data = results[8]
        self.activity_table = results[9]
        if not self.settings.get("isOnboarding", False):
            self.users = [u for u in results[6][0] if not u.get("waitlisted", False)]
        else:
            self.users = results[6][0]


        if "get_flags" in method_names:
            self.flags_data = results[10]

        ev = results[6][1] if results[6] and isinstance(results[6], list) else []
        self.events2 = [event for sublist in ev for event in sublist] if ev else []
        print("self.events25", self.events2)

        self.events = []
        if self.dd_data.get("is_events", True):
            for sublist in ev:
                for event in sublist:
                    if "part1" not in self.dd_data or self.dd_data["part1"]:
                        self.events.append(event)

    def get_data_summary(self):
        """Method for debugging or testing, which summarizes fetched data."""
        return {
            "availabilities": self.availabilities,
            "capacities": self.capacities,
            "subgroups": self.subgroups,
            "custom_constraints": self.custom_constraints,
            "branch_structure": self.branch_structure,
            "e_pair": self.e_pair,
            "events": len(self.events),
            "location_raw_data": self.location_raw_data,
            "activity_table": self.activity_table,
        }
