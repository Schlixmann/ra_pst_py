from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.instance import transform_ilp_to_branches, Instance
from src.ra_pst_py.schedule import Schedule
from src.ra_pst_py.simulator import Simulator

from lxml import etree
import unittest
import json
import copy




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

    def test_taskwise_allocation(self):
        instances_to_sim = [self.ra_pst, copy.deepcopy(self.ra_pst)]
        release_times = [0, 23]

        for instance in instances_to_sim:
            task1 = instance.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
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
        
    