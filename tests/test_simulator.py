from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator, AllocationTypeEnum
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
            process_file="test_instances/instance_generator_process.xml",
            resource_file="test_instances/instance_generator_resources.xml"
        )
        ilp_rep = self.ra_pst.get_ilp_rep()
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_rep, f, indent=2)
            f.close()

    def test_single_task_heuristic(self):
        sched = Schedule()
        release_times = [0,1,2]
        # Heuristic Single Task allocation
        show_tree_as_graph(self.ra_pst)
        allocation_type = AllocationTypeEnum.HEURISTIC
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched, id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)

        sim.simulate()
        
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 26
        self.assertEqual(objective, target, "HEURISTIC: The found objective does not match the target value")
    
    def test_single_task_heuristic_new(self):
        release_times = [0]
        # Heuristic Single Task allocation
        show_tree_as_graph(self.ra_pst)
        allocation_type = AllocationTypeEnum.HEURISTIC
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {},id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)

        sim.simulate()
        
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 26
        self.assertEqual(objective, target, "HEURISTIC: The found objective does not match the target value")

    def test_multiinstance_cp_sim(self):

        sched = Schedule()

        release_times = [0,1,2]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.ALL_INSTANCE_CP
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched, id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 21
        self.assertEqual(objective, target, "ALL_INSTANCE_CP: The found objective does not match the target value")
    
    def test_multiinstance_cp_sim_warm(self):
        release_times = [0,1,2]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.ALL_INSTANCE_CP_WARM
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 21
        self.assertEqual(objective, target, "ALL_INSTANCE_CP: The found objective does not match the target value")
        
    def test_single_instance_sim(self):
        sched = Schedule()
        
        release_times = [0,1,2]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched, id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)

        start = time.time()
        sim.simulate()
        end = time.time()
        print("Elapsed time: ", end-start)
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 23
        self.assertEqual(objective, target, "SINGLE_INSTANCE_CP: The found objective does not match the target value")

    def test_warmstart_single_instance_sim(self):
        release_times = [0,1,2]
        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)

        start = time.time()
        sim.simulate()
        end = time.time()
        print("Elapsed time: ", end-start)
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 23
        self.assertEqual(objective, target, "SINGLE_INSTANCE_CP: The found objective does not match the target value")

    """
    def test_all_three_types(self):
        sched = Schedule()      
        release_times = [0,1,2]

        # Heuristic Single Task allocation
        allocation_type = AllocationTypeEnum.HEURISTIC
        sim = Simulator(schedule_filepath=f"out/schedule_{str(allocation_type)}.json")
        file = f"out/schedule_{str(allocation_type)}.json"
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched, id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 26
        self.assertEqual(objective, target, "HEURISTIC: The found objective does not match the target value")
        
        # Single-Instance Task allocation
        print("SINGLE_INSTANCE_CP started")
        allocation_type = AllocationTypeEnum.SINGLE_INSTANCE_CP
        sim = Simulator(schedule_filepath=f"out/schedule_{str(allocation_type)}.json")
        file = f"out/schedule_{str(allocation_type)}.json"
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched, id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 23
        self.assertEqual(objective, target, "SINGLE_INSTANCE_CP: The found objective does not match the target value")
    
        # CP Multi Instance allocation
        print("All_INSTANCE_CP started")
        allocation_type = AllocationTypeEnum.ALL_INSTANCE_CP
        sim = Simulator(schedule_filepath=f"out/schedule_{str(allocation_type)}.json")
        file = f"out/schedule_{str(allocation_type)}.json"
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched, id=i)
            instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        target = 23
        self.assertEqual(objective, target, "ALL_INSTANCE_CP: The found objective does not match the target value")

    """