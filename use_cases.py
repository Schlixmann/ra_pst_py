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

        # Instantiate simulator and run
        self.sim = Simulator(
            schedule_filepath=schedule_dir, sigma=sigma, time_limit=time_limit
        )
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
                len(release_times) - 1
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

    def run(
        self, dirpath: os.PathLike, release_times: list, allocation_types: list = []
    ):
        """Executes different solution approaches for all subdirs of dirpath.
            Gets the process from subfolder "process"
            and resource description from subfolder "resource"


        parameters:
            dirpath: path of directory containing resource and process files
            release_times: release times of every single instance
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
                    Instance(copy.deepcopy(ra_pst), {}, id=i, release_time=release_time)
                    for i, release_time in enumerate(release_times)
                ]

                # Print problem size of ra_pst
                print(f"Problem Size per Instance: {ra_pst.get_problem_size()}")

                # Sigma mean(Task_cost)
                sigma = round(ra_pst.get_avg_cost())

                for atype in allocation_types:
                    self.execute_simulation(
                        instances,
                        dirpath,
                        atype,
                        release_times,
                        resource_file,
                        sigma=sigma,
                        time_limit=100,
                    )

                """
                # Setup Simulator for each allocation_type
                print(f"Start heuristic allocation of {resource_file.name}")
                schedule_path = dirpath / "evaluation" / "heuristic" / resource_file.name
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                #show_tree_as_graph(ra_pst, output_file=schedule_path, view=False)
                self.setup_simulator(ra_psts, "heuristic", path_to_dir=schedule_path, release_times=release_times)
                self.sim.simulate()
                self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                
                # Setup Simulator for single instance cp with shift
                print(f"Start single instance decomposed CP allocation of {resource_file.name}")
                schedule_path = dirpath / "evaluation" / "single_instance_decomp_sigma_shift" / resource_file.name
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(ra_psts, AllocationTypeEnum.SINGLE_INSTANCE_CP_DECOMPOSED, path_to_dir=schedule_path, release_times=release_times, sigma=sigma)
                self.sim.simulate()
                self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                self.combine_info_during_solving(schedule_path)

                # Setup Simulator for single instance cp with shift
                print(f"Start single instance CP allocation of {resource_file.name}")
                schedule_path = dirpath / "evaluation" / "single_instance_cp_sigma_shift" / resource_file.name
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(ra_psts, AllocationTypeEnum.SINGLE_INSTANCE_CP, path_to_dir=schedule_path, release_times=release_times, sigma=sigma)
                self.sim.simulate()
                self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                self.combine_info_during_solving(schedule_path)

                # Setup Simulator for scheduling ilp
                print(f"Start single instance ILP+CP allocation of {resource_file.name}")
                schedule_path = dirpath / "evaluation" / "single_instance_ilp_sigma_shift" / resource_file.name
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(ra_psts, AllocationTypeEnum.SINGLE_INSTANCE_ILP, path_to_dir=schedule_path, release_times=release_times, sigma=sigma)
                self.sim.simulate()
                self.add_ilp_data(schedule_path)
                self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                self.combine_info_during_solving(schedule_path)
                

                # Setup Simulator for scheduling optimal ilp
                print(f"Start all_instance_ILP + CP allocation of {resource_file.name}")
                schedule_path = dirpath / "evaluation" / "all_instance_ilp_new" / resource_file.name
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(ra_psts, AllocationTypeEnum.ALL_INSTANCE_ILP, path_to_dir=schedule_path, release_times=release_times)
                self.sim.simulate()
                self.add_ilp_data(schedule_path)
                self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                
                
                # Setup Simulator for CP_all 
                print(f"Start all_instance_CP_decomposed allocation of {resource_file.name}")
                schedule_path = dirpath / "evaluation" / "all_instance_cp_decomp" / resource_file.name
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(ra_psts, AllocationTypeEnum.ALL_INSTANCE_CP_WARM, path_to_dir=schedule_path, release_times=release_times)
                self.sim.simulate()
                self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                
                # Setup Simulator for CP_all 
                print(f"Start all_instance_CP allocation of {resource_file.name}")
                schedule_path = dirpath / "evaluation" / "all_instance_cp_test" / resource_file.name
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(ra_psts, AllocationTypeEnum.ALL_INSTANCE_CP, path_to_dir=schedule_path, release_times=release_times)
                self.sim.simulate()
                self.add_metadata_to_schedule(resource_file, schedule_path, ra_pst)
                """
                print("==============")
                print(f"Finish allocation of {resource_file.name}")
                print("==============")

    def execute_simulation(
        self,
        instances: list[Instance],
        directory: os.PathLike,
        allocation_type: AllocationTypeEnum,
        release_times: list,
        resource_file: Path,
        sigma=0,
        time_limit=100,
        suffix: str = "",
    ):
        """Setup and run simulation for a given allocation type."""
        schedule_path = (
            directory
            / "evaluation"
            / f"{str(allocation_type)}{suffix}"
            / f"{resource_file.stem}.json"
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
        self.sim.simulate()

        # Add ILP data if applicable
        if allocation_type in {
            AllocationTypeEnum.ALL_INSTANCE_ILP,
            AllocationTypeEnum.SINGLE_INSTANCE_ILP,
        }:
            self.add_ilp_data(schedule_path)

        # Add metadata to the schedule
        self.add_metadata_to_schedule(resource_file, schedule_path, instances[0].ra_pst)

        # Combine information during solving if applicable
        if allocation_type in {
            AllocationTypeEnum.SINGLE_INSTANCE_CP,
            AllocationTypeEnum.SINGLE_INSTANCE_CP_DECOMPOSED,
            AllocationTypeEnum.SINGLE_INSTANCE_ILP,
            AllocationTypeEnum.SINGLE_INSTANCE_HEURISTIC,
        }:
            self.combine_info_during_solving(schedule_path)

    def run_release_spread(self, dirpath: os.PathLike, release_times: list, i: int = 0):
        """Runs the different solution approaches for a directory.
        Uses the Same RA-PST each time,

        parameters:
            dirpath: path to dir where process and resource file are stored
            release_times: list of release times for the process instances

        """

        if dirpath.is_dir():  # Ensure it's a directory
            process_file = next(
                Path(dirpath / "process").iterdir()
            )  # Get the process file
            resources_dir = Path(dirpath / "resources")  # Get the resources directory

            if process_file.is_file() and resources_dir.exists():
                # Iterate over each file in the resources directory
                for resource_file in tqdm(resources_dir.iterdir()):
                    if (
                        resource_file.is_file() and process_file.is_file()
                    ):  # Ensure it's a file
                        ra_pst = build_rapst(process_file, resource_file)
                        ra_psts = [ra_pst for _ in range(len(release_times))]
                        # show_tree_as_graph(ra_pst)
                        print(f"Problem Size per Instance: {ra_pst.get_problem_size()}")

                        # Sigma mean(Task_cost)
                        sigma = round(ra_pst.get_avg_cost())

                        # Setup Simulator for each allocation_type
                        print(f"Start heuristic allocation of {resource_file.name}")
                        schedule_path = (
                            dirpath
                            / "evaluation"
                            / "heuristic"
                            / (str(i) + "-" + resource_file.name)
                        )
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        # show_tree_as_graph(ra_pst, output_file=schedule_path, view=False)
                        self.setup_simulator(
                            ra_psts,
                            "heuristic",
                            path_to_dir=schedule_path,
                            release_times=release_times,
                        )
                        self.sim.simulate()
                        self.add_metadata_to_schedule(
                            resource_file, schedule_path, ra_pst
                        )

                        # Setup Simulator for single instance cp with shift
                        print(
                            f"Start single instance CP allocation of {resource_file.name}"
                        )
                        schedule_path = (
                            dirpath
                            / "evaluation"
                            / "single_instance_cp_sigma_shift"
                            / (str(i) + "-" + resource_file.name)
                        )
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(
                            ra_psts,
                            AllocationTypeEnum.SINGLE_INSTANCE_CP,
                            path_to_dir=schedule_path,
                            release_times=release_times,
                            sigma=sigma,
                        )
                        self.sim.simulate()
                        self.add_metadata_to_schedule(
                            resource_file, schedule_path, ra_pst
                        )
                        self.combine_info_during_solving(schedule_path)

                        # Setup Simulator for scheduling ilp
                        print(
                            f"Start single instance ILP+CP allocation of {resource_file.name}"
                        )
                        schedule_path = (
                            dirpath
                            / "evaluation"
                            / "single_instance_ilp_sigma_shift"
                            / (str(i) + "-" + resource_file.name)
                        )
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(
                            ra_psts,
                            AllocationTypeEnum.SINGLE_INSTANCE_ILP,
                            path_to_dir=schedule_path,
                            release_times=release_times,
                            sigma=sigma,
                        )
                        self.sim.simulate()
                        self.add_ilp_data(schedule_path)
                        self.add_metadata_to_schedule(
                            resource_file, schedule_path, ra_pst
                        )
                        self.combine_info_during_solving(schedule_path)

                        # Setup Simulator for scheduling optimal ilp
                        print(
                            f"Start all_instance_ILP + CP allocation of {resource_file.name}"
                        )
                        schedule_path = (
                            dirpath
                            / "evaluation"
                            / "all_instance_ilp"
                            / (str(i) + "-" + resource_file.name)
                        )
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(
                            ra_psts,
                            AllocationTypeEnum.ALL_INSTANCE_ILP,
                            path_to_dir=schedule_path,
                            release_times=release_times,
                        )
                        self.sim.simulate()
                        self.add_ilp_data(schedule_path)
                        self.add_metadata_to_schedule(
                            resource_file, schedule_path, ra_pst
                        )

                        # Setup Simulator for CP_all
                        print(
                            f"Start all_instance_CP allocation of {resource_file.name}"
                        )
                        schedule_path = (
                            dirpath
                            / "evaluation"
                            / "all_instance_cp"
                            / (str(i) + "-" + resource_file.name)
                        )
                        schedule_path.parent.mkdir(parents=True, exist_ok=True)
                        self.setup_simulator(
                            ra_psts,
                            AllocationTypeEnum.ALL_INSTANCE_CP,
                            path_to_dir=schedule_path,
                            release_times=release_times,
                        )
                        self.sim.simulate()
                        self.add_metadata_to_schedule(
                            resource_file, schedule_path, ra_pst
                        )

                        print("==============")
                        print(f"Finish allocation of {resource_file.name + str(i)}")
                        print("==============")

    def run_random_ra_psts(self, dirpath: os.PathLike, release_times: list, i: int = 0):
        if dirpath.is_dir():  # Ensure it's a directory
            process_file = next(
                Path(dirpath / "process").iterdir()
            )  # Get the process file
            resources_dir = Path(dirpath / "resources")  # Get the resources directory

            if process_file.is_file() and resources_dir.exists():
                # Draw len(release_times) many resource files from resources dir
                ra_psts = []
                resource_files = [res_file for res_file in resources_dir.iterdir()]
                for _ in range(len(release_times)):
                    resource_file = random.choice(resource_files)
                    ra_psts.append(build_rapst(process_file, resource_file))

                # Sigma mean(Task_cost)
                sigma = round(
                    statistics.mean(
                        [round(ra_pst.get_avg_cost()) for ra_pst in ra_psts]
                    )
                )

                # Setup Simulator for each allocation_type
                print(f"Start heuristic allocation of {resource_file.name}")
                schedule_path = dirpath / "evaluation" / "heuristic" / f"multi_int_{i}"
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                # show_tree_as_graph(ra_pst, output_file=schedule_path, view=False)
                self.setup_simulator(
                    ra_psts,
                    "heuristic",
                    path_to_dir=schedule_path,
                    release_times=release_times,
                )
                self.sim.simulate()
                self.add_metadata_to_schedule(resource_file, schedule_path)

                # Setup Simulator for single instance cp with shift
                print(f"Start single instance CP allocation of {resource_file.name}")
                schedule_path = (
                    dirpath
                    / "evaluation"
                    / "single_instance_cp_sigma_shift"
                    / f"multi_int_{i}"
                )
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(
                    ra_psts,
                    AllocationTypeEnum.SINGLE_INSTANCE_CP,
                    path_to_dir=schedule_path,
                    release_times=release_times,
                    sigma=sigma,
                )
                self.sim.simulate()
                self.add_metadata_to_schedule(resource_file, schedule_path)
                self.combine_info_during_solving(schedule_path)

                # Setup Simulator for scheduling ilp
                print(
                    f"Start single instance ILP+CP allocation of {resource_file.name}"
                )
                schedule_path = (
                    dirpath
                    / "evaluation"
                    / "single_instance_ilp_sigma_shift"
                    / f"multi_int_{i}"
                )
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(
                    ra_psts,
                    AllocationTypeEnum.SINGLE_INSTANCE_ILP,
                    path_to_dir=schedule_path,
                    release_times=release_times,
                    sigma=sigma,
                )
                self.sim.simulate()
                self.add_ilp_data(schedule_path)
                self.add_metadata_to_schedule(resource_file, schedule_path)
                self.combine_info_during_solving(schedule_path)

                # Setup Simulator for scheduling optimal ilp
                print(f"Start all_instance_ILP + CP allocation of {resource_file.name}")
                schedule_path = (
                    dirpath / "evaluation" / "all_instance_ilp" / f"multi_int_{i}"
                )
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(
                    ra_psts,
                    AllocationTypeEnum.ALL_INSTANCE_ILP,
                    path_to_dir=schedule_path,
                    release_times=release_times,
                )
                self.sim.simulate()
                self.add_ilp_data(schedule_path)
                self.add_metadata_to_schedule(resource_file, schedule_path)

                # Setup Simulator for CP_all
                print(f"Start all_instance_CP allocation of {resource_file.name}")
                schedule_path = (
                    dirpath / "evaluation" / "all_instance_cp" / f"multi_int_{i}"
                )
                schedule_path.parent.mkdir(parents=True, exist_ok=True)
                self.setup_simulator(
                    ra_psts,
                    AllocationTypeEnum.ALL_INSTANCE_CP,
                    path_to_dir=schedule_path,
                    release_times=release_times,
                )
                self.sim.simulate()
                self.add_metadata_to_schedule(resource_file, schedule_path)

                print("==============")
                print(f"Finish allocation of {resource_file.name + str(i)}")
                print("==============")


def pos_random_normal(mean, sigma):
    x = round(np.random.normal(mean, sigma))
    return x if x >= 0 else pos_random_normal(mean, sigma)


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
    intervals = np.random.exponential(
        scale=mean_time_between_instances, size=num_instances
    ).round()

    # Calculate cumulative release times
    release_times = np.cumsum(intervals)
    release_times = [int(time) for time in release_times]
    return release_times


if __name__ == "__main__":
    # Main path of testsets
    root_path = Path("testsets_decomposed_paper")

    # Filter for subdirectories
    subdirectories = [folder for folder in root_path.iterdir() if folder.is_dir()][0:1]
    print(subdirectories)
    
    # Filter chosen allocation types
    allocation_types = [
        AllocationTypeEnum.HEURISTIC,
        AllocationTypeEnum.SINGLE_INSTANCE_CP,
    ]

    # run generator for folder
    for folder in subdirectories:
        # release_times = generate_release_times(num_instances=10, mean_time_between_instances=random.randint(5, 50))
        release_times = [0 for _ in range(10)]
        ep = EvalPipeline()
        ep.run(folder, release_times, allocation_types)

    """
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
    

    num_instances = 10
    for folder in subdirectories:
        for i in range(num_instances):
            release_times = generate_release_times(num_instances=num_instances, mean_time_between_instances=random.randint(5, 50))
            ep = EvalPipeline()
            ep.run_release_spread(folder, release_times, i = i)
    

    root_path = Path("testsets_multi_instance")
    subdirectories =  [folder for folder in root_path.iterdir() if folder.is_dir()]
    #subdirectories = subdirectories[2:6]
    print(subdirectories)

    num_instances = 10
    for folder in subdirectories:
        for i in range(5):
            release_times = generate_release_times(num_instances=num_instances, mean_time_between_instances=random.randint(5, 50))
            ep = EvalPipeline()
            ep.run_random_ra_psts(folder, release_times, i = i)

    """
