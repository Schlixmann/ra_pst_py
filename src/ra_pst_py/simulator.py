from src.ra_pst_py.instance import Instance

from collections import defaultdict
import numpy as np
from lxml import etree

class Simulator():
    def __init__(self) -> None:
        self.process_instances = [] # List of RA_PST instances
        self.task_queue = [] # List of tuples (i, task, release_time)
        self.allocation_type = None

    def initialize(self, process_instances:list[Instance], allocation_type) -> None:
        self.allocation_type = allocation_type
        self.process_instances = process_instances
        self.ns = process_instances[0].ns
        for i,instance in enumerate(process_instances):
            task = instance.current_task
            release_time = float(task.xpath("cpee1:release_time", namespaces = self.ns)[0].text)
            self.update_task_queue((instance, task, release_time))

    def simulate(self):
        while self.task_queue:
            next_task = self.task_queue.pop(0)
            print(next_task)
            instance, task, release_time = next_task

            if self.allocation_type == "heuristic":
                start_time, duration = instance.allocate_next_task()
                print("Times: \t ", instance.times)
                if instance.current_task != "end":
                    self.update_task_queue((instance, instance.current_task, start_time + duration))
            
                else:
                    print(f"Instance {instance} is finished")
            

    def update_task_queue(self, task:tuple) -> None:
        instance, task, release_time = task
        self.task_queue.append((instance, task, release_time))
        self.task_queue.sort(key=lambda tup: tup[2])
        