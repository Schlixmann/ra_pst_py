from src.ra_pst_py.instance import Instance
from src.ra_pst_py.core import Branch, RA_PST
from src.ra_pst_py.cp_docplex import cp_solver

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
    SINGLE_INSTANCE_CP = "single_instance_cp"
    SINGLE_INSTANCE_CP_WARM = "single_instance_cp_warm"
    ALL_INSTANCE_CP = "all_instance_cp"


class QueueObject():
    def __init__(self, instance: Instance, allocation_type: AllocationTypeEnum, task: etree._Element, release_time: float):
        self.instance = instance
        self.allocation_type = allocation_type
        self.task = task
        self.release_time = release_time


class Simulator():
    def __init__(self, schedule_filepath: str = "out/sim_schedule.json", is_warmstart:bool = False) -> None:
        self.schedule_filepath = schedule_filepath
        # List of [{instance:RA_PST_instance, allocation_type:str(allocation_type)}]
        self.process_instances = []
        self.task_queue: list[QueueObject] = []  # List of QueueObject
        self.allocation_type: AllocationTypeEnum = None
        self.ns = None
        self.is_warmstart:bool = is_warmstart

    def add_instance(self, instance: Instance, allocation_type: AllocationTypeEnum):  # TODO
        """ 
        Should add a new instance to self.process_instances after simulation has started.
        New instance will be added in queue
        """
        self.process_instances.append({"instance_id": len(
            self.process_instances), "instance": instance, "allocation_type": allocation_type})
        self.update_task_queue(QueueObject(
            instance, allocation_type, instance.current_task, instance.release_time))
        print(f"Instance added to simulator with allocation_type {allocation_type}")

    def check_setup(self):
        # Check namespaces for ra-pst:
        if not self.ns:
            self.ns = self.process_instances[0]["instance"].ns
        # Check/create schedule file:
        if not self.is_warmstart:
            os.makedirs(os.path.dirname(self.schedule_filepath), exist_ok=True)
            with open(self.schedule_filepath, "w"): pass

    def simulate(self, instance_mapper:dict ={}):
        """
        TODO: refactor so that different allocation types are possible
        within one Simulator. e.g. Heuristic + single instance cp
        """
        # Prelims
        self.check_setup()
        self.set_allocation_type()
            # objective = 0
        queue_object = self.task_queue[0]

        if queue_object.allocation_type == AllocationTypeEnum.HEURISTIC:
            #Start taskwise allocation with process tree heuristic
            start = time.time()
            self.single_task_processing(instance_mapper)
            end = time.time()
            self.add_allocation_metadata(float(end-start))
            
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_CP:
            # Create ra_psts for next instance in task_queue
            self.single_instance_processing()
        
        elif self.allocation_type == AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM:
            # Create ra_psts for next instance in task_queue
            self.single_instance_processing(warmstart=True)

        elif self.allocation_type == AllocationTypeEnum.ALL_INSTANCE_CP:
            ra_psts = {}
            ra_psts["instances"] = []

            # Generate dict needed for cp_solver
            for queue_object in self.task_queue:
                ilp_rep = queue_object.instance.get_ilp_rep()
                ra_psts["instances"].append(ilp_rep)
            ra_psts["resources"] = ilp_rep["resources"]
            
            # Save dict
            with open(self.schedule_filepath, "w") as f:
                json.dump(ra_psts, f, indent=2)
            result = cp_solver(self.schedule_filepath)

            # Save allocated dict
            with open(self.schedule_filepath, "w") as f:
                json.dump(result, f, indent=2)
        else:
            raise NotImplementedError(
                f"Allocation_type {self.allocation_type} has not been implemented yet")

    def single_task_processing(self, instance_mapper:dict = {}):
        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            if self.is_warmstart:
                instance_no = queue_object.instance.id
            else:
                instance_no = [element["instance_id"]
                            for element in self.process_instances if element["instance"] == queue_object.instance][0]

            best_branch = queue_object.instance.allocate_next_task(self.schedule_filepath)
            if not best_branch.check_validity():
                raise ValueError("Invalid Branch chosen")

            with open(self.schedule_filepath, "r+") as f:
                if os.path.getsize(self.schedule_filepath) > 0:
                    tmp_sched = json.load(f)
                else:
                    # Default if file is empty
                    tmp_sched = {"instances": [],
                                "resources": [], 
                                "objective": 0}

                # Create global resources list
                resources = set(tmp_sched["resources"])

                list_idx = len(instance_mapper.values())
                if instance_no in instance_mapper.keys():
                    list_idx = instance_mapper[instance_no]
                    tmp_sched["instances"][list_idx] = self.generate_dict_from_ra_pst(
                        best_branch, queue_object.instance, tmp_sched["instances"][list_idx])
                    resources.update(
                        list(tmp_sched["instances"][list_idx]["resources"]))
                else:
                    instance_mapper[instance_no] = list_idx
                    tmp_sched["instances"].append(self.generate_dict_from_ra_pst(
                        best_branch, queue_object.instance, queue_object.instance.get_ilp_rep()))
                    resources.update(
                        list(tmp_sched["instances"][-1]["resources"]))
                tmp_sched["resources"] = list(resources)

                queue_object.release_time = sum(
                    queue_object.instance.times[-1])
                if queue_object.release_time > tmp_sched["objective"]:
                    tmp_sched["objective"] = queue_object.release_time

                # Save back to file
                f.seek(0)  # Reset file pointer to the beginning
                json.dump(tmp_sched, f, indent=2)
                f.truncate()

            print("Times: \t ", queue_object.instance.times)
            if queue_object.instance.current_task != "end":
                self.update_task_queue(queue_object)

    def single_instance_processing(self, warmstart:bool = False):
        while self.task_queue:
            queue_object = self.task_queue.pop(0)
            ra_psts = {}
            ra_psts["instances"] = []
            # Find id of instance in self.process_instances
            instance_id = [element["instance"] for element in self.process_instances].index(
                queue_object.instance)
            ilp_rep = queue_object.instance.ra_pst.get_ilp_rep(
                instance_id=instance_id)

            ra_psts["instances"].append(ilp_rep)
            ra_psts["resources"] = ilp_rep["resources"]

            if os.path.exists(self.schedule_filepath) and os.path.getsize(self.schedule_filepath) > 0:
                # Load instances from file if exist
                with open(self.schedule_filepath, "r") as f:
                    all_instances = json.load(f)
                    all_instances = self.add_ra_psts_to_all_instances(
                        ra_psts, all_instances)
            else:
                all_instances = ra_psts  # Get only instances from ra_psts

            if warmstart:
                self.create_warmstart_file(all_instances, queue_object)

            with open(self.schedule_filepath, "w") as f:
                json.dump(all_instances, f, indent=2)

            # Add new Jobs to existing job file
            if warmstart:
                result = cp_solver(self.schedule_filepath, "tmp/warmstart.json")
            else:
                result = cp_solver(self.schedule_filepath)
            with open(self.schedule_filepath, "w") as f:
                json.dump(result, f, indent=2)
            
    def create_warmstart_file(self, ra_psts:dict, queue_object:QueueObject):
        with open("tmp/warmstart.json", "w") as f:
            ra_psts.setdefault("objective", 0)
            json.dump(ra_psts, f, indent=2)
        sim = Simulator(schedule_filepath="tmp/warmstart.json", is_warmstart=True)
        sim.add_instance(queue_object.instance, AllocationTypeEnum.HEURISTIC)
        instance_mapper = {id:id for id in range(len(ra_psts["instances"]))}
        sim.simulate(instance_mapper=instance_mapper)
        print("Warmstart file created")

    def update_task_queue(self, queue_object: QueueObject):
        # instance, allocation_type, task, release_time = task
        self.task_queue.append(queue_object)
        self.task_queue.sort(key=lambda object: object.release_time)

    def set_allocation_type(self):
        """
        Check that all instances are either instance wise allocation or
        Full Batch allocation. 
        """
        allocation_types = {item["allocation_type"]
                            for item in self.process_instances}

        # Determine the allocation type
        if allocation_types == {AllocationTypeEnum.HEURISTIC}:
            self.allocation_type = AllocationTypeEnum.HEURISTIC
        elif allocation_types == {AllocationTypeEnum.SINGLE_INSTANCE_CP}:
            self.allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP
        elif allocation_types == {AllocationTypeEnum.ALL_INSTANCE_CP}:
            self.allocation_type = AllocationTypeEnum.ALL_INSTANCE_CP
        elif allocation_types == {AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM}:
            self.allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM
        else:
            raise NotImplementedError(f"The allocation type combination {allocation_types} is not implemented")

    def add_ra_psts_to_all_instances(self, ra_psts, all_instances):
        """
        Add ra_psts dict to the all_instances dict which is given to the scheduler
        """
        instance_set = set(all_instances["resources"])
        instance_set.update(ra_psts["resources"])
        all_instances["resources"] = list(instance_set)
        all_instances["instances"].extend(ra_psts["instances"])
        return all_instances

    def generate_dict_from_ra_pst(self, branch: Branch, instance: Instance, ilp_rep):
        instance_id = ilp_rep["instanceId"]
        task_id = branch.node.attrib["id"]
        if len(instance.get_all_valid_branches_list()) != len(ilp_rep["branches"]):
            raise ValueError
        branch_running_id = instance.get_all_valid_branches_list().index(branch)
        branch_ilp_id = f"{instance_id}-{task_id}-{branch_running_id}"

        branch_ilp_dict = ilp_rep["branches"][branch_ilp_id]
        branch_ilp_jobs = branch_ilp_dict["jobs"]
        branch_ra_pst_tasks = branch.get_serialized_tasklist()

        if len(branch_ilp_jobs) != len(branch_ra_pst_tasks):
            raise ValueError(f"Length of Jobs in ilp_rep <{len(
                branch_ilp_jobs)}> does not match length of jobs in ra_pst_branch <{len(branch_ra_pst_tasks)}>")

        resource = branch.node.xpath("cpee1:children/cpee1:resource", namespaces=self.ns)[0].attrib["id"]
        for i, jobId in enumerate(branch_ilp_jobs):
            if i == 0:
                if resource != ilp_rep["jobs"][jobId]["resource"]:
                    raise ValueError
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
