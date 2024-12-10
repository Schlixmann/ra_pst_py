from src.ra_pst_py.builder import build_rapst, get_rapst_etree, get_rapst_str, build_optimized_instance, show_tree_as_graph, get_ilp_rep
from src.ra_pst_py.ilp import configuration_ilp, scheduling_ilp, combined_ilp
from src.ra_pst_py.brute_force import BruteForceSearch

from collections import defaultdict

cost_dict = defaultdict(list)

ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
instance = build_optimized_instance(ra_pst=ra_pst)
instance.save_optimal_process(f"out/processes/ilp_short.xml")
cost_dict["ilp"].append(instance.get_measure(measure="cost"))

search = BruteForceSearch(ra_pst)
all_options = search.get_all_branch_combinations()
results = search.find_solutions(all_options)
search.save_best_solution_process(top_n=1)
cost_dict["brute"].append(results[-1]['cost']) 
print(f"Brute force costs = {results[-1]['cost']}, ilp cost = {cost_dict["ilp"][-1]}")


ra_pst = build_rapst(
            process_file="test_instances/paper_process_shorter.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
instance = build_optimized_instance(ra_pst=ra_pst)
instance.save_optimal_process(f"out/processes/ilp_short.xml")
cost_dict["ilp"].append(instance.get_measure(measure="cost"))

search = BruteForceSearch(ra_pst)
all_options = search.get_all_branch_combinations()
print(len(all_options))
results = search.find_solutions(all_options)
search.save_best_solution_process(top_n=1)
cost_dict["brute"].append(results[-1]['cost']) 
print(f"Brute force costs = {results[-1]['cost']}, ilp cost = {cost_dict["ilp"][-1]}")


ra_pst = build_rapst(
            process_file="test_instances/paper_process.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
instance = build_optimized_instance(ra_pst=ra_pst)
instance.save_optimal_process(f"out/processes/ilp_invalids.xml")
cost_dict["ilp"].append(instance.get_measure(measure="cost"))

search = BruteForceSearch(ra_pst)
all_options = search.get_all_branch_combinations()
print(len(all_options))
results = search.find_solutions(all_options)
search.save_best_solution_process(top_n=1, out_file="out/processes/brute_force/brute_invalid.xml")
cost_dict["brute"].append(results[-1]['cost']) 
print(f"Brute force costs = {results[-1]['cost']}, ilp cost = {cost_dict["ilp"][-1]}")
print(cost_dict)

ra_pst = build_rapst(
            process_file="test_instances/paper_process.xml",
            resource_file="test_instances/offer_resources_heterogen.xml"
        )
instance = build_optimized_instance(ra_pst=ra_pst)
instance.save_optimal_process(f"out/processes/ilp_heterogen.xml")
cost_dict["ilp"].append(instance.get_measure(measure="cost"))

search = BruteForceSearch(ra_pst)
all_options = search.get_all_branch_combinations()
print(len(all_options))
results = search.find_solutions(all_options)
search.save_best_solution_process(top_n=1, out_file="out/processes/brute_force/brute_heterogen.xml")
cost_dict["brute"].append(results[-1]['cost']) 
print(f"Brute force costs = {results[-1]['cost']}, ilp cost = {cost_dict["ilp"][-1]}")
print(cost_dict)

"""
ra_pst = build_rapst(
            process_file="test_instances/paper_process.xml",
            resource_file="test_instances/offer_resources_plain_fully_synthetic_small.xml"
        )
instance = build_optimized_instance(ra_pst=ra_pst)
instance.save_optimal_process(f"out/processes/ilp_fully_synthetic.xml")
cost_dict["ilp"].append(instance.get_measure(measure="cost"))

search = BruteForceSearch(ra_pst)
all_options = search.get_all_branch_combinations()
print(len(all_options))
results = search.find_solutions(all_options)
search.save_best_solution_process(top_n=1, out_file="out/processes/brute_force/brute_fully_snythetic.xml")
cost_dict["brute"].append(results[-1]['cost']) 
print(f"Brute force costs = {results[-1]['cost']}, ilp cost = {cost_dict["ilp"][-1]}")
print(cost_dict)
"""

ra_pst = build_rapst(
            process_file="test_instances/paper_process.xml",
            resource_file="test_instances/offer_resources_close_maxima.xml"
        )
instance = build_optimized_instance(ra_pst=ra_pst)
instance.save_optimal_process(f"out/processes/ilp_close_maxima.xml")
cost_dict["ilp"].append(instance.get_measure(measure="cost"))

search = BruteForceSearch(ra_pst)
all_options = search.get_all_branch_combinations()
print(len(all_options))
results = search.find_solutions(all_options)
search.save_best_solution_process(top_n=1, out_file="out/processes/brute_force/brute_close_maxima.xml")
cost_dict["brute"].append(results[-1]['cost']) 
print(f"Brute force costs = {results[-1]['cost']}, ilp cost = {cost_dict["ilp"][-1]}")
print(cost_dict)

