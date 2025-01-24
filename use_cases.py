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

    # Check for replace pattern: 
    if "replace" in ra_pst.get_ra_pst_etree().xpath("//@type"):
        raise NotImplementedError("Replace pattern not implemented for allocation")

    # Instantiate simulator and run
    sim = Simulator(schedule_filepath=f"{path_to_dir}/{allocation_type}.json")
    for i, release_time in enumerate(release_times):
        instance = Instance(copy.deepcopy(ra_pst), {}, sched, id=i)
        instance.add_release_time(release_time)
        sim.add_instance(instance, allocation_type)
    sim.simulate()

def create_full_dir(path_to_dir):
    ra_pst_file_dict = []
    for filename in os.listdir(path_to_dir):
        filepath = os.path.join(path_to_dir, filename)
        if os.path.isfile(filepath):  # Check if it's a file
            ra_pst = build_rapst(
                process_file="test_instances/paper_process_clean.xml",
                resource_file=filepath
            )
            output_dir_path = f"evaluation/paper_process_{os.path.splitext(filename)[0]}"
            ra_pst_file_dict.append({"ra_pst" : ra_pst, "output_dir_path": output_dir_path})
    return ra_pst_file_dict
    

if __name__ == "__main__":

    #for element in create_full_dir("test_instances/offer_resources"):
    #    show_tree_as_graph(element["ra_pst"])
    #    run(element["ra_pst"], AllocationTypeEnum.HEURISTIC, element["output_dir_path"])
    #    run(element["ra_pst"], AllocationTypeEnum.SINGLE_INSTANCE_CP , element["output_dir_path"])
    #    run(element["ra_pst"], AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM , element["output_dir_path"])
    #    run(element["ra_pst"], AllocationTypeEnum.ALL_INSTANCE_CP , element["output_dir_path"])

    ra_pst = build_rapst(
        process_file="test_instances/instance_generator_process.xml",
        resource_file="test_instances/instance_generator_resources.xml"
    )
    output_dir_path = "evaluation/paper_process_short_invalids"
    
    run(ra_pst, AllocationTypeEnum.HEURISTIC, output_dir_path)
    run(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP , output_dir_path)
    run(ra_pst, AllocationTypeEnum.SINGLE_INSTANCE_CP_WARM , output_dir_path)
    run(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP , output_dir_path)
    run(ra_pst, AllocationTypeEnum.ALL_INSTANCE_CP_WARM , output_dir_path)


    

    
    