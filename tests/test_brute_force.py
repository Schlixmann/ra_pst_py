from src.ra_pst_py.builder import build_rapst
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance
from src.ra_pst_py.brute_force import BruteForceSearch

from lxml import etree
import unittest
import json



class BruteForceTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
        with open("out/ilp4_result.json", "r") as f:
            self.ilp_rep = json.load(f)
        self.search = BruteForceSearch(self.ra_pst)
    
    def test_get_all_opts(self):
        all_options = self.search.get_all_branch_combinations()
        self.assertEqual(len(all_options), self.search.solution_space_size)

    def test_find_solutions(self):
        all_options = self.search.get_all_branch_combinations()
        results = self.search.find_solutions(all_options)
        print(results[-1])
        self.search.save_best_solution_process(top_n = 1)
        #TODO saving and combining pickles
