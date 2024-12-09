from src.ra_pst_py.builder import build_rapst, get_rapst_etree, get_rapst_str, build_optimized_instance, show_tree_as_graph, get_ilp_rep
from src.ra_pst_py.ilp import configuration_ilp, scheduling_ilp, combined_ilp
from src.ra_pst_py.brute_force import BruteForceSearch

ra_pst = build_rapst(
            process_file="test_instances/paper_process_short.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
instance = build_optimized_instance(ra_pst=ra_pst)
instance.save_optimal_process(f"out/processes/ilp_short.xml")
cost = instance.get_measure(measure="cost")

search = BruteForceSearch(ra_pst)
all_options = search.get_all_branch_combinations()
results = search.find_solutions(all_options)
search.save_best_solution_process(top_n=1)
print(f"Brute force costs = {results[-1]['cost']}, ilp cost = {cost}")

ra_pst = build_rapst(
            process_file="test_instances/paper_process_shorter.xml",
            resource_file="test_instances/offer_resources_many_invalid_branches.xml"
        )
instance = build_optimized_instance(ra_pst=ra_pst)
instance.save_optimal_process(f"out/processes/ilp_short.xml")
cost = instance.get_measure(measure="cost")

search = BruteForceSearch(ra_pst)
all_options = search.get_all_branch_combinations()
print(len(all_options))
results = search.find_solutions(all_options)
search.save_best_solution_process(top_n=1)
print(f"Brute force costs = {results[-1]['cost']}, ilp cost = {cost}")

