from src.ra_pst_py.core import RA_PST, ResourceError
from src.ra_pst_py.file_parser import parse_process_file, parse_resource_file
from src.ra_pst_py.instance import Instance

import unittest
from lxml import etree
from collections import defaultdict
import warnings


class CoreTest(unittest.TestCase):

    def test_allocation(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        process = parse_process_file("tests/test_data/test_process.xml")
        resources = parse_resource_file("tests/test_data/test_resource.xml")
        ra_pst = RA_PST(process, resources)
        ra_pst.save_ra_pst("tests/outcome/ra_pst.xml")
        created = etree.parse("tests/outcome/ra_pst.xml")
        self.assertEqual(etree.tostring(created), etree.tostring(target))

    def test_invalid_allocation(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        process = parse_process_file("tests/test_data/test_process_2_tasks.xml")
        resources = parse_resource_file("tests/test_data/test_resource_invalid.xml")
        
        # Expected warning and error messages
        expected_error = "For Task decide_on_proposal no valid resource allocation can be found. RA-PST cannot lead to a possible solution"
        expected_warning = "No resource for task insert_a2, Branch is invalid"
        try:
            with warnings.catch_warnings(record=True) as caught_warnings:
                warnings.simplefilter("always")
                ra_pst = RA_PST(process, resources)
        except ResourceError as e:
            # Check the exception message
            self.assertEqual(
                str(e), 
                expected_error,
                f"Unexpected exception message: {e}"
            )
        # Verify the correct warning was raised
        self.assertTrue(
        any(expected_warning in str(w.message) for w in caught_warnings),
        f"Expected warning '{expected_warning}' not found in: {[str(w.message) for w in caught_warnings]}"
    )

    def test_set_branches_for_task(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        process = parse_process_file("tests/test_data/test_process.xml")
        resources = parse_resource_file("tests/test_data/test_resource.xml")
        ra_pst = RA_PST(process, resources)
        ra_pst.branches = defaultdict(list)
        task = ra_pst.get_tasklist()[0]
        ra_pst.set_branches_for_task(task)
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
        ser_jobs, deletes = branch.get_serialized_jobs()

        self.assertEqual(ser_jobs[0][0], "res_0")
        self.assertEqual(ser_jobs[0][1], "4")
        self.assertEqual(deletes[0], "wait")

    def test_get_branches_ilp(self):
        process = parse_process_file("example_data/test_process_cpee.xml")
        resources = parse_resource_file("example_data/test_resource.xml")

        ra_pst = RA_PST(process, resources)
        # Get tasklist from RA_PST
        tasklist = ra_pst.get_tasklist(attribute="id")

        # Get resourcelist from RA_PST
        resourcelist = ra_pst.get_resourcelist()

        # Get banches in shape
        ilp_branches = ra_pst.get_ilp_rep()
        #ra_pst.save_ra_pst("branches.xml")
        print(ilp_branches["tasks"])
        print(ilp_branches["resources"])
        print(ilp_branches["branches"])



