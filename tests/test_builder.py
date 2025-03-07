from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
import unittest
from lxml import etree

class BuilderTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
        self.ra_pst = build_rapst(
            process_file="tests/test_data/test_process_2_tasks.xml",
            resource_file="tests/test_data/test_resource_entropy.xml"
        )
    
    def test_build_rapst(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        
        ra_pst = build_rapst(process_file="tests/test_data/test_process.xml", resource_file="tests/test_data/test_resource.xml")
        ra_pst.save_ra_pst("tests/outcome/build_ra_pst.xml")
        created = etree.parse("tests/outcome/build_ra_pst.xml")
        show_tree_as_graph(ra_pst)
        self.assertEqual(etree.tostring(created), etree.tostring(target))


    def test_get_ilp_branches(self):
        ra_pst = build_rapst(process_file="tests/test_data/test_process.xml", resource_file="tests/test_data/test_resource.xml")
        
    def test_resource_tightness(self):
        target = etree.parse("tests/test_comparison_data/allocation.xml")
        ra_pst = build_rapst(process_file="testsets/10_generated/process/BPM_TestSet_10.xml", resource_file="testsets/10_generated/resources/(0.6, 0.4, 0.0)-random-3-uniform-normal-10.xml")
        
        show_tree_as_graph(ra_pst)
        tightness = ra_pst.get_resource_tightness()
        print(tightness)
        #ra_pst.save_ra_pst("tests/outcome/build_ra_pst.xml")
        #created = etree.parse("tests/outcome/build_ra_pst.xml")

        #self.assertEqual(etree.tostring(created), etree.tostring(target))

    def test_enthropy(self):
        ra_pst = self.ra_pst
        #show_tree_as_graph(ra_pst)
        print(ra_pst.get_enthropy())

    
    def test_show_tree(self):
        ra_pst = build_rapst(
            process_file="testsets_decomposed_final_8_freeze/5_tasks/process/BPM_TestSet_5.xml",
            resource_file="testsets_decomposed_final_8_freeze/5_tasks/resources/(0.8, 0.2, 0.0)-skill_short_branch-3-early-resource_based-3-1-10.xml"
        )
        print(ra_pst.get_problem_size())
        show_tree_as_graph(ra_pst)