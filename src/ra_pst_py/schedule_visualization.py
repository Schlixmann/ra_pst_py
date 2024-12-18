import matplotlib.pyplot as plt
import matplotlib.cm as cm
import json
import random


with open("out/ilp_result.json", "r") as f:
    ilp_result = json.load(f)
    jobs = ilp_result["jobs"]

resources = sorted(set(job["resource"] for job in jobs.values()))
resource_to_y = {resource: i for i, resource in enumerate(resources)}

colormap = cm.get_cmap("tab10", len(ilp_result["branches"]))

plt.figure(figsize=(10, 6))
for job in jobs.values():
    y = resource_to_y[job["resource"]]
    plt.barh(y, job["cost"]*job["selected"], left=job["start"], color=colormap(random.randint(0,len(ilp_result["branches"]))), edgecolor="black")
    plt.text(job["start"] + job["cost"] / 2, y, job["branch"], 
             ha="center", va="center", color="white", fontsize=10) if job["selected"] else None

plt.yticks(range(len(resources)), resources)
plt.xlabel("Time")
plt.ylabel("Resources")
plt.title("Job Scheduling Visualization")
plt.grid(axis="x", linestyle="--", alpha=0.7)

plt.tight_layout()
plt.show()
