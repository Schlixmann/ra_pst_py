from src.ra_pst_py.builder import build_rapst, get_rapst_etree, get_rapst_str, show_tree_as_graph, get_ilp_rep
from src.ra_pst_py.ilp import configuration_ilp, scheduling_ilp, combined_ilp
from src.ra_pst_py.brute_force import build_optimized_instance_brute

ra_pst = build_rapst(
        process_file="gen_test/BPM_TestSet_20.xml",
        resource_file="gen_test/test_config.xml"
    )
ra_pst.save_ra_pst("gen_test/test.xml")
show_tree_as_graph(ra_pst)