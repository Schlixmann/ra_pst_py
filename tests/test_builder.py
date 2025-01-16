from src.ra_pst_py.builder import build_rapst
import unittest
from lxml import etree

class BuilderTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
    
    def test_build_rapst(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        ra_pst = build_rapst(process_file="tests/test_data/test_process.xml", resource_file="tests/test_data/test_resource.xml")
        ra_pst.save_ra_pst("tests/outcome/build_ra_pst.xml")
        created = etree.parse("tests/outcome/build_ra_pst.xml")

        self.assertEqual(etree.tostring(created), etree.tostring(target))

    def test_get_ilp_branches(self):
        ra_pst = build_rapst(process_file="tests/test_data/test_process.xml", resource_file="tests/test_data/test_resource.xml")
        
