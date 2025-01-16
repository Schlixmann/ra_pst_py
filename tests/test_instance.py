from src.ra_pst_py.builder import build_rapst
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance

from lxml import etree
import unittest
import json



class InstanceTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
        with open("out/ilp4_result.json", "r") as f:
            self.ilp_rep = json.load(f)

    def test_transform_ilp_to_branches(self):        
        branches_to_apply = transform_ilp_to_branches(self.ra_pst, self.ilp_rep)
        # TODO add assertion
        print(branches_to_apply)

    def test_get_optimal_instances(self):
        branches_to_apply = transform_ilp_to_branches(self.ra_pst, self.ilp_rep)
        instance = Instance(self.ra_pst, branches_to_apply)
        instance.get_optimal_instance()

        tree = etree.ElementTree(instance.optimal_process)
        etree.indent(tree, space="\t", level=0)
        tree.write("test.xml")
        
        print(instance.get_measure("cost"))
        print("done")

        
    