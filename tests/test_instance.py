from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance
from src.ra_pst_py.schedule import Schedule
from src.ra_pst_py.simulator import Simulator

from lxml import etree
import unittest
import json
import copy
import os

class InstanceTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
            

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

    def test_taskwise_allocation(self):
        instances_to_sim = [self.ra_pst, copy.deepcopy(self.ra_pst)]
        release_times = [0, 23]

        created_instances = []
        for instance in instances_to_sim:
            task1 = instance.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            created_instances.append([instance, "heuristic"])
        instances_to_sim = created_instances
        sim = Simulator()
        sim.initialize(instances_to_sim, "heuristic")
        sched = Schedule()
        for i, task in enumerate(sim.task_queue):
            sched.add_task((11, task[1], 0+ i*10), "r_1", 7+i*7)
        for i, task in enumerate(sim.task_queue):
            sched.add_task((10, task[1], 0+ i*10), "r_5", 10+i*5)
            print(sched.schedule)
        print(sched.get_timeslot_matrix(0, "res1"))

        show_tree_as_graph(self.ra_pst)
        instance = Instance(self.ra_pst, {}, sched)
        while instance.optimal_process is None:
            instance.allocate_next_task()
        print(instance.branches_to_apply)
        print("Times: \t ", instance.times)

        instance.save_optimal_process("out/instance_test.xml")
    
    def test_allocation_options(self):
        """build new ra_pst for all files in tests/test_data/resource_cp_tests. 
        Test allocation on all resource files in folder"""

        for file in os.listdir("tests/test_data/resource_cp_tests"):
            if file.endswith(".xml"):
                ra_pst = build_rapst(
                    process_file="tests/test_data/test_process.xml",
                    resource_file=f"tests/test_data/resource_cp_tests/{file}"
                )
            sched = Schedule()
            instance = Instance(ra_pst, {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(0)
            task1 = etree.fromstring(etree.tostring(task1))
            while instance.optimal_process is None:
                instance.allocate_next_task()
            with open(f"tests/test_comparison_data/taskwise_sched_solution/{str(file)}.json", "r") as f:
                d = json.loads(json.dumps(sched.schedule_as_dict()))
                j = json.load(f)
                self.assertEqual(d, j, f'Error in {str(file)}')
            print(f"{str(file)}")
            sched.print_to_cli()
    
    def  test_allocation_options_w_deletes(self):
        """build new ra_pst for all files in tests/test_data/resource_cp_tests. 
        Test allocation on all resource files in folder"""

        for file in os.listdir("tests/test_data/resource_cp_tests_w_del"):
            if file.endswith(".xml"):
                ra_pst = build_rapst(
                    process_file="tests/test_data/test_process_w_del.xml",
                    resource_file=f"tests/test_data/resource_cp_tests_w_del/{file}"
                )
            sched = Schedule()
            instance = Instance(ra_pst, {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(0)
            task1 = etree.fromstring(etree.tostring(task1))
            while instance.optimal_process is None:
                instance.allocate_next_task()
            with open(f"tests/test_comparison_data/taskwise_sched_solution/{str(file)}.json", "r") as f:
                #json.dump(sched.schedule_as_dict(), f)
                d = json.loads(json.dumps(sched.schedule_as_dict()))
                j = json.load(f)
                self.assertEqual(d, j, f'Error in {str(file)}')
            print(f"{str(file)}")
            sched.print_to_cli()
        
    
    def  test_allocation_options_w_replace(self):
        """build new ra_pst for all files in tests/test_data/resource_cp_tests. 
        Test allocation on all resource files in folder"""

        for file in os.listdir("tests/test_data/resource_cp_tests_w_replace"):
            if file.endswith(".xml"):
                ra_pst = build_rapst(
                    process_file="tests/test_data/test_process_w_replace.xml",
                    resource_file=f"tests/test_data/resource_cp_tests_w_replace/{file}"
                )
            print(f"{str(file)}")
            #show_tree_as_graph(ra_pst)
            sched = Schedule()
            instance = Instance(ra_pst, {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(0)
            task1 = etree.fromstring(etree.tostring(task1))
            while instance.optimal_process is None:
                instance.allocate_next_task()
            with open(f"tests/test_comparison_data/taskwise_sched_solution/{str(file)}.json", "r") as f:
                #json.dump(sched.schedule_as_dict(), f)
                d = json.loads(json.dumps(sched.schedule_as_dict()))
                j = json.load(f)
                self.assertEqual(d, j, f'Error in {str(file)}')
            
            sched.print_to_cli()
            print("done")
    