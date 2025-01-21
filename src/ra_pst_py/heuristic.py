from . import utils
from src.ra_pst_py.schedule import Schedule
from src.ra_pst_py.core import Branch, RA_PST

from lxml import etree
import numpy as np
from collections import defaultdict
import warnings

class TaskAllocator():

    def __init__(self, ra_pst:RA_PST, schedule:Schedule, change_operation):
        self.ra_pst = ra_pst
        self.ns = ra_pst.ns
        self.schedule = schedule
        self.change_operation = change_operation

    def allocate_task(self, task:etree._Element) -> tuple[Branch, tuple]:
        """
        Allocates a task to a resource and propagate through ra_pst
        """
        branches = self.ra_pst.branches[task.attrib['id']]
        finish_times = []
        for branch in branches:
            #TODO create etree._Element release_time for each task in branch and set time to release_time
            if branch.check_validity():
                self.set_release_times(branch, task)
                finish_times.append((branch, self.calculate_finish_time(branch.node)[1:]))

        if not finish_times:
            raise ValueError("No valid branch for this task")
        finish_times.sort(key=lambda x: sum(x[1]))
        #print(finish_times)
        return finish_times[0]
    
    def set_release_times(self, branch, task):
        # TODO get all tasks in branch and set release_time to task.release_time
        release_time = task.xpath("cpee1:release_time", namespaces=self.ns)[0].text
        tasks = branch.get_tasklist()
        for branch_task in tasks:
            child = etree.SubElement(branch_task, f"{{{self.ns['cpee1']}}}release_time")
            child.text = release_time
    
    def calculate_finish_time(self, task:etree._Element) -> tuple[etree._Element, float, float, float]:
        """
        Calculates the finish time of a task for a specific branch.
        Propagation through branch needed.
        """
        to_del_time = float(0)
        next_change_patterns = task.xpath("cpee1:children/cpee1:resource/cpee1:resprofile/cpee1:changepattern", namespaces=self.ns)
        if not next_change_patterns:
            #release_time_element = task.xpath("cpee1:release_time", namespaces=self.ns)[0]
            #resource_element = task.xpath("cpee1:children/cpee1:resource", namespaces=self.ns)[0]
            allocated_resource, earliest_start, duration = self.find_best_resource(task)
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
                    pass

                if change_pattern_type == "insert":
                    if child_direction == "before":
                        # go one recursive step lower
                        start_element, earliest_start, duration, to_del_time = self.calculate_finish_time(
                            task=child)
                        #child.xpath("cpee1:expectedready", namespaces=self.ns)[
                        #    0].text = times_tuple[0].text
                        task.xpath("cpee1:release_time", namespaces=self.ns)[
                            0].text = str(earliest_start + duration)
                       
                        # find times for tree_node
                        allocated_resource, earliest_start, duration = self.find_best_resource(task)
                        start_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_start")
                        start_element.text = str(earliest_start)
                        end_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}expected_end")
                        end_element.text = str(earliest_start + duration)

                        # return to branch
                        return start_element, earliest_start, duration, to_del_time

                    elif child_direction == "after":

                        allocated_resource, earliest_start, duration = self.find_best_resource(task)
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
                            task=child)


                        # return to branch
                        return start_element, earliest_start, duration, to_del_time

                    elif child_direction == "parallel": 
                        #TODO implement parallel
                        #raise NotImplementedError("Parallel not Implemented")

                        # Set earliest possible starttime on both tasks Anchor and Inserted.
                        # Recurse further down if needed
                        anchor = task.xpath("cpee1:release_time", namespaces=self.ns)[0]
                        start_element, earliest_start, duration, to_del_time = self.calculate_finish_time(
                                                    task=child)
                        child_node = child.xpath("cpee1:release_time", namespaces=self.ns)[0]
                        if float(anchor.text) < float(earliest_start):
                            anchor.text = str(earliest_start)
                        else:
                            child_node.text = anchor.text
                            earliest_start = anchor.text
                        allocated_resource, earliest_start, duration = self.find_best_resource(task)
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
                        affected_tasks = new_child.xpath("cpee1:children/descendant::cpee1:children/*", namespaces=self.ns)

                        min_deletion_savings = []
                        for task in affected_tasks:
                            if len(affected_tasks) > 1:
                                warnings.warn("More than one task available to be deleted. Your process has multiple tasks with the same name")
                            proc_tasks = self.change_operation.get_proc_task(self.ra_pst.process, task, full_rapst=True)
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
                            task=new_child)
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
                        task=child)
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
                allocated_resource, earliest_start, duration = self.find_best_resource(task)
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


    def find_best_resource(self, task:etree._Element) -> None:
        """
        Finds best availabe timeslot for one task of an RA-PST.
        """
        earliest_start = np.inf
        earliest_finish = np.inf
        allocated_resource = None
        release_time = float(task.xpath("cpee1:release_time", namespaces = self.ns)[0].text)

        # Iterate over all resources and resource profiles to find slot with earliest possible finishing time
        if not task.xpath("cpee1:children/cpee1:resource/cpee1:resprofile", namespaces=self.ns):
            raise ValueError("No rp found")
        for resource in task.xpath("cpee1:children/cpee1:resource/cpee1:resprofile", namespaces=self.ns):
            resource_name = resource.xpath("parent::cpee1:resource", namespaces=self.ns)[0].attrib["id"]
            duration = float(resource.xpath(f"cpee1:measures/cpee1:cost", namespaces=self.ns)[0].text)
            timeslot_matrix = self.schedule.get_timeslot_matrix(float(release_time), resource_name)
            possible_slots = np.argwhere(np.diff(timeslot_matrix) >= duration)
            if possible_slots.size > 0:
                for slot in possible_slots:
                    earliest_slot = float(timeslot_matrix[slot[0]][0])
                    if earliest_slot+duration < earliest_finish and earliest_slot >= float(release_time):
                        earliest_start = earliest_slot
                        earliest_finish = earliest_slot+duration
                        allocated_resource = resource_name
                    elif timeslot_matrix[slot[0]][1] == np.inf and earliest_start == np.inf:
                        earliest_start = release_time
                        earliest_finish = earliest_slot+duration
                        allocated_resource = resource_name
            else:
                raise ValueError("No timeslot found")
        if allocated_resource is None:
            raise ValueError("No slot and resource found")
        #print(f" Best start: {earliest_start}, on resource {allocated_resource}")
        return allocated_resource, earliest_start, duration

