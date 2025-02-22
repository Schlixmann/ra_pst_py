from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator, AllocationTypeEnum
from src.ra_pst_py.instance import Instance
from src.ra_pst_py.schedule import Schedule
from src.ra_pst_py.core import RA_PST
from src.ra_pst_py.ilp import configuration_ilp

import copy
import os
from pathlib import Path
import numpy as np
from lxml import etree
import xmltodict
import json

class EvalPipeline():
    def __init__(self):
        self.release_times = [] # required
        self.expected_release_times = []
        self.sim: Simulator

    def setup_simulator(self, ra_pst:RA_PST, allocation_type:AllocationTypeEnum, path_to_dir: os.PathLike | str, release_times: list, expected_release_times: list = [], sigma:int=0) -> dict:
        # Check for replace pattern: 
        if "replace" in ra_pst.get_ra_pst_etree().xpath("//@type"):
            raise NotImplementedError("Replace pattern not implemented for allocation")
        self.release_times = sorted(release_times)
        self.expected_release_times = sorted(expected_release_times)
        # Instantiate simulator and run
        path_to_dir = path_to_dir.with_suffix(".json")
        self.sim = Simulator(schedule_filepath=path_to_dir, sigma=sigma)
        for i, release_time in enumerate(self.release_times):
            instance = Instance(copy.deepcopy(ra_pst), {}, id=i)
            instance.add_release_time(release_time)
            self.sim.add_instance(instance, allocation_type)

        for i, release_time in enumerate(self.expected_release_times):
            instance = Instance(copy.deepcopy(ra_pst), {}, id=i)
            instance.add_release_time(release_time)
            self.sim.add_instance(instance, allocation_type, expected_instance=True)
        

    def add_ilp_data(self, schedule_path):
        schedule_path = schedule_path.with_suffix(".json")
        with open(schedule_path, "r") as f:
            schedule = json.load(f)

        ilp_objective = schedule["ilp_objective"]
        ilp_runtime = schedule["ilp_runtime"]
        schedule["solution"]["ilp_objective"] = ilp_objective
        schedule["solution"]["ilp_runtime"] = ilp_runtime
        with open(schedule_path, "w") as f:
            json.dump(schedule, f, indent=2)

    def add_metadata_to_schedule(self, resource_xml, schedule_path, ra_pst:RA_PST):
        tree = etree.parse(resource_xml)
        root = tree.getroot()

        metadata = root.xpath("metadata")[0]
        metadata = xmltodict.parse(etree.tostring(metadata))
        metadata["metadata"]["instance_problem_size"] = ra_pst.get_problem_size()
        metadata["metadata"]["release_times"] = self.release_times
        metadata["metadata"]["flex_factor"] = ra_pst.get_flex_factor()
        metadata["metadata"]["enthropy"] = ra_pst.get_enthropy()

        # Parallelity measure: 
        ilp_path="tmp/ilp_rep.json"
        with open(ilp_path, "w") as f:
            ilp_rep = ra_pst.get_ilp_rep()
            json.dump(ilp_rep, f, indent=2)
        
        result = configuration_ilp(ilp_path)
        selected_branches = [branch for branch in result["branches"].values() if branch["selected"] == 1.0]
        all_selected_job_costs = []
        for branch in selected_branches:
            for jobId in branch["jobs"]:
                all_selected_job_costs.append(result["jobs"][jobId]["cost"])
        optimal_makespan = sum(all_selected_job_costs)
        metadata["metadata"]["optimal_makespan"] = optimal_makespan
        
        # calculate parallelity
        # parallelity = optimal_makespan/ (max(release_time)+makespan) - min(release_time)
        spread = max(self.release_times) - min(self.release_times)
        max_exp_spread = (len(release_times) -1) * optimal_makespan + optimal_makespan
        parallelity = 1 - (spread / max_exp_spread)
        metadata["metadata"]["parallelity"] = max(0, parallelity)

        schedule_path = schedule_path.with_suffix(".json")
        with open(schedule_path) as f:
            schedule = json.load(f)
        schedule["metadata"] = metadata["metadata"]
        with open(schedule_path, "w") as f:
            json.dump(schedule, f, indent=2)
    
    def combine_info_during_solving(self, schedule_path):
        schedule_path = schedule_path.with_suffix(".json")
        with open(schedule_path, "r") as f:
            schedule = json.load(f)
        
        solution_concat = {
            "objective" : [],
            "solver_status" : [],
            "lower_bound" : [],
            "optimality_gap" : [],
            "computing_time" : []
        }
        
        for instance in schedule["instances"]:
            solution = instance["solution"]
            
            solution_concat["objective"].append(solution["objective"])
            solution_concat["solver_status"].append(solution["solver status"])
            solution_concat["lower_bound"].append(solution["lower_bound"])
            solution_concat["computing_time"].append(solution["computing time"])
            solution_concat["optimality_gap"].append(solution["objective"] - solution["lower_bound"])
        
        schedule["solution_combined"] = solution_concat
        with open(schedule_path, "w") as f:
            json.dump(schedule, f, indent=2)



    def run(self, dirpath: os.PathLike, release_times: list, expected_release_times: list = []):


        if dirpath.is_dir():  # Ensure it's a directory
            process_file = next(Path(dirpath/"process").iterdir())  # Get the process file
            resources_dir = Path(dirpath/"resources")  # Get the resources directory
            
            if process_file.is_file() and resources_dir.exists():
                # Iterate over each file in the resources directory
                for resource_file in resources_dir.iterdir():
                    if resource_file.is_file() and process_file.is_file():  # Ensure it's a file
                        ra_pst = build_rapst(process_file, resource_file)
                        #show_tree_as_graph(ra_pst)
                        print(f"Problem Size per Instance: {ra_pst.get_problem_size()}")
                        
                        # Sigma mean(Task_cost)
                        sigma = round(ra_pst.get_avg_cost())
                        
                        # Setup Simulator for each allocation_type
                        print(f"Start heuristic allocation of {resource_file.name}")
                        schedule_path = dirpath / "evaluation" / "heuristic" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        #show_tree_as_graph(ra_pst, output_file=schedule_path, view=False)
                        self.setup_simulator(ra_pst, "heuristic", path_to_dir=schedule_path, release_times=release_times)
                        self.sim.simulate()
                        self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                        
                        """
                        # Setup Simulator for single instance heuristic
                        print(f"Start single_instance_heuristic allocation of {resource_file.name}")
                        schedule_path = dirpath / "evaluation" / "single_instance_heuristic" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_HEURISTIC, path_to_dir=schedule_path, release_times=release_times)
                        self.sim.simulate()
                        self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                        """
                        """
                        # Setup Simulator for single instance cp
                        print(f"Start single instance CP allocation of {resource_file.name}")
                        schedule_path = dirpath / "evaluation" / "single_instance_cp_fix_full" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP, path_to_dir=schedule_path, release_times=release_times)
                        self.sim.simulate()
                        self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                        self.combine_info_during_solving(schedule_path)
                        """
                        # Setup Simulator for single instance cp with shift
                        print(f"Start single instance CP allocation of {resource_file.name}")
                        schedule_path = dirpath / "evaluation" / "single_instance_cp_sigma_shift" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP, path_to_dir=schedule_path, release_times=release_times, sigma=sigma)
                        self.sim.simulate()
                        self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                        self.combine_info_during_solving(schedule_path)

                        # Setup Simulator for scheduling ilp
                        print(f"Start single instance ILP+CP allocation of {resource_file.name}")
                        schedule_path = dirpath / "evaluation" / "single_instance_ilp_sigma_shift" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_ILP, path_to_dir=schedule_path, release_times=release_times, sigma=sigma)
                        self.sim.simulate()
                        self.add_ilp_data(schedule_path)
                        self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                        self.combine_info_during_solving(schedule_path)
                        
                        # Setup Simulator for scheduling optimal ilp
                        print(f"Start all_instance_ILP + CP allocation of {resource_file.name}")
                        schedule_path = dirpath / "evaluation" / "all_instance_ilp" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(ra_pst, AllocationTypeEnum.ALL_INSTANCE_ILP, path_to_dir=schedule_path, release_times=release_times)
                        self.sim.simulate()
                        self.add_ilp_data(schedule_path)
                        self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                        
                        # Setup Simulator for CP_all 
                        print(f"Start all_instance_CP allocation of {resource_file.name}")
                        schedule_path = dirpath / "evaluation" / "all_instance_cp" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP, path_to_dir=schedule_path, release_times=release_times)
                        self.sim.simulate()
                        self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                        
                        print("==============")
                        print(f"Finish allocation of {resource_file.name}")
                        print("==============")
                        
                        """
                        # Setup Simulator for cp replan
                        print(f"Start single instance CP replan allocation of {resource_file.name}")
                        schedule_path = dirpath / "evaluation" / "single_instance_cp_replan" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP_REPLAN, path_to_dir=schedule_path, release_times=release_times)
                        self.sim.simulate()
                    
                        
                        print(f"Start all instance CP allocation Warm {resource_file.name}")
                        # Setup Simulator for each allocation_type
                        schedule_path = dirpath / "evaluation" / "all_instance_cp" / resource_file.name
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP_WARM, path_to_dir=schedule_path, release_times=release_times)
                        self.sim.simulate()
                        

                        print(f"Start single instance CP online of {resource_file.name}")
                        # Setup Simulator for each allocation_type
                        schedule_path = dirpath / "evaluation" / "single_instance_online" / resource_file.name
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

    root_path = Path("testsets_random_fin")
    subdirectories =  [folder for folder in root_path.iterdir() if folder.is_dir()]
    #subdirectories = subdirectories[0:2]
    print(subdirectories)


    num_instances = 10
    for folder in subdirectories:
        if folder.name.split('_')[-1] == 'generated' :
            release_times = generate_release_times(num_instances=num_instances, mean_time_between_instances=3)
            ep = EvalPipeline()
            ep.run(folder, release_times)
        
        else:
            release_times = [0 for _ in range(num_instances)]
            ep = EvalPipeline()
            ep.run(folder, release_times)



    

    
    