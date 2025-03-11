# Instance Configuration and Scheduling based on the Resource-Augmented Process Structure Tree

This Repo contains the code accompanying the publication named above. 

The computational evaluation is found in "testset_final_offline" and "testsets_final_online".

The Constraint Programming and MIP formulations can be found in. 
`source/ra_pst_py/cp_docplex_decomposed` and `source/ra_pst_py/cp_docplex`

To use the scheduling formulations, an installation of CPLEX CPOptimizer and Gurobi is needed. 
Academic Licenses are available for both solvers.

To see the evaluation results, have a look at `evaluation.ipynb`. 
To re-run the experiments. Run `use_cases.py`. 
Attention: Run-time of all experiments is > 48h. 


The ra_pst_py package enables users to create an ra_pst as xml-file, string or lxml.etree._Element.
The ra_pst is from a CPEE process model which can be run via "www.cpee.org"





