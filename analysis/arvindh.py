#!/usr/bin/env python3
"""
Plot AoI vs Packet Loss as a box and whisker plot.
Three groups: one for each lambda (0.0, 0.5, 1.0).
Uses parsing functions from analyze_latency.py.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# Import functions from analyze_latency.py
from analyze_latency import parse_csv, calculate_latency

RESULTS_DIR = Path(__file__).parent.parent / "packetloss_test_results"
OUTPUT_DIR = Path(__file__).parent

# Thresholds for filtering
OUTLIER_THRESHOLD = 8.0  # seconds
MIN_SAMPLES_PER_ITERATION = 100
MAX_MEAN_AOI = 7.5  # seconds


def calculate_aoi_for_iteration(iteration_path):
    """Calculate AoI values for a single iteration using analyze_latency functions."""
    client_out = iteration_path / "client_out.log"
    output_log = iteration_path / "output.log"

    try:
        client_log = parse_csv(str(client_out))
        server_log = parse_csv(str(output_log))
    except (FileNotFoundError, Exception):
        return []

    if not client_log or not server_log:
        return []

    latency = calculate_latency(client_log, server_log)

    # Extract non-None positive latency values
    aoi_values = [v for v in latency.values() if v is not None and v > 0]

    return aoi_values


def collect_all_data():
    """Collect all AoI data with iteration-level filtering."""
    all_data = []

    for dir_name in os.listdir(RESULTS_DIR):
        dir_path = RESULTS_DIR / dir_name
        if not dir_path.is_dir() or not dir_name.startswith("lambda_"):
            continue

        # Parse lambda and loss from directory name
        parts = dir_name.split("_")
        try:
            lambda_idx = parts.index("lambda") + 1
            loss_idx = parts.index("loss") + 1
            lambda_val = float(parts[lambda_idx])
            loss_val = int(parts[loss_idx].replace("pct", ""))
        except (ValueError, IndexError):
            continue

        # Process each iteration
        for iter_name in os.listdir(dir_path):
            iter_path = dir_path / iter_name
            if not iter_path.is_dir() or not iter_name.startswith("iteration_"):
                continue

            aoi_values = calculate_aoi_for_iteration(iter_path)

            if not aoi_values:
                continue

            # Filter individual outliers (> 8s)
            filtered_aoi = [v for v in aoi_values if v <= OUTLIER_THRESHOLD]

            # Calculate iteration stats for filtering
            iter_mean = np.mean(filtered_aoi) if filtered_aoi else float("inf")
            iter_count = len(filtered_aoi)

            # Check if iteration is valid
            is_valid = (
                iter_count >= MIN_SAMPLES_PER_ITERATION and iter_mean <= MAX_MEAN_AOI
            )

            if is_valid:
                for aoi in filtered_aoi:
                    all_data.append(
                        {
                            "lambda": lambda_val,
                            "loss": loss_val,
                            "aoi": aoi * 1000,  # Convert to ms
                        }
                    )

    return pd.DataFrame(all_data)


def create_box_plot(df):
    """Create box and whisker plot of AoI vs Packet Loss."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Colors for each lambda
    colors = {0.0: "#e74c3c", 0.5: "#f39c12", 1.0: "#3498db"}

    loss_values = sorted(df["loss"].unique())
    lambda_values = sorted(df["lambda"].unique())

    # Y-axis limit
    Y_LIMIT = 150

    # Width and positions for grouped boxplots
    width = 0.25
    positions_base = np.arange(len(loss_values))

    for i, lam in enumerate(lambda_values):
        positions = positions_base + (i - 1) * width
        data = [
            df[(df["lambda"] == lam) & (df["loss"] == loss)]["aoi"].values
            for loss in loss_values
        ]

        bp = ax.boxplot(
            data,
            positions=positions,
            widths=width * 0.8,
            patch_artist=True,
            showfliers=False,
        )

        for patch in bp["boxes"]:
            patch.set_facecolor(colors[lam])
            patch.set_alpha(0.7)
        for median in bp["medians"]:
            median.set_color("black")
            median.set_linewidth(1.5)

    # Add legend
    legend_patches = [
        plt.Rectangle(
            (0, 0), 1, 1, facecolor=colors[lam], alpha=0.7, label=f"λ = {lam}"
        )
        for lam in lambda_values
    ]
    ax.legend(handles=legend_patches, title="Lambda", fontsize=10, title_fontsize=11)

    ax.set_xlabel("Packet Loss (%)", fontsize=12)
    ax.set_ylabel("AoI (ms)", fontsize=12)
    ax.set_title(
        "Age of Information vs Packet Loss Rate", fontsize=14, fontweight="bold"
    )
    ax.set_xticks(positions_base)
    ax.set_xticklabels([f"{l}%" for l in loss_values])
    ax.set_ylim(0, Y_LIMIT)
    ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "arvindh.png", dpi=150, bbox_inches="tight")
    print(f"Saved: {OUTPUT_DIR / 'arvindh.png'}")
    plt.close()


def main():
    print("Collecting AoI data...")
    df = collect_all_data()

    print(f"Total samples: {len(df)}")
    print(f"Lambda values: {sorted(df['lambda'].unique())}")
    print(f"Loss values: {sorted(df['loss'].unique())}%")

    # Print summary stats
    print("\nMean AoI (ms) by Lambda and Loss:")
    summary = df.groupby(["loss", "lambda"])["aoi"].mean().unstack()
    print(summary.round(2))

    print("\nCreating box plot...")
    create_box_plot(df)

    print("\n✅ Done!")


if __name__ == "__main__":
    main()
