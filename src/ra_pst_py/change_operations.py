from . import utils 

import os
from lxml import etree
import copy
import re
import numpy as np
from datetime import datetime,timedelta

CURRENT_MIN_DATE = "2024-01-01T00:00"

class ChangeOperation():

    def __init__(self, ra_pst):
        self.ra_pst = ra_pst
        self.ns = {'cpee1': list(ra_pst.nsmap.values())[0]}
        self.to_del_label=[]

    def ChangeOperationFactory(self,process, core_task, task, branch, cptype, earliest_possible_start=None):
        localizer = {
            "insert": Insert,
            "replace": Replace,
            "delete": Delete
        }
        change_op = localizer[cptype](self.ra_pst)
        return change_op.apply(process, core_task, task, branch, earliest_possible_start)

    def get_proc_task(self, process, core_task, all:bool=False, full_rapst:bool=False):

        if full_rapst:
            proc_tasks = list(filter(lambda x: utils.get_label(etree.tostring(
                core_task)) == utils.get_label(etree.tostring(x)), process.xpath("//*[self::cpee1:call or self::cpee1:manipulate]", namespaces=self.ns)))
            return proc_tasks

        proc_tasks = process.xpath(
            f"//*[@id='{core_task.attrib['id']}'][not(ancestor::changepattern)]", namespaces=self.ns)
        if len(proc_tasks) != 1:
            proc_tasks = list(filter(lambda x: utils.get_label(etree.tostring(
                core_task)) == utils.get_label(etree.tostring(x)), proc_tasks))
            if len(proc_tasks) > 1:
                raise ProcessError(f"Task identifier + label is not unique for task \
                                   {utils.get_label(etree.tostring(core_task)), core_task.attrib}")
            elif len(proc_tasks) == 0:
                raise ProcessError(f"Task identifier + label do not exist \
                                   {utils.get_label(etree.tostring(core_task)), core_task.attrib}. \
                                    Are you trying to allocate a deleted resource?")
        if all: 
            return proc_tasks
        else:
            return proc_tasks[0]

    def add_res_allocation(self, task, branch):
        """ Ads the resources & expetec times of a branch to the RA-PST_instance
        
        Parameters: 
        task (etree.Element): Task from RA-PST that is allocated
        branch (etree.Element): Branchnode that is allocated to task

        Returns: 
        directly applies to RA-PST
        """

        self.ns = {'cpee1': list(task.nsmap.values())[
            0], "allo": "http://cpee.org/ns/allocation"}

        branch = copy.deepcopy(branch)
        if not task.xpath("cpee1:allocation", namespaces=self.ns):
            allocation_element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}allocation")
        else:
            allocation_element=task.xpath("cpee1:allocation", namespaces=self.ns)[0]

        # Removes children elements that are not direct childs of task
        if branch.xpath("descendant::cpee1:children[not(child::*)]", namespaces=self.ns):
            tree_part_to_delete = branch.xpath("descendant::cpee1:children[(ancestor::cpee1:children)]", namespaces=self.ns)[0]
            branch.xpath("cpee1:children/cpee1:resource/cpee1:resprofile/*",
                         namespaces=self.ns).remove(tree_part_to_delete)
        
        # Add resource to task
        resource = branch.xpath(
            "cpee1:children/cpee1:resource", namespaces=self.ns)[0]
        allocation_element.append(resource)

        # Set element "allocated resource"
        set_allocation = resource.xpath("@name")[0] + " role: " + resource.xpath("*/@role")[
            # add ID
            0] + resource.xpath("*/@id")[0] + " resource " + resource.xpath("@id")[0]
        task.xpath("cpee1:resources", namespaces=self.ns)[
            0].set("allocated_to", set_allocation)

        # Set release_time according to branch
        if branch.xpath("cpee1:release_time", namespaces = self.ns):
            if not task.xpath("cpee1:release_time", namespaces=self.ns):
                element = etree.SubElement(task, f"{{{self.ns['cpee1']}}}release_time")
            task.xpath("cpee1:release_time", namespaces=self.ns)[
                0].text = branch.xpath("cpee1:release_time", namespaces=self.ns)[0].text

            # Set "plannedstart" & "plannedend" times from branch
            if not task.xpath("cpee1:expected_start", namespaces=self.ns):
                expected_start, expected_end = branch.xpath("cpee1:expected_start", namespaces=self.ns)[
                    0], branch.xpath("cpee1:expected_end", namespaces=self.ns)[0]
                task.append(expected_start)
                task.append(expected_end)

    def get_next_task_id(self, process):
        """ 
        Finds the next task id for tasks inserted through change patterns
        
        Parameters: 
        process (etree.element): RA-PST

        Returns:
        None: sets directly on process object
        """
        # create unique task_id
        rt_ids = process.xpath("//@id")
        pattern = re.compile(r'rp|r_|a')
        try:
            curr_rp_id = max([int(re.split("\\D", id)[-1])
                             for id in rt_ids if not pattern.search(id)])
        except ValueError:
            # If no id exists
            curr_rp_id = 0

        return str(curr_rp_id + 1)

    def find_earliest_possible_timeslot(self, task, resource):
        """
        Finds the earliest possible timeslot a task can be executed based on the given 
        resource availability from the RA-PST
        
        Parameters: 
        task (etree.element): Task that is allocated
        resource (etree.element): Resource that is allocated
        """
        task_expected_ready = datetime.fromisoformat(task.xpath(
            "cpee1:expectedready", namespaces=self.ns)[0].text)
        
        current_time = str(task_expected_ready) # Fallback if no expectedready exists
        
        blocked_res_timeslots = resource.xpath(
            "cpee1:timeslots/cpee1:slot", namespaces=self.ns)
        
        # Build a matrix 2 x len(blocked_res_timeslots) matrix with all blocked slots
        timeslot_matrix = np.array([[datetime.fromisoformat(timeslot.xpath("cpee1:start", namespaces=self.ns)[0].text), datetime.fromisoformat(
            timeslot.xpath("cpee1:end", namespaces=self.ns)[0].text)] for timeslot in blocked_res_timeslots])
        if not len(timeslot_matrix) > 0:
            timeslot_matrix = np.array([[datetime.fromisoformat(current_time), datetime.fromisoformat(current_time)]])

        # Sort Timeslot Matrix
        timeslot_matrix.sort(axis=0)

        task_expected_ready = datetime.fromisoformat(task.xpath(
            "cpee1:expectedready", namespaces=self.ns)[0].text)

        # Find earliest resource slot available
        duration = timedelta(hours=float(resource.xpath(
            "cpee1:resprofile/cpee1:measures/cpee1:cost", namespaces=self.ns)[0].text))
        open_timeslots = np.roll(timeslot_matrix, 1) # open_timeslots
        open_timeslots[0, 0] = datetime.fromisoformat(current_time)
        possible_slots = np.argwhere(np.diff(
            open_timeslots) >= duration)
        possible_slots = open_timeslots[possible_slots[:,:1].flatten()]

        # if no possible_slot is available, just append at the end
        if len(possible_slots) > 0 and possible_slots.flatten()[0] > datetime.fromisoformat(current_time):
            planned_start_time = possible_slots.flatten()[0]
        else:
            planned_start_time = timeslot_matrix[-1][-1] if timeslot_matrix[-1][-1] >= task_expected_ready else task_expected_ready

        # apply times to task objects:
        planned_start_element = etree.Element(
            f"{{{self.ns['cpee1']}}}plannedstart")
        planned_start_element.text = planned_start_time.strftime('%Y-%m-%dT%H:%M:%S')
        planned_end_element = etree.Element(
            f"{{{self.ns['cpee1']}}}plannedend")
        planned_end_element.text = (planned_start_time+duration).strftime('%Y-%m-%dT%H:%M:%S')
        if len(planned_end_element.text) == 0:
            raise ValueError
        
        # apply times to resource objects
        slot_element, start_element, end_element = etree.Element(f"{{{self.ns['cpee1']}}}slot"), etree.Element(
            f"{{{self.ns['cpee1']}}}start"), etree.Element(f"{{{self.ns['cpee1']}}}end")
        start_element.text, end_element.text = str(
            planned_start_time), str(planned_start_time+duration)
        slot_element.append(start_element)
        slot_element.append(end_element)
        resource_element = resource.xpath(
            "cpee1:timeslots", namespaces=self.ns)

        if resource_element:
            resource_element.append(slot_element)

        else:
            resource_element = resource
            resource_element.append(etree.Element(
                f"{{{self.ns['cpee1']}}}timeslots"))
            timeslots_element = resource.xpath(
                "cpee1:timeslots", namespaces=self.ns)
            timeslots_element.append(slot_element)

        self.set_times_for_following_tasks(task, planned_start_time, duration)
        return (planned_start_element, planned_end_element)

    def set_times_for_following_tasks(self, task, planned_start_time, duration):
        task = task.xpath("following-sibling::*")
        if not task:
            return
        else:
            task = task[0]

        if task.tag in [f"{{{self.ns['cpee1']}}}choose", f"{{{self.ns['cpee1']}}}parallel"]:
            # call recursive for everything within the choose/parallel
            for child in task.xpath("child::*"):
                if child.xpath("child::*"):
                    task = child.xpath(
                        "child::*[self::cpee1:manipulate or self::cpee1:call]", namespaces=self.ns)[0]
                    if task.tag not in [f"{{{self.ns['cpee1']}}}choose", f"{{{self.ns['cpee1']}}}parallel"]:
                        self.set_expectedready(
                            task, planned_start_time, duration)
                    return self.set_times_for_following_tasks(task, planned_start_time, duration)

        else:
            self.set_expectedready(task, planned_start_time, duration)

        self.set_times_for_following_tasks(task, planned_start_time, duration)

    def set_expectedready(self, task, planned_start_time, duration):
        if task.xpath("cpee1:expectedready", namespaces=self.ns):
            task.xpath("cpee1:expectedready", namespaces=self.ns)[
                0].text = str(planned_start_time+duration)
        else:
            element = etree.Element(f"{{{self.ns['cpee1']}}}expectedready")
            element.text = str(planned_start_time+duration)
            task.append(element)

    def propagate_internal_times(self, tree_node=None, min_exp_ready=None, exp_ready_element=None, times_tuple=None):
        """ 
        For each task in the Branch, propagate the times according to its postition in the final process fragment.
        Insert Before: Shift times of tasks above backwards
        Insert After: Shift times of tasks below backwards
        Insert Parallel: Todo


        Returns:
        exp_ready_element (etree.element): Element with the expected ready time
        times_tuple (tuple): time for plannedstart and plannedend

        returns nothing if finished with a delete pattern
        """
        
        # If label is expected to get deleted, add empty timeslots for all tasks
        if utils.get_label(tree_node) in self.to_del_label:
            exp_ready_elements = tree_node.xpath("//cpee1:expectedready", namespaces=self.ns)
            resource = tree_node.xpath(
                "cpee1:children/cpee1:resource", namespaces=self.ns)[0]            
            times_tuple = self.find_earliest_possible_timeslot(
                tree_node, resource)
            
            for exp_ready_element in exp_ready_elements:
                exp_ready_element.text = min_exp_ready if min_exp_ready else CURRENT_MIN_DATE 

                # Append element with time 0
                for element in times_tuple:
                    element.text= exp_ready_element.text
                    exp_ready_element.xpath("parent::*")[0].append(copy.copy(element))
            return exp_ready_element, times_tuple
        
        next_change_patterns = tree_node.xpath(
            "cpee1:children/cpee1:resource/cpee1:resprofile/cpee1:changepattern", namespaces=self.ns)
        
        # Handling a leaf in the branch. e.g. setting the time
        if not next_change_patterns:

            exp_ready_element = tree_node.xpath(
                "cpee1:expectedready", namespaces=self.ns)[0]
            resource = tree_node.xpath(
                "cpee1:children/cpee1:resource", namespaces=self.ns)[0]
            times_tuple = self.find_earliest_possible_timeslot(
                tree_node, resource)

            for element in times_tuple:
                tree_node.append(element)

            return exp_ready_element, times_tuple

        # Handling change patterns based on their type
        else:
            next_children = tree_node.xpath(
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
                #print(f"Changepattern of type {
                #      change_pattern_type}, and direction {child_direction}")

                if change_pattern_type == "insert":
                    if child_direction == "before":
                        # go one recursive step lower

                        child.xpath("cpee1:expectedready", namespaces=self.ns)[0].text = tree_node.xpath(
                                "cpee1:expectedready", namespaces=self.ns)[0].text

                        exp_ready_element, times_tuple = self.propagate_internal_times(
                            tree_node=child)

                        #if not tree_node.xpath("cpee1:expectedready", namespaces=self.ns):
                        #    tree_node.append(exp_ready_element)
                        child.xpath("cpee1:expectedready", namespaces=self.ns)[
                            0].text = times_tuple[0].text
                        tree_node.xpath("cpee1:expectedready", namespaces=self.ns)[
                            0].text = times_tuple[1].text
                        resource = tree_node.xpath(
                            "cpee1:children/cpee1:resource", namespaces=self.ns)[0]

                        # find times for tree_node
                        times_tuple = self.find_earliest_possible_timeslot(
                            tree_node, resource)
                        
                        for element in times_tuple:
                            tree_node.append(element)

                        # return to branch
                        return exp_ready_element, times_tuple

                    elif child_direction == "after":

                        resource = tree_node.xpath(
                            "cpee1:children/cpee1:resource", namespaces=self.ns)[0]
                        times_tuple = self.find_earliest_possible_timeslot(
                            tree_node, resource)
                        for element in times_tuple:
                            tree_node.append(element)

                        new_min_exp_ready = tree_node.xpath(
                            "cpee1:plannedend", namespaces=self.ns)[0].text
                    
                        if not new_min_exp_ready:
                            raise ValueError
                        child.xpath("cpee1:expectedready", namespaces=self.ns)[
                            0].text = str(new_min_exp_ready)
                        new_min_exp_ready, times_tuple = self.propagate_internal_times(
                            tree_node=child, min_exp_ready=new_min_exp_ready)

                        return new_min_exp_ready, times_tuple

                    elif child_direction == "parallel":

                        # Set earliest possible starttime on both tasks Anchor and Inserted.
                        # Recurse further down if needed
                        anchor = tree_node.xpath("cpee1:expectedready", namespaces=self.ns)[0]
                        if not child.xpath("cpee1:expectedready", namespaces=self.ns):
                            child_exp_ready_element = etree.Element(
                                f"{{{self.ns['cpee1']}}}expectedready")
                            child_exp_ready_element.text = str(anchor.text)
                            child.append(child_exp_ready_element)

                        new_min_exp_ready_element, times_tuple = self.propagate_internal_times(
                            tree_node=child)
                        
                        child_node = child.xpath("cpee1:expectedready", namespaces=self.ns)[0]
                        
                        
                        if datetime.fromisoformat(anchor.text) < datetime.fromisoformat(new_min_exp_ready_element.text):
                            anchor.text = new_min_exp_ready_element.text
                        else:
                            child_node.text = anchor.text
                            new_min_exp_ready = datetime.fromisoformat(anchor.text)        

                        resource = tree_node.xpath(
                            "cpee1:children/cpee1:resource", namespaces=self.ns)[0]
                        times_tuple = self.find_earliest_possible_timeslot(
                                                    tree_node, resource)
                        for element in times_tuple:
                            tree_node.append(element)
                                       

                        return new_min_exp_ready, times_tuple

                    else:
                        print("Direction not implemented")

                elif change_pattern_type == "delete":
                    if child_direction == "any":
                        #print("delete")

                        #if not min_exp_ready:
                        #    tree_node.xpath(
                        #        "cpee1:expectedready", namespaces=self.ns)[0].text = CURRENT_MIN_DATE
                        #else:
                        #tree_node.xpath(
                        #        "cpee1:expectedready", namespaces=self.ns)[0].text = str(min_exp_ready)

                        new_child = tree_node

                        # Identify to del task: 
                        affected_tasks = new_child.xpath("cpee1:children/descendant::cpee1:children/*", namespaces=self.ns)

                        for task in affected_tasks:
                            proc_tasks = self.get_proc_task(self.ra_pst, task, full_rapst=True)
                            for proc_task in proc_tasks:
                                self.to_del_label.append(utils.get_label(etree.tostring(proc_task)))

                        cp_element = new_child.xpath("cpee1:children/cpee1:resource/cpee1:resprofile/cpee1:changepattern", namespaces=self.ns)[0]
                        new_child.xpath("cpee1:children/cpee1:resource/cpee1:resprofile", namespaces=self.ns)[0].remove(cp_element)

                        exp_ready_element, times_tuple = self.propagate_internal_times(tree_node=new_child, min_exp_ready= min_exp_ready)
                        tree_node.xpath("cpee1:expectedready", namespaces=self.ns)[0].text = exp_ready_element.text

                        resource = tree_node.xpath(
                            "cpee1:children/cpee1:resource", namespaces=self.ns)[0]
                        times_tuple = self.find_earliest_possible_timeslot(
                                                    tree_node, resource)
                        #for element in times_tuple:
                        #    tree_node.append(element)

                        return exp_ready_element, times_tuple
                    else:
                        print("Direction not implemented")

                elif change_pattern_type == "replace":
                    
                    child.xpath("cpee1:expectedready", namespaces=self.ns)[
                            0].text = tree_node.xpath("cpee1:expectedready", namespaces=self.ns)[0].text
                    
                    exp_ready_element, times_tuple = self.propagate_internal_times(
                            tree_node=child)
                    
                    tree_node.xpath("cpee1:expectedready", namespaces=self.ns)[0].text = exp_ready_element.text
                    resource = tree_node.xpath(
                            "cpee1:children/cpee1:resource", namespaces=self.ns)[0]
                    times_tuple = self.find_earliest_possible_timeslot(
                                                    tree_node, resource)
                    for element in times_tuple:
                        tree_node.append(element)                 

                    return exp_ready_element, times_tuple
            
            if tree_node.xpath("descendant::cpee1:changepattern/@type", namespaces=self.ns)[0] == "delete":
                # set values for task and resource
                #print("Delete is ok")   
                resource = tree_node.xpath(
                        "cpee1:children/cpee1:resource", namespaces=self.ns)[0]
                times_tuple = self.find_earliest_possible_timeslot(
                                                tree_node, resource)
                for element in times_tuple:
                    tree_node.append(element)                 

                return exp_ready_element, times_tuple
            else:
                print("Invalid branch, no time")
                inval_child = tree_node.xpath("descendant::cpee1:children[not(child::*)]", namespaces=self.ns)[0]
                parent = inval_child.xpath("parent::*")[0]
                exp_ready_element = etree.SubElement(parent, f"{{{self.ns['cpee1']}}}expectedready")
                exp_ready_element.text = tree_node.xpath("cpee1:expectedready", namespaces=self.ns)[0].text
                start_element, end_element = etree.SubElement(tree_node, f"{{{self.ns['cpee1']}}}plannedstart"), etree.SubElement(tree_node, f"{{{self.ns['cpee1']}}}plannedend")
                start_element.text, end_element.text = min_exp_ready, min_exp_ready
                start_element, end_element = etree.SubElement(parent, f"{{{self.ns['cpee1']}}}plannedstart"), etree.SubElement(parent, f"{{{self.ns['cpee1']}}}plannedend")
                start_element.text, end_element.text = min_exp_ready, min_exp_ready

                return exp_ready_element, (start_element, end_element)
            pass
        return


class Insert(ChangeOperation):
    def apply(self, process, core_task: etree.Element, task: etree.Element, branch, earliest_possible_start):
        invalid = False
        process = copy.deepcopy(process)
        # core_task = task.xpath("/*")[0]
        proc_task = self.get_proc_task(process, core_task)

        # create next id for task to insert (changed in branch as well!)
        new_id = "r"+self.get_next_task_id(process)
        task.attrib["id"] = new_id
        task = copy.deepcopy(task)

        match task.attrib["direction"]:
            case "before":
                proc_task.addprevious(task)
            case "after":
                proc_task.addnext(task)
            case "parallel":
                proc_task_parent = proc_task.xpath("parent::*")[0]
                new_parent = CpeeElements().parallel()
                new_parent.xpath("cpee1:parallel_branch", namespaces=self.ns)[
                    0].append(copy.deepcopy(proc_task))
                new_parent.xpath("cpee1:parallel_branch", namespaces=self.ns)[
                    1].append(task)
                proc_task.addnext(new_parent)
                proc_task_parent.remove(proc_task)

        branchtask = copy.deepcopy(task)
        task = self.get_proc_task(process, task)
        try:
            if task.xpath("cpee1:children/*", namespaces=self.ns):
                self.add_res_allocation(
                    task, branchtask)
            else:
                invalid = True
                #raise ChangeOperationError(
                #    "No Resource available. Invalid Allocation")
        except ChangeOperationError:
            # print(inst.__str__())
            invalid = True
        return process, invalid


class Delete(ChangeOperation):

    def apply(self,process, core_task: etree.Element, task: etree.Element, branch, earliest_possible_start):
        invalid = False
        # proc_task= self.get_proc_task(process, core_task)
        proc_task = 1
        match task.attrib["direction"]:
            case "before":
                # TODO:
                # Check if Task is in previous of process
                # Delete Task from Process Tree
                proc_task.addprevious(task)
            case "after":
                # TODO:
                # Check if Task is in following of process
                # Delete Task from Process Tree

                proc_task.addnext(task)
            case "parallel":
                # TODO:
                # Check if Task is in following of process
                # Delete Task from Process Tree
                proc_task_parent = proc_task.xpath("parent::*")[0]
                new_parent = CpeeElements().parallel()
                new_parent.xpath("cpee1:parallel_branch", namespaces=self.ns)[
                    0].append(copy.deepcopy(proc_task))
                new_parent.xpath("cpee1:parallel_branch", namespaces=self.ns)[
                    1].append(copy.deepcopy(task))

                proc_task_parent.append(new_parent)

            case "any":
                # TODO:
                # Check if Task is in process
                # Delete Task from Process Tree
                proc = process.xpath(
                    "//*[not(ancestor::changepattern) and not(ancestor::cpee1:allocation) and not(ancestor::cpee1:children)]", namespaces=self.ns)
                try:
                    to_del_label = utils.get_label(
                        etree.tostring(task)).lower()
                except TypeError as inst:
                    print(inst.__str__())
                    print("The Element Tag of the task is {}".format(
                        inst.args[1]))

                pos_deletes = []
                for x in proc:
                    try:
                        # with open("new_x.xml", "wb") as f:
                        #    f.write(etree.tostring(x))
                        if to_del_label == utils.get_label(etree.tostring(x)).lower():
                            pos_deletes.append(
                                x.xpath("@id", namespaces=self.ns)[0])

                    except TypeError:
                        # print(inst.__str__())
                        pass
                try:
                    if pos_deletes:
                        to_del_id = pos_deletes[0]
                    else:
                        invalid = True
                        return process, invalid
                        raise ChangeOperationError(
                            "No matching task to delete found in Process Model")
                except ChangeOperationError:
                    invalid = True
                    return process, invalid

                to_dels = process.xpath(
                    f"//*[@id='{to_del_id}'][not(ancestor::changepattern) and not(ancestor::cpee1:allocation)and not(ancestor::cpee1:children)]", namespaces=self.ns)

                # TODO Delete Cascade: if to_del has change patterns in allocation, they need to be deleted as well.
                to_del = to_dels[0]
                to_del_parent = to_del.xpath("parent::*")[0]
                to_del_parent.remove(to_del)

                # Delete Cascade:
                for to_del2 in to_del.xpath("cpee1:allocation/resource/resprofile/cpee1:children/*", namespaces=self.ns):
                    to_del2.attrib["type"], to_del2.attrib["direction"] = task.attrib["type"], task.attrib["direction"]
                    process, invalid = Delete().apply(process, core_task, to_del2)

        return process, invalid


def print_node_structure(ns, node, level=0):
    if node.tag == f"{{{ns['cpee1']}}}manipulate":
        print('  ' * level + node.tag + ' ' + str(node.attrib), node)
    for child in node.xpath("*"):
        print_node_structure(ns, child, level + 1)


class Replace(ChangeOperation):
    def apply(self,process, core_task, task, branch, earliest_possible_start):
        invalid = False
        proc_task = self.get_proc_task(process, core_task)
        task.attrib["id"] = "r" + self.get_next_task_id(process)

        # proc_task = self.get_proc_task(process, to_replace)
        proc_task.xpath("parent::*")[0].replace(proc_task, task)

        try:
            if task.xpath("cpee1:children/*", namespaces=self.ns):
                resource_info = copy.deepcopy(task.xpath(
                    "cpee1:children/*", namespaces=self.ns)[0])
                self.add_res_allocation(task, resource_info)
            else:
                raise ChangeOperationError(f"No Resource available for replaced \
                                           {utils.get_label(etree.tostring(task))}. Invalid Allocation")

        except ChangeOperationError:
            invalid = True
        return process, invalid

class CpeeElements():
    ns = dict()

    def __init__(self):
        self.elem_file = os.path.join(os.path.dirname(__file__), "process_descriptions/cpee_elements.xml")
        with open(self.elem_file) as f:
            self.elems_et = etree.fromstring(f.read())
        self.ns = {'cpee1' : list(self.elems_et.nsmap.values())[0]}
        ns = {'cpee1' : list(self.elems_et.nsmap.values())[0]}

        self.task_elements = [f"{{{ns['cpee1']}}}manipulate", f"{{{ns['cpee1']}}}call"]

    def parallel(self):
        return self.elems_et.xpath("cpee1:parallel", namespaces=self.ns)[0]
    
    def exclusive(self):
        return self.elems_et.xpath("cpee1:choose", namespaces=self.ns)[0]

    def call(self):
        return self.elems_et.xpath("cpee1:call", namespaces=self.ns)[0]
    
    def manipulate(self):
        return self.elems_et.xpath("cpee1:manipulate", namespaces=self.ns)[0]
    
def get_allowed_roles(element):
    elem_et = etree.fromstring(element)
    ns = {'cpee1' : list(elem_et.nsmap.values())[0]}
    to_ret = [role.text for role in elem_et.xpath("cpee1:resources/cpee1:resource", namespaces=ns)]
    return to_ret


class ChangeOperationError(Exception):
    "Raised when an Error Occurs during application of a change operation"
    pass


class ResourceAllocationError(Exception):
    "Raised when no fitting resource is available"
    pass


class ProcessError(Exception):
    "Raised when no fitting resource is available"
    pass



