from src.ra_pst_py.instance import Instance
from src.ra_pst_py.core import Branch, RA_PST
from src.ra_pst_py.cp_docplex import cp_solver, cp_solver_decomposed, cp_solver_alternative_new, cp_solver_scheduling_only
from src.ra_pst_py.cp_docplex_decomposed import cp_solver_decomposed_strengthened_cuts, cp_subproblem
from src.ra_pst_py.ilp import configuration_ilp

from enum import Enum, StrEnum
from collections import defaultdict
import numpy as np
from lxml import etree
import json
import os
import time
import itertools


class AllocationTypeEnum(StrEnum):
    HEURISTIC = "heuristic"
    SINGLE_INSTANCE_HEURISTIC = "single_instance_heuristic"
    SINGLE_INSTANCE_CP = "single_instance_cp"
    SINGLE_INSTANCE_CP_DECOMPOSED = "single_instance_cp_decomposed"
    ALL_INSTANCE_CP = "all_instance_cp"
    ALL_INSTANCE_CP_DECOMPOSED = "all_instance_cp_decomposed"
    SINGLE_INSTANCE_CP_REPLAN = "single_instance_replan"
    SINGLE_INSTANCE_ILP = "single_instance_ilp"
    ALL_INSTANCE_ILP = "all_instance_ilp"


class QueueObject():
    def __init__(self, instance: Instance, schedule_idx:int,  allocation_type: AllocationTypeEnum, task: etree._Element, release_time: float):
        self.instance = instance
        self.schedule_idx: int = schedule_idx
        self.allocation_type = allocation_type
        self.task = task
        self.release_time = release_time

class Simulator():
    def __init__(self, schedule_filepath:str, sigma:int, time_limit:int) -> None:
        self.schedule_filepath = schedule_filepath
        # List of [{instance:RA_PST_instance, allocation_type:str(allocation_type)}]
        self.task_queue: list[QueueObject] = []  # List of QueueObject
        self.expected_instances_queue: list[QueueObject] = [] # List of Queu objects only for online allocation.
        self.allocation_type: AllocationTypeEnum = None
        self.ns = None
        self.is_warmstart:bool = None
        self.sigma = sigma
        self.time_limit = time_limit

    def add_instance(self, instance: Instance, allocation_type: AllocationTypeEnum, expected_instance:bool=False):  # TODO
        """ 
        Adds a new instance that needs allocation
        """
        if self.allocation_type is None:
            if isinstance(allocation_type, AllocationTypeEnum):
                self.allocation_type = allocation_type
            elif isinstance(allocation_type, str):
                self.allocation_type = AllocationTypeEnum(allocation_type)
            else:
                raise ValueError("Invalid allocation type")
        
        if self.is_warmstart: 
            schedule_idx = instance.id
        else:
            if expected_instance:
                schedule_idx = len(self.expected_instances_queue)
            else:    
                schedule_idx = len(self.task_queue)
        if expected_instance is False:
            self.update_task_queue(self.task_queue, QueueObject(
                instance, schedule_idx, allocation_type, instance.current_task, instance.release_time))
        else:
            self.update_task_queue(self.expected_instances_queue, QueueObject(
                instance, schedule_idx, allocation_type, instance.current_task, instance.release_time))


    def set_namespace(self):
        """ Sets the namespaces if it is not set yet """
        if not self.ns:
            self.ns = self.task_queue[0].instance.ns
    
    def set_schedule_file(self):
        # Check/create schedule file:
        if not self.is_warmstart:
            os.makedirs(os.path.dirname(self.schedule_filepath), exist_ok=True)
            with open(self.schedule_filepath, "w"): pass

    def simulate(self):
        """
        within one Simulator. e.g. Heuristic + single instance cp
        """
        # Prelims
        self.set_namespace()
        self.set_schedule_file()

        if self.allocation_type == AllocationTypeEnum.HEURISTIC:
            #Start taskwise allocation with process tree heuristic
            self.single_task_processing()
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_CP:
            # Create ra_psts for next instance in task_queue
            self.single_instance_processing()
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_CP_DECOMPOSED:
            # Create ra_psts for next instance in task_queue
            self.single_instance_processing(decomposed=True)
        elif self.allocation_type == AllocationTypeEnum.ALL_INSTANCE_CP:
            self.all_instance_processing()
        elif self.allocation_type == AllocationTypeEnum.ALL_INSTANCE_CP_DECOMPOSED:
            self.all_instance_processing(warmstart=False, decomposed=True)
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_CP_REPLAN:
            self.single_instance_replan()
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_HEURISTIC:
            self.single_instance_heuristic()
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_ILP:
            self.single_instance_ilp()
        elif self.allocation_type == AllocationTypeEnum.ALL_INSTANCE_ILP:
            self.all_instance_ilp()
        else:
            raise NotImplementedError(
                f"Allocation_type {self.allocation_type} has not been implemented yet")
        
    def get_current_instance_ilp_rep(self, schedule:dict, queue_object:QueueObject, expected_instance:bool=False):
        if len(schedule["instances"]) > queue_object.schedule_idx and expected_instance is False:
            return schedule["instances"][queue_object.schedule_idx]
        else:
            return queue_object.instance.get_ilp_rep()

    def add_ilp_rep_to_schedule(self, ilp_rep:dict, schedule:dict, queue_object:QueueObject, expected_instance:bool=False):
        if len(schedule["instances"]) > queue_object.schedule_idx and expected_instance is False:
            schedule["instances"][queue_object.schedule_idx] = ilp_rep
        else:
            schedule["instances"].append(ilp_rep)
            if schedule["instances"].index(ilp_rep) != queue_object.schedule_idx and expected_instance is False:
                raise ValueError(f'QueueObject.schedule_idx <{queue_object.schedule_idx}> does not match the position in Schedule["instances"] <{schedule["instances"].index(ilp_rep)}>')
        schedule["resources"] = list(set(schedule["resources"]).union(ilp_rep["resources"]))
        return schedule
    
    def save_schedule(self, schedule):
        with open(self.schedule_filepath, "w") as f:
            json.dump(schedule, f, indent=2)

    def add_branch_to_ilp_rep(self, branch:Branch, ilp_rep:dict, queue_object:QueueObject):
        task_id = branch.node.attrib["id"]
        branch_running_id = queue_object.instance.get_all_valid_branches_list().index(branch)
        branch_ilp_id = f"{queue_object.schedule_idx}-{task_id}-{branch_running_id}"
    
        branch_ilp_jobs = ilp_rep["branches"][branch_ilp_id]["jobs"]
        branch_ra_pst_tasks = branch.get_serialized_tasklist()

        if len(branch_ilp_jobs) != len(branch_ra_pst_tasks):
            raise ValueError(f"Length of Jobs in ilp_rep <{len(branch_ilp_jobs)}> does not match length of jobs in ra_pst_branch <{len(branch_ra_pst_tasks)}>")
        if len(queue_object.instance.get_all_valid_branches_list()) != len(ilp_rep["branches"]):
            raise ValueError
        #resource = branch.node.xpath("cpee1:children/cpee1:resource", namespaces=self.ns)[0].attrib["id"]
        for i, jobId in enumerate(branch_ilp_jobs):
            #if i == 0:
            #    if resource != ilp_rep["jobs"][jobId]["resource"]:
            #        raise ValueError(f"Resource <{resource}> != <{ilp_rep["jobs"][jobId]["resource"]}>")
            task = branch_ra_pst_tasks[i]
            start_time = float(task.xpath(
                "cpee1:expected_start", namespaces=self.ns)[0].text)
            end_time = float(task.xpath("cpee1:expected_end",
                             namespaces=self.ns)[0].text)
            duration = float(end_time) - float(start_time)

            ilp_rep["jobs"][jobId]["start"] = start_time
            ilp_rep["jobs"][jobId]["cost"] = duration
            ilp_rep["jobs"][jobId]["selected"] = True

        return ilp_rep
    
    def get_current_schedule_dict(self) -> dict:
        with open(self.schedule_filepath, "r+") as f:
            if os.path.getsize(self.schedule_filepath) > 0:
                schedule = json.load(f)
            else:
                # Default if file is empty
                schedule = {"instances": [],
                            "resources": [], 
                            "objective": 0}
        return schedule

    def single_task_processing(self):
        """
        Calls the heuristic allocation one task at a time. The queue object holds the current task. 
        """
        start = time.time()
        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            best_branch = queue_object.instance.allocate_next_task(self.schedule_filepath)
            if not best_branch.check_validity():
                raise ValueError("Invalid Branch chosen")

            schedule = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule, queue_object)
            instance_ilp_rep = self.add_branch_to_ilp_rep(best_branch, instance_ilp_rep, queue_object)
            schedule = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule, queue_object)
            queue_object.release_time = sum(queue_object.instance.times[-1])
            if queue_object.release_time > schedule["objective"]:
                schedule["objective"] = queue_object.release_time
            schedule["resources"] = list(set(schedule["resources"]).union(instance_ilp_rep["resources"]))
            self.save_schedule(schedule)
            if queue_object.instance.current_task != "end":
                self.update_task_queue(self.task_queue, queue_object)

        end = time.time()
        self.add_allocation_metadata(float(end-start))

    def single_instance_heuristic(self):
        """
        Calls heuristic allocation for each task in an instance before going over to the next instance
        """
        # TODO single_instance_heuristic()
        # like single task process but do not update process until the end. 
        # Make sure the deletion of a previous task is also prossible! 
        start = time.time()
        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            while queue_object.instance.current_task != "end":
                best_branch = queue_object.instance.allocate_next_task(self.schedule_filepath)
                queue_object.release_time = sum(queue_object.instance.times[-1])
                if not best_branch.check_validity():
                    raise ValueError("Invalid Branch chosen")
                schedule = self.get_current_schedule_dict()
                instance_ilp_rep = self.get_current_instance_ilp_rep(schedule, queue_object)
                instance_ilp_rep = self.add_branch_to_ilp_rep(best_branch, instance_ilp_rep, queue_object)
                schedule = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule, queue_object)
                #self.update_task_queue(self.task_queue, queue_object)

                schedule["resources"] = list(set(schedule["resources"]).union(instance_ilp_rep["resources"]))
                
                if queue_object.release_time > schedule["objective"]:
                    schedule["objective"] = queue_object.release_time          
                self.save_schedule(schedule)    
        end = time.time()
        self.add_allocation_metadata(float(end-start))
    
    def single_instance_processing(self, decomposed:bool=False):
        """
        Allocates each instance on arrival. 
        Already scheduled instances are in the schedule and are added to the cp as fixed. 
        Allowance for rescheduling can be set through self.sigma.
        """
        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            schedule_dict = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
            schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
            schedule_dict["resources"] = list(set(schedule_dict["resources"]).union(instance_ilp_rep["resources"]))
            #if warmstart:
            #    self.create_warmstart_file(schedule_dict, [queue_object])
            self.save_schedule(schedule_dict)

            if decomposed:
                result = cp_solver_decomposed_strengthened_cuts(self.schedule_filepath, TimeLimit=100)
            else:
                result = cp_solver(self.schedule_filepath, log_file=f"{self.schedule_filepath}.log", sigma=self.sigma, timeout=100)
            self.save_schedule(result)


    def single_instance_replan(self, warmstart:bool = False):
        """
        Deprecated: 
        Allowed full replaning of scheduled instances.
        """
        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            schedule_dict = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
            schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
            schedule_dict["resources"] = list(set(schedule_dict["resources"]).union(instance_ilp_rep["resources"]))
            if warmstart:
                self.create_warmstart_file(schedule_dict, [queue_object])
            # set "fixed" to false for all instances
            for ra_pst in schedule_dict["instances"]:
                ra_pst["fixed"] = False
            self.save_schedule(schedule_dict)

            # Get current timestamp: == release time of queue object
            # Replannable tasks are all tasks that have a release time > current time
            # set job to unfixed 
            # create extra online cp_solver method
            release_time = queue_object.release_time

            if warmstart:
                result = cp_solver(self.schedule_filepath, "tmp/warmstart.json")
            else:
                result = cp_solver_alternative_new(self.schedule_filepath, log_file=f"{self.schedule_filepath}.log", replan=True, release_time=release_time, timeout=100)
            self.save_schedule(result)


    def single_instance_ilp(self):
        """
        Allocates an instance that was previously configured through the ILP
        ILP configuration and scheduling is done in this method
        """
        queue_object = self.task_queue.pop(0)
        schedule_dict = self.get_current_schedule_dict()
        instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
        schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
        self.save_schedule(schedule_dict)

        # Get optimal configuration through ILP
        result = configuration_ilp(self.schedule_filepath)
        with open("tmp/ilp_rep.json", "w") as f:
            json.dump(result, f, indent=2)

        schedule_dict = self.ilp_to_schedule_file(result, schedule_dict, queue_object.instance.id)
        self.save_schedule(schedule_dict)
        schedule_dict = cp_solver_scheduling_only(self.schedule_filepath, timeout=100, sigma=self.sigma)
        schedule_dict["ilp_objective"] = result["objective"]
        schedule_dict["ilp_runtime"] = result["runtime"]
        self.save_schedule(schedule_dict)

        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            schedule_dict = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
            schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
            schedule_dict = self.ilp_to_schedule_file(result, schedule_dict, queue_object.instance.id)
            self.save_schedule(schedule_dict)
            schedule_dict = cp_solver_scheduling_only(self.schedule_filepath, timeout=100, sigma=self.sigma)
            self.save_schedule(schedule_dict)
    

    def all_instance_ilp(self):
        """
        Schedules all instances simultaneously based on the optimal configuration found with ILP
        """
        queue_object = self.task_queue.pop(0)
        schedule_dict = self.get_current_schedule_dict()
        instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
        schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
        self.save_schedule(schedule_dict)
        result = configuration_ilp(self.schedule_filepath)
        with open("tmp/ilp_rep.json", "w") as f:
            json.dump(result, f, indent=2)
        schedule_dict = self.ilp_to_schedule_file(result, schedule_dict, queue_object.instance.id)
        schedule_dict["ilp_objective"] = result["objective"]
        schedule_dict["ilp_runtime"] = result["runtime"]
        self.save_schedule(schedule_dict)

        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            schedule_dict = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
            schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
            schedule_dict = self.ilp_to_schedule_file(result, schedule_dict, queue_object.instance.id)
            self.save_schedule(schedule_dict)

        schedule_dict = cp_solver_scheduling_only(self.schedule_filepath, timeout=100, sigma=self.sigma)
        self.save_schedule(schedule_dict)
        
    def all_instance_processing(self, warmstart:bool = False, decomposed:bool=False):
        """
        Schedules all instances simultaneously and also creates the optimal configurations. 
        Integrated CP for scheduling.
        """
        # Generate dict needed for cp_solver
        for queue_object in self.task_queue:
            schedule_dict = self.get_current_schedule_dict()
            instance_ilp_rep = self.get_current_instance_ilp_rep(schedule_dict, queue_object)
            schedule_dict = self.add_ilp_rep_to_schedule(instance_ilp_rep, schedule_dict, queue_object)
            self.save_schedule(schedule_dict)
        
        if warmstart:
            self.create_warmstart_file(schedule_dict, self.task_queue)
            result = cp_solver(self.schedule_filepath, "tmp/warmstart.json")
        elif decomposed:
            result = cp_solver_decomposed_strengthened_cuts(self.schedule_filepath, TimeLimit=2000)
        else:
            _, logfile = os.path.split(os.path.basename(self.schedule_filepath))
            result = cp_solver(self.schedule_filepath, log_file=f"{self.schedule_filepath}.log", timeout=2000, break_symmetries=False)
        self.save_schedule(result)
            
    def create_warmstart_file(self, ra_psts:dict, queue_objects:list[QueueObject]):
        with open("tmp/warmstart.json", "w") as f:
            ra_psts.setdefault("objective", 0)
            json.dump(ra_psts, f, indent=2)
        
        # Create new sim to create warmsstart file
        sim = Simulator(schedule_filepath="tmp/warmstart.json", is_warmstart=True)
        for queue_object in queue_objects:
            sim.add_instance(queue_object.instance, AllocationTypeEnum.HEURISTIC)
        sim.simulate()
        print("Warmstart file created")

    def update_task_queue(self, queue:list[QueueObject], queue_object: QueueObject):
        # instance, allocation_type, task, release_time = task
        queue.append(queue_object)
        queue.sort(key=lambda object: object.release_time)

    def add_allocation_metadata(self, computing_time: float):
        with open(self.schedule_filepath, "r+") as f:
            ra_psts = json.load(f)
            intervals = []
            for ra_pst in ra_psts["instances"]:
                for jobId, job in ra_pst["jobs"].items():
                    if job["selected"]:
                        intervals.append({
                            "jobId": jobId,
                            "start": job["start"],
                            "duration": job["cost"]
                        })
            total_interval_length = sum(
                [element["duration"] for element in intervals])
            ra_psts["solution"] = {
                "objective": ra_psts["objective"],
                "computing time": computing_time,
                "total interval length": total_interval_length
            }
            # Save back to file
            f.seek(0)  # Reset file pointer to the beginning
            json.dump(ra_psts, f, indent=2)
            f.truncate()
    
    def ilp_to_schedule_file(self, ilp_rep, schedule_dict, instance_id):
        selected_branches = [branch for branchId, branch in ilp_rep["branches"].items() if branch["selected"] == 1.0]

        selected_jobs = []
        for branch in selected_branches:
            for jobId in branch["jobs"]:
                parts = jobId.split("-")
                parts[0], parts[1] = str(instance_id), str(instance_id)
                jobId = "-".join(parts)
                selected_jobs.append(jobId)

        for schedule_jobId, schedule_job in schedule_dict["instances"][instance_id]["jobs"].items():
            if schedule_jobId in selected_jobs:
                schedule_job["selected"] = True
        
        return schedule_dict


if __name__ == "__main__":
    pass
