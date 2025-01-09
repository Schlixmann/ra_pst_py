import numpy as np
from lxml import etree
from collections import defaultdict

class Schedule():
    def __init__(self) -> None:
        self.schedule = defaultdict(list)

    def add_task(self, task:tuple, resource, duration, branch) -> None:
        instance, task, start_time = task
        ns = {"cpee1": list(task.nsmap.values())[0]}
        #duration = task.xpath("cpee1:measures/cpee1:cost", namespaces = ns)[0].text
        #resource  = task.xpath("cpee1:resources", namespaces = ns)[0].attrib["allocated_to"]
        self.schedule[resource].append({"task": task, "start_time": float(start_time), "duration": float(duration), "instance": instance, "branch": branch})
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
    
    def schedule_as_dict(self):
        """
        present schedule in format: 

        { 
        "instance_no":{
            objective: value, 
            "jobs": [
            {
                "task_id": task_id,
                "task": task,
                "resource": ["resource_id"],
                "cost" : duration, 
                "selected" : 1, 
                "start": start_time,
                "duration": duration}]}}
        """
        schedule_dict = {}
        instances = set()
        for resource, tasks in self.schedule.items():
            instances.update([task["instance"] for task in tasks])
        for resource, tasks in self.schedule.items():
            for task in tasks:
                instance_no = list(instances).index(task["instance"])
                if instance_no not in schedule_dict:
                    schedule_dict[instance_no] = {"objective": 0, "jobs": []}
                schedule_dict[instance_no]["jobs"].append({
                    "task": task["task"].attrib["id"],
                    "resource": [resource],
                    "cost": task["duration"],
                    "selected": 1,
                    "start": task["start_time"],
                    "duration": task["duration"],
                    "branch": task["branch"]
                })
        return schedule_dict

    def print_to_cli(self):       
        # Print the formatted schedule
        for resource, tasks in self.schedule.items():
            items = []
            for task in tasks:
                items.append((task["start_time"], task["task"].attrib["id"], task["start_time"] + task["duration"]))
            print(f"{resource} | {''.join(str(items))}")

import matplotlib.pyplot as plt
import matplotlib.cm as cm
def print_schedule(schedule):
    resources = sorted(set(schedule.keys()))
    resource_to_y = {resource: i for i, resource in enumerate(resources)}

    colormap = cm.get_cmap("tab10", len(schedule.values()))

    plt.figure(figsize=(10, 6))
    for resource, tasks in schedule.items():
        y = resource_to_y[resource]
        for task in tasks:
            plt.barh(y, task["duration"], left=task["start_time"], edgecolor="black")
            plt.text(task["start_time"] + task["duration"] / 2, y, "a", 
                    ha="center", va="center", color="white", fontsize=10)

    plt.yticks(range(len(resources)), resources)
    plt.xlabel("Time")
    plt.ylabel("Resources")
    plt.title("Job Scheduling Visualization")
    plt.grid(axis="x", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.show()