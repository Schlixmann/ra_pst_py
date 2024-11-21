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