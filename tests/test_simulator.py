from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator
from src.ra_pst_py.heuristic import TaskAllocator
from src.ra_pst_py.instance import Instance
from src.ra_pst_py.schedule import Schedule, print_schedule

from lxml import etree
import unittest
import json
import copy

class ScheduleTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/instance_generator_process.xml",
            resource_file="test_instances/instance_generator_resources.xml"
        )
        self.ra_pst = build_rapst(
            process_file="test_instances/instance_generator_process.xml",
            resource_file="test_instances/instance_generator_resources.xml"
        )
        ilp_rep = self.ra_pst.get_ilp_rep()
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_rep, f, indent=2)
            f.close()
    
    def test_check_homogeneous_allocation_types(self):
        instances_to_sim = []
        sched = Schedule()
        sim = Simulator()
        release_times = [0, 0, 0]
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, "heuristic"])
        
        sim.initialize(instances_to_sim, "heuristic")
        result = sim.check_homogeneous_allocation_types()
        self.assertEqual(result, "heuristic", f"found allocation type {result}, expected 'heuristic'")

        sim = Simulator()
        instances_to_sim.append([instance, "batching_cp"])
        exp_values = set(("heuristic", "batching_cp"))
        expected_error = f"More than one allocation_type among the instances to allocate. Types: {exp_values}"
        try:
            sim.initialize(instances_to_sim, "heuristic")
            result = sim.check_homogeneous_allocation_types()
        except ValueError as e:
            self.assertEqual(
                str(e), 
                expected_error,
                f"Unexpected exception message: {e}"
            )
        instances_to_sim = []
        sched = Schedule()
        sim = Simulator()
        release_times = [0, 0, 0]
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, "cp_all"])
        sim.initialize(instances_to_sim, "heuristic")
        result = sim.check_homogeneous_allocation_types()
        self.assertEqual(result, "cp_all", f"found allocation type {result}, expected 'heuristic'")

    def test_new_sim(self):
        instances_to_sim = []
        sched = Schedule()
        sim = Simulator()
        release_times = [0, 0, 0]
        created_instances = []
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, "heuristic"])

        sim.initialize(instances_to_sim, "heuristic")
        sim.simulate()
        print(f"Schedule:\n {sched.schedule}")
        sched.print_to_cli()
        json.dump(sched.schedule_as_dict(), open("out/schedule.json", "w"), indent=2)

    def test_multiinstance_cp_sim(self):
        instances_to_sim = []
        sched = Schedule()
        sim = Simulator()
        release_times = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        created_instances = []
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, "cp_all"])

        sim.initialize(instances_to_sim, "h")
        sim.simulate()
        
        #print(f"Schedule:\n {sched.schedule}")
        #sched.print_to_cli()
        #json.dump(sched.schedule_as_dict(), open("out/schedule.json", "w"), indent=2)
