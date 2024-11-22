from src.ra_pst_py.core import RA_PST
from src.ra_pst_py.file_parser import parse_process_file, parse_resource_file

import unittest
from lxml import etree

class CoreTest(unittest.TestCase):
    
    def test_allocation(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        process = parse_process_file("tests/test_data/test_process.xml")
        resources = parse_resource_file("tests/test_data/test_resource.xml")
        ra_pst = RA_PST(process, resources)
        ra_pst.save_ra_pst("tests/outcome/ra_pst.xml")
        created = etree.parse("tests/outcome/ra_pst.xml")

        self.assertEqual(etree.tostring(created), etree.tostring(target))

    def test_branches(self):
        branches = 1

