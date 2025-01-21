from src.ra_pst_py.builder import build_rapst, show_tree_as_graph
from src.ra_pst_py.simulator import Simulator
from src.ra_pst_py.heuristic import TaskAllocator
from src.ra_pst_py.instance import Instance
from src.ra_pst_py.schedule import Schedule, print_schedule
from src.ra_pst_py.core import RA_PST

from lxml import etree
import unittest
import json
import copy
import time

def run(ra_pst:RA_PST) -> dict:
    # Main File to test multiple use cases for paper
    sched = Schedule()
    results = {}
    release_times = [0,10,23]

    # Heuristic Single Task allocation
    sim = Simulator()
    allocation_type = "heuristic"

    for i, release_time in enumerate(release_times):
        instance = Instance(copy.deepcopy(ra_pst), {}, sched, id=i)
        instance.add_release_time(release_time)
        sim.add_instance(instance, allocation_type)

    start = time.time()
    sim.simulate()
    end = time.time()

    with open(f"out/schedule_{allocation_type}.json") as f:
        jobs = json.load(f)
        results[allocation_type] = {}
        results[allocation_type]["objective"] = jobs["solution"]["objective"]
        results[allocation_type]["time"] = str(end - start)
        print(f"Objective: {jobs["solution"]['objective']}")

    return results

if __name__ == "__main__":
    ra_pst = build_rapst(
        process_file="test_instances/paper_process_short.xml",
        resource_file="test_instances/offer_resources_many_invalid_branches_sched.xml"
    )
    run(ra_pst)