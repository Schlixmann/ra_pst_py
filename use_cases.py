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
from tqdm import tqdm
import random
import statistics
import json


class EvalPipeline:
    def __init__(self):
        self.sim: Simulator
        self.release_times: list

    def setup_simulator(
        self,
        instances: list[Instance],
        allocation_type: AllocationTypeEnum,
        schedule_dir: os.PathLike | str = "out/sim_schedule.json",
        sigma: int = 0,
        time_limit: int = 100,
    ) -> None:
        # Check for replace pattern:
        for instance in instances:
            if "replace" in instance.ra_pst.get_ra_pst_etree().xpath("//@type"):
                raise NotImplementedError(
                    "Replace pattern not implemented for allocation"
                )

        # Instantiate simulator
        self.sim = Simulator(
            schedule_filepath=schedule_dir, sigma=sigma, time_limit=time_limit
        )
        
        # Add instances to simulator
        instances = sorted(instances, key=lambda obj: obj.release_time)
        self.release_times = [instance.release_time for instance in instances]
        for instance in instances:
            instance.add_release_time(instance.release_time)
            self.sim.add_instance(instance, allocation_type)

    def add_ilp_data(self, schedule_path):
        """Only if ilp is used.
        Adds the objective and the runtime of the ILP to the schedule

        Parameters:
            schedule_path: Path to the schedule file
        """
        schedule_path = schedule_path.with_suffix(".json")
        with open(schedule_path, "r") as f:
            schedule = json.load(f)

        ilp_objective = schedule["ilp_objective"]
        ilp_runtime = schedule["ilp_runtime"]
        schedule["solution"]["ilp_objective"] = ilp_objective
        schedule["solution"]["ilp_runtime"] = ilp_runtime

        with open(schedule_path, "w") as f:
            json.dump(schedule, f, indent=2)

    def add_metadata_to_schedule(
        self, resource_xml, schedule_path, ra_pst: RA_PST = None
    ):
        """Adds metadata of the problem to the schdedule.
        Metadata is mainly derived from the RA-PST.
        Important Data:
            metadata = metadata dict from resource file
            instance_problem_size = product(branches_per_task)
            release_times = release times of each instance
            flex_factor = Flexibility factor in process (currently unused)
            enthropy = Entropy in RA-PST.

        Parameters:
            resource_xml: path to resource file
            schedule_path: path to schedule file
            ra_pst: RA-PST object for instances
        """

        tree = etree.parse(resource_xml)
        root = tree.getroot()

        metadata = root.xpath("metadata")[0]
        metadata = xmltodict.parse(etree.tostring(metadata))
        metadata["metadata"]["instance_problem_size"] = (
            ra_pst.get_problem_size() if ra_pst is not None else None
        )
        metadata["metadata"]["release_times"] = self.release_times
        metadata["metadata"]["flex_factor"] = (
            ra_pst.get_flex_factor() if ra_pst is not None else None
        )
        metadata["metadata"]["enthropy"] = (
            ra_pst.get_enthropy() if ra_pst is not None else None
        )

        # Parallelity measure:
        if ra_pst is not None:
            ilp_path = "tmp/ilp_rep.json"
            with open(ilp_path, "w") as f:
                ilp_rep = ra_pst.get_ilp_rep()
                json.dump(ilp_rep, f, indent=2)

            result = configuration_ilp(ilp_path)
            selected_branches = [
                branch
                for branch in result["branches"].values()
                if branch["selected"] == 1.0
            ]
            all_selected_job_costs = []
            for branch in selected_branches:
                for jobId in branch["jobs"]:
                    all_selected_job_costs.append(result["jobs"][jobId]["cost"])
            optimal_makespan = sum(all_selected_job_costs)
            metadata["metadata"]["optimal_makespan"] = optimal_makespan

            # calculate parallelity
            # parallelity = optimal_makespan/ (max(release_time)+makespan) - min(release_time)
            spread = max(self.release_times) - min(self.release_times)
            max_exp_spread = (
                len(self.release_times) - 1
            ) * optimal_makespan + optimal_makespan
            parallelity = 1 - (spread / max_exp_spread)
            metadata["metadata"]["parallelity"] = max(0, parallelity)
        else:
            metadata["metadata"]["parallelity"] = None
        schedule_path = schedule_path.with_suffix(".json")
        with open(schedule_path) as f:
            schedule = json.load(f)
        schedule["metadata"] = metadata["metadata"]
        with open(schedule_path, "w") as f:
            json.dump(schedule, f, indent=2)

    def combine_info_during_solving(self, schedule_path):
        """Adds solution_combined info dict for the schedule, which tracks metadata
        for each solver run (only for single instance solving)

        parameters:
            schedule_path: path of schedule file

        """
        schedule_path = schedule_path.with_suffix(".json")
        with open(schedule_path, "r") as f:
            schedule = json.load(f)

        solution_concat = {
            "objective": [],
            "solver_status": [],
            "lower_bound": [],
            "optimality_gap": [],
            "computing_time": [],
        }

        for instance in schedule["instances"]:
            solution = instance["solution"]

            solution_concat["objective"].append(solution["objective"])
            solution_concat["solver_status"].append(solution["solver status"])
            solution_concat["lower_bound"].append(solution["lower_bound"])
            solution_concat["computing_time"].append(solution["computing time"])
            solution_concat["optimality_gap"].append(
                solution["objective"] - solution["lower_bound"]
            )

        schedule["solution_combined"] = solution_concat
        with open(schedule_path, "w") as f:
            json.dump(schedule, f, indent=2)

    def run_same_release(
        self, dirpath: os.PathLike, allocation_types: list = [], num_instances:int=10, time_limit:int=100, sigma:int = None, suffix:str="", add_metadata:bool=True,
    ):
        """
        Executes various solution approaches for all subdirectories within `dirpath`.

        The process file is retrieved from the `process` subfolder,  
        and the resource description is retrieved from the `resource` subfolder.  
        Each instance is assigned a release time of 0.  

        The generated schedule file is saved at:  
        `dirpath/evaluation/{allocation_type}/{resource_file.name}`  

        Parameters:
            dirpath (Path): Directory containing `resource` and `process` subfolders.
            allocation_types (list): Allocation strategies to be applied.
            num_instances (int): Number of instances to add to the simulator.
            time_limit (int): Timeout for the allocation approach.
            sigma (Optional[int]): Sigma value for online allocation.  
                If `None`, it defaults to 1 times the average task size.
        """

        if not allocation_types:
            [enum.value for enum in AllocationTypeEnum]
        if dirpath.is_dir():  # Ensure it's a directory
            process_file = next(
                Path(dirpath / "process").iterdir()
            )  # Get the process file
            resources_dir = Path(dirpath / "resources")  # Get the resources directory

            if not process_file.is_file():
                raise ValueError("Process file is not a file")
            if not resources_dir.exists():
                raise ValueError("Resource Dir does not exist")

            # Iterate over each file in the resources directory
            for resource_file in tqdm(sorted(resources_dir.iterdir(), reverse=True)):
                if not resource_file.is_file():
                    raise ValueError("Resource file is not a file")

                # Build rapst
                ra_pst = build_rapst(process_file, resource_file)

                # Build rapst instances:
                instances = [
                    Instance(copy.deepcopy(ra_pst), {}, id=i, release_time=0)
                    for i in range(num_instances)
                ]

                # Print problem size of ra_pst
                print(f"Problem Size per Instance: {ra_pst.get_problem_size()}")

                # Sigma mean(Task_cost)
                sigma = round(ra_pst.get_avg_cost()) if sigma is None else sigma

                # Run for each allocation_type
                for atype in allocation_types:
                    self.execute_simulation(
                        instances,
                        dirpath,
                        atype,
                        resource_file,
                        sigma=sigma,
                        time_limit=time_limit,
                        suffix=suffix,
                        add_metadata=add_metadata
                    )

                print("==============")
                print(f"Finish allocation of {resource_file.name}")
                print("==============")


    def run_generated_release(
        self, dirpath: os.PathLike, allocation_types: list = [], num_instances:int=10, time_limit:int=100, sigma:int = None, suffix:str="", spread:int=None, add_metadata:bool=True, fixed_release_times:callable = None
    ):
        """
        Executes various solution approaches for all subdirectories within `dirpath`.

        The process file is retrieved from the `process` subfolder,  
        and the resource description is retrieved from the `resource` subfolder.  
        Each instance is assigned a release time of 0.  

        The generated schedule file is saved at:  
        `dirpath/evaluation/{allocation_type}/{resource_file.name}`  

        Parameters:
            dirpath (Path): Directory containing `resource` and `process` subfolders.
            allocation_types (list): Allocation strategies to be applied.
            num_instances (int): Number of instances to add to the simulator.
            time_limit (int): Timeout for the allocation approach.
            sigma (Optional[int]): Sigma value for online allocation.  
                If `None`, it defaults to 1 times the average task size.
        """

        if not allocation_types:
            [enum.value for enum in AllocationTypeEnum]
        if dirpath.is_dir():  # Ensure it's a directory
            process_file = next(
                Path(dirpath / "process").iterdir()
            )  # Get the process file
            resources_dir = Path(dirpath / "resources")  # Get the resources directory

            if not process_file.is_file():
                raise ValueError("Process file is not a file")
            if not resources_dir.exists():
                raise ValueError("Resource Dir does not exist")

            # Iterate over each file in the resources directory
            for resource_file in tqdm(sorted(resources_dir.iterdir(), reverse=True)):
                if not resource_file.is_file():
                    raise ValueError("Resource file is not a file")

                # Build rapst
                ra_pst = build_rapst(process_file, resource_file)

                # generate release times:
                avg_task_cost = round(ra_pst.get_avg_cost())
                spread = avg_task_cost if sigma is None else spread
                release_times = self.generate_release_times(num_instances, spread) if not fixed_release_times else fixed_release_times(dirpath, resource_file)
                # Build rapst instances:
                instances = [
                    Instance(copy.deepcopy(ra_pst), {}, id=i, release_time=release_time)
                    for i, release_time in enumerate(release_times)
                ]

                # Print problem size of ra_pst
                print(f"Problem Size per Instance: {ra_pst.get_problem_size()}")

                # Sigma mean(Task_cost)
                sigma = round(ra_pst.get_avg_cost()) if sigma is None else sigma

                # Run for each allocation_type
                for atype in allocation_types:
                    self.execute_simulation(
                        instances,
                        dirpath,
                        atype,
                        resource_file,
                        sigma=sigma,
                        time_limit=time_limit,
                        suffix=suffix,
                        add_metadata=add_metadata
                    )

                    if atype in [AllocationTypeEnum.SINGLE_INSTANCE_CP, AllocationTypeEnum.SINGLE_INSTANCE_CP_DECOMPOSED]:
                        no_sig_suffix = suffix + "_no_sigma"
                        self.execute_simulation(
                            instances,
                            dirpath,
                            atype,
                            resource_file,
                            sigma=0,
                            time_limit=time_limit,
                            suffix=no_sig_suffix,
                            add_metadata=add_metadata
                        )

                print("==============")
                print(f"Finish allocation of {resource_file.name}")
                print("==============")

    
    def run_random_instances(
        self, dirpath: os.PathLike, allocation_types: list = [], num_instances:int=10, time_limit:int=100, sigma:int = None, suffix:str="", spread:int=None, add_metadata:bool=True, res_file_suffix:str="", spread_release:bool=True, selected_resource_files:list[Path]=[], fixed_release_times:list=[]
    ):
        """
        Executes various solution approaches for all subdirectories within `dirpath`.

        The process file is retrieved from the `process` subfolder,  
        and the resource description is retrieved from the `resource` subfolder.  
        Each instance is assigned a release time of 0.  

        The generated schedule file is saved at:  
        `dirpath/evaluation/{allocation_type}/{resource_file.name}`  

        Parameters:
            dirpath (Path): Directory containing `resource` and `process` subfolders.
            allocation_types (list): Allocation strategies to be applied.
            num_instances (int): Number of instances to add to the simulator.
            time_limit (int): Timeout for the allocation approach.
            sigma (Optional[int]): Sigma value for online allocation.  
                If `None`, it defaults to 1 times the average task size.
        """

        if not allocation_types:
            [enum.value for enum in AllocationTypeEnum]
        if dirpath.is_dir():  # Ensure it's a directory
            process_file = next(
                Path(dirpath / "process").iterdir()
            )  # Get the process file
            resources_dir = Path(dirpath / "resources")  # Get the resources directory

            if not process_file.is_file():
                raise ValueError("Process file is not a file")
            if not resources_dir.exists():
                raise ValueError("Resource Dir does not exist")

            # Choose num_instances random instances from `dirpath/resources`:
            resource_files = [file for file in resources_dir.iterdir() if file.is_file()]
                        
            # Iterate over each file in the selected_files
            
            ra_psts = []
            instances = []
            spread = 5 if spread is None else spread          
            
            selected_files = []
            for i in range(num_instances):
                # Select random resource file
                resource_file = random.choice(resource_files) if not selected_resource_files else selected_resource_files.pop(0)
                selected_files.append(resource_file.name)
                if not resource_file.is_file():
                    raise ValueError("Resource file is not a file")

                # Build rapst from resource_file
                ra_psts.append(build_rapst(process_file, resource_file))


            spread = round(statistics.mean([ra_pst.get_avg_cost() for ra_pst in ra_psts])) if spread is None else spread

            if not fixed_release_times:
                release_times = self.generate_release_times(num_instances, spread) if spread_release else [0 for _ in range(num_instances)]
            else:
                release_times = fixed_release_times

            for i in range(num_instances):
                # Build rapst instances:
                #instances.append(Instance(copy.deepcopy(ra_pst), {}, id=i, release_time=release_times[i]))
                instances.append(Instance(copy.deepcopy(ra_psts[i]), {}, id=i, release_time=release_times[i]))

                # Print problem size of ra_pst
            print(f"{i} instances generated")

            # Sigma mean(Task_cost)
            sigma = round(statistics.mean([ra_pst.get_avg_cost() for ra_pst in ra_psts])) if sigma is None else sigma

            # Run for each allocation_type
            for atype in allocation_types:
                self.execute_simulation(
                    instances,
                    dirpath,
                    atype,
                    resource_file,
                    sigma=sigma,
                    time_limit=time_limit,
                    suffix=suffix,
                    add_metadata=add_metadata,
                    different_instances=True,
                    res_file_suffix = res_file_suffix
                )
                schedule_path = (
                dirpath
                / "evaluation"
                / f"{str(atype)}{suffix}"
                / f"{resource_file.stem}{res_file_suffix}.json"
                )
                with open(schedule_path, "r") as f:
                    schedule_dict = json.load(f)
                schedule_dict["metadata"]["picked_instances"] = selected_files
                
                with open(schedule_path, "w") as f:
                    json.dump(schedule_dict, f, indent=2)

                    if atype in [AllocationTypeEnum.SINGLE_INSTANCE_CP, AllocationTypeEnum.SINGLE_INSTANCE_CP_DECOMPOSED]:
                        print("No_Sigma allocation")
                        no_sig_suffix = suffix + "_no_sigma"
                        self.execute_simulation(
                            instances,
                            dirpath,
                            atype,
                            resource_file,
                            sigma=0,
                            time_limit=time_limit,
                            suffix=no_sig_suffix,
                            add_metadata=add_metadata,
                            different_instances=True,
                            res_file_suffix = res_file_suffix
                        )
                        schedule_path = (
                        dirpath
                        / "evaluation"
                        / f"{str(atype)}{no_sig_suffix}"
                        / f"{resource_file.stem}{res_file_suffix}.json"
                        )
                        with open(schedule_path, "r") as f:
                            schedule_dict = json.load(f)
                        schedule_dict["metadata"]["picked_instances"] = selected_files
                        
                        with open(schedule_path, "w") as f:
                            json.dump(schedule_dict, f, indent=2)
        
        
            print("==============")
            print(f"Finish allocation of {resource_file.name}")
            print("==============")

    def execute_simulation(
        self,
        instances: list[Instance],
        directory: os.PathLike,
        allocation_type: AllocationTypeEnum,
        resource_file: Path,
        sigma=0,
        time_limit=100,
        suffix: str = "",
        add_metadata:bool = True, 
        different_instances:bool = False,
        res_file_suffix:str = ""
    ):
        """Setup and run simulation for a given allocation type."""
        schedule_path = (
            directory
            / "evaluation"
            / f"{str(allocation_type)}{suffix}"
            / f"{resource_file.stem}{res_file_suffix}.json"
        )
        # Ensure the parent directory exists
        schedule_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup the simulator
        self.setup_simulator(
            instances,
            allocation_type,
            schedule_dir=schedule_path,
            sigma=sigma,
            time_limit=time_limit,
        )

        # Run the simulation
        print("____________")
        print(f"Start {str(allocation_type)} allocation of {resource_file.name}")
        print("------------")
        self.sim.simulate(different_instances=different_instances)

        # Add ILP data if applicable
        if allocation_type in {
            AllocationTypeEnum.ALL_INSTANCE_ILP,
            AllocationTypeEnum.SINGLE_INSTANCE_ILP,
        }:
            self.add_ilp_data(schedule_path)

        # Add metadata to the schedule
        if add_metadata:
            self.add_metadata_to_schedule(resource_file, schedule_path, instances[0].ra_pst)

        # Combine information during solving if applicable
        if allocation_type in {
            AllocationTypeEnum.SINGLE_INSTANCE_CP,
            AllocationTypeEnum.SINGLE_INSTANCE_CP_DECOMPOSED,
            AllocationTypeEnum.SINGLE_INSTANCE_ILP,
            AllocationTypeEnum.SINGLE_INSTANCE_HEURISTIC,
        }:
            self.combine_info_during_solving(schedule_path)


    def generate_release_times(self, num_instances:int, spread:int):
        """
        Generate release times for processes using an exponential distribution.

        Args:
            num_instances (int): The number of process instances to generate.
            spread (float): The average time between releases (in hours).

        Returns:
            list: Cumulative release times for the process instances (in hours).
        """
        release_times = [0]
        # Sample time intervals from the exponential distribution
        intervals = np.random.exponential(
            scale=spread, size=num_instances-1
        ).round()
        #intervals = np.round(intervals).astype(int)
        # Calculate cumulative release times
        release_times.extend(np.cumsum(intervals))
        release_times = [round(time) for time in release_times]
        
        return release_times


def pos_random_normal(mean, sigma):
    x = round(np.random.normal(mean, sigma))
    return x if x >= 0 else pos_random_normal(mean, sigma)

def get_release_times(dirpath:Path, resource_file:Path):
    file_name = Path(resource_file.stem + ".json")
    eval_file = dirpath / "comparison" / file_name
    with open(eval_file, "r") as f:
        data = json.load(f)
    return data["metadata"]["release_times"]


if __name__ == "__main__":

    offline=True
    online =True


    if offline:
        # Main path of testsets
        root_path = Path("testsets_final_offline")

        # Filter for subdirectories
        subdirectories = sorted([folder for folder in root_path.iterdir() if folder.is_dir()])
        subdirectories_gen = [subdirectories[i] for i in [0,1]]
        subdirectories_random = [subdirectories[i] for i in [3]]
        clinic_set = [subdirectories[i] for i in [2]]
        print(subdirectories_gen, subdirectories_random, clinic_set)
        
        # Filter chosen allocation types
        allocation_types = [
            AllocationTypeEnum.ALL_INSTANCE_CP,
            AllocationTypeEnum.ALL_INSTANCE_CP_DECOMPOSED,
            AllocationTypeEnum.ALL_INSTANCE_ILP
        ]

        # run clinic set, no metadata
        for folder in clinic_set:
            ep = EvalPipeline()
            ep.run_same_release(folder, allocation_types, num_instances=8, time_limit=7200, suffix="_7200", add_metadata=False)

        # run same release time pipeline for folder
        for folder in subdirectories_gen:
            ep = EvalPipeline()
            #ep.run_same_release(folder, allocation_types, num_instances=8)
            ep.run_same_release(folder, allocation_types, num_instances=8, time_limit=7200, suffix="_7200")

        # set instances for random instance
        eval_path = root_path / "random_instances" / "comparison"
        json_files = list(eval_path.glob("*.json"))
        resource_path = root_path/ "random_instances" / "resources"
        selected_resource_files = []
        for file in json_files:
            with open(file, "r") as f:
                data = json.load(f)
            path_list = [resource_path / Path(file_string) for file_string in data["metadata"]["picked_instances"]]
            selected_resource_files.append(path_list)

        print("Start random 1")
        for i in range(2):
            for folder in subdirectories_random:
                ep = EvalPipeline()
                #ep.run_same_release(folder, allocation_types, num_instances=8)
                ep.run_random_instances(folder, allocation_types, num_instances=8, time_limit=7200, suffix="_7200", res_file_suffix=f"_{i}", spread_release=False, selected_resource_files=selected_resource_files[i])
    
    if online:
    
        print("===========")
        print("RUN ONLINE TESTS")
        print("===========")
        
        
        # Folder with online testsets
        root_path = Path("testsets_final_online")

        # Filter for subdirectories
        subdirectories = sorted([folder for folder in root_path.iterdir() if folder.is_dir()])
        subdirectories_normal = [subdirectories[i] for i in [0,2,4]]
        subdirectories_random = [subdirectories[i] for i in [1,3,5]]

            # Filter chosen allocation types
        allocation_types = [
            AllocationTypeEnum.ALL_INSTANCE_CP,
            AllocationTypeEnum.HEURISTIC,
            AllocationTypeEnum.SINGLE_INSTANCE_CP,
            AllocationTypeEnum.SINGLE_INSTANCE_CP,
            AllocationTypeEnum.SINGLE_INSTANCE_ILP,
            AllocationTypeEnum.SINGLE_INSTANCE_CP_DECOMPOSED,
            AllocationTypeEnum.ALL_INSTANCE_ILP
        ]
        
        # Run online tests
        for folder in subdirectories_normal:
            ep = EvalPipeline()
            #ep.run_same_release(folder, allocation_types, num_instances=8)
            ep.run_generated_release(folder, allocation_types, num_instances=8, time_limit=100, suffix="", fixed_release_times=get_release_times)
        
        # Run online tests
                # run with random instance picking
        eval_path = root_path / "random_instances" / "comparison"
        json_files = list(eval_path.glob("*.json"))
        resource_path = root_path/ "random_instances" / "resources"
        selected_resource_files = []
        for file in json_files:
            with open(file, "r") as f:
                data = json.load(f)
            path_list = [resource_path / Path(file_string) for file_string in data["metadata"]["picked_instances"]]
            selected_resource_files.append(path_list)
        

        for folder in subdirectories_random:
            eval_path = folder / "comparison"
            json_files = list(eval_path.glob("*.json"))
            resource_path = folder/ "resources"
            selected_resource_files = []
            fixed_release_times = []
            for file in json_files:
                with open(file, "r") as f:
                    data = json.load(f)
                path_list = [resource_path / Path(file_string) for file_string in data["metadata"]["picked_instances"]]
                selected_resource_files.append(path_list)
                fixed_release_times.append(data["metadata"]["release_times"])
            
            for i in range(2):
                ep = EvalPipeline()
                #ep.run_same_release(folder, allocation_types, num_instances=8)
                ep.run_random_instances(folder, allocation_types, num_instances=8, time_limit=100, suffix="", res_file_suffix=f"_{i}", spread_release=True, selected_resource_files=selected_resource_files[i], fixed_release_times=fixed_release_times[i])
