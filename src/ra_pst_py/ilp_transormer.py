from .core import RA_PST

### currently unused module ###
class IlpTransformer():
    """
    Transforms and RA-PST into the needed datastructures for an ILP
    has multiple functions to retrieve different data needed for ILP
    """

    def __init__(self, ra_pst:RA_PST):
        self.ra_pst = ra_pst

    def get_tasklist(self, attribute:str = None) -> list:
        "Returns list of all Task-Ids in self.ra_pst"
        tasklist = self.ra_pst.xpath("(//cpee1:call|//cpee1:manipulate)[not (ancestor::cpee1:children|ancestor::cpee1:allocation)]", namespaces=self.ns)
        if not attribute:
            return tasklist
        else:
            return [task.attrib[f"{attribute}"] for task in tasklist]
        
    def get_resourcelist(self) -> list:
        "Returns list of all Resource-IDs in self.resource_url"
        tree = self.resource_url
        resources = tree.xpath("//resource[not(descendant::cpee1:changepattern)]", namespaces=self.ns)
        return [resource.attrib["id"] for resource in resources]

    def get_branches_as_jobs(self) -> dict:
        self.ra_pst.get_branches_ilp()


