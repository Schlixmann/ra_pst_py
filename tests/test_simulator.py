from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator
from src.ra_pst_py.heuristic import TaskAllocator
from src.ra_pst_py.instance import Instance
from src.ra_pst_py.schedule import Schedule, print_schedule

from lxml import etree
import unittest
import json
import copy
import time

class ScheduleTest(unittest.TestCase):

    def setUp(self):
        # Initialize shared variables for tests
        self.ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches_sched.xml"
        )
        self.ra_pst = build_rapst(
            process_file="test_instances/instance_generator_process_short.xml",
            resource_file="test_instances/instance_generator_resources.xml"
        )
        ilp_rep = self.ra_pst.get_ilp_rep()
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_rep, f, indent=2)
            f.close()
    
    def test_get_allocation_types(self):
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
        result = sim.get_allocation_types()
        self.assertEqual(result, "heuristic", f"found allocation type {result}, expected 'heuristic'")

        sim = Simulator()
        instances_to_sim.append([instance, "batching_cp"])
        exp_values = set(("heuristic", "batching_cp"))
        expected_error = f"More than one allocation_type among the instances to allocate. Types: {exp_values}"
        try:
            sim.initialize(instances_to_sim, "heuristic")
            result = sim.get_allocation_types()
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
        result = sim.get_allocation_types()
        self.assertEqual(result, "cp_all", f"found allocation type {result}, expected 'heuristic'")

    def test_single_task_heuristic(self):
        instances_to_sim = []
        sched = Schedule()
        sim = Simulator()
        release_times = [0, 50, 0]
        created_instances = []
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, "heuristic"])

        sim.initialize(instances_to_sim)
        sim.simulate()
        #print(f"Schedule:\n {sched.schedule}")
        sched.print_to_cli()
        

    def test_multiinstance_cp_sim(self):
        instances_to_sim = []
        sched = Schedule()
        sim = Simulator()
        release_times = [0, 10, 15, 20, 30]
        created_instances = []
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, "cp_all"])

        sim.initialize(instances_to_sim)
        sim.simulate()
        
        #print(f"Schedule:\n {sched.schedule}")
        #sched.print_to_cli()
        #json.dump(sched.schedule_as_dict(), open("out/schedule.json", "w"), indent=2)
        
    def test_single_instance_sim(self):
        instances_to_sim = []
        sched = Schedule()
        sim = Simulator()
        release_times = [0] #[0, 10, 15, 20, 30]
        created_instances = []
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, "cp_single_instance"])

        show_tree_as_graph(instances_to_sim[0][0].ra_pst)
        sim.initialize(instances_to_sim)
        sim.simulate()
    
    def test_all_three_types(self):               
        sched = Schedule()
        results = {}
        org_release_times = [30,15]

        # Heuristic Single Task allocation
        sim = Simulator()
        instances_to_sim = []
        release_times = copy.copy(org_release_times)
        allocation_type = "heuristic"
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, allocation_type])

        sim.initialize(instances_to_sim, f"out/schedule_{allocation_type}.json")
        start = time.time()
        sim.simulate()
        end = time.time()

        with open(f"out/schedule_{allocation_type}.json") as f:
            jobs = json.load(f)
            results[allocation_type] = {}
            results[allocation_type]["objective"] = jobs["objective"]
            results[allocation_type]["time"] = str(end - start)
            print(f"Objective: {jobs["objective"]}")

        # CP Single Instance allocation
        sim = Simulator()
        instances_to_sim = []
        release_times = copy.copy(org_release_times)
        allocation_type = "cp_single_instance"
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, allocation_type])
        show_tree_as_graph(instance.ra_pst)

        sim.initialize(instances_to_sim, f"out/schedule_{allocation_type}.json")
        start = time.time()
        sim.simulate()
        end = time.time()

        with open(f"out/schedule_{allocation_type}.json") as f:
            jobs = json.load(f)
            results[allocation_type] = {}
            results[allocation_type]["objective"] = jobs["objective"]
            results[allocation_type]["time"] = str(end - start)
            print(f"Objective: {jobs["objective"]}")
    
        # CP Multi Instance allocation
        sim = Simulator()
        instances_to_sim = []
        release_times = copy.copy(org_release_times)
        allocation_type = "cp_all"
        for _  in range(len(release_times)):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append([instance, allocation_type])

        sim.initialize(instances_to_sim, f"out/schedule_{allocation_type}.json")
        start = time.time()
        sim.simulate()
        end = time.time()
        
        with open(f"out/schedule_{allocation_type}.json") as f:
            jobs = json.load(f)
            results[allocation_type] = {}
            results[allocation_type]["objective"] = jobs["objective"]
            results[allocation_type]["time"] = str(end - start)
            print(f"Objective: {jobs["objective"]}")
        
        print(f"Results: {results}")