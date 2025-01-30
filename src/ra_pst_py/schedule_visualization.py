import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import json


def show_scheduling_matplotlib(file):
    with open(file, "r") as f:
        ilp_result = json.load(f)

    resources = sorted(set(ilp_result["resources"]))
    resource_to_y = {resource: i for i, resource in enumerate(resources)}

    # color_list = ['#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c','#fdbf6f','#ff7f00','#cab2d6','#6a3d9a','#ffff99','#b15928'] 
    color_list = list(mcolors.XKCD_COLORS)

    plt.figure(figsize=(10, 6))
    for instance in ilp_result["instances"]:
        jobs = instance["jobs"]
        for job in jobs.values():
            y = resource_to_y[job["resource"]]
            plt.barh(y, job["cost"]*job["selected"], left=job["start"], color=color_list[int(job["branch"].split("-")[0][1:])], edgecolor="black")
            plt.text(job["start"] + job["cost"] / 2, y, job["branch"].split("-")[0], 
                    ha="center", va="center", color="white", fontsize=10) if job["selected"] else None

    plt.yticks(range(len(resources)), resources)
    plt.xlabel("Time")
    plt.ylabel("Resources")
    plt.title("Job Scheduling Visualization")
    plt.grid(axis="x", linestyle="--", alpha=0.7)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    show_scheduling_matplotlib("tests/test_data/cp_result.json")
