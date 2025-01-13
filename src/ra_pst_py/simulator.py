from src.ra_pst_py.instance import Instance
from src.ra_pst_py.cp_docplex import cp_solver

from collections import defaultdict
import numpy as np
from lxml import etree
import json

class Simulator():
    def __init__(self) -> None:
        self.process_instances = [] # List of [{instance:RA_PST_instance, allocation_type:str(allocation_type)}]
        self.task_queue = [] # List of tuples (i, task, release_time)
        self.allocation_type = None

    def initialize(self, process_instances:list[Instance], allocation_type) -> None:
        """
        Initializes the Simulator adds instances and adds the first task to the allocation queue
        TODO: different allocation types for different instances.
        """
        #self.allocation_type = allocation_type
        for instance in process_instances:
            self.process_instances.append({"instance":instance[0], "allocation_type":instance[1]})
        self.ns = process_instances[0][0].ns

        for i,allocation_instance in enumerate(self.process_instances):
            instance = allocation_instance["instance"]
            task = instance.current_task
            release_time = float(task.xpath("cpee1:release_time", namespaces = self.ns)[0].text)
            self.update_task_queue((instance, allocation_instance["allocation_type"], task, release_time))
        
    def add_instance(self): # TODO
        """ 
        Should add a new instance to self.process_instances after sumalation has started.
        New instance will be added in queue
        """
        raise NotImplementedError("Method not implemented")

    def simulate(self):
        """
        TODO: refactor so that different allocation types are possible
        within one Simulator. e.g. Heuristic + single instance cp
        """
        self.allocation_type = self.check_homogeneous_allocation_types()
        if self.allocation_type == "heuristic":
            while self.task_queue:
                next_task = self.task_queue.pop(0)
                print(next_task)
                instance, instance_allocation_type, task, release_time = next_task

                if instance_allocation_type == "heuristic":
                    start_time, duration = instance.allocate_next_task()
                    print("Times: \t ", instance.times)
                    if instance.current_task != "end":
                        self.update_task_queue((instance, instance_allocation_type, instance.current_task, start_time + duration))
                
                    else:
                        print(f"Instance {instance} is finished")
                
                elif self.allocation_type == "cp_single_instance":
                    # TODO use CP for each instance seperately
                    pass
                elif self.allocation_type == "cp_all_instances":
                    # TODO use CP for all instances at once
                    pass
                else:
                    raise NotImplementedError(f"Allocation_type {instance_allocation_type} has not been implemented yet")
        
        elif self.allocation_type == "cp_all":
            ra_psts = {}
            ra_psts["instances"] = []
            for i, allocation_object in enumerate(self.process_instances):
                instance_to_allocate = allocation_object["instance"] 
                ilp_rep = instance_to_allocate.ra_pst.get_ilp_rep(instance_id=f'i{i+1}')
                ra_psts["instances"].append(ilp_rep)
            ra_psts["resources"] = ilp_rep["resources"]      
            with open("out/cp_rep_multiinstance_input.json", "w") as f:
                json.dump(ra_psts, f, indent=2)     
            result = cp_solver("out/cp_rep_multiinstance_input.json")
            #with open("out/cp_rep_multiinstance.json", "w") as f:
            #    json.dump(result, f, indent=2)
            
            print(result["objective"])
            #TODO combine with Schedule class
            #raise NotImplemented(f"Allocation_type {self.allocation_type} has not been implemented yet")
        else:
            #TODO implement batched allocation with cp
            # for now raise Error
            raise NotImplemented(f"Allocation_type {self.allocation_type} has not been implemented yet")


    def update_task_queue(self, task:tuple) -> None:
        instance, allocation_type, task, release_time = task
        self.task_queue.append((instance, allocation_type, task, release_time))
        self.task_queue.sort(key=lambda tup: tup[3])
    
    def check_homogeneous_allocation_types(self) -> str:
        """
        Check that all instances are either instance wise allocation or
        Full Batch allocation. 
        returns:
            str(allocation_type)
        """
        allocation_types = set()
        for allocation_object in self.process_instances:
            allocation_types.add(allocation_object["allocation_type"])
        if len(allocation_types) == 1:
            return list(allocation_types)[0]
        elif len(allocation_types) > 1:
            raise ValueError(f"More than one allocation_type among the instances to allocate. Types: {allocation_types}")
        else:
            raise ValueError("No allocation type found? Maybe wrong data shape?")
        
        