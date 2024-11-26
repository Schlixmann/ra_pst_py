from src.ra_pst_py.builder import build_rapst, get_rapst_etree, get_rapst_str, show_tree_as_graph, get_ilp_rep

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
show_tree_as_graph(ra_pst)

# Get a dict which is available for an ilp representation of the RA-PST
# the current shape is:
# {
#   tasks: list of tasks,
#   resources: list of resources,
#   branches: dict(task : [branch1[(job1),(job2),...], branch2]))
#    }
ilp_rep = ra_pst.get_ilp_rep()
