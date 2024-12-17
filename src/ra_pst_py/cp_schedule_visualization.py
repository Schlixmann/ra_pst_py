import matplotlib.pyplot as plt
import matplotlib.cm as cm
import json

jobs = {}
resources = set()
with open("out/cp_result.json", "r") as f:
    ilp_result = json.load(f)
    for sequence, values in ilp_result.items():
        jobs[sequence] = values["jobs"]

        resources.update(set(job["resource"][0] for job in jobs[sequence]))
resources = sorted(resources)
resource_to_y = {resource: i for i, resource in enumerate(resources)}

colormap = cm.get_cmap("tab10", len(list(ilp_result.keys())))

plt.figure(figsize=(10, 6))
for sequence, values in ilp_result.items():
    for job in jobs[sequence]:
        y = resource_to_y[job["resource"][0]]
        if job["resource"][0] == "r":
            print(job["resource"][0])
        plt.barh(y, job["cost"], left=job["start"], color=colormap(int(sequence)), edgecolor="black") if job["selected"] else None
        plt.text(job["start"] + job["cost"] / 2, y, f"{sequence, job["task"], job["branch"]}", 
                ha="center", va="center", color="white", fontsize=10) if job["selected"] else None

plt.yticks(range(len(resources)), resources)
plt.xlabel("Time")
plt.ylabel("Resources")
plt.title("Job Scheduling Visualization")
plt.grid(axis="x", linestyle="--", alpha=0.7)

plt.tight_layout()
plt.show()
