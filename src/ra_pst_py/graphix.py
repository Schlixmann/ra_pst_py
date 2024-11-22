import utils

from lxml import etree
import uuid
import os
from graphviz import Source


class TreeGraph:
    def __init__(self):
        self.dot_content = "digraph CallTree {\n"
        self.ns = {"cpee1": "http://cpee.org/ns/description/1.0"}

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
        time = element.xpath("cpee1:timeslots/cpee1:slot/*", namespaces=self.ns)
        if time:
            time = [f"{value.xpath("name()")}: {value.text}" for value in time]
        else:
            time = "free"
        self.dot_content += f'\t"{element.attrib["unid"]}" [label = "{element.attrib["id"]}: {element.attrib["name"]} \n time: \n {time}"]  \t; \n '

    def add_visualization_resprofile(self, element, measure="cost"):
        value = element.xpath(f"cpee1:measures/cpee1:{measure}", namespaces=self.ns)
        if value:
            value = value[0].text

        time = element.xpath(
            "parent::*/cpee1:timeslots/cpee1:slot/*", namespaces=self.ns
        )
        if time:
            time = [f"{value.xpath("name()")}: {value.text}" for value in time]
        else:
            time = "free"
        self.dot_content += f'\t"{element.attrib["unid"]}" [label = "{element.attrib["id"]}: {element.attrib["role"]} \n {element.attrib["name"]} \n {measure} : {value} \n time: {time}" shape=polygon sides=6]\t; \n'

    def add_visualization_task(self, element):
        name = utils.get_label(etree.tostring(element))
        try:
            task_type = element.attrib["type"]
        except:
            task_type = "Core"
        try:
            direction = element.attrib["direction"]
        except:
            direction = "Core"

        # Timing:
        ready_time = element.xpath("cpee1:expectedready", namespaces=self.ns)
        planned_start = element.xpath("cpee1:plannedstart", namespaces=self.ns)
        planned_end = element.xpath("cpee1:plannedend", namespaces=self.ns)
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
            f"{{{self.ns['cpee1']}}}alternative",
            f"{{{self.ns['cpee1']}}}otherwise",
            f"{{{self.ns['cpee1']}}}parallel_branch",
            f"{{{self.ns['cpee1']}}}choose",
            f"{{{self.ns['cpee1']}}}parallel",
        ]:
            children = node.xpath(
                "child::*[self::cpee1:manipulate or self::cpee1:call]",
                namespaces=self.ns,
            )
        else:
            children = node.xpath(f"cpee1:{res_option}/*", namespaces=self.ns)

        if node.tag == f"{{{self.ns['cpee1']}}}description":
            if not branch:
                node.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_root(node)
                for child in node.xpath("child::*", namespaces=self.ns):
                    child.attrib["unid"] = str(uuid.uuid1())
                    if child.tag in [
                        f"{{{self.ns['cpee1']}}}manipulate",
                        f"{{{self.ns['cpee1']}}}call",
                    ]:
                        self.add_visualization_task(child)
                    elif child.tag == f"{{{self.ns['cpee1']}}}choose":
                        self.add_visualization_choose(child)
                    elif child.tag == f"{{{self.ns['cpee1']}}}parallel":
                        self.add_visualization_parallel(child)

                    self.dot_content += self.add_node_to_dot(node, child)
                    self.tree_iter(child, res_option, True)

        elif node.tag == f"{{{self.ns['cpee1']}}}choose":
            for alternative in node.xpath("child::*", namespaces=self.ns):
                alternative.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_root(alternative)

                self.dot_content += self.add_node_to_dot(node, alternative)
                self.tree_iter(alternative, res_option, True)

        elif node.tag in [
            f"{{{self.ns['cpee1']}}}alternative",
            f"{{{self.ns['cpee1']}}}otherwise",
        ]:
            for child in node.xpath(
                "child::*[self::cpee1:manipulate or self::cpee1:call or self::cpee1:choose or self::cpee1:parallel]",
                namespaces=self.ns,
            ):
                child.attrib["unid"] = str(uuid.uuid1())
                if child.tag in [
                    f"{{{self.ns['cpee1']}}}manipulate",
                    f"{{{self.ns['cpee1']}}}call",
                ]:
                    self.add_visualization_task(child)
                elif child.tag == f"{{{self.ns['cpee1']}}}choose":
                    self.add_visualization_choose(child)
                elif child.tag == f"{{{self.ns['cpee1']}}}parallel":
                    self.add_visualization_parallel(child)

                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        elif node.tag == f"{{{self.ns['cpee1']}}}parallel":
            for alternative in node.xpath("child::*", namespaces=self.ns):
                alternative.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_root(alternative)

                self.dot_content += self.add_node_to_dot(node, alternative)
                self.tree_iter(alternative, res_option, True)

        elif node.tag == f"{{{self.ns['cpee1']}}}parallel_branch":
            for child in node.xpath(
                "child::*[self::cpee1:manipulate or self::cpee1:call or self::cpee1:choose or self::cpee1:parallel]",
                namespaces=self.ns,
            ):
                child.attrib["unid"] = str(uuid.uuid1())
                if child.tag in [
                    f"{{{self.ns['cpee1']}}}manipulate",
                    f"{{{self.ns['cpee1']}}}call",
                ]:
                    self.add_visualization_task(child)
                elif child.tag == f"{{{self.ns['cpee1']}}}choose":
                    self.add_visualization_choose(child)
                elif child.tag == f"{{{self.ns['cpee1']}}}parallel":
                    self.add_visualization_parallel(child)

                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        elif (
            node.tag == f"{{{self.ns['cpee1']}}}call"
            or node.tag == f"{{{self.ns['cpee1']}}}manipulate"
        ):
            if not branch:
                node.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_task(node)
                for child in node.xpath(f"cpee1:{res_option}/*", namespaces=self.ns):
                    child.attrib["unid"] = str(uuid.uuid1())

            if len(children) == 0:
                return node

            for child in children:
                child.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_res(child)
                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        elif node.tag == f"{{{self.ns['cpee1']}}}resprofile":
            if not branch:
                node.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_resprofile(node)
                for child in node.xpath("cpee1:children/*", namespaces=self.ns):
                    child.attrib["unid"] = str(uuid.uuid1())

            if len(children) == 0:
                return node

            for child in children:
                child.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_task(child)
                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        elif node.tag == f"{{{self.ns['cpee1']}}}resource":
            if not branch:
                node.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_res(node)
                for child in node.xpath("cpee1:resprofile", namespaces=self.ns):
                    child.attrib["unid"] = str(uuid.uuid1())

            if len(node.xpath("cpee1:resprofile", namespaces=self.ns)) == 0:
                return node

            for child in node.xpath("cpee1:resprofile", namespaces=self.ns):
                child.attrib["unid"] = str(uuid.uuid1())
                self.add_visualization_resprofile(child)
                self.dot_content += self.add_node_to_dot(node, child)
                self.tree_iter(child, res_option, True)

        else:
            raise ("Unknown nodetype")

        return node

    def show(
        self,
        root,
        format="png",
        output_file="graphs/output_graph",
        view=True,
        res_option="children",
    ):
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
