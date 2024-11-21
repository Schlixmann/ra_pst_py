from src.builder import *

# Build RA-PST
ra_pst = get_rapst(process_file="example_data/test_process_cpee.xml", resource_file="example_data/test_resource.xml")

# Get RA-PST as binary string
ra_pst_st = get_rapst_str(process_file="example_data/test_process_cpee.xml", resource_file="example_data/test_resource.xml")

# Get RA-PST as etree
ra_pst_et = get_rapst_etree(process_file="example_data/test_process_cpee.xml", resource_file="example_data/test_resource.xml")

# Save RA-PST at specified location
ra_pst.save_ra_pst("rapst.xml")

