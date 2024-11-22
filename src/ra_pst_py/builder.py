from src.ra_pst_py.core import RA_PST
from src.ra_pst_py.graphix import TreeGraph
from .file_parser import parse_process_file, parse_resource_file

from lxml import etree

def build_rapst(process_file, resource_file):
    process_data = parse_process_file(process_file)
    resource_data = parse_resource_file(resource_file)
    ra_pst = RA_PST(process_data, resource_data)
    ra_pst.get_ra_pst()
    return ra_pst

def get_rapst_etree(process_file, resource_file):
    ra_pst = build_rapst(process_file, resource_file)
    return etree.fromstring(ra_pst.ra_rpst)

def get_rapst_str(process_file, resource_file):
    ra_pst = build_rapst(process_file, resource_file)
    return ra_pst.ra_rpst

def show_tree_as_graph(tree_xml, format="png", output_file="graphs/output_graph", view=True, res_option="children"):
    process_data = parse_process_file(tree_xml)
    graph = TreeGraph()
    graph.show(process_data, format, output_file, view, res_option)
