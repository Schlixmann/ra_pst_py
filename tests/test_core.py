from src.ra_pst_py.core import RA_PST
from src.ra_pst_py.file_parser import parse_process_file, parse_resource_file

import unittest
from lxml import etree
from collections import defaultdict


class CoreTest(unittest.TestCase):

    def test_allocation(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        process = parse_process_file("tests/test_data/test_process.xml")
        resources = parse_resource_file("tests/test_data/test_resource.xml")
        ra_pst = RA_PST(process, resources)
        ra_pst.save_ra_pst("tests/outcome/ra_pst.xml")
        created = etree.parse("tests/outcome/ra_pst.xml")

        self.assertEqual(etree.tostring(created), etree.tostring(target))

    def test_get_branches_for_task(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        process = parse_process_file("tests/test_data/test_process.xml")
        resources = parse_resource_file("tests/test_data/test_resource.xml")
        ra_pst = RA_PST(process, resources)
        ra_pst.branches = defaultdict(list)
        task = ra_pst.get_tasklist()[0]
        ra_pst.get_branches_for_task(task)
        ra_pst.save_ra_pst("branches.xml")
        self.assertEqual(len(ra_pst.branches["a1"]), 3)

    def test_get_serialized_jobs(self):
        process = parse_process_file("tests/test_data/test_process.xml")
        resources = parse_resource_file("tests/test_data/test_resource.xml")
        ra_pst = RA_PST(process, resources)

        # Get tasklist from RA_PST
        tasklist = ra_pst.get_tasklist(attribute="id")

        # Get resourcelist from RA_PST
        resourcelist = ra_pst.get_resourcelist()

        # Get banches in shape of jobs precedence from left to right
        branch = ra_pst.branches["a1"][1]
        ser_jobs = branch.get_serialized_jobs()

        self.assertEqual(ser_jobs[0][0], "res_0")
        self.assertEqual(ser_jobs[0][1], "4")
        

    def test_get_branches_ilp(self):
        process = parse_process_file("example_data/test_process_cpee.xml")
        resources = parse_resource_file("example_data/test_resource.xml")

        ra_pst = RA_PST(process, resources)
        # Get tasklist from RA_PST
        tasklist = ra_pst.get_tasklist(attribute="id")

        # Get resourcelist from RA_PST
        resourcelist = ra_pst.get_resourcelist()

        # Get banches in shape
        ilp_branches = ra_pst.get_branches_ilp()
        ra_pst.save_ra_pst("branches.xml")
        #print(ilp_branches)
