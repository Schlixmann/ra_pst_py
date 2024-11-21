from lxml import etree
import os

def parse_process_file(process_file):
    if isinstance(process_file, etree._Element):
        process = process_file
    elif os.path.isfile(process_file):
        with open(process_file, "r") as f:
           process = etree.fromstring(f.read())
    elif type(process_file) == str:
        process = etree.fromstring(process_file)
    else:
        raise TypeError(f" 'process_file' must be of type path to a file, xml-str, or etree._Element")
    proc_ns = {'cpee1':'http://cpee.org/ns/description/1.0'}
    process = process.xpath(f"//cpee1:description", namespaces = proc_ns)[0]
    return process

def parse_resource_file(resource_file):
    if isinstance(resource_file, etree._Element):
        resource =  resource_file
    elif os.path.isfile(resource_file):
        with open(resource_file, "r") as f:
           resource = etree.fromstring(f.read())
    elif type(resource_file) == str:
        resource = etree.fromstring(resource_file)
    else:
        raise TypeError(f" 'process_file' must be of type path to a file, xml-str, or etree._Element")
    return resource
        

    