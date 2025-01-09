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
        ilp_rep = self.ra_pst.get_ilp_rep()
        with open("tests/test_data/ilp_rep.json", "w") as f:
            json.dump(ilp_rep, f, indent=2)
            f.close()
    
    def test_new_sim(self):
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
            instances_to_sim.append(instance)
        
        sim.initialize(instances_to_sim, "heuristic")
        sim.simulate()
        print(f"Schedule:\n {sched.schedule}")
        sched.print_to_cli()
        json.dump(sched.schedule_as_dict(), open("out/schedule.json", "w"), indent=2)
