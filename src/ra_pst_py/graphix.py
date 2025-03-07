from .utils import get_label

from lxml import etree
import uuid
import os
import json
from pathlib import Path
from graphviz import Source


class TreeGraph:
    def __init__(self, config=None):
        self.dot_content = "digraph CallTree {\n"
        if config is None:
            config = Path(__file__).parent / "configs" / "ra_pst_config.json"
            self.config = self._load_config(config)
        else:
            self.config = config if isinstance(config, dict) else self._load_config(config)

        self.ns = self.config.get("namespaces", {"cpee1": "http://cpee.org/ns/description/1.0"} )
        self.ns_key = self.config.get("ns_key", "cpee1")
        self.rapst_branch = self.config.get("rapst_branch", f"{self.ns_key}:children")
        self.allocation_node = self.config.get("allocation_node", f"{self.ns_key}:allocation")
        
    def _load_config(self, config:Path) -> dict:
        config = Path(config)
        with open(config, "r") as f:
            return json.load(f)

    def add_node_to_dot(self, parent_id, element):
        return f'\t"{parent_id.attrib["unid"]}" -> "{element.attrib["unid"]}"\t ;\n'

    def add_visualization_root(self, element):
        self.dot_content += (
            f'\t"{element.attrib["unid"]}" [label = "{element.tag}"]\t; \n '
        )

    def add_visualization_choose(self, element):
        self.dot_content += (
            f'\t"{element.attrib["unid"]}" [label = "X" shape=diamond] \t; \n '
        )

    def add_visualization_parallel(self, element):
        self.dot_content += (
            f'\t"{element.attrib["unid"]}" [label = "+" shape=diamond]\t; \n '
        )

    def add_visualization_res(self, element):
        time = element.xpath(f"{self.ns_key}:timeslots/{self.ns_key}:slot/*", namespaces=self.ns)
        if time:
            time = [f'{value.xpath("name()")}: {value.text}' for value in time]
        else:
            time = "free"
        self.dot_content += f'\t"{element.attrib["unid"]}" [label = "{element.attrib["id"]}: {element.attrib["name"]} \n time: \n {time}"]  \t; \n '

    def add_visualization_resprofile(self, element, measure="cost"):
        value = element.xpath(f"{self.ns_key}:measures/{self.ns_key}:{measure}", namespaces=self.ns)
        if value:
            value = value[0].text

        time = element.xpath(
            f"parent::*/{self.ns_key}:timeslots/{self.ns_key}:slot/*", namespaces=self.ns
        )
        if time:
            time = [f'{value.xpath("name()")}: {value.text}' for value in time]
        else:
            time = "free"
        self.dot_content += f'\t"{element.attrib["unid"]}" [label = "{element.attrib["id"]}: {element.attrib["role"]} \n {element.attrib["name"]} \n {measure} : {value} \n time: {time}" shape=polygon sides=6]\t; \n'

    def add_visualization_task(self, element):
        name = get_label(etree.tostring(element))
        try:
            task_type = element.attrib["type"]
        except:
            task_type = "Core"
        try:
            direction = element.attrib["direction"]
        except:
            direction = "Core"

        # Timing:
        ready_time = element.xpath(f"{self.ns_key}:expectedready", namespaces=self.ns)
        planned_start = element.xpath(f"{self.ns_key}:plannedstart", namespaces=self.ns)
        planned_end = element.xpath(f"{self.ns_key}:plannedend", namespaces=self.ns)
        try:
            times = {
                "ready": ready_time[0].text,
                "start": planned_start[0].text,
                "end": planned_end[0].text,
            }
        except :
            # Todo missing time error
            # raise ValueError("Missing times for Resource")
            times = {"ready": ready_time, "start": planned_start, "end": planned_end}

        self.dot_content += f'\t"{element.attrib["unid"]}" [label = "{element.attrib["id"]}: {name} \n Type: {task_type} \n Direction: {direction} \n Timing: {times}" shape=rectangle]\t; \n'

    def tree_iter(self, node, res_option, branch=None):
        if node.tag in [
            f"{{{self.ns[f'{self.ns_key}']}}}alternative",
            f"{{{self.ns[f'{self.ns_key}']}}}otherwise",
            f"{{{self.ns[f'{self.ns_key}']}}}parallel_branch",
            f"{{{self.ns[f'{self.ns_key}']}}}choose",
            f"{{{self.ns[f'{self.ns_key}']}}}parallel",
        ]:
            children = node.xpath(
                f"child::*[self::{self.ns_key}:manipulate or self::{self.ns_key}:call]",
                namespaces=self.ns,
            )
        else:
            children = node.xpath(f"{self.ns_key}:{res_option}/*", namespaces=self.ns)

        if node.tag == f"{{{self.ns[f'{self.ns_key}']}}}description":
            if not branch:
                node.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_root(node)
                for child in node.xpath("child::*", namespaces=self.ns):
                    child.attrib["unid"] = str(uuid.uuid1())
                    if child.tag in [
                        f"{{{self.ns[f'{self.ns_key}']}}}manipulate",
                        f"{{{self.ns[f'{self.ns_key}']}}}call",
                    ]:
                        self.add_visualization_task(child)
                    elif child.tag == f"{{{self.ns[f'{self.ns_key}']}}}choose":
                        self.add_visualization_choose(child)
                    elif child.tag == f"{{{self.ns[f'{self.ns_key}']}}}parallel":
                        self.add_visualization_parallel(child)

                    self.dot_content += self.add_node_to_dot(node, child)
                    self.tree_iter(child, res_option, True)

        elif node.tag == f"{{{self.ns[f'{self.ns_key}']}}}choose":
            for alternative in node.xpath("child::*", namespaces=self.ns):
                alternative.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_root(alternative)

                self.dot_content += self.add_node_to_dot(node, alternative)
                self.tree_iter(alternative, res_option, True)

        elif node.tag in [
            f"{{{self.ns[f'{self.ns_key}']}}}alternative",
            f"{{{self.ns[f'{self.ns_key}']}}}otherwise",
        ]:
            for child in node.xpath(
                f"child::*[self::{self.ns_key}:manipulate or self::{self.ns_key}:call or self::{self.ns_key}:choose or self::{self.ns_key}:parallel]",
                namespaces=self.ns,
            ):
                child.attrib["unid"] = str(uuid.uuid1())
                if child.tag in [
                    f"{{{self.ns[f'{self.ns_key}']}}}manipulate",
                    f"{{{self.ns[f'{self.ns_key}']}}}call",
                ]:
                    self.add_visualization_task(child)
                elif child.tag == f"{{{self.ns[f'{self.ns_key}']}}}choose":
                    self.add_visualization_choose(child)
                elif child.tag == f"{{{self.ns[f'{self.ns_key}']}}}parallel":
                    self.add_visualization_parallel(child)

                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        elif node.tag == f"{{{self.ns[f'{self.ns_key}']}}}parallel":
            for alternative in node.xpath("child::*", namespaces=self.ns):
                alternative.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_root(alternative)

                self.dot_content += self.add_node_to_dot(node, alternative)
                self.tree_iter(alternative, res_option, True)

        elif node.tag == f"{{{self.ns[f'{self.ns_key}']}}}parallel_branch":
            for child in node.xpath(
                f"child::*[self::{self.ns_key}:manipulate or self::{self.ns_key}:call or self::{self.ns_key}:choose or self::{self.ns_key}:parallel]",
                namespaces=self.ns,
            ):
                child.attrib["unid"] = str(uuid.uuid1())
                if child.tag in [
                    f"{{{self.ns[f'{self.ns_key}']}}}manipulate",
                    f"{{{self.ns[f'{self.ns_key}']}}}call",
                ]:
                    self.add_visualization_task(child)
                elif child.tag == f"{{{self.ns[f'{self.ns_key}']}}}choose":
                    self.add_visualization_choose(child)
                elif child.tag == f"{{{self.ns[f'{self.ns_key}']}}}parallel":
                    self.add_visualization_parallel(child)

                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        elif (
            node.tag == f"{{{self.ns[f'{self.ns_key}']}}}call"
            or node.tag == f"{{{self.ns[f'{self.ns_key}']}}}manipulate"
        ):
            if not branch:
                node.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_task(node)
                for child in node.xpath(f"{self.ns_key}:{res_option}/*", namespaces=self.ns):
                    child.attrib["unid"] = str(uuid.uuid1())

            if len(children) == 0:
                return node

            for child in children:
                child.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_res(child)
                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        elif node.tag == f"{{{self.ns[f'{self.ns_key}']}}}resprofile":
            if not branch:
                node.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_resprofile(node)
                for child in node.xpath(f"{self.ns_key}:{self.rapst_branch}/*", namespaces=self.ns):
                    child.attrib["unid"] = str(uuid.uuid1())

            if len(children) == 0:
                return node

            for child in children:
                child.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_task(child)
                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        elif node.tag == f"{{{self.ns[f'{self.ns_key}']}}}resource":
            if not branch:
                node.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_res(node)
                for child in node.xpath(f"{self.ns_key}:resprofile", namespaces=self.ns):
                    child.attrib["unid"] = str(uuid.uuid1())

            if len(node.xpath(f"{self.ns_key}:resprofile", namespaces=self.ns)) == 0:
                return node

            for child in node.xpath(f"{self.ns_key}:resprofile", namespaces=self.ns):
                child.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_resprofile(child)
                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        else:
            raise ("Unknown nodetype")

        return node

    def show(
        self,
        root:etree._Element,
        format="png",
        output_file="graphs/output_graph",
        view=True,
        res_option=None,
    ):
        res_option = res_option if res_option else self.rapst_branch
        out_path, out_file = os.path.split(output_file)

        self.tree_iter(root, res_option=res_option)
        self.dot_content += "}\n"

        # Write DOT content to a file (replace 'call_tree.dot' with your desired output_file)
        if not os.path.exists(out_path):
            os.makedirs(out_path)

        with open("graphs/call_tree.dot", "w") as dot_file:
            dot_file.write(self.dot_content)
        source = Source(self.dot_content, filename=f"{out_file}.dot", format=format)
        source.render(
            filename=f"{out_file}", directory=out_path, cleanup=True, view=view
        )


if __name__ == "__main__":
    with open("tests/test_output/graphix_test_rapst.xml", "rb") as f:
        # tree = etree.fromstring(f.read())
        TreeGraph().show(f.read(), output_file="out_new")
