from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance
from src.ra_pst_py.brute_force import BruteForceSearch
from src.ra_pst_py.cp_google_or import conf_cp
from src.ra_pst_py.cp_docplex import cp_solver

from lxml import etree
import unittest
import json



class CPTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
        ilp_rep = self.ra_pst.get_ilp_rep()
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_rep, f, indent=2)
            f.close()
    
    def test_cp(self):
        result = conf_cp("tests/test_data/ilp_rep.json")
        print([branch for branch in result["branches"] if branch["selected"] == 1])
        print(result["objective"])
        self.assertEqual(result["objective"], 59)
        #show_tree_as_graph(self.ra_pst)


class DocplexTest(unittest.TestCase):
    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
        ilp_rep = self.ra_pst.get_ilp_rep()
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_rep, f, indent=2)
    
    def test_cp(self):
        self.setUp()
        result = cp_solver("tests/test_data/ilp_rep.json")
        # print([branch for branch in result["branches"] if branch["selected"] == 1])
        print(result["objective"])
        self.assertEqual(result["objective"], 59)
        #show_tree_as_graph(self.ra_pst)

