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
import pathlib
from lxml import etree

class BruteForceSearch():
    def __init__(self, ra_pst:RA_PST, measure="cost"):
        self.ra_pst = ra_pst
        self.solutions = []
        self.ns = {"cpee1" : list(self.ra_pst.process.nsmap.values())[0]}
        self.pickle_writer = 0
        self.best_solutions = None
        #self.num_brute_solutions = self.get_num_brute_solutions()

    def save_best_solution_process(self, top_n = 1, out_path="out/processes/brute_force/", measure="cost"):
        if not self.best_solutions:
            raise ValueError("self.best_solutions not set. Rund 'find_solutions' first")
        pathlib.Path(out_path).mkdir(parents=True, exist_ok=True)
        for i, solution in enumerate(sorted(self.best_solutions, key=lambda d: d[measure])[:top_n]):
            instance = solution["solution"]
            path = out_path + f"brute_solution_{1}"
            instance.optimal_process = etree.fromstring(instance.optimal_process)
            instance.save_optimal_process(path)
                
    
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
        results = self.combine_pickles()
        return results
    
    def get_all_branch_combinations(self):
        branchlist = [list(range(len(values))) for values in self.ra_pst.branches.values()]
        brute_solutions = [solution for solution in itertools.product(*branchlist)]
        self.solution_space_size = len(brute_solutions)
        tasklist = self.ra_pst.get_tasklist(attribute="id")
        brute_solutions = [dict(zip(tasklist, solution)) for solution in brute_solutions]
        return brute_solutions

    def combine_pickles(self, folder_path="tmp/results", measure="cost"):
        print("combine_pickles")
        files = os.listdir(folder_path) # Get all Pickle files
        best_solutions = []
        for file in files:
            file_path = os.path.join(folder_path, file)
            if os.path.isdir(file_path):
                continue
            
            with open(file_path, "rb") as f:        
                ra_psts = pickle.load(f)
            for solution_dict in ra_psts:
                if best_solutions:
                    if solution_dict[measure] < best_solutions[0][measure] or np.isnan(best_solutions[0][measure]): 
                        best_solutions.append(solution_dict) 
                    best_solutions = sorted(best_solutions, key=lambda d: d[measure], reverse=True) 
                    if len(best_solutions) > 10: 
                        best_solutions.pop(0)
                else:
                    best_solutions.append(solution_dict)
        self.best_solutions = best_solutions
        return best_solutions

def find_best_solution(solutions): # branches ,measure, n):
    solution_branches, measure, n = solutions

    dummy_ra_pst = build_rapst("tmp/process.xml", "tmp/resources.xml")
    best_solutions = [] 
    start, start1 = time.time(), time.time()
    timetrack = []
    for i, individual in enumerate(solution_branches):
        
        start2 = time.time()
        new_solution = Instance(copy.deepcopy(dummy_ra_pst), individual) #create solution
        #new_solution.branches_to_apply = list(individual)
        created_instance = new_solution.get_optimal_instance()
        #new_solution.check_validity()
        value = new_solution.get_measure(measure, flag=False)   # calc. fitness of solution
        end2 = time.time()
        timetrack.append(end2-start2)

        if not np.isnan(value) :
            if not best_solutions:
                best_solutions.append({"solution": new_solution, "cost": value})             
            elif (value < best_solutions[0].get("cost") or np.isnan(best_solutions[0].get("cost"))) and not np.isnan(value):
                best_solutions.append({"solution": new_solution, "cost": value})
                best_solutions = sorted(best_solutions, key=lambda d: d[measure], reverse=True) 
                if len(best_solutions) > 25:
                    best_solutions.pop(0)

        if i%1000 == 0:
            end1 = time.time()
            print(f"{i}/{len(solution_branches)}, Time: {(end1-start1):.2f}")
            start1 = time.time()
        elif i%100 == 0:
            end = time.time()
            print(f"{i}/{len(solution_branches)}, Time: {(end-start):.2f}, AVG: {sum(timetrack)/len(timetrack)}")
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
        pickle.dump([solution], f)

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


