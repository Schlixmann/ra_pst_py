from src.ra_pst_py.core import RA_PST

class DepthFirstHeuristic():
    """
    Heuristic solution approach to solve the scheduling problem.
    Adaption of Xu 2016 to RA-PST
    """

class DynamicLocalHeuristic():
    pass

class DynamicGlobalHeuristic():


    def __init__(self, instances):
        self.instances = instances

    def solve(self):
        #BG Strategy
        # Resources are used to schedule the task with minimal penalty based on all instances
        # Based on 3 Rules to determine prioritised task:
        # 1: When slt is allocated to task t, total time gap increase of all task influences penalty
        # 2: Instances with few unscheduled tasks get scheduled first
        # 3: Penalty gets higher, if mor instances have to divert from their optimal branch. 
        # -> since overall resource usage rises 
        
        pass


class Scheduler():
    def __init__(self, solver):
        self.solver = solver
        instances = [RA_PST]

