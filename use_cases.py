from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator, AllocationTypeEnum
from src.ra_pst_py.instance import Instance
from src.ra_pst_py.schedule import Schedule
from src.ra_pst_py.core import RA_PST

import copy
import os
from pathlib import Path
import numpy as np

class EvalPipeline():
    def __init__(self):
        self.release_times = [] # required
        self.expected_release_times = []
        self.sim: Simulator

    def setup_simulator(self, ra_pst:RA_PST, allocation_type:AllocationTypeEnum, path_to_dir: os.PathLike | str, release_times: list, expected_release_times: list = []) -> dict:
        # Check for replace pattern: 
        if "replace" in ra_pst.get_ra_pst_etree().xpath("//@type"):
            raise NotImplementedError("Replace pattern not implemented for allocation")
        self.release_times = sorted(release_times)
        self.expected_release_times = sorted(expected_release_times)
        # Instantiate simulator and run
        self.sim = Simulator(schedule_filepath=f"{path_to_dir}.json")
        for i, release_time in enumerate(self.release_times):
            instance = Instance(copy.deepcopy(ra_pst), {}, id=i)
            instance.add_release_time(release_time)
            self.sim.add_instance(instance, allocation_type)

        
        for i, release_time in enumerate(self.expected_release_times):
            instance = Instance(copy.deepcopy(ra_pst), {}, id=i)
            instance.add_release_time(release_time)
            self.sim.add_instance(instance, allocation_type, expected_instance=True)
        
    def run(self, dirpath: os.PathLike, release_times: list, expected_release_times: list = []):

        testsets_dir = Path(dirpath)
        for testset in testsets_dir.iterdir():
            if testset.is_dir():  # Ensure it's a directory
                process_file = testset / "process/BPM_TestSet_20.xml"  # Get the process file
                resources_dir = testset / "resources"  # Get the resources directory
                
                if process_file.is_file() and resources_dir.exists():
                    # Iterate over each file in the resources directory
                    for resource_file in resources_dir.iterdir():
                        if resource_file.is_file() and process_file.is_file():  # Ensure it's a file
                            ra_pst = build_rapst(process_file, resource_file)
                            
                            print(f"Problem Size per Instance: {ra_pst.get_problem_size()}")
                            
                            # Setup Simulator for each allocation_type
                            print(f"Start heuristic allocation of {resource_file.name}")
                            schedule_path = testset / "evaluation" / "heuristic_new" / resource_file.name
                            schedule_path.parent.mkdir(parents=True, exist_ok=True)
                            show_tree_as_graph(ra_pst, output_file=schedule_path, view=False)
                            self.setup_simulator(ra_pst, "heuristic", path_to_dir=schedule_path, release_times=release_times)
                            self.sim.simulate()

                            # Setup Simulator for single instance heuristic
                            print(f"Start single_instance_heuristic allocation of {resource_file.name}")
                            schedule_path = testset / "evaluation" / "single_instance_heuristic" / resource_file.name
                            schedule_path.parent.mkdir(parents=True, exist_ok=True)
                            self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_HEURISTIC, path_to_dir=schedule_path, release_times=release_times)
                            self.sim.simulate()
                            
                            # Setup Simulator for single instance cp
                            print(f"Start single instance CP allocation of {resource_file.name}")
                            schedule_path = testset / "evaluation" / "single_instance_cp_shift" / resource_file.name
                            schedule_path.parent.mkdir(parents=True, exist_ok=True)
                            self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP, path_to_dir=schedule_path, release_times=release_times)
                            self.sim.simulate()
                            """
                            # Setup Simulator for cp replan
                            print(f"Start single instance CP replan allocation of {resource_file.name}")
                            schedule_path = testset / "evaluation" / "single_instance_cp_replan" / resource_file.name
                            schedule_path.parent.mkdir(parents=True, exist_ok=True)
                            self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP_REPLAN, path_to_dir=schedule_path, release_times=release_times)
                            self.sim.simulate()
                            
                            # Setup Simulator for CP_all 
                            print(f"Start all instance CP allocation of {resource_file.name}")
                            schedule_path = testset / "evaluation" / "all_instance_cp_new" / resource_file.name
                            schedule_path.parent.mkdir(parents=True, exist_ok=True)
                            self.setup_simulator(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP, path_to_dir=schedule_path, release_times=release_times)
                            self.sim.simulate()
                            print(f"Finish allocation of {resource_file.name}")
                            
                            
                            print(f"Start all instance CP allocation Warm {resource_file.name}")
                            # Setup Simulator for each allocation_type
                            schedule_path = testset / "evaluation" / "all_instance_cp" / resource_file.name
                            schedule_path.parent.mkdir(parents=True, exist_ok=True)
                            self.setup_simulator(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP_WARM, path_to_dir=schedule_path, release_times=release_times)
                            self.sim.simulate()
                            

                            print(f"Start single instance CP online of {resource_file.name}")
                            # Setup Simulator for each allocation_type
                            schedule_path = testset / "evaluation" / "single_instance_online" / resource_file.name
                            schedule_path.parent.mkdir(parents=True, exist_ok=True)
                            self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP_ONLINE, path_to_dir=schedule_path, release_times=release_times, expected_release_times=expected_release_times)
                            self.sim.simulate()
                            print(f"Finish allocation of {resource_file.name}")
                            """ 

    def print_block():
        pass

def pos_random_normal(mean, sigma):
    x = round(np.random.normal(mean, sigma))
    return(x if x>=0 else pos_random_normal(mean,sigma))


def generate_release_times(num_instances, mean_time_between_instances):
    """
    Generate release times for processes using an exponential distribution.

    Args:
        num_instances (int): The number of process instances to generate.
        mean_time_between_instances (float): The average time between releases (in hours).

    Returns:
        list: Cumulative release times for the process instances (in hours).
    """
    # Sample time intervals from the exponential distribution
    intervals = np.random.exponential(scale=mean_time_between_instances, size=num_instances).round()
    
    # Calculate cumulative release times
    release_times = np.cumsum(intervals)
    release_times = [int(time) for time in release_times]
    return release_times


if __name__ == "__main__":
    #TODO write up a tracker of progress of simulation
    release_times = [0,0,0,0,0,0]
    release_times = generate_release_times(num_instances=10, mean_time_between_instances=3)
    expected_release_times = []
    for release_time in release_times:
        expected_release_times.append(pos_random_normal(release_time, 1))
    expected_release_times = [0,5,8,10,12,15]
    ep = EvalPipeline()
    ep.run("testsets5", release_times, expected_release_times=expected_release_times)
    
"""
if __name__ == "__main__":

    for element in create_full_dir("test_instances/offer_resources"):
        show_tree_as_graph(element["ra_pst"])
    #    run(element["ra_pst"], AllocationTypeEnum.HEURISTIC, element["output_dir_path"])
    #    run(element["ra_pst"], AllocationTypeEnum.SINGLE_INSTANCE_CP , element["output_dir_path"])
    #    run(element["ra_pst"], AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM , element["output_dir_path"])
    #    run(element["ra_pst"], AllocationTypeEnum.ALL_INSTANCE_CP , element["output_dir_path"])

    ra_pst = build_rapst(
        process_file="test_instances/instance_generator_process.xml",
        resource_file="test_instances/instance_generator_resources.xml"
    )
    output_dir_path = "evaluation/paper_process_short_invalids"
    
    #run(ra_pst, AllocationTypeEnum.HEURISTIC, output_dir_path)
    #run(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP , output_dir_path)
    #run(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM , output_dir_path)
    run(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP , output_dir_path)
"""

    

    
    