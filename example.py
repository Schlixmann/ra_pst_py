from src.ra_pst_py.builder import build_rapst, get_rapst_etree, get_rapst_str, build_optimized_instance, show_tree_as_graph, get_ilp_rep
from src.ra_pst_py.ilp import configuration_ilp, scheduling_ilp, combined_ilp
from src.ra_pst_py.brute_force import build_optimized_instance_brute

def run():
    # Build RA-PST
    ra_pst = build_rapst(process_file="example_data/test_process_cpee.xml",
                        resource_file="example_data/test_resource.xml")

    # Same with processes from paper
    ra_pst2 = build_rapst(process_file="test_instances/paper_process_short.xml",
                        resource_file="test_instances/resources_paper_process_short.xml")
    ra_pst2.save_ra_pst("out/ra_pst_short.xml")

    # Get RA-PST as binary string
    ra_pst_str = get_rapst_str(process_file="example_data/test_process_cpee.xml",
                            resource_file="example_data/test_resource.xml")
    print(f"RA-PST first letters: {ra_pst_str[:55]}")

    # Get RA-PST as etree
    ra_pst_et = get_rapst_etree(process_file="example_data/test_process_cpee.xml",
                                resource_file="example_data/test_resource.xml")
    print(f"RA-PST element: {ra_pst_et}")

    # Save RA-PST at specified location
    ra_pst.save_ra_pst("rapst.xml")

    # Prints tree as graphviz graph
    #show_tree_as_graph(ra_pst)

    # Get a dict which is available for an ilp representation of the RA-PST
    # the current shape is:
    # {
    #   tasks: list of tasks,
    #   resources: list of resources,
    #   branches: dict(task : [branch1[(job1),(job2),...], branch2]))
    #    }
    ilp_rep = ra_pst.get_ilp_rep()

    ra_psts = {}


    #show_tree_as_graph(ra_pst2)

    #ra_pst3 = build_rapst(process_file="test_instances/instance_generator_process.xml",
    #                     resource_file="test_instances/instance_generator_resources.xml")
    #ra_psts["generated_process"] = ra_pst3
    #show_tree_as_graph(ra_pst3, output_file="graphs/ra_pst3")

    ra_pst4 = build_rapst(process_file="test_instances/paper_process.xml",
                        resource_file="test_instances/offer_resources_heterogen.xml")
    ra_psts["paper_heterogen"] = ra_pst4
    #show_tree_as_graph(ra_pst4, output_file="graphs/ra_pst4")

    ra_pst5 = build_rapst(process_file="test_instances/paper_process.xml",
                        resource_file="test_instances/offer_resources_many_invalid_branches.xml")
    ra_psts["paper_invalids"] = ra_pst5
    #show_tree_as_graph(ra_pst4, output_file="graphs/ra_pst4")

    for key, ra_pst in ra_psts.items():
        instance = build_optimized_instance(ra_pst=ra_pst, solver = "ilp") # you can specify solver "ilp" or "cp"
        instance.save_optimal_process(f"out/processes/{key}.xml")

    # find optimal instance with brute force approach
    # Beware: only useful for smaller sets 
    ra_pst = build_rapst(
                process_file="test_instances/paper_process_short.xml",
                resource_file="test_instances/offer_resources_many_invalid_branches.xml"
            )
    instance = build_optimized_instance_brute(ra_pst=ra_pst)
    instance.save_optimal_process(f"out/process/brute_heterogen.xml")
    print(f"Value of best BruteForce instance: {instance.get_measure(measure='cost')}") 


if __name__ == "__main__":
    ra_pst = build_rapst(
        process_file="",
        resource_file="testsets/testset1/resources/resources_050_random_uni_cost.xml"
    )
    ra_pst.save_ra_pst("out/test_050_random_uni_cost.xml")
    show_tree_as_graph(ra_pst)

