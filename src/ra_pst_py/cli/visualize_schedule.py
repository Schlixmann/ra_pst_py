import argparse
import json

from src.ra_pst_py.schedule_visualization_plotly import show_schedule

def visualize_schedule(json_file):
    """Loads a JSON schedule file and visualizes it using schedule_visualization_plotly."""
    try:
        with open(json_file, "r") as file:
            schedule_data = json.load(file)
        
        # Call the visualization function from your script
        show_schedule(json_file)

    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found.")
    except json.JSONDecodeError:
        print(f"Error: '{json_file}' is not a valid JSON file.")

def main():
    parser = argparse.ArgumentParser(description="Visualize schedule files using Plotly.")
    
    parser.add_argument(
        "json_file", type=str, help="Path to the JSON schedule file to visualize."
    )

    args = parser.parse_args()
    
    visualize_schedule(args.json_file)

if __name__ == "__main__":
    main()