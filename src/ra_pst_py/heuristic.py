from src.ra_pst_py import utils
from src.ra_pst_py.core import Branch, RA_PST
from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from lxml import etree
import numpy as np
from collections import defaultdict
import warnings
import os
import json
from abc import ABC, abstractmethod
from enum import StrEnum

    
class CPType_Enum(StrEnum):
    INSERT = "insert"
    REPLACE = "replace"
    DELETE = "delete"

class CPDirction_Enum(StrEnum):
    BEFORE = "before"
    AFTER = "after"
    PARALLEL = "parallel"
    ANY = "any"
    REPLACE = "replace"    

class TaskNode():
    def __init__(self, task, initialize:bool=True):
        self.task:etree._Element = task
        self.ns = self.get_namespace()
        self.release_time:float = None
        self.earliest_start:float = None
        self.change_patterns: list['TaskNode'] = []
        self.deletion_savings:float = float(0)
        self.cp_type:CPType_Enum = None
        self.cp_direction: CPDirction_Enum = None
        self.backwards_delete:bool = False
        if initialize:
            self.initialize_resource_attributes()

    def initialize_resource_attributes(self):
        self.duration:float = self.get_duration()
        self.resource:str = self.get_resource()
    
    def get_release_time(self):
        return float(self.task.xpath("cpee1:release_time", namespaces=self.ns)[0])
    
    def get_duration(self):
        attrib = "cost"
        return float(self.task.xpath(f"cpee1:children/cpee1:resource/cpee1:resprofile/cpee1:measures/cpee1:{attrib}", namespaces=self.ns)[0].text)

    def get_resource(self):
        return (self.task.xpath("cpee1:children/cpee1:resource", namespaces=self.ns)[0].attrib["id"])
    
    def get_namespace(self):
        return {"cpee1": list(self.task.nsmap.values())[0]}

    def set_change_patterns(self):
        children = self.task.xpath("cpee1:children/cpee1:resource/cpee1:resprofile/cpee1:children/*", namespaces=self.ns)
        self.change_patterns = [CpTaskNode(child) for child in children]
    
    def set_release_time(self, release_time):
        self.release_time = float(release_time)

    def check_release_time(self):
        if self.release_time is None:
            raise ValueError("No release time set")
    
    def add_all_times_to_branch(self):
        if self.cp_type != CPType_Enum.DELETE:
            release_time = etree.SubElement(self.task, f"{{{self.ns["cpee1"]}}}release_time")
            release_time.text = str(self.release_time)
            start_element = etree.SubElement(self.task, f"{{{self.ns["cpee1"]}}}expected_start")
            start_element.text = str(self.earliest_start)
            end_element = etree.SubElement(self.task, f"{{{self.ns["cpee1"]}}}expected_end")
            end_element.text = str(self.earliest_start+self.duration)
        else:
            if self.deletion_savings < 0:
                delete_element = etree.SubElement(self.task, f"{{{self.ns["cpee1"]}}}expected_delete")
                delete_element.text = str(self.deletion_savings)
        for child in self.change_patterns:
            child.add_all_times_to_branch()
    
    def get_interval(self, ra_pst:RA_PST) -> tuple:
        starts = self.task.xpath("//cpee1:expected_start/text()", namespaces=self.ns)
        starts = sorted([float(start) for start in starts])
        ends = self.task.xpath("//cpee1:expected_end/text()", namespaces=self.ns)
        ends = sorted([float(end) for end in ends])
        
        # Find all <cpee1:expected_delete> nodes
        # find self.task in ra_pst: 
        task = [task for task in ra_pst.get_tasklist() if task.attrib["id"] == self.task.attrib["id"]][0]
        nodes_to_delete = self.task.xpath("//cpee1:expected_delete/parent::*", namespaces=self.ns)
        nodes_to_delete_ra_pst = []
        for node in nodes_to_delete:
            nodes_to_delete_ra_pst.extend([delete_task for delete_task in ra_pst.get_tasklist() if utils.get_label(delete_task) == utils.get_label(node)])
        
        filtered_deletes = []
        for delete_task in nodes_to_delete_ra_pst:
            if ra_pst.get_tasklist().index(delete_task) > ra_pst.get_tasklist().index(task):
                filtered_deletes.append(utils.get_label(delete_task))
            else:
                warnings.warn("Previous tasks can not be deleted from the process")
                self.backwards_delete = True

        nodes_to_delete = sorted([float(delete_task.xpath("cpee1:expected_delete/text()", namespaces=self.ns)[0]) for delete_task in nodes_to_delete if utils.get_label(delete_task) in filtered_deletes])
        return (starts[0], ends[-1] - starts[0], sum(nodes_to_delete),  ends[-1])
        
    def set_earliest_start(self, schedule_dict:dict) -> None:
        """
        Finds best availabe timeslot for one task of an RA-PST.
        """
        earliest_start = np.inf
        earliest_finish = np.inf
        timeslot_matrix = self.get_timeslot_matrix(schedule_dict)
        possible_slots = np.argwhere(np.diff(timeslot_matrix) >= self.duration)
        if possible_slots.size > 0:
            for slot in possible_slots:
                earliest_slot = float(timeslot_matrix[slot[0]][0])
                if earliest_slot+self.duration < earliest_finish and earliest_slot >= float(self.release_time):
                    earliest_start = earliest_slot
                    earliest_finish = earliest_slot+self.duration
                elif timeslot_matrix[slot[0]][1] == np.inf and earliest_start == np.inf:
                    earliest_start = self.release_time
                    earliest_finish = earliest_slot+self.duration
        else:
            raise ValueError("No timeslot found")
        #print(f" Best start: {earliest_start}, on resource {allocated_resource}")
        self.earliest_start = earliest_start
    
    def get_timeslot_matrix(self, schedule_dict:dict):
        if not schedule_dict:
            return np.array([[self.release_time, np.inf]])
        matrix = []
        jobs_on_resource = []
        # Match selected Jobs and resources
        for instance in schedule_dict["instances"]:
            jobs_on_resource.extend([job for jobId, job in instance["jobs"].items() if job["selected"] and job["resource"] == self.resource])
        for block in jobs_on_resource:
            if float(block["start"]) + float(block["cost"]) >= self.release_time:
                matrix.append([block["start"], block["start"] + block["cost"]])
        matrix.sort()
        matrix.append([np.inf, 0])
        if matrix:
            return np.roll(np.array(matrix), 1) 
        else:
            return np.array([[self.release_time, np.inf]])
        
    def calculate_finish_time(self, schedule_dict:dict, ra_pst:RA_PST, backwards_delete:bool=False):

        self.set_change_patterns()
        if self.change_patterns:
            for child_task_node in self.change_patterns:
                if child_task_node.cp_type == CPType_Enum.INSERT:
                    if child_task_node.cp_direction == CPDirction_Enum.BEFORE:
                        # Insert Before
                        child_task_node.set_release_time(self.release_time)
                        child_task_node.calculate_finish_time(schedule_dict, ra_pst)
                        child_fin = [child_node.earliest_start + child_node.duration for child_node in child_task_node.change_patterns]
                        child_task_node_finish = child_fin.append(child_task_node.earliest_start + child_task_node.duration)
                        child_task_node_finish = max(child_fin)
                        self.set_release_time(child_task_node_finish)
                        self.set_earliest_start(schedule_dict)

                    elif child_task_node.cp_direction == CPDirction_Enum.AFTER:
                        # Insert After
                        self.set_earliest_start(schedule_dict)
                        child_task_node.set_release_time(self.earliest_start + self.duration)
                        child_task_node.calculate_finish_time(schedule_dict, ra_pst)
                    elif child_task_node.cp_direction == CPDirction_Enum.PARALLEL:
                        # Insert Parallel
                        pass
                
                elif child_task_node.cp_type == CPType_Enum.DELETE:
                    # DELETE Task
                    # TODO calc_minimum deletion savings
                    warnings.warn("The direction of the delete is any, for taskwise allocation, previous tasks can not be deleted from the process")
                    self.set_earliest_start(schedule_dict)
                    affected_tasks= [ra_pst_task for ra_pst_task in ra_pst.get_tasklist() if child_task_node.task.attrib["label"] == utils.get_label(ra_pst_task)]
                    if len(affected_tasks) > 1:
                        warnings.warn("More than one task available to be deleted. Your process has multiple tasks with the same name")
                    min_deletion_savings = []
                    for affected_task in affected_tasks:
                        branches = ra_pst.branches[affected_task.attrib["id"]]
                        min_deletion_savings.append(sorted([branch.get_branch_costs() for branch in branches])[0])
                    if min_deletion_savings:
                        child_task_node.deletion_savings = -float(sorted(min_deletion_savings)[0])
                    child_task_node.duration = 0.0
                    child_task_node.earliest_start = 0.0

                    
                elif child_task_node.cp_type == CPType_Enum.REPLACE:
                    # Replace Task
                    pass
                else:
                    raise NotImplementedError(f"CP_TYPE {child_task_node.cp_type} not implemented")
            
                # Handover release time to next child:
                child_task_node_idx = self.change_patterns.index(child_task_node)
                if child_task_node_idx < len(self.change_patterns) -1:
                    next_child = self.change_patterns[child_task_node_idx + 1]
                    next_child.set_release_time(child_task_node.earliest_start + child_task_node.duration)

        else:
            # Find earliest timeslot in schedule and set it
            self.check_release_time()
            self.set_earliest_start(schedule_dict)

        return self

class CpTaskNode(TaskNode):
    def __init__(self, task, initialize:bool=False):
        super().__init__(task, initialize)
        self.cp_type:CPType_Enum = self.get_cp_type()
        self.cp_direction: CPDirction_Enum = self.get_cp_direction()
        if self.cp_type != CPType_Enum.DELETE:
            self.initialize_resource_attributes()
    
    def get_cp_type(self):
        return CPType_Enum(self.task.attrib["type"])

    def get_cp_direction(self):
        if self.cp_type == CPType_Enum.REPLACE:
            return CPDirction_Enum.REPLACE
        else:
            return CPDirction_Enum(self.task.attrib["direction"])


class TaskAllocator():

    def __init__(self, ra_pst:RA_PST,  change_operation):
        self.ra_pst = ra_pst
        self.ns = ra_pst.ns
        self.change_operation = change_operation

    def allocate_task(self, task:etree._Element, schedule_filepath:os.PathLike | str) -> tuple[Branch, tuple]:
        """
        Allocates a task to a resource and propagate through ra_pst
        """
        if os.path.getsize(schedule_filepath) > 0:
            with open(schedule_filepath, "r") as f:
                schedule_dict = json.load(f)
        else:
            schedule_dict = {}
        branches = self.ra_pst.branches[task.attrib['id']]
        finish_times = []
        for branch in branches:
            #TODO create etree._Element release_time for each task in branch and set time to release_time
            if branch.check_validity():
                task_node = TaskNode(branch.node)
                branch_release = task.xpath("cpee1:release_time", namespaces=self.ns)[0].text
                task_node.set_release_time(float(branch_release))
                task_node.calculate_finish_time(schedule_dict, self.ra_pst)
                task_node.add_all_times_to_branch()
                branch.node = task_node.task    # Update branch node
                interval = task_node.get_interval(self.ra_pst)
                if not task_node.backwards_delete:
                    finish_times.append((branch, interval))

        if not finish_times:
            raise ValueError("No valid branch for this task")
        finish_times.sort(key=lambda x: sum(x[1][0:3]))
        #print(finish_times)
        return finish_times[0]
    
    def set_release_times(self, branch, task):
        # TODO get all tasks in branch and set release_time to task.release_time
        release_time = task.xpath("cpee1:release_time", namespaces=self.ns)[0].text
        tasks = branch.get_tasklist()
        for branch_task in tasks:
            child = etree.SubElement(branch_task, f"{{{self.ns['cpee1']}}}release_time")
            child.text = release_time
    
    def calculate_finish_time_old(self, task_node:TaskNode, schedule_dict:dict):

        if task_node.change_patterns:
            for child_task_node in task_node.change_patterns:
                if child_task_node.cp_type == CPType_Enum.INSERT:
                    if child_task_node.cp_direction == CPDirction_Enum.BEFORE:
                        # Insert Before
                        child_task_node.calculate_finish_time(schedule_dict)
                        task_node.release_time = child_task_node.earliest_start + child_task_node.duration
                        task_node.set_earliest_start()

                    elif child_task_node.cp_direction == CPDirction_Enum.AFTER:
                        # Insert After
                        task_node.set_earliest_start()
                        child_task_node.release_time = task_node.earliest_start + task_node.duration
                        child_task_node.calculate_finish_time(schedule_dict)
                    
                    elif child_task_node.cp_direction == CPDirction_Enum.PARALLEL:
                        # Insert Parallel
                        pass
                
                elif child_task_node.cp_type == CPType_Enum.DELETE:
                    # DELETE Task
                    # TODO calc_minimum deletion savings
                    task_node.set_earliest_start()
                    

                elif child_task_node.cp_type == CPType_Enum.REPLACE:
                    # Replace Task
                    pass
                else:
                    raise NotImplementedError(f"CP_TYPE {child_task_node.cp_type} not implemented")
            
                # Handover release time to next child:
        else:
            # Find earliest timeslot in schedule and set it
            task_node.check_release_time()
            task_node.set_earliest_start(schedule_dict)

        return task_node

    def calculate_finish_time(self, task:etree._Element, schedule_dict:dict) -> tuple[etree._Element, float, float, float]:
        """
        Calculates the finish time of a task for a specific branch.
        Propagation through branch needed.
        """
        to_del_time = float(0)
        next_change_patterns = task.xpath("cpee1:children/cpee1:resource/cpee1:resprofile/cpee1:changepattern", namespaces=self.ns)
        if not next_change_patterns:
            #release_time_element = task.xpath("cpee1:release_time", namespaces=self.ns)[0]
            #resource_element = task.xpath("cpee1:children/cpee1:resource", namespaces=self.ns)[0]
            allocated_resource, earliest_start, duration = self.find_best_resource(task, schedule_dict)
            start_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_start")
            start_element.text = str(earliest_start)
            end_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_end")
            end_element.text = str(earliest_start + duration)

            return start_element, earliest_start, duration, to_del_time

        else:
            next_children = task.xpath(
                "cpee1:children/cpee1:resource/cpee1:resprofile/cpee1:children/*", namespaces=self.ns)
            for child in next_children:
                change_pattern_type = child.xpath("@type")[0]
                try:
                    child_direction = child.xpath(
                        "@direction", namespaces=self.ns)[0]
                except:
                    #TODO implement for replace pattern
                    #raise NotImplementedError("Child is probably replace pattern")
                    child_direction = "replace"

                if change_pattern_type == "insert":
                    if child_direction == "before":
                        # go one recursive step lower
                        start_element, earliest_start, duration, to_del_time = self.calculate_finish_time(
                            task=child, schedule_dict=schedule_dict)
                        #child.xpath("cpee1:expectedready", namespaces=self.ns)[
                        #    0].text = times_tuple[0].text
                        task.xpath("cpee1:release_time", namespaces=self.ns)[
                            0].text = str(earliest_start + duration)
                       
                        # find times for tree_node
                        allocated_resource, earliest_start, duration = self.find_best_resource(task, schedule_dict)
                        start_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_start")
                        start_element.text = str(earliest_start)
                        end_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_end")
                        end_element.text = str(earliest_start + duration)

                        # return to branch
                        return start_element, earliest_start, duration, to_del_time

                    elif child_direction == "after":

                        allocated_resource, earliest_start, duration = self.find_best_resource(task, schedule_dict)
                        start_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_start")
                        start_element.text = str(earliest_start)
                        end_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_end")
                        end_element.text = str(earliest_start + duration)
                        new_release_time = earliest_start+duration

                        if not new_release_time:
                            raise ValueError
                        for descendant in child.xpath("descendant-or-self::cpee1:release_time", namespaces=self.ns):
                            descendant.text = str(new_release_time)
                        start_element, earliest_start, duration, to_del_time = self.calculate_finish_time(
                            task=child, schedule_dict=schedule_dict)


                        # return to branch
                        return start_element, earliest_start, duration, to_del_time

                    elif child_direction == "parallel": 
                        #TODO implement parallel
                        #raise NotImplementedError("Parallel not Implemented")

                        # Set earliest possible starttime on both tasks Anchor and Inserted.
                        # Recurse further down if needed
                        anchor = task.xpath("cpee1:release_time", namespaces=self.ns)[0]
                        start_element, earliest_start, duration, to_del_time = self.calculate_finish_time(
                                                    task=child,schedule_dict=schedule_dict)
                        child_node = child.xpath("cpee1:release_time", namespaces=self.ns)[0]
                        if float(anchor.text) < float(earliest_start):
                            anchor.text = str(earliest_start)
                        else:
                            child_node.text = anchor.text
                            earliest_start = anchor.text
                        allocated_resource, earliest_start, duration = self.find_best_resource(task, schedule_dict)
                        start_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_start")
                        start_element.text = str(earliest_start)
                        end_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_end")
                        end_element.text = str(earliest_start + duration)
                        new_release_time = earliest_start+duration
                        return start_element, earliest_start, duration, to_del_time

                    else:
                        print("Direction not implemented")

                elif change_pattern_type == "delete":
                    if child_direction == "any":
                        warnings.warn("The direction of the delete is any, for taskwise allocation, previous tasks can not be deleted from the process")

                        new_child = task

                        # Identify to del task: 
                        affected_tasks = new_child.xpath("cpee1:children/descendant::cpee1:children/cpee1:manipulate | cpee1:children/descendant::cpee1:children/cpee1:call", namespaces=self.ns)

                        min_deletion_savings = []
                        for affected_task in affected_tasks:
                            if len(affected_tasks) > 1:
                                warnings.warn("More than one task available to be deleted. Your process has multiple tasks with the same name")
                            proc_tasks = self.change_operation.get_proc_task(self.ra_pst.process, affected_task, full_rapst=True)
                            for proc_task in proc_tasks:
                                delete_element = etree.SubElement(proc_task, f"{{{self.ns['cpee1']}}}to_delete")
                                self.change_operation.to_del_label.append(utils.get_label(etree.tostring(proc_task)))
                            
                            label = utils.get_label(etree.tostring(task))
                            tasks_ra_pst = self.ra_pst.get_tasklist()
                            to_del_tasks_ra_pst = [task for task in tasks_ra_pst if utils.get_label(etree.tostring(task)) == label]
                            for to_del_task in to_del_tasks_ra_pst:
                                branches = self.ra_pst.branches[to_del_task.attrib["id"]]
                                min_deletion_savings.append(sorted([branch.get_branch_costs() for branch in branches])[0])
                                # TODO how to store this value
                            

                        cp_element = new_child.xpath("cpee1:children/cpee1:resource/cpee1:resprofile/cpee1:changepattern", namespaces=self.ns)[0]
                        new_child.xpath("cpee1:children/cpee1:resource/cpee1:resprofile", namespaces=self.ns)[0].remove(cp_element)

                        start_element, earliest_start, duration, to_del_time = self.calculate_finish_time(
                            task=new_child, schedule_dict=schedule_dict)
                        task.xpath("cpee1:release_time", namespaces=self.ns)[0].text = str(earliest_start)
                        to_del_time = 0
                        if min_deletion_savings:
                            to_del_time = -float(sorted(min_deletion_savings)[0])

                        # return to branch
                        return start_element, earliest_start, duration, to_del_time
                    else:
                        print("Direction not implemented")

                elif change_pattern_type == "replace":                   
                    start_element, earliest_start, duration, to_del_time = self.calculate_finish_time(
                        task=child, schedule_dict=schedule_dict)
                    #allocated_resource, earliest_start, duration = self.find_best_resource(child)
                    start_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_start")
                    start_element.text = str(earliest_start)
                    end_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_end")
                    end_element.text = str(earliest_start + duration)
                    new_release_time = earliest_start+duration

                    # return to branch
                    return start_element, earliest_start, duration, to_del_time
            
            if task.xpath("descendant::cpee1:changepattern/@type", namespaces=self.ns)[0] == "delete":
                # set values for task and resource
                allocated_resource, earliest_start, duration = self.find_best_resource(task, schedule_dict)
                start_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_start")
                start_element.text = str(earliest_start)
                end_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_end")
                end_element.text = str(earliest_start + duration)                 
                # return to branch
                return start_element, earliest_start, duration, to_del_time
            else:
                print("Invalid branch, no time")
                inval_child = task.xpath("descendant::cpee1:children[not(child::*)]", namespaces=self.ns)[0]
                parent = inval_child.xpath("parent::*")[0]
                exp_ready_element = etree.SubElement(parent, f"{{{self.ns['cpee1']}}}release_time")
                exp_ready_element.text = task.xpath("cpee1:release_time", namespaces=self.ns)[0].text
                min_exp_ready = task.xpath("cpee1:release_time", namespaces=self.ns)[0].text
                start_element, end_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_start"), etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_end")
                start_element.text, end_element.text = min_exp_ready, min_exp_ready
                start_element, end_element = etree.SubElement(parent, f"{{{self.ns['cpee1']}}}expected_start"), etree.SubElement(parent, f"{{{self.ns['cpee1']}}}expected_end")
                start_element.text, end_element.text = min_exp_ready, min_exp_ready
                # TODO implement to deal with invalid branches
                #raise NotImplementedError("Invalid branch, no time")    
                return start_element, float(min_exp_ready), float(min_exp_ready), to_del_time
            pass
        return exp_ready_element



    
    def get_timeslot_matrix(self, release_time:float, resource_name:str, schedule_dict:dict):
        if not schedule_dict:
            return np.array([[release_time, np.inf]])
        
        matrix = []
        jobs_on_resource = []

        # Match selected Jobs and resources
        for instance in schedule_dict["instances"]:
            jobs_on_resource.extend([job for jobId, job in instance["jobs"].items() if job["selected"] and job["resource"] == resource_name])
        for block in jobs_on_resource:
            if float(block["start"]) + float(block["cost"]) >= release_time:
                matrix.append([block["start"], block["start"] + block["cost"]])
        matrix.sort()
        matrix.append([np.inf, 0])
        if matrix:
            return np.roll(np.array(matrix), 1) 
        else:
            return np.array([[release_time, np.inf]])
    

if __name__ == "__main__":
    ra_pst = build_rapst(process_file="testsets/testset1/process/process_short.xml", resource_file="testsets/testset1/resources/1_skill_short.xml")
    show_tree_as_graph(ra_pst)
    tree = etree.parse("tests/test_data/bef_after_test.xml")
    root = tree.getroot()
    task_node = TaskNode(root)
    task_node.set_release_time(0)
    with open("tests/test_data/test_sched.json", "r") as f:
        schedule_dict = json.load(f)
    task_node.calculate_finish_time(schedule_dict, ra_pst)
    print("task_node")
    task_node.add_all_times_to_branch()
    tree = etree.ElementTree(task_node.task)
    etree.indent(tree, space="\t", level=0)
    tree.write("test.xml")
    print(task_node.get_interval())
    