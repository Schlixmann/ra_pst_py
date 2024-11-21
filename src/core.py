# Import modules
from src import utils

# Import external packages
from lxml import etree
import uuid
import warnings
import copy


class RA_PST:
    """
    Holds the allocation of the full process
    self.allocation: dict of {task:TaskAllocation} pairs
    self.solutions: list of all found solutions
    self.ra_rpst: The RA-RPST as CPEE-Tree. build through self.get_ra_rpst
    """

    def __init__(self, process: etree._Element, resource: etree._Element):
        self.id = str(uuid.uuid1())
        self.process = process
        self.resource_url = resource
        self.allocations = {}
        self.solutions = []
        self.ns = {"cpee1": list(self.process.nsmap.values())[0]}
        self.ra_rpst: str = None
        self.solver = None

    def get_ra_pst(self) -> str:
        if not self.ra_rpst:
            self.build_ra_rpst()
        return self.ra_rpst

    def save_ra_pst(self, path: str):
        """
        Saves etree as xml file in path
        """
        process = self.get_ra_pst()
        tree = etree.ElementTree(etree.fromstring(process))
        etree.indent(tree, space="\t", level=0)
        tree.write(path)

    def allocate_process(self):
        """
        This method calls the allocation of each task in the process
        """
        self.ns = {
            "cpee1": list(self.process.nsmap.values())[0],
            "ra_pst": "http://cpee.org/ns/ra_rpst",
        }

        tasks = self.process.xpath(
            "//cpee1:call|//cpee1:manipulate", namespaces=self.ns
        )
        for task in tasks:
            allocation = TaskAllocation(self, etree.tostring(task))
            allocation.allocate_task(None, self.resource_url)
            self.allocations[task.xpath("@id")[0]] = allocation

    def add_allocation(self, task, output):
        # task.xpath("cpee1:allocation", namespaces=self.ns)[0].append(output)
        pass

    def build_ra_rpst(self) -> None:
        """
        Build the RA-RPST from self.allocations
        - The Allocation trees are part of the Cpee-Tree und the tag ra_rpst
        - if self.allocations = {} -> call self.allocate_process()

        return:
            RA-RPST as xml String in CPEE-Tree format.
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
        self.ra_rpst = etree.tostring(process)

    def print_node_structure(self, node=None, level=0):
        """
        Prints structure of etree.element to cmd
        """
        if node is None:
            node = self.process
        print("  " * level + node.tag)
        for child in node.xpath("*"):
            self.print_node_structure(child, level + 1)


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

    def print_node_structure(self, node, level=0):
        """
        Prints structure of etree.element to cmd
        """
        print("  " * level + node.tag + " " + str(node.attrib))
        for child in node.xpath("*"):
            self.print_node_structure(child, level + 1)


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
