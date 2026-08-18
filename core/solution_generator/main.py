import os
import re
import logging
from core.shared.event_schedular.main import EventScheduler
from core.shared.data_gatherer import Data_Gatherer
from solve import Solution_Generator
import time

# from utils.timing_utils import measure_time, visualize_timings

logging.basicConfig(level=logging.DEBUG)


class SolutionGenerator:
    def __init__(self, data):
        self.backend_url = os.getenv("BACKEND_URL")
        tenant_id = data.get("header", {}).get("X-Tenant-Id")
        if tenant_id == "beta":
            self.backend_url = "https://beta-api.abaschedules.com/api"
        else:
            self.backend_url = "https://production-api.abaschedules.com/api"

        # self.backend_url = "https://beta-api.abaschedules.com/api"

        self.timings = {}
        self.data = data
        self.formatted_data = self._format_data()
        start_time = time.time()
        self.data_gatherer = Data_Gatherer(self.formatted_data)
        self.timings["Data_Gatherer"] = time.time() - start_time
        self.solutions1 = None
        self.solutions2 = None
        self.start_format = "%Y-%m-%d"

    # @measure_time(return_time=False)
    def _format_data(self):
        """Format the input data for solution generation."""
        formatted_data = {
            "host": self.backend_url,
            "req_type": "solutionGenerator",
            "optimizer_sol": False,
            "isolatedResources": [],
        }
        formatted_data.update(self.data)

        return formatted_data

    # @measure_time
    def initialize_solutions(self):
        """Initialize Solution Generator objects."""
        self.data_gatherer.resourceCombinationsExclude = []
        # old solution generator
        # self.solutions2 = Solution_Generator(
        #     self.data_gatherer, {
        #         "is_orange": True,
        #         "ignoreConstraintArray": self.formatted_data.get("uncheckOrangeSolutionConstraints", []),
        #         'investigate': self.formatted_data.get('investigate', []),
        #         "soft": True
        #     }
        # )
        # new solution generator
        self.solutions2 = EventScheduler(
            self.data_gatherer,
            {
                "is_orange": True,
                "ignoreConstraintArray": self.formatted_data.get(
                    "uncheckOrangeSolutionConstraints", []
                ),
                "investigate": self.formatted_data.get("investigate", []),
                "soft": True,
            },
        )
        self.solutions1 = self.solutions2

    # @measure_time
    def generate_possible_and_unmatched_events(self):
        """Generate possible and unmatched events."""
        generate_event_timings = {}
        start_time = time.time()
        # new solution generator-main2 function
        unmatch_poss_events = self.solutions2.generate_scheduling_events()
        generate_event_timings["generate_scheduling_events"] = time.time() - start_time

        start_time = time.time()
        # new solution generator-main3 function
        unmatch_poss_events = self.solutions2.refine_scheduling_constraints()
        generate_event_timings["refine_scheduling_constraints"] = (
            time.time() - start_time
        )

        # Old solution generator code
        # unmatch_poss_events = self.solutions2.main2()
        # unmatch_poss_events.extend(self.solutions2.main3())
        # start_time = time.time()
        events_poss = []
        if self.formatted_data.get("settings", {}).get("driveTime", False):
            print("Drive time triggered")
            events_poss = self.solutions1.main_drive_time()
            new_events = self.solutions2.main_drive_time()
            
            existing_event_ids = {event["id"] for event in unmatch_poss_events}
            
            for new_event in new_events:
                if new_event["id"] in existing_event_ids:
                    for i, old_event in enumerate(unmatch_poss_events):
                        if old_event["id"] == new_event["id"]:
                            unmatch_poss_events[i] = new_event
                            break
                else:
                    # Add new event if not found
                    unmatch_poss_events.append(new_event)
            
        generate_event_timings["main_drive_time"] = time.time() - start_time
        generate_event_timings["total_time"] = sum(generate_event_timings.values())

        # if False and os.getenv("ENV") == "development":
        #     visualize_timings(
        #         generate_event_timings,
        #         title="generate_events",
        #         save_path="/var/task/benchmarking/generate_events.png",
        #     )

        return events_poss, unmatch_poss_events

    # @measure_time
    def assign_colors(self, events, color_type="orange"):
        """Assign color codes to events based on matching criteria."""
        colored_events = []
        for event in events:
            type = color_type
            if "ov" in event and event["ov"] == "t":
                type = "yellow"
            colored_events.append(
                {**event, "colorType": type, "backgroundColor_real": type}
            )
        return colored_events

    # @measure_time
    def categorize_events(self, unmatch_poss_events_new2):
        """Categorize events into matched and unmatched lists based on constraints."""
        section_timings = {}

        start_time = time.time()
        highPriority = [*self.data.get("highPriority", []), *self.data.get("soft", [])]
        # highPriority = self.data.get("soft", [])
        high_priority_str = "|".join(highPriority)
        future_events = self.data_gatherer.some_data.get_event_future(
            unmatch_poss_events_new2, high_priority_str
        )
        section_timings["fetch_future_events"] = time.time() - start_time

        new_match = []
        new_unmatch = []

        start_time = time.time()
        for event in unmatch_poss_events_new2:
            color = "orange"
            if len(future_events.get(event["id"], {}).get("constraints", [])) == 0:
                event.pop("reasons", None)
                color = "yellow" if "ov" in event else "white"
                new_match.append(
                    {**event, "backgroundColor_real": color, "colorType": color}
                )
            else:
                reasons = []
                for c in future_events[event["id"]]["constraints"]:
                    description = c.get("description", "")
                    color = "yellow" if "ov" in event else "orange"
                    if description not in reasons:
                        reasons.append(
                            {"reason": re.sub(r"</?strong>", "", description)}
                        )
                new_unmatch.append(
                    {
                        **event,
                        "orange_sol": True,
                        "constraint": future_events[event["id"]]["constraints"],
                        "reasons": reasons,
                    }
                )

        section_timings["iterate_events"] = time.time() - start_time
        section_timings["total_time"] = sum(section_timings.values())

        # if False and os.getenv("ENV") == "development":
        #     visualize_timings(
        #         section_timings,
        #         title="Solution Generator",
        #         save_path="/var/task/benchmarking/section_timings_chart.png",
        #     )
        return new_match, new_unmatch

    def organize_users_list(self, unmatch_poss_events):
        """Organize a sorted list of users from unmatched events."""
        users_list = []
        names = set()
        for event in unmatch_poss_events:
            for id in event["resourceIds_r"]:
                actual_id = self.solutions1.users[id]["id"]
                if id not in names:
                    users_list.append(
                        {"label": self.solutions1.users[id]["name"], "value": actual_id}
                    )
                    names.add(id)
        return sorted(users_list, key=lambda d: d["label"])

    def create_output(
        self,
        events_poss,
        new_match,
        new_unmatch,
        unmatch_poss_events,
        unmatch_poss_events_new2,
        calc_time,
    ):
        """Create output object based on processed events."""
        users_list_sorted = self.organize_users_list(unmatch_poss_events)

        all_slot = set()
        for event in unmatch_poss_events_new2:
            all_slot.update(range(event["start_r"], event["end_r"] + 1))

        all_slot_ranges = list(self.solutions1.detect_range(sorted(all_slot)))
        ev_dict = {slot_range: [] for slot_range in all_slot_ranges}
        for event in unmatch_poss_events_new2:
            for slot_range in all_slot_ranges:
                start, end = slot_range
                if event["start_r"] >= start and event["end_r"] <= end:
                    ev_dict[slot_range].append(event["id"])
                    break

        obj_return = {}
        for key, value in ev_dict.items():
            actual_length = len(value)
            obj_return[actual_length] = {
                "start": key[0],
                "end": key[1],
                "ids": value,
                "index": 0,
                "index_groups": [],
            }

        return {
            "intersections": [],
            "conflicts": self.solutions2.conflicted_constraints["conflicts"],
            "poss_events": new_match,
            "unmatch_poss_events": new_unmatch,
            "resources": users_list_sorted,
            "obj_return": obj_return,
            "num_of_obj": len(obj_return),
            "calc_time": calc_time,
        }

    def run(self):
        """Main method to run the solution generation process."""

        # self.timings["initialize_solutions"], _ = self.initialize_solutions()
        self.initialize_solutions()

        # self.timings["generate_events"], (events_poss, unmatch_poss_events) = (
        #     self.generate_possible_and_unmatched_events()
        # )
        events_poss, unmatch_poss_events = self.generate_possible_and_unmatched_events()

        # self.timings["assign_colors"], unmatch_poss_events_new2 = self.assign_colors(
        #     unmatch_poss_events
        # )
        unmatch_poss_events_new2 = self.assign_colors(unmatch_poss_events)

        # self.timings["categorize_events"], (new_match, new_unmatch) = (
        #     self.categorize_events(unmatch_poss_events_new2)
        # )
        new_match, new_unmatch = self.categorize_events(unmatch_poss_events_new2)

        if not self.formatted_data.get("settings", True).get("orange", True):
            new_unmatch = []

        result = self.create_output(
            events_poss,
            new_match,
            new_unmatch,
            unmatch_poss_events,
            unmatch_poss_events_new2,
            self.timings,
        )
        # self.timings["total_time"] = sum(self.timings.values())

        # print("Function Timings:", self.timings)
        # if False and os.getenv("ENV") == "development":
        #     visualize_timings(
        #         self.timings,
        #         title="Solution Generator",
        #         save_path="/var/task/benchmarking/solution_generator.png",
        #     )

        return result


def runSolutionGenerator(data):
    generator = SolutionGenerator(data)
    return generator.run()
