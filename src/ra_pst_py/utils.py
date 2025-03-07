from lxml import etree

def get_label(element):

    elem_etree = element if isinstance(element, etree._Element) else etree.fromstring(element)
    ns = {"cpee1" : list(elem_etree.nsmap.values())[0]}
    if elem_etree.tag == f"{{{ns['cpee1']}}}manipulate":
        return elem_etree.attrib["label"]
    elif elem_etree.tag == f"{{{ns['cpee1']}}}call":
        return elem_etree.xpath("cpee1:parameters/cpee1:label", namespaces=ns)[0].text
    else:
        raise TypeError("Wrong Element Type: No Task element Given. Type is: ", elem_etree.tag)
    
def get_allowed_roles(element):
    elem_et = etree.fromstring(element)
    ns = {"cpee1" : list(elem_et.nsmap.values())[0]}
    return [role.text for role in elem_et.xpath("cpee1:resources/cpee1:resource", namespaces=ns)]

def get_next_task(tasks_iter, instance=None):
    if instance:
        ns = instance.ra_pst.ns
    while True:
        task = next(tasks_iter, "end")
        if task == "end":
            #print("Final Task reached. solution found")
            return task
        
        # check that next task was not deleted:
        elif instance: 
            if not instance.ra_pst.ra_pst.xpath(f"//*[@id='{task.attrib['id']}'][not(ancestor::cpee1:children) and not(ancestor::cpee1:allocation) and not(ancestor::RA_RPST)]", namespaces=ns):
                pass
            else:
                break
        else:
            break
    return task


def get_process_task(ra_pst:etree._Element, task:etree._Element, ns=None):
    task_id = task.attrib["id"]
    tasks = ra_pst.xpath(f"//cpee1:manipulate[@id='{task_id}'][not(ancestor::cpee1:children) and not(ancestor::cpee1:allocation)] |" 
                         f"//cpee1:call[@id='{task_id}'][not(ancestor::cpee1:children) and not(ancestor::cpee1:allocation)]", 
                        namespaces=ns)
    task_label = get_label(task)
    tasks = [task for task in tasks if get_label(task) == task_label]
    if len(tasks) > 1:
        raise ValueError ("More than one task with same ID and label")
    return tasks[0]
    