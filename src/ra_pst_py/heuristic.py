from lxml import etree
import numpy as np

def find_best_resource(task:etree._Element, ns, schedule) -> None:
    """
    Finds best availabe timeslot for one task of an RA-PST.
    """
    earliest_start = np.inf
    earliest_finish = np.inf
    allocated_resource = None
    release_time = float(task.xpath("cpee1:release_time", namespaces = ns)[0].text)

    # Iterate over all resources and resource profiles to find slot with earliest possible finishing time
    for resource in task.xpath("cpee1:children/cpee1:resource/cpee1:resprofile", namespaces=ns):
        resource_name = resource.xpath("parent::cpee1:resource", namespaces=ns)[0].attrib["id"]
        duration = float(resource.xpath(f"cpee1:measures/cpee1:cost", namespaces=ns)[0].text)
        timeslot_matrix = schedule.get_timeslot_matrix(float(release_time), resource_name)
        possible_slots = np.argwhere(np.diff(timeslot_matrix) >= duration)
        if possible_slots.size > 0:
            for slot in possible_slots:
                earliest_slot = float(timeslot_matrix[slot[0]][0])
                if earliest_slot+duration < earliest_finish and earliest_slot >= float(release_time):
                    earliest_start = earliest_slot
                    earliest_finish = earliest_slot+duration
                    allocated_resource = resource_name
                elif timeslot_matrix[slot[0]][1] == np.inf and earliest_start == np.inf:
                    earliest_start = release_time
                    earliest_finish = earliest_slot+duration
                    allocated_resource = resource_name
        else:
            raise ValueError("No timeslot found")
    if allocated_resource is None:
        raise ValueError("No slot and resource found")
    #print(f" Best start: {earliest_start}, on resource {allocated_resource}")
    return allocated_resource, earliest_start, duration


def allocate_task(task:etree._Element, ns, schedule) -> None:
    """
    Allocates a task to a resource and propagate through ra_pst
    """

    
    resource, start_time, duration = find_best_resource(task, ns, schedule)
    schedule.add_task(task, resource, start_time, duration)
    
import matplotlib.pyplot as plt
import matplotlib.cm as cm
def print_schedule(schedule):
    resources = sorted(set(schedule.keys()))
    resource_to_y = {resource: i for i, resource in enumerate(resources)}

    colormap = cm.get_cmap("tab10", len(schedule.values()))

    plt.figure(figsize=(10, 6))
    for resource, tasks in schedule.items():
        y = resource_to_y[resource]
        for task in tasks:
            plt.barh(y, task["duration"], left=task["start_time"], edgecolor="black")
            plt.text(task["start_time"] + task["duration"] / 2, y, task["instance"], 
                    ha="center", va="center", color="white", fontsize=10)

    plt.yticks(range(len(resources)), resources)
    plt.xlabel("Time")
    plt.ylabel("Resources")
    plt.title("Job Scheduling Visualization")
    plt.grid(axis="x", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.show()