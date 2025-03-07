from src.ra_pst_py.change_operations import ChangeOperation
from src.ra_pst_py.heuristic import TaskAllocator
from src.ra_pst_py.schedule import Schedule
from src.ra_pst_py.core import RA_PST, Branch

from . import utils 

import numpy as np
from pathlib import Path
from lxml import etree
import os
import json


CURRENT_MIN_DATE = "2024-01-01T00:00" # Placeholder for scheduling heuristics

class Instance():
    def __init__(self, ra_pst, branches_to_apply:dict, schedule:Schedule=None, id=None, release_time:int = None):
        self.id = id
        self.ra_pst:RA_PST = ra_pst
        self.ns = ra_pst.ns
        self.branches_to_apply = branches_to_apply
        self.applied_branches = {}
        self.delayed_deletes = []
        self.change_op = ChangeOperation(ra_pst=self.ra_pst.process, config=self.ra_pst.config)
        self.tasks_iter = iter(self.ra_pst.get_tasklist())  # iterator
        self.current_task = utils.get_next_task(self.tasks_iter, self)
        self.optimal_process = None
        self.invalid = False
        self.allocator = TaskAllocator(self.ra_pst, self.change_op)
        self.allocated_tasks = set()
        self.times = []
        self.release_time:int = release_time
        self.add_release_time(release_time=release_time)

    def add_release_time(self, release_time:float):
        """ """
        task1 = self.ra_pst.get_tasklist()[0]
        child = etree.SubElement(task1, f"{{{self.ns['cpee1']}}}release_time")
        child.text = str(release_time)
        task1 = etree.fromstring(etree.tostring(task1)) # save with namespaces
        
    def get_ilp_rep(self) -> dict:
        """Returns the RA-PST of the instance as dict for an ILP or CP"""
        return self.ra_pst.get_ilp_rep(instance_id=self.id)

    def get_all_valid_branches_list(self) -> list:
        branches = []
        for key, values in self.ra_pst.branches.items():
            branches.extend([branch for branch in values if branch.check_validity()])
        return branches

    def allocate_next_task(self, schedule_filepath:os.PathLike) -> Branch:
        """ Allocate next task in ra_pst based on earliest finish time heuristic"""

        best_branch, times = self.allocator.allocate_task(self.current_task, schedule_filepath=schedule_filepath)
        times = times[0:2]
        task_id = self.current_task.attrib["id"]
        branch_no = self.ra_pst.branches[task_id].index(best_branch)
        self.ra_pst.branches[task_id][branch_no] = best_branch
        self.times.append(times)
        # transform best branch to job representation

        alloc_times = []
        for task in best_branch.get_tasklist():
            cp_type = task.attrib["type"] if "type" in list(task.attrib.keys()) else None
            if cp_type == "delete":
                continue
            if task.xpath("cpee1:children/descendant::cpee1:changepattern", namespaces=self.ns):
                if task.xpath("cpee1:children/descendant::cpee1:changepattern", namespaces=self.ns)[0].attrib["type"] == "replace":
                    continue
                
            resource = task.xpath("cpee1:children/cpee1:resource", namespaces=self.ns)[0].attrib["id"]
            start_time = task.xpath("cpee1:expected_start", namespaces=self.ns)[0].text
            end_time = task.xpath("cpee1:expected_end", namespaces=self.ns)[0].text
            duration = float(end_time) - float(start_time)
            alloc_times.append((start_time, duration))

        # Apply best branch to processmodel
        self.branches_to_apply[self.current_task.attrib["id"]] = best_branch
        self.apply_single_branch(self.current_task, best_branch)       

        # Set new release time for following task
        self.current_task = utils.get_next_task(self.tasks_iter, self)
        if self.current_task == "end":
            self.optimal_process = self.ra_pst.process
            return best_branch
        if self.current_task.xpath("cpee1:release_time", namespaces=self.ns):
            self.current_task.xpath("cpee1:release_time", namespaces=self.ns)[0].text = str(sum(times))
        else:
            child = etree.SubElement(self.current_task, f"{{{self.ns['cpee1']}}}release_time")
            child.text = str(sum(times))
        return best_branch
    
    def apply_single_branch(self, task, branch):
        if self.optimal_process is not None:
            raise ValueError("All tasks have already been allocated")
        task_id = task.attrib["id"]
        current_time = task.xpath("cpee1:release_time", namespaces=self.ns)
        delete=False
        if branch.node.xpath("//*[@type='delete']"):
            #self.delayed_deletes.append((branch, task, current_time))
            delete = False
        self.ra_pst = branch.apply_to_process(
            self, earliest_possible_start=current_time, delete=delete)  # build branch
        branch_no = self.ra_pst.branches[task_id].index(branch)
        self.applied_branches[task_id] = branch_no
        
    def get_optimal_instance_from_schedule(self, schedule_file):
        branches_to_apply = self.transform_ilp_to_branchmap(schedule_file)
        self.optimal_process = self.apply_branches(branches_to_apply)
        return self.optimal_process

    def save_optimal_process(self, path):
        path = Path(path)        
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.name.endswith(".xml"):
            path = path.with_suffix(".xml")
        tree = etree.ElementTree(self.optimal_process)
        etree.indent(tree, space="\t", level=0)
        tree.write(path)

    def apply_branches(self, branches_to_apply:dict=None, current_time = CURRENT_MIN_DATE):
        if branches_to_apply:
            if not isinstance(branches_to_apply, dict):
                raise TypeError(f"Input must be a dict")
            self.branches_to_apply = branches_to_apply
        if not self.branches_to_apply:
            raise ValueError(f"No branches to apply specified.")
        if len(self.branches_to_apply) != len(self.ra_pst.get_tasklist(attribute="id")):
            raise ValueError(f"Len of branches_to_apply does not fit task lengths. Remark also deleted tasks need an empty branch")
        if self.current_task == "end" and self.optimal_process is not None:
            print("Optimal Process already created")
            return self.optimal_process
        
        while True:
            if not self.current_task == "end":
                task, task_id = self.current_task, self.current_task.attrib["id"]
            if task_id in self.branches_to_apply.keys():
                branch_no = self.branches_to_apply[task_id]
                if isinstance(branch_no, list):
                    self.current_task = utils.get_next_task(self.tasks_iter, self)
                    if self.current_task == "end":
                        pass
                    else:
                        continue
            elif self.current_task == "end":
                    pass
            else:
                # Will be deleted
                self.current_task = utils.get_next_task(self.tasks_iter, self)
                if self.current_task == "end":
                    pass
                else:
                    continue
            if self.current_task != "end":
                # Try to build Branch from RA-PST
                branch = self.ra_pst.branches[task_id][branch_no]            
                self.applied_branches[task_id] = branch_no
                
                delete=False
                if branch.node.xpath("//*[@type='delete']"):
                    self.delayed_deletes.append((branch, task, current_time))
                    delete = True
                #TODO add branch invalidities on branch building!
                self.ra_pst = branch.apply_to_process(
                    self, earliest_possible_start=current_time, delete=delete)  # build branch
                self.applied_branches[task_id] = branch_no

                # gets next tasks and checks for deletes
                self.current_task = utils.get_next_task(self.tasks_iter, self)
            else:
                for branch, task, current_time in self.delayed_deletes:
                    # TODO fix deleted task time propagation
                    if self.ra_pst.process.xpath(f"//*[@id='{task.attrib['id']}'][not(ancestor::cpee1:children) and not(ancestor::cpee1:allocation) and not(ancestor::RA_RPST)]", namespaces=self.ns):
                        self.ra_pst = branch.apply_to_process(
                            self, earliest_possible_start=current_time)  # apply delays
                self.is_final = True
                break
        return self.ra_pst.process

    def check_validity(self):  
        tasks = self.optimal_process.xpath(
            "//*[self::cpee1:call or self::cpee1:manipulate][not(ancestor::cpee1:changepattern) and not(ancestor::cpee1:allocation)and not(ancestor::cpee1:children)]", namespaces=self.ns)

        for task in tasks:
            if not task.xpath("cpee1:allocation/*", namespaces=self.ns):
                self.invalid = True
                break

    def get_measure(self, measure, operator=sum, flag=False): 
        """Returns 0 if Flag is set wrong or no values are given, does not check if allocation is is_valid"""
        if flag:
            values = self.optimal_process.xpath(
                f".//allo:allocation/cpee1:resource/cpee1:resprofile/cpee1:measures/cpee1:{measure}", namespaces=self.ns)
        else:
            values = self.optimal_process.xpath(
                f".//cpee1:allocation/cpee1:resource/cpee1:resprofile/cpee1:measures/cpee1:{measure}", namespaces=self.ns)
        self.check_validity()
        if self.invalid:
            return np.nan
        else:
            return operator([float(value.text) for value in values])
        
    def transform_ilp_to_branchmap(self, ilp_path:os.PathLike|str):
        """
        Transform the branch dict received from ILP into a branch dict for the RA_PST.
        Form: {task_id:branch_to_allocate}
        """
        if isinstance(ilp_path, (str, os.PathLike, Path)):
            with open(ilp_path) as f:
                data = json.load(f)
        else:
            raise TypeError("No valid type, must be path to a file")

        # Check for instanceId in data
        if not any(instance["instanceId"] == self.id for instance in data["instances"]):
            raise ValueError("InstanceId not found in Schedule")
        instance = next((instance for instance in data["instances"] if instance["instanceId"] == self.id), None)
        if instance is None:
            raise ValueError(f"InstanceId {self.id} not found in Schedule")
        
        branch_map = {task_id : [] for task_id in self.ra_pst.get_tasklist(attribute = "id")}
        selected_branches = list(set(job["branch"] for jobId, job in instance["jobs"].items() if job["selected"]))
                           
        for branchId in selected_branches:
            selected_branch = instance["branches"][branchId]
            instance_task_id = selected_branch["task"]
            task_id = selected_branch["task"].split("-")[-1]


            # Compare len ilp_rep branches with instance branches
            valid_branches = [branch for branch in self.ra_pst.branches[task_id] if branch.check_validity()]
            if len(valid_branches) != len(instance["tasks"][instance_task_id]["branches"]):
                raise ValueError(f"The number of branches in the scheduled instance {len(instance["tasks"][instance_task_id]["branches"])} " 
                                f"does not match the number of branches in the Instance {len(valid_branches)}")
            
            # Get branch_idx out of all valid branches for task
            branch_idx = instance["tasks"][instance_task_id]["branches"].index(branchId)

            # Get valid branches for task: 
            branch_to_apply = [branch for branch in self.ra_pst.get_branches()[task_id] if branch.check_validity()][branch_idx]
            branch_map[task_id] = self.ra_pst.branches[task_id].index(branch_to_apply)
        
        return branch_map


def transform_ilp_to_branches(ra_pst:RA_PST, ilp_rep):
    """
    Transform the branch dict received from ILP into a branch dict for the RA_PST.
    Form: {task_id:branch_to_allocate}
    """

    tasklist = ra_pst.get_tasklist(attribute="id")
    branches = ilp_rep["branches"]
    deletes = [item["id"] for item in ilp_rep["tasks"] if item["deleted"] == 1]
    branch_map = {}
    for task in tasklist:
        if task in deletes:
            continue

        taskbranches = [item for item in branches if item["task"] == task]
        choosen_branch = [item for item in taskbranches if item["selected"] == 1]
        if len(choosen_branch) > 1:
            raise ValueError(f"More than one branch choosen for task {task}")
        
        #branch_no = taskbranches[choosen_branch[0]["branch_no"]]
        branch_map[task] = choosen_branch[0]["branch_no"]
    
    return branch_map

    # To enable online allocation, for each task a branch has to be selected and applied singularily
    # Therefore we need to track the currently allocated task and only add and apply branches on the fly
    # to_del tasks must also be tracked. 
    # The RA_PST instance will be kept in memory and updated.
    # The following functions are needed: 
    # allocated_next_task
    # apply_single_branch
    # the allocation decision should be made externally by heuristic.find_best_resource
    # the propagation through should also be done externally 
    