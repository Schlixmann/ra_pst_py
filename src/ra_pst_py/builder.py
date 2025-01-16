from .core import RA_PST
from .graphix import TreeGraph
from .file_parser import parse_process_file, parse_resource_file
from src.ra_pst_py.ilp import configuration_ilp, scheduling_ilp, combined_ilp
from src.ra_pst_py.cp_google_or import conf_cp
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance

import json
import pathlib


def build_rapst(process_file, resource_file) -> RA_PST:
    """Build an RA_PST object from file (str, etree._Element)"""
    process_data = parse_process_file(process_file)
    resource_data = parse_resource_file(resource_file)
    ra_pst = RA_PST(process_data, resource_data)
    return ra_pst


def get_rapst_etree(process_file, resource_file):
    """Returns only etree._Element form of ra_pst"""
    ra_pst = build_rapst(process_file, resource_file)
    return ra_pst.ra_pst


def get_rapst_str(process_file, resource_file):
    """Returns only string form of ra_pst"""
    ra_pst = build_rapst(process_file, resource_file)
    return ra_pst.get_ra_pst_str()


def show_tree_as_graph(ra_pst, format="png", output_file="graphs/output_graph", view=True, res_option="children"):
    """Creates graphical representation from RA-PST description or Object

    Args:
        tree_xml (RA_PST, str, etree._Element, file): Input RA-PST, 
        format (str): Format of resulting graphic
        output_file (str): Path where graphic will be saved
    """
    if type(ra_pst) is RA_PST:
        tree_xml = ra_pst.ra_pst
    else:
        tree_xml = ra_pst
    process_data = parse_process_file(tree_xml)
    graph = TreeGraph()
    graph.show(process_data, format, output_file, view, res_option)


# TODO create representation of RA-PST for Scheduling with ILP or CP
# Returned object should be in the shape of:
# Tasks: [t1, ..., tn]
# Resources: [R1, ..., Rn]
# Branches: [I1[j1..n],..,In[j1..n]]
# Jobs: [j[R1,C],..,j]
def get_ilp_rep(ra_pst: RA_PST):
    if type(ra_pst) is not RA_PST:
        raise TypeError("Input must be an object of RA_PST")

    # Get tasklist from RA_PST
    tasklist = ra_pst.get_tasklist(attribute="id")

    # Get resourcelist from RA_PST
    resourcelist = ra_pst.get_resourcelist()

    # Returns each branch of a task represented as flat list and the
    # allocations represented as jobs, precedence inside the branch is from left to right:
    # One branch = [(resource, cost), (resource, cost), ...]
    # Final structure is: {task1: [[branch1], [branch2]]}
    branches = ra_pst.get_branches_ilp()

    return {
        "tasks": tasklist,
        "resources": resourcelist,
        "branches": branches
    }

def build_optimized_instance(ra_pst:RA_PST, solver:str = "ilp") -> Instance:        
    ilp_rep = ra_pst.get_ilp_rep() 
    pathlib.Path("tmp").mkdir(parents=True, exist_ok=True)
    with open("tmp/ilp_rep.json", "w") as f:
        json.dump(ilp_rep, f, indent=2)
        f.close()
    if solver == "ilp":
        conf_ilp = combined_ilp("tmp/ilp_rep.json")
        with open("out/ilp_result.json", "w") as f:
            json.dump(conf_ilp, f)
    elif solver == "cp":
        conf_ilp = conf_cp("tmp/ilp_rep.json")
    else:
        raise NotImplementedError(f"Specified solver {solver} not implemented.")
    
    branches_to_apply = transform_ilp_to_branches(ra_pst, conf_ilp)
    instance = Instance(ra_pst, branches_to_apply)
    instance.get_optimal_instance()
    return instance

        

