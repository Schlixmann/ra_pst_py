
from src.ra_pst_py.heuristic import find_best_resource

from collections import defaultdict
import numpy as np
from lxml import etree

class Simulator():
    def __init__(self) -> None:
        self.process_instances = [] # List of RA_PST instances
        self.task_queue = [] # List of tuples (i, task, release_time)
        self.schedule = Schedule
        self.allocation_type = None

    def initialize(self, process_instances:list, allocation_type) -> None:
        self.allocation_type = allocation_type
        self.process_instances = process_instances
        self.ns = process_instances[0].ns
        for i,instance in enumerate(process_instances):
            task = instance.get_tasklist()[0]
            release_time = float(task.xpath("cpee1:release_time", namespaces = self.ns)[0].text)
            self.update_task_queue((i, task, release_time))

    def simulate(self):
        while self.task_queue:
            next_task = self.task_queue.pop(0)
            print(next_task)
            i, task, release_time = next_task

            if self.allocation_type == "heuristic":
                resource, start_time, duration = find_best_resource(task, self.ns, self.schedule)
                next_task = (i, task, start_time)
                self.schedule.add_task(next_task, resource, duration)
            
            # get following task from instance
            instance = self.process_instances[i]
            tasklist = instance.get_tasklist()
            following_task_idx = tasklist.index(task) + 1
            if following_task_idx < len(tasklist):
                following_task = tasklist[following_task_idx]
                child = etree.SubElement(following_task, f"{{{self.ns["cpee1"]}}}release_time")
                child.text = str(start_time + duration)
            # Depending on allocation logic either next task or full instance should be scheduled
                self.update_task_queue((i, following_task, start_time + duration))
            else:
                print(f"Instance {i} is finished")

    def update_task_queue(self, task:tuple) -> None:
        i, task, release_time = task
        self.task_queue.append((i, task, release_time))
        self.task_queue.sort(key=lambda tup: tup[2])

class Schedule():
    def __init__(self) -> None:
        self.schedule = defaultdict(list)

    def add_task(self, task:tuple, resource, duration) -> None:
        i, task, start_time = task
        ns = {"cpee1": list(task.nsmap.values())[0]}
        #duration = task.xpath("cpee1:measures/cpee1:cost", namespaces = ns)[0].text
        #resource  = task.xpath("cpee1:resources", namespaces = ns)[0].attrib["allocated_to"]
        self.schedule[resource].append({"task": task, "start_time": float(start_time), "duration": float(duration), "instance": i})
        self.schedule[resource].sort(key=lambda x: x["start_time"])

    def get_timeslot_matrix(self, release_time, resource) -> list:
        # Returns a matrix of free timeslots for a resource:
        # [[start_time, end_time], [start_time, end_time], ...]
        matrix = []
        for block in self.schedule[resource]:
            if block["start_time"] + block["duration"] >= release_time:
                matrix.append([block["start_time"], block["start_time"] + block["duration"]])
        matrix.append([np.inf, 0])
        if matrix:
            return np.roll(np.array(matrix), 1) 
        else:
            return np.array([[release_time, np.inf]])
        