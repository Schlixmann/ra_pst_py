import plotly.graph_objects as go
import json

def show_schedule(path):
    # Load data
    jobs = {}
    resources = set()
    with open(path, "r") as f:
        ilp_result = json.load(f)

    # Prepare data
    resources.update(ilp_result["resources"])
    resources = sorted(resources)
    resource_to_y = {resource: i for i, resource in enumerate(resources)}

    # Create color mapping for sequences
    sequences = list(ilp_result["instances"])
    colors = [f"rgba({i*25 % 255}, {i*50 % 255}, {i*75 % 255}, 0.8)" for i in range(len(sequences))]

    # Initialize Plotly figure
    fig = go.Figure()

    # Add traces for each job
    for instance in ilp_result["instances"]:
        first_job = True  # Flag to control legend display for the first job in each sequence
        for job_ref, job in instance["jobs"].items():
            y = resource_to_y[job["resource"]]
            if job["selected"]:
                fig.add_trace(
                    go.Bar(
                        x=[job["cost"]],
                        y=[resources[y]],
                        base=job["start"],
                        orientation="h",
                        name=f"Sequence {sequences.index(instance)}",
                        legendgroup=f"Sequence {sequences.index(instance)}",  # Group legend entries
                        showlegend=first_job,
                        text=f"Task: {job_ref}<br>Branch: {job['branch']}",
                        hoverinfo="text",
                        marker=dict(color=colors[int(sequences.index(instance))]),
                    )
                )
                first_job = False  # Set to False after the first job in the sequence

    # Update layout
    fig.update_layout(
        title="Job Scheduling Visualization",
        xaxis=dict(title="Time", gridcolor="lightgray"),
        yaxis=dict(
            title="Resources",
            tickvals=list(range(len(resources))),
            ticktext=resources,
        ),
        barmode="stack",
        showlegend=True,
        legend_title="Sequences",
        plot_bgcolor="white",
    )

    # Show plot
    print(f"Objective: {ilp_result['objective']}")
    fig.show()

if __name__ == "__main__":
    #show_schedule("out/sim_schedule.json")
    #show_schedule("out/cp_rep_multiinstance.json")
    show_schedule("out/schedule_cp_all.json")
    show_schedule("out/schedule_cp_single_instance.json")
    #show_schedule("out/schedule_heuristic.json")
    show_schedule("tests/test_data/cp_result copy.json")
