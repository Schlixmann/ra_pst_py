# Import modules
from . import utils 
from src.ra_pst_py.change_operations import ChangeOperationError

# Import external packages
from lxml import etree
import uuid
import warnings
import copy
import math
from collections import defaultdict

class RA_PST:
    """
    Holds the allocation of the full process
    self.allocation: dict of {task:TaskAllocation} pairs
    self.solutions: list of all found solutions
    self.ra_pst: The RA-pst as CPEE-Tree. build through self.get_ra_pst
    """

    def __init__(self, process: etree._Element, resource: etree._Element):
        self.id = str(uuid.uuid1())
        self.process = process # The ra_pst process xml
        self.raw_process = copy.copy(process)
        self.resource_url = resource
        self.allocations = {}
        self.solutions = []
        self.ns = {"cpee1": list(self.process.nsmap.values())[0]}
        self.ra_pst:etree._Element = None
        self.solver = None
        self.branches = defaultdict(list)
        self.build_ra_pst()
        self.set_branches()
        self.transformed_items = []
        self.problem_size = math.prod([len([value for value in values if value.is_valid]) for key, values in self.branches.items()])

    def get_ra_pst_str(self) -> str:
        if not self.ra_pst:
            self.build_ra_pst()
        return etree.tostring(self.ra_pst)
    
    def get_ra_pst_etree(self) -> str:
        if not self.ra_pst:
            self.build_ra_pst()
        return self.ra_pst
    
    def get_tasklist(self, attribute:str = None) -> list:
        "Returns list of all Task-Ids in self.ra_pst"
        tasklist = self.ra_pst.xpath("(//cpee1:call|//cpee1:manipulate)[not (ancestor::cpee1:children|ancestor::cpee1:allocation)]", namespaces=self.ns)
        if not attribute:
            return tasklist
        else:
            return [task.attrib[f"{attribute}"] for task in tasklist]
    
    def get_resourcelist(self) -> list:
        "Returns list of all Resource-IDs in self.resource_url"
        tree = self.resource_url
        resources = tree.xpath("//resource[not(descendant::cpee1:changepattern)]", namespaces=self.ns)
        return [resource.attrib["id"] for resource in resources]

    def get_ilp_rep(self, instance_id = 'i1') -> dict:
        """
        Transforms information from RA-PST into a dictionary format suitable for an ILP model.
        Returns:
        {
            "tasks": { 
                taskId: {
                    "branches": [branchId]
                }
            },
            "resources": [resourceId],
            "branches": {
                branchId: {
                    "task": taskId,
                    "jobs": [jobId],
                    "deletes": [taskId],
                    "branchCost": cost
                }
            },
            "jobs": {
                jobId: {
                    "branch": branchId,
                    "resource": resourceId,
                    "cost": cost,
                    "after": [jobId],
                    "instance": instanceId
                }
            }
        }
        """
        instanceId = '1'

        # Get resourcelist from RA_PST
        resourcelist = self.get_resourcelist()

        # Creates defaultdict(lists) for the allocation branches.
        # allocations represented as jobs, precedence inside the branch is from left to right:
        # One task = {task1: [{jobs: [(resource, cost),...], deletes:["id"] }, {jobs:[...], deletes:[]}]}
        branches = defaultdict(list)
        for key, values in self.branches.items():
            for i, branch in enumerate(values):
                #TODO branch.serialize_jobs
                if branch.is_valid:
                    jobs, deletes = branch.get_serialized_jobs(attribute="id")

                    # find task id by label for deletes: 
                    tasklist = self.get_tasklist()
                    deletes = list({task.attrib["id"] for task in tasklist if utils.get_label(task) in deletes})
                    branches[key].append({"jobs":jobs, "deletes": deletes, "branch_no": i})
        # Get tasklist from RA_PST
        tasklist = self.get_tasklist(attribute="id")
        
        temp = {
            "tasks": tasklist,
            "resources": resourcelist,
            "branches": branches
        }

        # Different ilp format
        result = {
            "tasks": {},
            "resources": temp["resources"],
            "branches": {},
            "jobs": {}
        }
        for task in temp["tasks"]:
            result["tasks"][f'{instance_id}-{task}'] = {"branches": []}
            for branch in temp["branches"][task]:
                branchId = f'{instance_id}-{task}-{len(result["branches"])}'
                result["tasks"][f'{instance_id}-{task}']["branches"].append(branchId)
                newBranch = {
                    "task": f'{instance_id}-{task}',
                    "jobs": [],
                    "deletes": branch["deletes"],
                    "branch_no":branch["branch_no"],
                    "branchCost": 0
                }
                previousJob = None
                for job in branch["jobs"]:
                    newJob = {
                        "branch": branchId,
                        "resource": job[0],
                        "cost": float(job[1]),
                        "after": []
                    }
                    if previousJob is not None:
                        newJob["after"].append(previousJob)
                    for b in result["branches"].values():
                        newJob["after"].append(b["jobs"][-1])
                    newBranch["branchCost"] += float(job[1])
                    jobId = f'{instance_id}-{branchId}-{len(result["jobs"])}'
                    newBranch["jobs"].append(jobId)
                    result["jobs"][jobId] = newJob
                    previousJob = jobId
                result["branches"][branchId] = newBranch
        return result
    
    def get_optimized_instance(self, branch_list):
        pass

    def save_ra_pst(self, path: str):
        """
        Saves etree as xml file in path
        """
        tree = etree.ElementTree(self.ra_pst)
        etree.indent(tree, space="\t", level=0)
        tree.write(path)

    def allocate_process(self):
        """
        This method calls the allocation of each task in the process
        """
        self.ns = {
            "cpee1": list(self.process.nsmap.values())[0],
            "ra_pst": "http://cpee.org/ns/ra_pst",
        }

        tasks = self.process.xpath(
            "//cpee1:call|//cpee1:manipulate", namespaces=self.ns
        )
        for task in tasks:
            allocation = TaskAllocation(self, etree.tostring(task))
            allocation.allocate_task(None, self.resource_url)
            self.allocations[task.xpath("@id")[0]] = allocation

    def build_ra_pst(self) -> None:
        """
        Build the RA-pst from self.allocations
        - The Allocation trees are part of the Cpee-Tree und the tag ra_pst
        - if self.allocations = {} -> call self.allocate_process()

        return:
            RA-pst as xml String in CPEE-Tree format.
        """
        if not self.allocations:
            self.allocate_process()

        process = copy.deepcopy(self.process)
        for key, value in self.allocations.items():
            node = process.xpath(
                f"//*[@id='{str(key)}'][not(ancestor::cpee1:children)]",
                namespaces=self.ns,
            )[0]
            node.append(
                value.intermediate_trees[0].xpath("cpee1:children", namespaces=self.ns)[
                    0
                ]
            )  # add allocation tree of task to process
        self.ra_pst = etree.fromstring(etree.tostring(process))

    def set_branches(self):
        tasklist = self.get_tasklist()
        for task in tasklist:
            self.set_branches_for_task(task)
        
    def set_branches_for_task(self, node, branch=None):  
            # node = anchor_task
            # if possible, cache in object?!
            """ 
            Delete Everything from a deepcopied node, which is not part of the new branch
            append branch to self.branches

            params:
            - node: not needed for initialization
            - branch: not needed for initialization
            """

            if node is None:
                # branch = Branch(copy.deepcopy(self.))
                # TODO add based on id of branch 
                self.branches[branch.attrib["id"]].append(branch)
                node = branch.node

            if not branch:
                branch = Branch(copy.deepcopy(node))
                self.branches[node.attrib["id"]].append(branch)
                node = branch.node

            if node.tag == f"{{{self.ns['cpee1']}}}resprofile" or (node.tag == "resprofile"):
                # Delete other resource profiles from branch
                parent = node.xpath("parent::node()", namespaces=self.ns)[0]

                if len(parent.xpath("*", namespaces=self.ns)) > 1:
                    to_remove = [elem for elem in parent.xpath(
                        "child::cpee1:resprofile", namespaces=self.ns) if elem != node]
                    set(map(parent.remove, to_remove))

                # Iter through children
                children = node.xpath("cpee1:children/*", namespaces=self.ns)
                branches = children, [branch for _ in children]

                set(map(self.set_branches_for_task, *branches))

            elif node.tag == f"{{{self.ns['cpee1']}}}resource" or (node.tag == "resource"):
                # Delete other Resources from branch
                parent = node.xpath("parent::node()", namespaces=self.ns)[0]

                if len(parent.xpath("*", namespaces=self.ns)) > 1:
                    to_remove = [elem for elem in parent.xpath(
                        "child::*", namespaces=self.ns) if elem != node]
                    set(map(parent.remove, to_remove))

                # Create a new branch for each resource profile
                children = node.xpath("cpee1:resprofile", namespaces=self.ns)
                branches = [], []

                for i, child in enumerate(children):
                    path = child.getroottree().getpath(child)

                    if i > 0:
                        new_branch = Branch(copy.deepcopy(
                            child.xpath("/*", namespaces=self.ns)[0]))
                        self.branches[new_branch.node.attrib["id"]].append(new_branch)
                        branches[0].append(new_branch.node.xpath(path)[0])                        
                        branches[1].append(new_branch)
                    else:
                        branches[0].append(child)
                        branches[1].append(branch)

                set(map(self.set_branches_for_task, *branches))

            elif node.tag == f"{{{self.ns['cpee1']}}}call" or node.tag == f"{{{self.ns['cpee1']}}}manipulate":
                # Create new branch for each resource
                children = node.xpath("cpee1:children/*", namespaces=self.ns)
                node_type = node.xpath("@type")

                if node_type:
                    if node_type[0] == "delete":
                        branch.open_delete = True

                if not children and node_type[0] != 'delete':
                    # If task has no valid resource allocation, branch is_valid=False
                    branch.is_valid = False

                if not children and node_type[0] == 'delete':
                    # If task must be deleted and an equivalent task is in the core process, the branch is valid
                    task_labels = [utils.get_label(etree.tostring(
                        task)).lower() for task in self.get_tasklist()]
                    del_task = utils.get_label(etree.tostring(node).lower())
                    if del_task not in task_labels:
                        branch.is_valid = False

                branches = [], []
                for i, child in enumerate(children):

                    path = child.getroottree().getpath(child)
                    if i > 0:
                        new_branch = Branch(copy.deepcopy(
                            child.xpath("/*", namespaces=self.ns)[0]))
                        # node exchanged for new_branch.node
                        self.branches[new_branch.node.attrib["id"]].append(new_branch)
                        branches[1].append(new_branch)
                        branches[0].append(new_branch.node.xpath(
                            path, namespaces=self.ns)[0])
                    else:
                        branches[0].append(child)
                        branches[1].append(branch)
                set(map(self.set_branches_for_task, *branches))

            else:
                raise ValueError("cpee_allocation_set_branches: Wrong node Type")


class TaskAllocation(RA_PST):
    "Creates the allocation tree for one task in process"

    def __init__(self, parent: RA_PST, task: str, state="initialized") -> None:
        self.parent = parent
        self.process = self.parent.process
        self.task = task
        self.state = state
        self.final_tree = None
        self.intermediate_trees = []  # etree
        self.invalid_branches: bool = False
        self.branches: list = []
        self.lock: bool = False
        self.open_delete = False
        self.ns = self.parent.ns
        self.task_elements = [
            f"{{{self.ns['cpee1']}}}manipulate",
            f"{{{self.ns['cpee1']}}}call",
        ]

    def allocate_task(self, root=None, resource_url: etree = None, excluded=[]):
        """
        Builds the allocation tree for self.task.

        params:
        - root: the task to be allocated (initially = None since first task is self.task)
        - resource_url: resource file as etree (etree)
        - excluded: list, task that are already part of the branch

        returns:
        -root: the allocation tree for self.task
        """

        if root is None:
            root = etree.fromstring(self.task)
            etree.SubElement(root, f"{{{self.ns['cpee1']}}}children")
            self.intermediate_trees.append(
                copy.deepcopy(
                    self.allocate_task(root, resource_url=resource_url, excluded=[root])
                )
            )
            return self.intermediate_trees[0]
        else:
            etree.SubElement(root, f"{{{self.ns['cpee1']}}}children")

        etree.register_namespace("ra_pst", self.ns["ra_pst"])
        res_xml = copy.deepcopy(resource_url)

        # Create Resource Children
        for resource in res_xml.xpath("*"):
            # Delete non fitting profiles
            for profile in resource.xpath("resprofile"):
                etree.SubElement(profile, f"{{{self.ns['cpee1']}}}children")
                if not (
                    utils.get_label(etree.tostring(root).lower())
                    == profile.attrib["task"].lower()
                    and (
                        profile.attrib["role"]
                        in utils.get_allowed_roles(etree.tostring(root))
                        if len(utils.get_allowed_roles(etree.tostring(root))) > 0
                        else True
                    )
                ):
                    resource.remove(profile)

            # Add Resource if it has fitting profiles
            if len(resource.xpath("resprofile", namespaces=self.ns)) > 0:
                root.xpath("cpee1:children", namespaces=self.ns)[0].append(resource)

        # End condition for recursive call
        if (
            len(root.xpath("cpee1:children", namespaces=self.ns)) == 0
        ):  # no task parents exist
            if (
                len(
                    [
                        parent
                        for parent in root.xpath(
                            "ancestor::cpee1:*", namespaces=self.ns
                        )
                        if parent.tag in self.task_elements
                    ]
                )
                == 0
            ):
                warnings.warn("No resource for a core task")
                raise (ResourceError(root))
            else:
                task_parents = [
                    parent
                    for parent in root.xpath("ancestor::cpee1:*", namespaces=self.ns)
                    if parent.tag in self.task_elements
                ]
                task_parent = task_parents[-1]

            if len(task_parent.xpath("cpee1:children/*", namespaces=self.ns)) == 0:
                warnings.warn(
                    "The task can not be allocated due to missing resource availability",
                    ResourceWarning,
                )
                raise (ResourceError(task_parent))
            return root

        # Add next tasks to the tree
        for profile in root.xpath(
            "cpee1:children/resource/resprofile", namespaces=self.ns
        ):
            ex_branch = copy.copy(excluded)

            for change_pattern in profile.xpath("changepattern"):
                cp_tasks = [
                    element
                    for element in change_pattern.xpath(".//*")
                    if element.tag in self.task_elements
                ]
                cp_task_labels = [
                    utils.get_label(etree.tostring(task)).lower() for task in cp_tasks
                ]
                ex_tasks = [
                    utils.get_label(etree.tostring(task)).lower() for task in ex_branch
                ]

                if any(
                    x in ex_tasks or x == utils.get_label(etree.tostring(root))
                    for x in cp_task_labels
                ):
                    # print(f"Break reached, task {\
                    #      [x for x in cp_task_labels if x in ex_tasks]} in excluded")
                    root.xpath(
                        "cpee1:children/resource/resprofile", namespaces=self.ns
                    ).remove(profile)
                    continue

                for task in cp_tasks:
                    attribs = {
                        "type": change_pattern.xpath("@type"),
                        "direction": change_pattern.xpath(
                            "parameters/direction/text()"
                        ),
                    }
                    task.attrib.update(
                        {
                            key: value[0].lower()
                            for key, value in attribs.items()
                            if value
                        }
                    )

                    if change_pattern.xpath("@type")[0].lower() in [
                        "insert",
                        "replace",
                    ]:
                        # generate path to current task
                        path = etree.ElementTree(task.xpath("/*")[0]).getpath(task)
                        # Deepcopy whole tree and re-locate current task
                        task = copy.deepcopy(
                            task.xpath("/*", namespaces=self.ns)[0]
                        ).xpath(path, namespaces=self.ns)[0]
                        ex_branch.append(task)
                        profile.xpath("cpee1:children", namespaces=self.ns)[0].append(
                            self.allocate_task(task, resource_url, excluded=ex_branch)
                        )

                    elif change_pattern.xpath("@type")[0].lower() == "delete":
                        self.lock = True
                        profile.xpath("cpee1:children", namespaces=self.ns)[0].append(
                            task
                        )
                        self.open_delete = True
                        # Branch ends here

                    else:
                        raise ValueError(
                            "Changepattern type not in ['insert', 'replace', 'delete']"
                        )
        return root
    
class Branch():
    def __init__(self, node:etree._Element):
            self.node = node
            self.is_valid = True
            self.ns = {"cpee1": list(self.node.nsmap.values())[
                0], "allo": "http://cpee.org/ns/allocation"}

    def get_serialized_jobs(self, attribute:str=None) -> list:
        """
        Returns the tasks in a branch as jobs (resource, cost) pair. 
        Returns a list of tasklabels which will be deleted
        """
        # TODO: How to deal with deletes? -> do we need to deal with deletes?
        # TODO: Does currently not deal with change fragments/ multiple tasks
        # WARN: ("Not fully implemented. \n Please only use with single change patterns. \n Does not deal with multiple change patterns or change fragments")
        
        try:
            tasklist = self.get_tasklist()
            task = tasklist.pop(0)
            resource = task.xpath("descendant::cpee1:resource[not(parent::cpee1:resources)][1]", namespaces=self.ns)[0]
            cost = resource.xpath("descendant::cpee1:cost[1]", namespaces=self.ns)[0].text
            
            jobs = [(resource.attrib["id"], cost)]
            deletes = []
            current_position = 0
            for task in tasklist:
                if task.attrib["type"] == 'delete':
                    deletes.append(task.attrib["label"])
                    continue
                resource = task.xpath("descendant::cpee1:resource[not(parent::cpee1:resources)][1]", namespaces=self.ns)[0]
                cost = resource.xpath("descendant::cpee1:cost[1]", namespaces=self.ns)[0].text
                if task.attrib["direction"] == "before":
                    jobs.insert(current_position, (resource.attrib["id"], cost))
                
                elif task.attrib["direction"] == "after":
                    new_position = current_position + 1
                    jobs.insert(new_position, (resource.attrib["id"], cost))
                elif task.attrib["direction"] == "parallel":
                    jobs.insert(current_position, (resource.attrib["id"], cost))
                else:
                    raise NotImplementedError(f"This direction has not been implemented {task.attrib['direction']}")
        except IndexError as e:
            raise IndexError(f"{e}. Hint: The branch you're trying to serialize is probably invalid")
        return jobs, deletes

    def check_validity(self):
        self.is_valid = True
        empty_children = self.node.xpath("descendant::cpee1:children[not(*)]", namespaces=self.ns)
        for child in empty_children:
            if child.xpath("preceding-sibling::cpee1:changepattern[not(@type='delete')]", namespaces=self.ns):
                self.is_valid = False
                continue

    def apply_to_process(self, ra_pst, solution=None, next_task=None, earliest_possible_start=None, change_op = None, delete:bool=False) -> etree:
            """
            -> Find task to allocate in process
            -> apply change operations
            """
            ns = {"cpee1" : list(ra_pst.nsmap.values())[0]}
            with open("branch_raw.xml", "wb") as f:
                f.write(etree.tostring(self.node))
            new_node = copy.deepcopy(self.node)
            self.check_validity()

            # Add expectedready to each manipulate / call task, that is in a children node 
            if not new_node.xpath("cpee1:expectedready", namespaces=self.ns):
                        exp_ready_element = etree.SubElement(new_node, f"{{{self.ns['cpee1']}}}expectedready")
                        exp_ready_element.text = str(earliest_possible_start)
            
            for element in new_node.xpath("(//cpee1:manipulate | //cpee1:call)[parent::cpee1:children]", namespaces=self.ns):
                exp_ready_element = etree.SubElement(element, f"{{{self.ns['cpee1']}}}expectedready")

            #change_op.propagate_internal_times(new_node, min_exp_ready=earliest_possible_start)
            self.node=new_node

            # check if all manipulates have planned starts and ends:
            #for element in new_node.xpath("(//cpee1:manipulate | //cpee1:call)[parent::cpee1:children and @type!='delete'][not(//cpee1:to_delete)]", namespaces=self.ns):
            #    TODO deal with deletes!
            #    try:
            #        el = element.xpath("child::cpee1:plannedend", namespaces=self.ns)[0]
            #    except:
            #        raise ValueError(f"{element.tag} Should have a plannedend but doesn't")
            tasks = copy.deepcopy(self.node).xpath("//*[self::cpee1:call or self::cpee1:manipulate][not(ancestor::changepattern) and not(ancestor::cpee1:changepattern)and not(ancestor::cpee1:allocation)]", namespaces=ns)[1:]
            task = change_op.get_proc_task(ra_pst, self.node)
            if delete:
                return ra_pst

            # Allocate resource to anchor task
            if self.node.xpath("cpee1:children/*", namespaces=ns):
                poop = copy.deepcopy(self.node.xpath("cpee1:children/*", namespaces=ns)[0])
                poop.xpath("cpee1:resource/cpee1:resprofile/cpee1:children", namespaces=ns)
                
                change_op.add_res_allocation(task, self.node)

            
            delay_deletes = []
            for task in tasks:
                try:
                    if task.xpath("@type = 'delete'"):
                        delay_deletes.append(task)
                    else:
                        anchor = task.xpath("ancestor::cpee1:manipulate | ancestor::cpee1:call", namespaces=ns)[-1]
                        ra_pst, solution.invalid_branches = change_op.ChangeOperationFactory(ra_pst, anchor, task, self.node, cptype= task.attrib["type"], earliest_possible_start=earliest_possible_start)

                except ChangeOperationError:
                    solution.invalid_branches = True
                    #print(inst.__str__())
                    #print("Solution invalid_branches = True")

            for task in delay_deletes:
                try:
                    anchor = task.xpath("ancestor::cpee1:manipulate | ancestor::cpee1:call", namespaces=ns)[-1]
                    ra_pst, solution.invalid_branches = change_op.ChangeOperationFactory(ra_pst, anchor, task, self.node, cptype= task.attrib["type"], earliest_possible_start=earliest_possible_start)

                except ChangeOperationError:
                    solution.invalid_branches = True
                
            with open("process.xml", "wb") as f: 
                f.write(etree.tostring(ra_pst))
            #print("Checkpoint for application")
            return ra_pst
    
    def get_tasklist(self, attribute=None):
        "Returns list of all Task-Ids in self.ra_pst"
        tasklist = self.node.xpath("(//cpee1:call|//cpee1:manipulate)[not(ancestor::cpee1:changepattern|ancestor::cpee1:allocation)]", namespaces=self.ns)
        if not attribute:
            return tasklist
        else:
            return [task.attrib[f"{attribute}"] for task in tasklist]


class ResourceError(Exception):
    # Exception is raised if no sufficiant allocation for a task can be found for available resources

    def __init__(
        self,
        task,
        message="{} No valid resource allocation can be found for the given set of available resources",
    ):
        self.task = task
        self.message = message.format(utils.get_label(etree.tostring(self.task)))
        super().__init__(self.message)


class ResourceWarning(UserWarning):
    pass
