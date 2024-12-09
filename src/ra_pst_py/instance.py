from src.ra_pst_py.change_operations import ChangeOperation
from . import utils 

import numpy as np
import pathlib
from lxml import etree
from .core import RA_PST

CURRENT_MIN_DATE = "2024-01-01T00:00" # Placeholder for scheduling heuristics

class Instance():
    def __init__(self, ra_pst, branches_to_apply:dict):
        self.ra_pst:RA_PST = ra_pst
        self.ns = ra_pst.ns
        self.branches_to_apply = branches_to_apply
        self.applied_branches = {}
        self.delayed_deletes = []
        self.change_op = ChangeOperation(ra_pst=self.ra_pst.process)
        self.tasks_iter = iter(self.ra_pst.get_tasklist())  # iterator
        self.current_task = utils.get_next_task(self.tasks_iter, self)
        self.optimal_process = None
        self.invalid = False

    def get_optimal_instance(self):
        self.apply_branches()
        self.ra_pst.process = etree.fromstring(etree.tostring(self.ra_pst.process))
        self.optimal_process = self.ra_pst.process

    def save_optimal_process(self, path):
        path = pathlib.Path(path)        
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.name.endswith(".xml"):
            path = path.with_suffix(".xml")
        tree = etree.ElementTree(self.optimal_process)
        etree.indent(tree, space="\t", level=0)
        tree.write(path)

    def apply_branches(self, tasks_to_apply:list = None, current_time = CURRENT_MIN_DATE):
        
        while True:
            if not self.current_task == "end":
                task, task_id = self.current_task, self.current_task.attrib["id"]
            if task_id in self.branches_to_apply.keys():
                branch_no = self.branches_to_apply[task_id]
            elif self.current_task == "end":
                    pass
            else:
                print("will be deleted")
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
                self.ra_pst.process = branch.apply_to_process(
                    self.change_op.ra_pst, solution=self, earliest_possible_start=current_time, change_op=self.change_op, delete=delete)  # build branch
                self.change_op.ra_pst = self.ra_pst.process
                self.applied_branches[task_id] = branch_no

                # If branch is already delayed because of delete: #TODO check for reasonability
                #if self.ra_pst.process.xpath("//cpee1:plannedend", namespaces=self.ns):
                #    current_time=self.ra_pst.process.xpath("//cpee1:plannedend", namespaces=self.ns)[-1].text

                # gets next tasks and checks for deletes
                self.current_task = utils.get_next_task(self.tasks_iter, self)
            else:
                for branch, task, current_time in self.delayed_deletes:
                    # TODO fix deleted task time propagation
                    if self.ra_pst.process.xpath(f"//*[@id='{task.attrib['id']}'][not(ancestor::cpee1:children) and not(ancestor::cpee1:allocation) and not(ancestor::RA_RPST)]", namespaces=self.ns):
                        self.ra_pst.process = branch.apply_to_process(
                            self.change_op.ra_pst, solution=self, earliest_possible_start=current_time, change_op=self.change_op)  # apply delays
                self.is_final = True
                break
            self.ra_pst.process = self.change_op.ra_pst

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
    