from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator, AllocationTypeEnum
from src.ra_pst_py.instance import Instance
from src.ra_pst_py.schedule import Schedule
from src.ra_pst_py.core import RA_PST

import copy
import os

def run(ra_pst:RA_PST, allocation_type:AllocationTypeEnum, path_to_dir: os.PathLike | str) -> dict:
    # Main File to test multiple use cases for paper
    sched = Schedule()
    release_times = [0,10,23]

    # Instantiate simulator and run
    sim = Simulator(schedule_filepath=f"{path_to_dir}/{allocation_type}.json")
    for i, release_time in enumerate(release_times):
        instance = Instance(copy.deepcopy(ra_pst), {}, sched, id=i)
        instance.add_release_time(release_time)
        sim.add_instance(instance, allocation_type)

    sim.simulate(instance_mapper={})

if __name__ == "__main__":

    ra_pst = build_rapst(
        process_file="test_instances/paper_process_first_4.xml",
        resource_file="test_instances/offer_resources_plain_fully_synthetic_small.xml"
    )
    output_dir_path = "evaluation/paper_process_first_invalids"
    show_tree_as_graph(ra_pst)
    run(ra_pst, AllocationTypeEnum.HEURISTIC, output_dir_path)
    run(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP , output_dir_path)
    run(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM , output_dir_path)
    run(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP , output_dir_path)

    ra_pst = build_rapst(
        process_file="test_instances/instance_generator_process.xml",
        resource_file="test_instances/instance_generator_resources.xml"
    )
    output_dir_path = "evaluation/paper_process_short_invalids"
    
    run(ra_pst, AllocationTypeEnum.HEURISTIC, output_dir_path)
    run(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP , output_dir_path)
    run(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM , output_dir_path)
    run(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP , output_dir_path)


    

    
    