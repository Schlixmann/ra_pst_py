from src.core import RA_PST
from .file_parser import parse_process_file, parse_resource_file

from lxml import etree

def get_rapst(process_file, resource_file):
    process_data = parse_process_file(process_file)
    resource_data = parse_resource_file(resource_file)
    ra_pst = RA_PST(process_data, resource_data)
    ra_pst.allocate_process()
    ra_pst.get_ra_pst()
    return ra_pst

def get_rapst_etree(process_file, resource_file):
    process_data = parse_process_file(process_file)
    resource_data = parse_resource_file(resource_file)
    ra_pst = RA_PST(process_data, resource_data)
    ra_pst.allocate_process()
    ra_pst.get_ra_pst()
    return etree.fromstring(ra_pst.ra_rpst)

def get_rapst_str(process_file, resource_file):
    process_data = parse_process_file(process_file)
    resource_data = parse_resource_file(resource_file)
    ra_pst = RA_PST(process_data, resource_data)
    ra_pst.allocate_process()
    ra_pst.get_ra_pst()
    return ra_pst.ra_rpst