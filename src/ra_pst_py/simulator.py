from src.ra_pst_py.instance import Instance
from src.ra_pst_py.core import Branch, RA_PST
from src.ra_pst_py.cp_docplex import cp_solver

from collections import defaultdict
import numpy as np
from lxml import etree
import json
import os
import time
import itertools

class Simulator():
    def __init__(self) -> None:
        self.process_instances = [] # List of [{instance:RA_PST_instance, allocation_type:str(allocation_type)}]
        self.task_queue = [] # List of tuples (i, task, release_time)
        self.allocation_type = None
        self.schedule_filepath = None

    def initialize(self, process_instances:list[Instance], schedule_filepath:str="out/sim_schedule.json") -> None:
        """
        Initializes the Simulator adds instances and adds the first task to the allocation queue
        TODO: different allocation types for different instances.
        """
        #self.allocation_type = allocation_type
        for i, instance in enumerate(process_instances):
            self.process_instances.append({"instance_id":i, "instance":instance[0], "allocation_type":instance[1]})
        self.ns = process_instances[0][0].ns

        for i,allocation_instance in enumerate(self.process_instances):
            instance = allocation_instance["instance"]
            task = instance.current_task
            release_time = float(task.xpath("cpee1:release_time", namespaces = self.ns)[0].text)
            self.update_task_queue((instance, allocation_instance["allocation_type"], task, release_time))
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(schedule_filepath), exist_ok=True)
        with open(schedule_filepath, "w") as f:
            self.schedule_filepath = schedule_filepath
        
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
        self.allocation_type = self.get_allocation_types()
        if self.allocation_type in ["heuristic", "cp_single_instance"]:
            print("Start single instance/task allocation")
            objective = 0
            instance_mapper = {}
            start = time.time()
            while self.task_queue:
                next_task = self.task_queue.pop(0)
                instance, instance_allocation_type, task, release_time = next_task
                instance_no = [element["instance_id"] for element in self.process_instances if element["instance"] == instance][0]

                if instance_allocation_type == "heuristic":
                    best_branch = instance.allocate_next_task()
                    instance_dict = self.format_branch_to_job_dict(best_branch, next_task, instance)
                    instance_dict = self.generate_dict_from_ra_pst(best_branch, instance, next_task)
                    with open(self.schedule_filepath, "r+") as f:
                        if os.path.getsize(self.schedule_filepath) > 0:
                            tmp_sched = json.load(f)
                        else: 
                            tmp_sched = {"instances": [], "resources":[], "objective":0}  # Default if file is empty

                        # Create global resources list
                        resources = set(tmp_sched["resources"])
                        resources.update(list(instance_dict["resources"]))

                        # Update schedule dict
                        tmp_sched["resources"] = list(resources)
                        if instance_no in instance_mapper.keys():
                            list_idx = instance_mapper[instance_no]
                            for job_id, job in instance_dict["jobs"].items():
                                tmp_sched["instances"][list_idx]["jobs"][job_id] = job
                        else:
                            if instance_mapper.values():
                                instance_mapper[instance_no] = max(instance_mapper.values()) + 1
                            else:
                                instance_mapper[instance_no] = 0
                            tmp_sched["instances"].append(instance_dict)
                        
                        if sum(instance.times[-1]) > tmp_sched["objective"]:
                            tmp_sched["objective"] = sum(instance.times[-1])

                        # Save back to file
                        f.seek(0)  # Reset file pointer to the beginning
                        json.dump(tmp_sched, f, indent=4)  
                        f.truncate()
                        
                    print("Times: \t ", instance.times)
                    if instance.current_task != "end":
                        self.update_task_queue((instance, instance_allocation_type, instance.current_task, sum(instance.times[-1])))
                    else:
                        if sum(instance.times[-1]) > objective:
                            objective = sum(instance.times[-1])
                        print(f"Instance {instance} is finished")

                
                elif self.allocation_type == "cp_single_instance":
                    # General file of all instances --> Could be in Scheduler
                    #all_singles_file_path = "out/all_single_cp.json"

                    # Create ra_psts for next instance in task_queue
                    instance_to_allocate = instance
                    ra_psts = {}
                    ra_psts["instances"] = []
                    # Find id of instance in self.process_instances
                    instance_id = [element["instance"] for element in self.process_instances].index(instance_to_allocate)
                    ilp_rep = instance_to_allocate.ra_pst.get_ilp_rep(instance_id=instance_id)

                    ra_psts["instances"].append(ilp_rep)
                    ra_psts["resources"] = ilp_rep["resources"]

                    if os.path.exists(self.schedule_filepath) and os.path.getsize(self.schedule_filepath) > 0:
                        with open(self.schedule_filepath, "r") as f:    # Load instances from file if exist
                            all_instances = json.load(f)
                            all_instances = self.add_ra_psts_to_all_instances(ra_psts, all_instances)
                    else:
                        all_instances = ra_psts # Get only instances from ra_psts

                    with open(self.schedule_filepath, "w") as f:
                        json.dump(all_instances, f, indent=2)
                        
                    # TODO add new Jobs to existing job file
                    result = cp_solver(self.schedule_filepath)
                    with open(self.schedule_filepath, "w") as f:
                        json.dump(result, f, indent=2)
                else:
                    raise NotImplementedError(f"Allocation_type {instance_allocation_type} has not been implemented yet")
            
            if instance_allocation_type == "heuristic":
                # Collect information on heuristic allocation: 
                end = time.time()
                with open(self.schedule_filepath, "r+") as f:
                    ra_psts = json.load(f)
                    intervals = []
                    for ra_pst in ra_psts["instances"]:
                        for jobId, job in ra_pst["jobs"].items():
                            if job["selected"]: 
                                intervals.append({
                                    "jobId":jobId,
                                    "start":job["start"],
                                    "duration":job["cost"]
                                })
                    total_interval_length = sum([element["duration"] for element in intervals])
                    ra_psts["solution"] = {
                        "objective": ra_psts["objective"],
                        "computing time": end-start,
                        "total interval length": total_interval_length
                    }
                    # Save back to file
                    f.seek(0)  # Reset file pointer to the beginning
                    json.dump(ra_psts, f, indent=4)  
                    f.truncate()

        elif self.allocation_type == "cp_all":
            ra_psts = {}
            ra_psts["instances"] = []
            for i, allocation_object in enumerate(self.process_instances):
                instance_to_allocate = allocation_object["instance"] 
                ilp_rep = instance_to_allocate.ra_pst.get_ilp_rep(instance_id=i)
                ra_psts["instances"].append(ilp_rep)
            ra_psts["resources"] = ilp_rep["resources"]      
            with open(self.schedule_filepath, "w") as f:
                json.dump(ra_psts, f, indent=2)     
            result = cp_solver(self.schedule_filepath)
            with open(self.schedule_filepath, "w") as f:
                json.dump(result, f, indent=2)            
            #TODO combine with Schedule class
            #raise NotImplemented(f"Allocation_type {self.allocation_type} has not been implemented yet")
        else:
            #TODO implement batched allocation with cp
            # for now raise Error
            raise NotImplementedError(f"Allocation_type {self.allocation_type} has not been implemented yet")


    def update_task_queue(self, task:tuple) -> None:
        instance, allocation_type, task, release_time = task
        self.task_queue.append((instance, allocation_type, task, release_time))
        self.task_queue.sort(key=lambda tup: tup[3])
    
    def get_allocation_types(self) -> str:
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
        
    def add_ra_psts_to_all_instances(self, ra_psts, all_instances):
        """
        Add ra_psts dict to the all_instances dict which is given to the scheduler
        """
        instance_set = set(all_instances["resources"])
        instance_set.update(ra_psts["resources"])
        all_instances["resources"] = list(instance_set)
        all_instances["instances"] += ra_psts["instances"]
        return all_instances

    def format_branch_to_job_dict(self, branch, task, instance):
        resources = set()
        jobs_dict = {}
        for task in branch.get_tasklist():
            cp_type = task.attrib["type"] if "type" in list(task.attrib.keys()) else None
            if cp_type == "delete":
                continue
            if task.xpath("cpee1:children/descendant::cpee1:changepattern", namespaces=self.ns):
                if task.xpath("cpee1:children/descendant::cpee1:changepattern", namespaces=self.ns)[0].attrib["type"] == "replace":
                    continue
            instance_id = 0
            task_id = task.attrib["id"]
            branch_id = list(itertools.chain(*instance.ra_pst.branches.values())).index(branch)
            job_id = f"{instance_id}-{instance_id}-{task_id}-{branch_id}-0"
            resource = task.xpath("cpee1:children/cpee1:resource", namespaces=self.ns)[0].attrib["id"]
            start_time = float(task.xpath("cpee1:expected_start", namespaces=self.ns)[0].text)
            end_time = float(task.xpath("cpee1:expected_end", namespaces=self.ns)[0].text)
            duration = float(end_time) - float(start_time)
            jobs_dict[job_id] = {
                "branch" : branch_id,
                "resource" : str(resource),
                "cost" : duration,
                "after" : [],
                "release_time": None,
                "start" : start_time,
                "selected" : True
            }
            resources.add(resource)
        
        instances_dict = {}
        instances_dict["resources"] = list(resources)
        instances_dict["jobs"] = jobs_dict
        return instances_dict
    
    def generate_dict_from_ra_pst(self, branch:Branch, instance:Instance, next_task):
        ilp_rep = instance.ra_pst.get_ilp_rep()
        instance_id = ilp_rep["instanceId"]
        task_id = branch.node.attrib["id"]
        branch_running_id = list(itertools.chain(*instance.ra_pst.branches.values())).index(branch)
        branch_ilp_id = f"{instance_id}-{task_id}-{branch_running_id}"

        branch_ilp_dict = ilp_rep["branches"][branch_ilp_id]
        branch_ilp_jobs = branch_ilp_dict["jobs"]
        branch_ra_pst_tasks = branch.get_serialized_tasklist()

        if len(branch_ilp_jobs) != len(branch_ra_pst_tasks):
            raise ValueError(f"Length of Jobs in ilp_rep <{len(branch_ilp_jobs)}> does not match length of jobs in ra_pst_branch <{len(branch_ra_pst_tasks)}>")

        for i, jobId in enumerate(branch_ilp_jobs):
            task = branch_ra_pst_tasks[i]
            start_time = float(task.xpath("cpee1:expected_start", namespaces=self.ns)[0].text)
            end_time = float(task.xpath("cpee1:expected_end", namespaces=self.ns)[0].text)
            duration = float(end_time) - float(start_time)
            
            ilp_rep["jobs"][jobId]["start"] = start_time
            ilp_rep["jobs"][jobId]["cost"] = duration
            ilp_rep["jobs"][jobId]["selected"]=True

        return ilp_rep


