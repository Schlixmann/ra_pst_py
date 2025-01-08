from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator
from src.ra_pst_py.heuristic import TaskAllocator
from src.ra_pst_py.instance import Instance
from src.ra_pst_py.schedule import Schedule, print_schedule

from lxml import etree
import unittest
import json
import copy


class SimTest(unittest.TestCase):

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
    
    def test_sim(self):
        instances_to_sim = [self.ra_pst, copy.deepcopy(self.ra_pst)]
        release_times = [0, 23]

        for instance in instances_to_sim:
            task1 = instance.get_tasklist()[0]
            child = etree.SubElement(task1, "release_time")
            child.text = str(release_times.pop(0))
        sim = Simulator()
        sim.initialize(instances_to_sim, "heuristic")
        sim.simulate()

class ScheduleTest(unittest.TestCase):

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
    
    def test_sched(self):
        instances_to_sim = []

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

        sim.schedule = sched
        sim.simulate()
        print_schedule(sched.schedule)
        print(sched.schedule)

    
    def test_new_sim(self):
        instances_to_sim = []
        sched = Schedule()
        sim = Simulator()
        release_times = [0, 23]
        for _  in range(2):
            instance = Instance(copy.deepcopy(self.ra_pst), {}, sched)
            task1 = instance.ra_pst.get_tasklist()[0]
            child = etree.SubElement(task1, f"{{{instance.ns['cpee1']}}}release_time")
            child.text = str(release_times.pop(0))
            task1 = etree.fromstring(etree.tostring(task1))
            instances_to_sim.append(instance)
        
        sim.initialize(instances_to_sim, "heuristic")
        sim.simulate()
        print(f"Schedule:\n {sched.schedule}")
        #print_schedule(sched.schedule)
        json.dump(sched.schedule_as_dict(), open("out/schedule.json", "w"), indent=2)
