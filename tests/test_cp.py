from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance
from src.ra_pst_py.brute_force import BruteForceSearch
from src.ra_pst_py.cp_google_or import conf_cp, conf_cp_scheduling
from src.ra_pst_py.cp_docplex import cp_solver, cp_solver_decomposed
from src.ra_pst_py.cp_docplex_decomposed import cp_solver_decomposed_monotone_cuts, cp_solver_decomposed_strengthened_cuts
from src.ra_pst_py.ilp import configuration_ilp

from lxml import etree
import unittest
import json



class CPTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches_sched.xml"
        )


        ilp_rep = self.ra_pst.get_ilp_rep()
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_rep, f, indent=2)
            f.close()
    
    def test_cp(self):
        result = conf_cp("tests/test_data/ilp_rep2.json")
        print([branch for branch in result["branches"] if branch["selected"] == 1])
        print(result["objective"])
        self.assertEqual(result["objective"], 59)
        #show_tree_as_graph(self.ra_pst)

    def test_cp_sched(self):
        #show_tree_as_graph(self.ra_pst)
        result = conf_cp_scheduling("tests/test_data/ilp_rep.json")
        with open("out/cp_result.json", "w") as f:
            json.dump(result, f, indent=2)
        #print([branch for branch in result["branches"] if branch["selected"] == 1])
        #print(result["objective"])
        #self.assertEqual(result["objective"], 59)
        #show_tree_as_graph(self.ra_pst)


class DocplexTest(unittest.TestCase):
    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_plain_fully_synthetic_small.xml"
        )
        self.ra_pst = build_rapst(
            process_file="testsets_decomposed_paper/10_instantArr/process/BPM_TestSet_10.xml",
            resource_file="testsets_decomposed_paper/10_instantArr/resources/simple-10.xml"
        )
        #self.ra_pst = build_rapst(
        #    process_file="testsets_decomposed_paper/10_instantArr/process/BPM_TestSet_2_Clinic.xml",
        #    resource_file="testsets_decomposed_paper/10_instantArr/resources/Clinig_res.xml"
        #)
        self.ra_pst = build_rapst(
            process_file="testsets_decomposed_paper/10_instantArr/process/BPM_TestSet_10.xml",
            resource_file="testsets_decomposed_paper/10_instantArr/resources/(0.6, 0.4, 0.0)-random-3-uniform-resource_based-2-1-10.xml"
        )
        ilp_rep = self.ra_pst.get_ilp_rep()
        ilp_dict = {"instances" : []}
        ilp_dict["instances"].append(ilp_rep)
        ilp_dict["resources"] = ilp_rep["resources"]
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_dict, f, indent=2)
            f.close()
    
    def test_cp(self):
        self.setUp()
        result = cp_solver_decomposed("tests/test_data/ilp_rep.json")
        # print([branch for branch in result["branches"] if branch["selected"] == 1])
        print(result["solution"]["objective"])
        with open("tests/test_data/cp_result.json", "w") as f:
            json.dump(result, f, indent=2)
        self.assertEqual(result["solution"]["objective"], 59)
        #show_tree_as_graph(self.ra_pst)
    
    def test_multiple_cp(self):
        self.setUp()
        ra_psts = {}
        ra_psts["instances"] = []

        for i in range(4):
            ilp_rep = self.ra_pst.get_ilp_rep(instance_id=f'i{i+1}')

            ra_psts["instances"].append(ilp_rep)
        ra_psts["resources"] = ilp_rep["resources"]
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ra_psts, f, indent=2)
        result = cp_solver("tests/test_data/ilp_rep.json", TimeLimit=300)
        # print([branch for branch in result["branches"] if branch["selected"] == 1])
        print(result["solution"]["objective"])
        with open("tests/test_data/cp_result.json", "w") as f:
            json.dump(result, f, indent=2)
    
    def test_multiple_cp_decomposed(self):
        self.setUp()
        ra_psts = {}
        ra_psts["instances"] = []
        show_tree_as_graph(self.ra_pst)
        print(f"Problem Size: {self.ra_pst.get_problem_size()}")
        for i in range(5):
            ilp_rep = self.ra_pst.get_ilp_rep(instance_id=f'i{i+1}')

            ra_psts["instances"].append(ilp_rep)
        ra_psts["resources"] = ilp_rep["resources"]
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ra_psts, f, indent=2)
        result = cp_solver_decomposed_monotone_cuts("tests/test_data/ilp_rep.json", TimeLimit=50)
        print(result["solution"]["objective"])
        with open("tests/test_data/cp_result.json", "w") as f:
            json.dump(result, f, indent=2)
        
        result = cp_solver_decomposed_strengthened_cuts("tests/test_data/ilp_rep.json", TimeLimit=50)
        print(result["solution"]["objective"])
        with open("tests/test_data/cp_result2.json", "w") as f:
            json.dump(result, f, indent=2)


    def test_cp_warmstart(self):
        sched = None
        results = {}
        org_release_times = [0]
        
        # CP Single Instance allocation
        release_times = [0]

        instance = Instance(self.ra_pst, {}, sched)
        task1 = instance.ra_pst.get_tasklist()[0]
        child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
        child.text = str(release_times.pop(0))
        task1 = etree.fromstring(etree.tostring(task1))

        ilp_rep = instance.ra_pst.get_ilp_rep()
        ra_psts = {}
        ra_psts["instances"] = []
        ra_psts["instances"].append(ilp_rep)
        ra_psts["resources"] = ilp_rep["resources"]
    
        with open("tests/test_data/cp_instance.json", "w") as f:
            json.dump(ra_psts, f, indent=2)
           
        #show_tree_as_graph(instance.ra_pst)
        # TODO add new Jobs to existing job file
        warm_start_file = "tests/test_data/cp_warmstart_gen_process.json"
        result1 = cp_solver("tests/test_data/cp_instance.json")
        print("Test with warmstarting")
        result2 = cp_solver("tests/test_data/cp_instance.json", warm_start_file)
        print(f"Time w/o warm_start: {result1['solution']['computing time']}, \n Time w warm_start: {result2['solution']['computing time']}")
        self.assertEqual(result1["solution"]["objective"], 17, "Objective of normal cp is wrong, maybe check used input files")
        self.assertEqual(result2["solution"]["objective"], 17, "Objective of warm_started cp is wrong, maybe check used input files")
        with open("tests/outcome/cp_cold.json", "w") as f:
            json.dump(result1, f, indent=2)
        with open("tests/outcome/cp_warm.json", "w") as f:
            json.dump(result2, f, indent=2)


    def test_ilp(self):
        ilp_rep = self.ra_pst.get_ilp_rep()
        show_tree_as_graph(self.ra_pst)
        with open("test.json" , "w") as f:
            json.dump(ilp_rep, f, indent=2)
        result = configuration_ilp("test.json")
        with open("test.json", "w") as f:
            json.dump(result, f, indent=2)

