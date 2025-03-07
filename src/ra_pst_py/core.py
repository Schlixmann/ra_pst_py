# Import modules
from . import utils
from src.ra_pst_py.change_operations import ChangeOperationError, ChangeOperation

# Import external packages
from lxml import etree
import uuid
import warnings
import copy
import math
import numpy as np
import statistics
import itertools
import json
from pathlib import Path
from collections import defaultdict


class RA_PST:
    """
    Holds the allocation of the full process
    self.allocation: dict of {task:TaskAllocation} pairs
    self.solutions: list of all found solutions
    self.ra_pst: The RA-pst as CPEE-Tree. build through self.get_ra_pst
    """

    def __init__(self, process: etree._Element, resource: etree._Element, config:Path=None):
        self.id: str = str(uuid.uuid1())
        self.process: etree._Element = process  # The ra_pst process xml, will be adapted and changed when allocated
        self.raw_process: etree._Element = copy.copy(process)
        self.resource_data: etree._Element = resource
        self.allocations = dict()
        self.solutions = list()
        self.solver = None
        self.branches: dict[list[Branch]] = defaultdict(list)
        if config is None:
            config = Path(__file__).parent / "configs" / "ra_pst_config.json"
            self.config = self._load_config(config)
        else:
            self.config = config if isinstance(config, dict) else self._load_config(config)
        self.ns = self.config.get("namespaces", {"cpee1": list(self.process.nsmap.values())[0]} )
        self.ns_key = self.config.get("ns_key", "cpee1")
        self.rapst_branch = self.config.get("rapst_branch", f"{self.ns_key}:children")
        self.allocation_node = self.config.get("allocation_node", f"{self.ns_key}:allocation")
        self.ra_pst: etree._Element = self.build_ra_pst(self.process) # Will not be changed, holds all branches
        self.set_branches()
        self.transformed_items = []
        self.problem_size = None
        self.flex_factor = None


    def _load_config(self, config:Path) -> dict:
        config = Path(config)
        with open(config, "r") as f:
            return json.load(f)
        
    def get_ra_pst_str(self) -> str:
        if not self.ra_pst:
            self.build_ra_pst()
        return etree.tostring(self.ra_pst)

    def get_ra_pst_etree(self) -> str:
        if self.ra_pst is None:
            self.build_ra_pst()
        return self.ra_pst

    def get_tasklist(self, attribute: str = None) -> list:
        "Returns list of all Task-Ids in self.ra_pst"
        tasklist = self.ra_pst.xpath(
            f"(//cpee1:call|//cpee1:manipulate)[not (ancestor::{self.ns_key}:{self.rapst_branch}|ancestor::{self.allocation_node})]",
            namespaces=self.ns,
        )
        if not attribute:
            return tasklist
        else:
            return [task.attrib[f"{attribute}"] for task in tasklist]

    def get_resourcelist(self) -> list:
        "Returns list of all Resource-IDs in self.resource_data"
        tree = self.resource_data
        resources = tree.xpath(
            "//resource[not(descendant::cpee1:changepattern)]", namespaces=self.ns
        )
        return [resource.attrib["id"] for resource in resources]

    def get_first_release_time(self) -> int:
        " Returns release time of first task "
        first_task = self.get_tasklist()[0]
        # find release_time of first_task
        release_time_element = first_task.xpath("descendant::cpee1:release_time", namespaces=self.ns)
        if release_time_element:
            return int(release_time_element[0].text)
        else: 
            return None
    
    def get_problem_size(self) -> int:
        branches = [
                len([branch for branch in branches if branch.check_validity()])
                for taskId, branches in self.branches.items()
            ]
        size = math.prod(branches)
        return size

    def get_branches(self) -> dict:
        """ Returns self.branches as dict"""
        return self.branches
    
    def get_flex_factor(self):
        """
        Describes the flexibility possible within the RA-PST. 
        Flex_factor = (sum_branches/no_of_tasks) * (1-unevenness)
        unevenness = standard_deviaton branches per task / mean of branches per task

        returns: 
            self.flex_factor: 
        """
        if self.flex_factor is None:
            sum_branches = len([branch for task_branches in self.branches.values() for branch in task_branches  if branch.check_validity()])
            no_of_tasks = len(self.get_tasklist())

            # unevenness_factor = stand. dev. of branches / mean(no of branches)
            mean_branches = sum_branches/no_of_tasks
            std_branches = np.std([len(branches) for task, branches in self.branches.items()])
            unevenness = std_branches/mean_branches if mean_branches > 0 else 0

            self.flex_factor = mean_branches * (1 - unevenness)

        return self.flex_factor
    
    def get_enthropy(self):
        entropy_per_task = {}
        for task, branches in self.branches.items():
            costs_per_branch = [branch.get_branch_costs() for branch in branches if branch.check_validity(ra_pst=self)]
            inverted_costs = 1/np.array(costs_per_branch)
            probabilities = inverted_costs / inverted_costs.sum()
            entropy_per_task[task] = -np.sum(probabilities * np.log(probabilities))
    
        return np.mean(list(entropy_per_task.values()))
    
    def get_resource_tightness(self):
        """"as"""
        resource_list = self.get_resourcelist()
        resource_tree = self.resource_data
        resource_dict = {}
        
        all_available_tasks = []
        # Tasks in RA-PST:
        for branches_p_task in self.branches.values():
            all_available_tasks.extend([branch.get_tasklist() for branch in branches_p_task])
        all_available_tasks = list(itertools.chain(*all_available_tasks))
        all_available_tasks = [utils.get_label(task) for task in all_available_tasks]
        all_available_tasks = list(set(all_available_tasks))
        for resource in resource_list:
            resource_dict[resource] = {}
            resource_dict[resource]["costs"] = [float(cost) for cost in resource_tree.xpath(f"resource[@id='{resource}']/resprofile/measures/cost/text()", namespaces=self.ns)]
            resource_dict[resource]["tasks"] = list(set(resource_tree.xpath(f"resource[@id='{resource}']/resprofile/@task", namespaces=self.ns)))
            resource_dict[resource]["task_proportion"] = len(resource_dict[resource]["tasks"]) / len(all_available_tasks)

        std_costs = np.std([statistics.mean(values["costs"]) for key,values  in resource_dict.items()])
        mean_costs = statistics.mean([statistics.mean(values["costs"]) for key,values  in resource_dict.items()])
        cost_uniform = 1-(std_costs / mean_costs) if mean_costs > 0 else 0
                      

        probabilities = [values["task_proportion"] for resource, values in resource_dict.items()]
        entropy = -sum(p * np.log(p) for p in probabilities if p > 0)
        max_entropy = np.log(len(resource_list))
        usage_distribution = entropy/max_entropy if max_entropy > 0 else 0

        resource_flexibility = cost_uniform * usage_distribution
        return resource_flexibility
    
    def get_avg_cost(self):
        costs = [int(cost) for cost in self.ra_pst.xpath("//cpee1:cost/text()", namespaces=self.ns)]
        return statistics.mean(costs) if len(costs) > 0 else 0 

    def get_ilp_rep(self, instance_id = 'i1') -> dict:
        """
        Transforms information from RA-PST into a dictionary format suitable for an ILP model.
        Returns:
        {   
            "id": instanceId
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
                    "selected": False
                }
            }
        }
        """
        # Get resourcelist from RA_PST
        resourcelist = self.get_resourcelist()

        # Creates defaultdict(lists) for the allocation branches.
        # allocations represented as jobs, precedence inside the branch is from left to right:
        # One task = {task1: [{jobs: [(resource, cost),...], deletes:["id"] }, {jobs:[...], deletes:[]}]}
        branches = defaultdict(list)
        for key, values in self.branches.items():
            for i, branch in enumerate(values):
                # TODO branch.serialize_jobs
                if branch.check_validity():
                    jobs, deletes = branch.get_serialized_jobs(attribute="id")

                    # find task id by label for deletes:
                    tasklist = self.get_tasklist()
                    deletes = list(
                        {
                            task.attrib["id"]
                            for task in tasklist
                            if utils.get_label(task) in deletes
                        }
                    )
                    branches[key].append(
                        {"jobs": jobs, "deletes": deletes, "branch_no": i}
                    )
        # Get tasklist from RA_PST
        tasklist = self.get_tasklist(attribute="id")

        temp = {"tasks": tasklist, "resources": resourcelist, "branches": branches}
        release_time = self.get_first_release_time()
        task_release_dict = {}
        if release_time is not None:
            task_release_dict[tasklist[0]] = release_time
        # Different ilp format
        result = {
            "tasks": {},
            "resources": temp["resources"],
            "branches": {},
            "jobs": {},
        }
        for task in temp["tasks"]:
            result["tasks"][f'{instance_id}-{task}'] = {"branches": []}
            for branch in temp["branches"][task]:
                branchId = f'{instance_id}-{task}-{len(result["branches"])}'
                result["tasks"][f'{instance_id}-{task}']["branches"].append(branchId)

                newBranch = {
                    "task": f'{instance_id}-{task}',
                    "jobs": [],
                    "deletes": [f"{instance_id}-{element}" for element in branch["deletes"]],
                    "branch_no": branch["branch_no"],
                    "branchCost": 0,
                    "release_time": release_time if release_time is not None else 0 
                }
                if task in task_release_dict.keys():
                    newBranch["release_time"] = task_release_dict[task]
                previousJob = None
                for job in branch["jobs"]:
                    newJob = {
                        "branch": branchId,
                        "resource": job[0],
                        "cost": float(job[1]),
                        "after": [],
                        "release_time": release_time if release_time is not None else 0, 
                        "start": None,
                        "selected": False
                    }
                    if previousJob is not None:
                        newJob["after"].append(previousJob)
                    for b in result["branches"].values():
                        newJob["after"].append(b["jobs"][-1])
                    newBranch["branchCost"] += float(job[1])
                    if task in task_release_dict.keys():
                        newJob["release_time"] = task_release_dict[task] 
                    jobId = f'{instance_id}-{branchId}-{len(result["jobs"])}'
                    newBranch["jobs"].append(jobId)
                    result["jobs"][jobId] = newJob
                    previousJob = jobId
                result["branches"][branchId] = newBranch
        result["release_time"] = release_time
        result["instanceId"] = instance_id
        return result

    def save_ra_pst(self, path: str):
        """
        Saves etree as xml file in path
        """
        tree = etree.ElementTree(self.ra_pst)
        etree.indent(tree, space="\t", level=0)
        tree.write(path)

    def allocate_process(self, process):
        """
        This method calls the allocation of each task in the process
        """

        tasks = process.xpath(
            "//cpee1:call|//cpee1:manipulate", namespaces=self.ns
        )
        for task in tasks:
            allocation = TaskAllocation(self, etree.tostring(task))
            allocation.allocate_task(None, self.resource_data)
            self.allocations[task.xpath("@id")[0]] = allocation

    def build_ra_pst(self, process) -> None:
        """
        Build the RA-pst from self.allocations
        - The Allocation trees are part of the Cpee-Tree und the tag ra_pst
        - if self.allocations = {} -> call self.allocate_process()

        return:
            RA-pst as xml String in CPEE-Tree format.
        """
        if not self.allocations:
            self.allocate_process(process)

        process = copy.deepcopy(self.process)
        for key, value in self.allocations.items():
            node = process.xpath(
                f"//*[@id='{str(key)}'][not(ancestor::{self.ns_key}:{self.rapst_branch})]",
                namespaces=self.ns,
            )[0]
            node.append(
                value.intermediate_trees[0].xpath(f'{self.ns_key}:{self.rapst_branch}', namespaces=self.ns)[
                    0
                ]
            )  # add allocation tree of task to process
        #self.ra_pst = etree.fromstring(etree.tostring(process))
        return etree.fromstring(etree.tostring(process))

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
            branch = Branch(copy.deepcopy(node), config=self.config)
            self.branches[node.attrib["id"]].append(branch)
            node = branch.node

        if node.tag == f"{{{self.ns['cpee1']}}}resprofile" or (
            node.tag == "resprofile"
        ):
            # Delete other resource profiles from branch
            parent = node.xpath("parent::node()", namespaces=self.ns)[0]

            if len(parent.xpath("*", namespaces=self.ns)) > 1:
                to_remove = [
                    elem
                    for elem in parent.xpath(
                        "child::cpee1:resprofile", namespaces=self.ns
                    )
                    if elem != node
                ]
                set(map(parent.remove, to_remove))

            # Iter through children
            children = node.xpath(f'{self.ns_key}:{self.rapst_branch}/*', namespaces=self.ns)
            branches = children, [branch for _ in children]

            set(map(self.set_branches_for_task, *branches))

        elif node.tag == f"{{{self.ns['cpee1']}}}resource" or (node.tag == "resource"):
            # Delete other Resources from branch
            parent = node.xpath("parent::node()", namespaces=self.ns)[0]

            if len(parent.xpath("*", namespaces=self.ns)) > 1:
                to_remove = [
                    elem
                    for elem in parent.xpath("child::*", namespaces=self.ns)
                    if elem != node
                ]
                set(map(parent.remove, to_remove))

            # Create a new branch for each resource profile
            children = node.xpath("cpee1:resprofile", namespaces=self.ns)
            branches = [], []

            for i, child in enumerate(children):
                path = child.getroottree().getpath(child)

                if i > 0:
                    new_branch = Branch(
                        copy.deepcopy(child.xpath("/*", namespaces=self.ns)[0]),
                        config=self.config,
                    )
                    self.branches[new_branch.node.attrib["id"]].append(new_branch)
                    branches[0].append(new_branch.node.xpath(path)[0])
                    branches[1].append(new_branch)
                else:
                    branches[0].append(child)
                    branches[1].append(branch)

            set(map(self.set_branches_for_task, *branches))

        elif (
            node.tag == f"{{{self.ns['cpee1']}}}call"
            or node.tag == f"{{{self.ns['cpee1']}}}manipulate"
        ):
            # Create new branch for each resource
            children = node.xpath(f'{self.ns_key}:{self.rapst_branch}/*', namespaces=self.ns)
            node_type = node.xpath("@type")

            if node_type:
                if node_type[0] == "delete":
                    branch.open_delete = True

            if not children and node_type[0] != "delete":
                # If task has no valid resource allocation, branch is_valid=False
                branch.is_valid = False

            if not children and node_type[0] == "delete":
                # If task must be deleted and an equivalent task is in the core process, the branch is valid
                task_labels = [
                    utils.get_label(etree.tostring(task)).lower()
                    for task in self.get_tasklist()
                ]
                del_task = utils.get_label(etree.tostring(node).lower())
                if del_task not in task_labels:
                    branch.is_valid = False

            branches = [], []
            for i, child in enumerate(children):
                path = child.getroottree().getpath(child)
                if i > 0:
                    new_branch = Branch(
                        copy.deepcopy(child.xpath("/*", namespaces=self.ns)[0]),
                        config=self.config,
                    )
                    # node exchanged for new_branch.node
                    self.branches[new_branch.node.attrib["id"]].append(new_branch)
                    branches[1].append(new_branch)
                    branches[0].append(
                        new_branch.node.xpath(path, namespaces=self.ns)[0]
                    )
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
        self.task_elements2 = [
            f"{{{self.ns['cpee1']}}}manipulate",
            f"{{{self.ns['cpee1']}}}call",
        ]  # deprecated
        self.task_elements = [
            "cpee1:manipulate",
            "cpee1:call",
        ]

    def allocate_task(self, root=None, resource_data: etree = None, excluded=[]):
        """
        Builds the allocation tree for self.task.

        params:
        - root: the task to be allocated (initially = None since first task is self.task)
        - resource_data: resource file as etree (etree)
        - excluded: list, task that are already part of the branch

        returns:
        -root: the allocation tree for self.task
        """

        if root is None:
            root = etree.fromstring(self.task)
            self.intermediate_trees.append(
                copy.deepcopy(
                    self.allocate_task(root, resource_data=resource_data, excluded=[root])
                )
            )
            return self.intermediate_trees[0]
        etree.SubElement(root, f"{{{self.ns[f'{self.parent.ns_key}']}}}{self.parent.rapst_branch}")
        res_xml = copy.deepcopy(resource_data)
        self.add_resources_as_children(root, res_xml)

        # Check invalidity, raise error if a process task has no available resource
        if (
            len(root.xpath(f'{self.parent.ns_key}:{self.parent.rapst_branch}/*', namespaces=self.ns)) == 0
        ):  # no task parents exist
            elements_xpath = " | ".join(f"self::{el}" for el in self.task_elements)
            if root.xpath(f"{elements_xpath}", namespaces=self.ns):
                elements_xpath = " | ".join(
                    f"ancestor::{el}" for el in self.task_elements
                )
                if not root.xpath(f"{elements_xpath}", namespaces=self.ns):
                    raise ResourceError(
                        root
                    )  # Error if a Root task has no valid allocation option
                else:
                    label = utils.get_label(etree.tostring(root))
                    warnings.warn(f"No resource for task {label}, Branch is invalid")
            return root

        # Add next tasks to the tree
        for profile in root.xpath(
            f'{self.parent.ns_key}:{self.parent.rapst_branch}/resource/resprofile', namespaces=self.ns
        ):
            ex_branch = copy.copy(excluded)

            for change_pattern in profile.xpath("changepattern"):
                cp_tasks, cp_task_labels, ex_tasks = self.get_tasks_of_changepatterns(
                    change_pattern, ex_branch
                )

                if any(
                    x in ex_tasks or x == utils.get_label(etree.tostring(root))
                    for x in cp_task_labels
                ):
                    root.xpath(
                        f'{self.parent.ns_key}:{self.parent.rapst_branch}/resource/resprofile', namespaces=self.ns
                    ).remove(profile)
                    continue

                for task in cp_tasks:
                    self.update_task_attributes(task, change_pattern)
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
                        profile.xpath(f'{self.parent.ns_key}:{self.parent.rapst_branch}', namespaces=self.ns)[0].append(
                            self.allocate_task(task, resource_data, excluded=ex_branch)
                        )
                    elif change_pattern.xpath("@type")[0].lower() == "delete":
                        self.lock = True
                        profile.xpath(f'{self.parent.ns_key}:{self.parent.rapst_branch}', namespaces=self.ns)[0].append(
                            task
                        )
                        self.open_delete = True
                        # Branch ends here
                    else:
                        raise ValueError(
                            "Changepattern type not in ['insert', 'replace', 'delete']"
                        )
        return root

    def add_resources_as_children(self, root, res_xml):
        # Iterate through all resources
        for resource in res_xml.xpath("*"):
            # Delete non fitting profiles
            for profile in resource.xpath("resprofile"):
                etree.SubElement(profile, f"{{{self.ns[f'{self.parent.ns_key}']}}}{self.parent.rapst_branch}")
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
                root.xpath(f'{self.parent.ns_key}:{self.parent.rapst_branch}', namespaces=self.ns)[0].append(resource)

    def get_tasks_of_changepatterns(self, changepattern, ex_branch):
        # cp_tasks = [element for element in changepattern.xpath(".//*") if element.tag in self.task_elements]  # deprecated
        elements_xpath = " | ".join(f".//{el}" for el in self.task_elements)
        cp_tasks = changepattern.xpath(f".//{elements_xpath}", namespaces=self.ns)
        cp_task_labels = [
            utils.get_label(etree.tostring(task)).lower() for task in cp_tasks
        ]
        ex_tasks = [utils.get_label(etree.tostring(task)).lower() for task in ex_branch]
        return cp_tasks, cp_task_labels, ex_tasks

    def update_task_attributes(self, task, changepattern):
        attribs = {
            "type": changepattern.xpath("@type"),
            "direction": changepattern.xpath("parameters/direction/text()"),
        }
        task.attrib.update(
            {key: value[0].lower() for key, value in attribs.items() if value}
        )


class Branch:
    def __init__(self, node: etree._Element, config:dict):
        #if config is None:
        #    config = Path(__file__).parent / "configs" / "ra_pst_config.json"       
        self.node = node
        self.config = config
        self.ns = self.config.get("namespaces", {"cpee1": list(self.node.nsmap.values())[0]})
        self.ns_key = self.config.get("ns_key", "cpee1")
        self.rapst_branch = self.config.get("rapst_branch", f"{self.ns_key}:children")
        self.allocation_node = self.config.get("allocation_node", f"{self.ns_key}:allocation")
        self.is_valid = True
    
    def _load_config(self, config:Path) -> dict:
        config = Path(config)
        with open(config, "r") as f:
            return json.load(f)

    def get_serialized_jobs(self, attribute: str = None) -> list:
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
            resource = task.xpath(
                "descendant::cpee1:resource[not(parent::cpee1:resources)][1]",
                namespaces=self.ns,
            )[0]
            cost = resource.xpath("descendant::cpee1:cost[1]", namespaces=self.ns)[
                0
            ].text

            jobs = [(resource.attrib["id"], cost)]
            deletes = []
            current_position = 0
            for task in tasklist:
                if task.attrib["type"] == "delete":
                    deletes.append(task.attrib["label"])
                    continue
                resource = task.xpath(
                    "descendant::cpee1:resource[not(parent::cpee1:resources)][1]",
                    namespaces=self.ns,
                )[0]
                cost = resource.xpath("descendant::cpee1:cost[1]", namespaces=self.ns)[
                    0
                ].text
                if task.attrib["direction"] == "before":
                    jobs.insert(current_position, (resource.attrib["id"], cost))

                elif task.attrib["direction"] == "after":
                    new_position = current_position + 1
                    jobs.insert(new_position, (resource.attrib["id"], cost))
                elif task.attrib["direction"] == "parallel":
                    jobs.insert(current_position, (resource.attrib["id"], cost))
                else:
                    raise NotImplementedError(
                        f"This direction has not been implemented {task.attrib['direction']}"
                    )
        except IndexError as e:
            raise IndexError(
                f"{e}. Hint: The branch you're trying to serialize is probably invalid"
            )
        return jobs, deletes
    
    def get_serialized_tasklist(self) -> list:
        """
        Returns the tasks in a branch following the precedence constraints through inserts.
        """
        # TODO: How to deal with deletes? -> do we need to deal with deletes?
        # TODO: Does currently not deal with change fragments/ multiple tasks
        # WARN: ("Not fully implemented. \n Please only use with single change patterns. \n Does not deal with multiple change patterns or change fragments")

        try:
            tasklist = self.get_tasklist()
            task = tasklist.pop(0)
            jobs = [task]
            current_position = 0
            for task in tasklist:
                if task.attrib["type"] == "delete":
                    continue
                if task.attrib["direction"] == "before":
                    jobs.insert(current_position, task)

                elif task.attrib["direction"] == "after":
                    new_position = current_position + 1
                    jobs.insert(new_position, task)
                elif task.attrib["direction"] == "parallel":
                    jobs.insert(current_position, task)
                else:
                    raise NotImplementedError(
                        f"This direction has not been implemented {task.attrib['direction']}"
                    )
        except IndexError as e:
            raise IndexError(
                f"{e}. Hint: The branch you're trying to serialize is probably invalid"
            )
        return jobs
    
    def get_branch_costs(self, attribute:str = "cost"):
        attributes_list = self.node.xpath(f"//cpee1:resprofile/cpee1:measures/cpee1:{attribute}", namespaces = self.ns)
        return sum([float(element.text) for element in attributes_list])

    def check_validity(self, ra_pst:RA_PST=None) -> bool:
        #TODO if delete task does not exist become invalid.
        self.is_valid = True
        empty_children = self.node.xpath(
            f'descendant::{self.ns_key}:{self.rapst_branch}[not(*)][not(parent::cpee1:resprofile)]',
            namespaces=self.ns,
        )
        for child in empty_children:
            if child.xpath(
                "preceding-sibling::cpee1:changepattern[@type='delete']",
                namespaces=self.ns,
            ):
                if ra_pst is not None:
                    if child.xpath("cpee1:manipulate || cpee1:call", namespaces=self.n)[0].attrib["id"] not in ra_pst.get_tasklist("id"):
                        self.is_valid = False
                # if child.xpath("preceding-sibling::*[not(@type='delete')]", namespaces=self.ns):
                continue
            else:
                self.is_valid = False
                continue
        return self.is_valid

    def apply_to_process_old(
        self,
        ra_pst,
        solution=None,
        next_task=None,
        earliest_possible_start=None,
        change_op=None,
        delete: bool = False,
    ) -> etree:
        """
        -> Find task to allocate in process
        -> apply change operations
        """
        ns = {"cpee1": list(ra_pst.nsmap.values())[0]}
        with open("branch_raw.xml", "wb") as f:
            f.write(etree.tostring(self.node))
        new_node = copy.deepcopy(self.node)
        self.check_validity()

        # Add expectedready to each manipulate / call task, that is in a children node
        # if not new_node.xpath("cpee1:expectedready", namespaces=self.ns):
        #            exp_ready_element = etree.SubElement(new_node, f"{{{self.ns['cpee1']}}}expectedready")
        #            exp_ready_element.text = str(earliest_possible_start)

        for element in new_node.xpath(
            f'(//cpee1:manipulate | //cpee1:call)[parent::{self.ns_key}:{self.rapst_branch}]',
            namespaces=self.ns,
        ):
            exp_ready_element = etree.SubElement(
                element, f"{{{self.ns['cpee1']}}}expectedready"
            )

        # change_op.propagate_internal_times(new_node, min_exp_ready=earliest_possible_start)
        self.node = new_node

        # check if all manipulates have planned starts and ends:
        # for element in new_node.xpath("(//cpee1:manipulate | //cpee1:call)[parent::cpee1:children and @type!='delete'][not(//cpee1:to_delete)]", namespaces=self.ns):
        #    TODO deal with deletes!
        #    try:
        #        el = element.xpath("child::cpee1:plannedend", namespaces=self.ns)[0]
        #    except:
        #        raise ValueError(f"{element.tag} Should have a plannedend but doesn't")
        tasks = copy.deepcopy(self.node).xpath(
            "//*[self::cpee1:call or self::cpee1:manipulate][not(ancestor::changepattern) and not(ancestor::cpee1:changepattern)and not(ancestor::cpee1:allocation)]",
            namespaces=ns,
        )[1:]
        task = change_op.get_proc_task(ra_pst, self.node)
        if delete:
            return ra_pst

        # Allocate resource to anchor task
        if self.node.xpath(f'{self.ns_key}:{self.rapst_branch}/*', namespaces=ns):
            poop = copy.deepcopy(self.node.xpath(f'{self.ns_key}:{self.rapst_branch}/*', namespaces=ns)[0])
            poop.xpath(f'cpee1:resource/cpee1:resprofile/{self.ns_key}:{self.rapst_branch}', namespaces=ns)

            change_op.add_res_allocation(task, self.node)

        delay_deletes = []
        for task in tasks:
            try:
                if task.xpath("@type = 'delete'"):
                    delay_deletes.append(task)
                else:
                    anchor = task.xpath(
                        "ancestor::cpee1:manipulate | ancestor::cpee1:call",
                        namespaces=ns,
                    )[-1]
                    ra_pst, solution.invalid_branches = (
                        change_op.ChangeOperationFactory(
                            ra_pst,
                            anchor,
                            task,
                            self.node,
                            cptype=task.attrib["type"],
                            earliest_possible_start=earliest_possible_start,
                        )
                    )

            except ChangeOperationError:
                solution.invalid_branches = True
                # print(inst.__str__())
                # print("Solution invalid_branches = True")

        for task in delay_deletes:
            try:
                anchor = task.xpath(
                    "ancestor::cpee1:manipulate | ancestor::cpee1:call", namespaces=ns
                )[-1]
                ra_pst, solution.invalid_branches = change_op.ChangeOperationFactory(
                    ra_pst,
                    anchor,
                    task,
                    self.node,
                    cptype=task.attrib["type"],
                    earliest_possible_start=earliest_possible_start,
                )

            except ChangeOperationError:
                solution.invalid_branches = True

        with open("process.xml", "wb") as f:
            f.write(etree.tostring(ra_pst))
        # print("Checkpoint for application")
        return ra_pst
    
    def apply_to_process(
        self,
        instance,
        earliest_possible_start=None,
        delete:bool = False
    ) -> etree: #Should be instance
        """
        -> Find task to allocate in process
        -> apply change operations
        """
        change_operation = ChangeOperation(copy.deepcopy(instance.ra_pst.ra_pst), self.config)
        new_node = copy.deepcopy(self.node)

        for element in new_node.xpath(
            f'(//cpee1:manipulate | //cpee1:call)[parent::{self.ns_key}:{self.rapst_branch}]',
            namespaces=self.ns,
        ):
            exp_ready_element = etree.SubElement(
                element, f"{{{self.ns['cpee1']}}}expectedready"
            )

        tasks = copy.deepcopy(self.node).xpath(
            "//*[self::cpee1:call or self::cpee1:manipulate][not(ancestor::changepattern) and not(ancestor::cpee1:changepattern)and not(ancestor::cpee1:allocation)]",
            namespaces=self.ns,
        )
        
        if delete:
            return instance.ra_pst

        # Allocate resource to anchor task
        if self.node.xpath(f'{self.ns_key}:{self.rapst_branch}/*', namespaces=self.ns):
            task = utils.get_process_task(instance.ra_pst.ra_pst, self.node, ns=self.ns)
            change_operation.add_res_allocation(task, self.node)
            tasks.pop(0)

        delay_deletes = []
        for task in tasks:
            try:
                if task.xpath("@type = 'delete'"):
                    delay_deletes.append(task)
                else:
                    anchor = task.xpath(
                        "ancestor::cpee1:manipulate | ancestor::cpee1:call",
                        namespaces=self.ns,
                    )[-1]
                    instance.ra_pst.ra_pst, invalid = (
                        change_operation.ChangeOperationFactory(
                            instance.ra_pst.ra_pst,
                            anchor,
                            task,
                            self.node,
                            cptype=task.attrib["type"],
                            earliest_possible_start=earliest_possible_start,
                        )
                    )

            except ChangeOperationError:
                instance.invalid_branches = True

        for task in delay_deletes:
            try:
                anchor = task.xpath(
                    "ancestor::cpee1:manipulate | ancestor::cpee1:call", namespaces=self.ns
                )[-1]
                instance.ra_pst.ra_pst, invalid = change_operation.ChangeOperationFactory(
                    instance.ra_pst.ra_pst,
                    anchor,
                    task,
                    self.node,
                    cptype=task.attrib["type"],
                    earliest_possible_start=earliest_possible_start,
                )

            except ChangeOperationError:
                instance.invalid_branches = True

        with open("tmp/process.xml", "wb") as f:
            f.write(etree.tostring(instance.ra_pst.ra_pst))
        return instance.ra_pst

    def get_tasklist(self, attribute=None):
        "Returns list of all Task-Ids in self.ra_pst"
        tasklist = self.node.xpath(
            "(//cpee1:call|//cpee1:manipulate)[not(ancestor::cpee1:changepattern|ancestor::cpee1:allocation)]",
            namespaces=self.ns,
        )
        if not attribute:
            return tasklist
        else:
            return [task.attrib[f"{attribute}"] for task in tasklist]


class ResourceError(Exception):
    # Exception is raised if no sufficiant allocation for a task can be found for available resources

    def __init__(
        self,
        task,
        message="For Task {} no valid resource allocation can be found. RA-PST cannot lead to a possible solution",
    ):
        self.task = task
        self.message = message.format(utils.get_label(etree.tostring(self.task)))
        super().__init__(self.message)
