from src.ra_pst_py.builder import build_rapst, get_rapst_etree, get_rapst_str, show_tree_as_graph

# Build RA-PST
ra_pst = build_rapst(process_file="example_data/test_process_cpee.xml", resource_file="example_data/test_resource.xml")

# Get RA-PST as binary string
ra_pst_str = get_rapst_str(process_file="example_data/test_process_cpee.xml", resource_file="example_data/test_resource.xml")
print(f"RA-PST first letters: {ra_pst_str[:55]}")

# Get RA-PST as etree
ra_pst_et = get_rapst_etree(process_file="example_data/test_process_cpee.xml", resource_file="example_data/test_resource.xml")
print(f"RA-PST element: {ra_pst_et}")

# Save RA-PST at specified location
ra_pst.save_ra_pst("rapst.xml")

show_tree_as_graph("rapst.xml")

