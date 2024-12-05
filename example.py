from src.ra_pst_py.builder import build_rapst, get_rapst_etree, get_rapst_str, show_tree_as_graph, get_ilp_rep
from src.ra_pst_py.ilp import configuration_ilp, scheduling_ilp, combined_ilp

import json

# Build RA-PST
ra_pst = build_rapst(process_file="example_data/test_process_cpee.xml",
                     resource_file="example_data/test_resource.xml")

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

# Same with processes from paper
ra_pst2 = build_rapst(process_file="test_instances/paper_process_short.xml",
                     resource_file="test_instances/resources_paper_process_short.xml")
show_tree_as_graph(ra_pst2)

ra_pst3 = build_rapst(process_file="test_instances/instance_generator_process.xml",
                     resource_file="test_instances/instance_generator_resources.xml")
show_tree_as_graph(ra_pst3, output_file="graphs/ra_pst3")

ra_pst4 = build_rapst(process_file="test_instances/paper_process.xml",
                     resource_file="test_instances/resources_paper_process_long.xml")
show_tree_as_graph(ra_pst4, output_file="graphs/ra_pst4")

ilp_rep2 = ra_pst2.get_ilp_rep()
ilp_rep3 = ra_pst3.get_ilp_rep()
# ilp_rep4 = ra_pst4.get_ilp_rep()

with open("ilp_rep.json", "w") as f:
    json.dump(ilp_rep3, f, indent=2)
    f.close()

conf_ilp = combined_ilp("ilp_rep.json")
