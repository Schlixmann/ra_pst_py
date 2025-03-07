from src.ra_pst_py.instance import transform_ilp_to_branches, Instance
from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator, AllocationTypeEnum

import unittest
import copy
import json

class HeuristicTest(unittest.TestCase):
        
    def test_insert_before(self):
        ra_pst = build_rapst(
            process_file="tests/test_data/test_process_2_tasks.xml",
            resource_file="tests/test_data/resource_cp_tests/insert_before_after.xml",
        )
        #show_tree_as_graph(ra_pst)
        release_times = [0,1,2]
        # Heuristic Single Task allocation
        #show_tree_as_graph(self.ra_pst)
        allocation_type = AllocationTypeEnum.HEURISTIC
        file = f"out/schedule_{str(allocation_type)}.json"
        sim = Simulator(schedule_filepath=file, sigma=0, time_limit=100)
        for i, release_time in enumerate(release_times):
            instance = Instance(copy.deepcopy(ra_pst), {},id=i, release_time=release_time)
            #instance.add_release_time(release_time)
            sim.add_instance(instance, allocation_type)
        sim.simulate()
        with open(file, "r") as f:
            data = json.load(f)
            objective = data["solution"]["objective"]
        print("Objective: ", objective)

        show_tree_as_graph(instance.optimal_process)
        proc = instance.get_optimal_instance_from_schedule(schedule_file=file)
        show_tree_as_graph(proc, res_option="allocation")