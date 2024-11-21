from lxml import etree
import os

def parse_process_file(process_file):
    if isinstance(process_file, etree._Element):
        process = process_file
    elif os.path.isfile(process_file):
        with open(process_file, "r") as f:
           process = etree.fromstring(f.read())
    
    proc_ns = {'cpee1':'http://cpee.org/ns/description/1.0'}
    process = process.xpath(f"//cpee1:description", namespaces = proc_ns)[0]
    return process

def parse_resource_file(resource_file):
    if isinstance(resource_file, etree._Element):
        return resource_file
    elif os.path.isfile(resource_file):
        with open(resource_file, "r") as f:
           resource = etree.fromstring(f.read())
           return resource
        

    