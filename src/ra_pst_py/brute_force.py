from src.ra_pst_py.instance import Instance
from src.ra_pst_py.core import RA_PST
from src.ra_pst_py.builder import build_rapst

import multiprocessing as mp
import numpy as np
import itertools
import pickle
import os
import time
import copy
import uuid
from lxml import etree

class BruteForceSearch():
    def __init__(self, ra_pst:RA_PST, measure="cost"):
        self.ra_pst = ra_pst
        self.solutions = []
        self.ns = {"cpee1" : list(self.ra_pst.process.nsmap.values())[0]}
        self.pickle_writer = 0
        #self.num_brute_solutions = self.get_num_brute_solutions()
    
    def find_solutions(self, solutions, measure="cost"):
        pool = mp.Pool()
        results = {1:[]}
        num_parts = mp.cpu_count()
        part_size = len(solutions) // num_parts
        list_parts = []
        
        folder_name = 'tmp'
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            os.makedirs(folder_name + "/results")
        

        tree = etree.ElementTree(self.ra_pst.raw_process)
        etree.indent(tree, space="\t", level=0)
        tree.write("tmp/process.xml")
    
        tree = etree.ElementTree(self.ra_pst.resource_url)
        etree.indent(tree, space="\t", level=0)
        tree.write("tmp/resources.xml")
        list_parts = [solutions[part_size * i : part_size * (i + 1)] for i in range(num_parts)]

        #for i, lst in enumerate(list_parts):
        #    for test in lst:
        #        find_best_solution((lst, measure, i))

        results[1] = pool.map(find_best_solution, [(part, measure, i) for i, part in enumerate(list_parts)])
        pool.close()
        pool.join()
        print(results [1])
    
    def get_all_branch_combinations(self):
        branchlist = [list(range(len(values))) for values in self.ra_pst.branches.values()]
        brute_solutions = [solution for solution in itertools.product(*branchlist)]
        self.solution_space_size = len(brute_solutions)
        tasklist = self.ra_pst.get_tasklist(attribute="id")
        brute_solutions = [dict(zip(tasklist, solution)) for solution in brute_solutions]
        return brute_solutions

def find_best_solution(solutions): # branches ,measure, n):
    solution_branches, measure, n = solutions

    dummy_ra_pst = build_rapst("tmp/process.xml", "tmp/resources.xml")
    best_solutions = [] 
    start = time.time()
    for i, individual in enumerate(solution_branches):
        
        new_solution = Instance(copy.copy(dummy_ra_pst), individual) #create solution
        #new_solution.branches_to_apply = list(individual)
        created_instance = new_solution.get_optimal_instance()
        #new_solution.check_validity()
        value = new_solution.get_measure(measure, flag=False)   # calc. fitness of solution
        

        if not np.isnan(value) :
            if not best_solutions:
                best_solutions.append({"solution": new_solution, "cost": value})             
            elif (value < best_solutions[0].get("cost") or np.isnan(best_solutions[0].get("cost"))) and not np.isnan(value):
                best_solutions.append({"solution": new_solution, "cost": value})
                best_solutions = sorted(best_solutions, key=lambda d: d[measure], reverse=True) 
                if len(best_solutions) > 25:
                    best_solutions.pop(0)
    
        if i%1000 == 0:
            end = time.time()
            print(f"{i}/{len(solution_branches)}, Time: {(end-start):.2f}")
            start = time.time()
    
    print("Best solutions: ", best_solutions)
    if best_solutions:
        dump_to_pickle(best_solutions, n)
    return (f"done_{n}")

def dump_to_pickle(best_solutions, i):
    #for solution in best_solutions:
    #    solution["solution"] = solution["solution"].get_pickleable_object()

    solution = best_solutions[-1]
    solution = instance_to_pickle(solution["solution"])
    solution = {"solution": solution, "cost": best_solutions[-1]["cost"]}
    with open(f"tmp/results/results_{i}.pkl", "wb") as f:
        pickle.dump(solution, f)

def instance_to_pickle(solution):
    solution = copy.deepcopy(solution)
    solution.ra_pst = None
    solution.ns = {"cpee1": list(solution.optimal_process.nsmap.values())[
        0], "allo": "http://cpee.org/ns/allocation"}
    solution.optimal_process = etree.tostring(solution.optimal_process)
    solution.change_op = None
    solution.tasks_iter = None
    solution.current_task = None

    solution.branches_to_apply = {}
    solution.applied_branches = {}
    solution.delayed_deletes = []
    solution.invalid = False

    return solution

def combine_pickles(folder_path="tmp/results", measure="cost"):
    print("combine_pickles")
    files = os.listdir(folder_path)
    best_solutions = []
    for file in files:
        file_path = folder_path + "/" + file
        if os.path.isdir(file_path):
            continue
        
        with open(file_path, "rb") as f:        
            dd = pickle.load(f)
        for d in dd:
            if best_solutions:
                if d.get("cost") < best_solutions[0].get(measure) or np.isnan(best_solutions[0].get(measure)): 
                    best_solutions.append(d) 
                best_solutions = sorted(best_solutions, key=lambda d: d[measure], reverse=True) 
                if len(best_solutions) > 10: 
                    best_solutions.pop(0)
            else:
                best_solutions.append(d)
    return best_solutions
