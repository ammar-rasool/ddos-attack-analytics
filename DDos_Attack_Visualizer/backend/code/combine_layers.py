"""
combine_layers.py
-----------------
Fetches Layer 3 and Layer 7 DDoS flow data, tags each row with its
attack layer, interleaves the rows (one Layer 7 row followed by one
Layer 3 row), and saves the resulting DataFrame as a JSON file in the
parent directory of this script.
"""

from ddos_visualizer_data import generate_recent_flows
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent  # one level above DDos_Attack_Visualizer/
OUTPUT_PATH = PARENT_DIR / "data" / "combined_ddos_flows.json"


def interleave_dataframes(df_l7: pd.DataFrame, df_l3: pd.DataFrame) -> pd.DataFrame:
    """
    Interleave two DataFrames row-by-row: one Layer 7 row followed by
    one Layer 3 row.  If one DataFrame is longer than the other, the
    remaining rows of the longer one are appended at the end.

    Parameters
    ----------
    df_l7 : pd.DataFrame  – Layer 7 flows (already tagged)
    df_l3 : pd.DataFrame  – Layer 3 flows (already tagged)

    Returns
    -------
    pd.DataFrame  – interleaved and reset-indexed DataFrame
    """
    len7, len3 = len(df_l7), len(df_l3)
    min_len = min(len7, len3)

    # Build interleaved portion
    interleaved_parts: list[pd.DataFrame] = []
    for i in range(min_len):
        interleaved_parts.append(df_l7.iloc[[i]])
        interleaved_parts.append(df_l3.iloc[[i]])

    # Append any leftover rows
    if len7 > min_len:
        interleaved_parts.append(df_l7.iloc[min_len:])
    elif len3 > min_len:
        interleaved_parts.append(df_l3.iloc[min_len:])

    combined = pd.concat(interleaved_parts, ignore_index=True)
    return combined


def main() -> None:
    # -----------------------------------------------------------------------
    # 1. Fetch data for both layers
    # -----------------------------------------------------------------------
    logger.info("Fetching Layer 7 flows …")
    layer7_result = generate_recent_flows(layer="layer7", max_attack_count=500_000)
    df_l7: pd.DataFrame = layer7_result["flows"].copy()

    logger.info("Fetching Layer 3 flows …")
    layer3_result = generate_recent_flows(layer="layer3", max_attack_count=500_000)
    df_l3: pd.DataFrame = layer3_result["flows"].copy()

    if df_l7.empty and df_l3.empty:
        logger.error("Both layer DataFrames are empty – nothing to combine.")
        return

    # -----------------------------------------------------------------------
    # 2. Tag each row with its attack layer
    # -----------------------------------------------------------------------
    df_l7["attack_layer"] = "Layer 7"
    df_l3["attack_layer"] = "Layer 3"

    logger.info(f"Layer 7 rows: {len(df_l7):,}  |  Layer 3 rows: {len(df_l3):,}")

    # -----------------------------------------------------------------------
    # 3. Interleave: one Layer 7 row then one Layer 3 row
    # -----------------------------------------------------------------------
    combined_df = interleave_dataframes(df_l7, df_l3)

    logger.info(f"Combined DataFrame rows: {len(combined_df):,}")

    # -----------------------------------------------------------------------
    # 4. Reorder columns so attack_layer is clearly visible near the front
    # -----------------------------------------------------------------------
    base_cols = [
        "attack_layer",
        "timestamp",
        "origin",
        "origin_lat",
        "origin_lng",
        "target",
        "target_lat",
        "target_lng",
        "attack_intensity",
        "hourly_probability",
    ]
    # Keep any unexpected extra columns at the end
    extra_cols = [c for c in combined_df.columns if c not in base_cols]
    combined_df = combined_df[base_cols + extra_cols]

    # -----------------------------------------------------------------------
    # 5. Convert to JSON and save
    # -----------------------------------------------------------------------
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_json(
        OUTPUT_PATH,
        orient="records",   # list of {col: value, …} objects — easy for JS/globe.gl
        indent=2,
        force_ascii=False,
        date_format="iso",
    )

    logger.info(f"JSON saved to: {OUTPUT_PATH}")
    print(f"\n[DONE] Combined JSON saved to:\n    {OUTPUT_PATH}")
    print(f"    Total records : {len(combined_df):,}")
    print(f"    Layer 7 rows  : {len(df_l7):,}")
    print(f"    Layer 3 rows  : {len(df_l3):,}")



