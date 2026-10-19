# from ddos_historic_data import generate_historic_flows
from ddos_visualizer_data import generate_recent_flows
import combine_layers
import pandas as pd
from pathlib import Path

current_dir = Path(__file__).resolve().parent
project_dir = current_dir.parent


if __name__ == '__main__':
    # layer3_flows = generate_recent_flows(layer='layer3', max_attack_count=1_000_000)
    # df = layer3_flows['flows']
    # df.to_csv(project_dir / "layer3_flows.csv", index=False)

    # layer7_flows = generate_recent_flows(layer='layer7', max_attack_count=1_000_000)
    # df = layer7_flows['flows']
    # df.to_csv(project_dir / "layer7_flows.csv", index=False)

    combine_layers.main()