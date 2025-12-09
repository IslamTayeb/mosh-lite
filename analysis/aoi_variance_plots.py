#!/usr/bin/env python3
"""
Visualize AoI variance across packet loss test results using seaborn.
Creates boxplots similar to the lambda test results style.
Filters out bad iterations and outliers.
"""

import os
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path(__file__).parent.parent / "packetloss_test_results"
OUTPUT_DIR = Path(__file__).parent

# Thresholds for filtering
OUTLIER_THRESHOLD = 8.0  # seconds - individual AoI values above this are outliers
MIN_SAMPLES_PER_ITERATION = 100  # iterations with fewer samples are "bullshit"
MAX_MEAN_AOI = 0.5  # seconds - iterations with mean AoI above this are suspicious


def parse_log_file(filepath):
    """Parse a log file with format: timestamp, sequence_number"""
    data = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) >= 2:
                    timestamp = float(parts[0].strip())
                    seq_num = int(parts[1].strip())
                    data[seq_num] = timestamp
    except FileNotFoundError:
        return None
    return data


def calculate_aoi_for_iteration(iteration_path):
    """Calculate AoI values for a single iteration."""
    client_out = iteration_path / "client_out.log"
    output_log = iteration_path / "output.log"

    sent_times = parse_log_file(client_out)
    received_times = parse_log_file(output_log)

    if sent_times is None or received_times is None:
        return []

    aoi_values = []
    for seq_num, recv_time in received_times.items():
        if seq_num in sent_times:
            aoi = recv_time - sent_times[seq_num]
            if aoi > 0:
                aoi_values.append(aoi)

    return aoi_values


def collect_all_data():
    """Collect all AoI data with iteration-level filtering."""
    all_data = []
    iteration_stats = []

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
            iter_median = np.median(filtered_aoi) if filtered_aoi else float("inf")
            iter_count = len(filtered_aoi)

            # Check if iteration is "bullshit"
            is_valid = (
                iter_count >= MIN_SAMPLES_PER_ITERATION and iter_mean <= MAX_MEAN_AOI
            )

            iteration_stats.append(
                {
                    "lambda": lambda_val,
                    "loss": loss_val,
                    "iteration": iter_name,
                    "count": iter_count,
                    "mean": iter_mean,
                    "median": iter_median,
                    "is_valid": is_valid,
                }
            )

            if is_valid:
                for aoi in filtered_aoi:
                    all_data.append(
                        {
                            "lambda": lambda_val,
                            "loss": loss_val,
                            "aoi": aoi * 1000,  # Convert to ms
                            "iteration": iter_name,
                        }
                    )

    return pd.DataFrame(all_data), pd.DataFrame(iteration_stats)


def print_iteration_report(iter_stats):
    """Print report on which iterations were filtered."""
    print("=" * 80)
    print("ITERATION QUALITY REPORT")
    print("=" * 80)

    invalid = iter_stats[~iter_stats["is_valid"]]
    valid = iter_stats[iter_stats["is_valid"]]

    print(f"\nTotal iterations: {len(iter_stats)}")
    print(f"Valid iterations: {len(valid)}")
    print(f"Filtered out (bullshit): {len(invalid)}")

    if len(invalid) > 0:
        print("\n--- Filtered iterations ---")
        for _, row in invalid.iterrows():
            reason = []
            if row["count"] < MIN_SAMPLES_PER_ITERATION:
                reason.append(f"low samples ({row['count']})")
            if row["mean"] > MAX_MEAN_AOI:
                reason.append(f"high mean ({row['mean'] * 1000:.1f}ms)")
            print(
                f"  λ={row['lambda']}, loss={row['loss']}%, {row['iteration']}: {', '.join(reason)}"
            )

    print()
    return valid, invalid


def create_boxplots(df):
    """Create boxplot visualizations."""
    sns.set_style("whitegrid")
    sns.set_palette("husl")

    # Color palette
    colors = {0: "#2ecc71", 10: "#3498db", 25: "#e67e22", 50: "#e74c3c"}

    # Y-axis limit for better visualization
    Y_LIMIT = 250  # ms

    # Figure 1: AoI by Lambda, separated by Loss %
    fig1, axes1 = plt.subplots(2, 2, figsize=(14, 10))
    fig1.suptitle(
        "AoI Distribution by Lambda (λ) for Each Packet Loss Level\n(Outliers > 8s and bad iterations removed)",
        fontsize=14,
        fontweight="bold",
    )

    loss_values = sorted(df["loss"].unique())

    for idx, loss in enumerate(loss_values):
        ax = axes1[idx // 2, idx % 2]
        subset = df[df["loss"] == loss]

        bp = ax.boxplot(
            [
                subset[subset["lambda"] == lam]["aoi"].values
                for lam in sorted(df["lambda"].unique())
            ],
            positions=sorted(df["lambda"].unique()),
            widths=0.3,
            patch_artist=True,
            showfliers=False,
        )  # Hide fliers, we'll annotate count

        for patch in bp["boxes"]:
            patch.set_facecolor(colors[loss])
            patch.set_alpha(0.7)

        ax.set_xlabel("Lambda (λ)", fontsize=11)
        ax.set_ylabel("AoI (ms)", fontsize=11)
        ax.set_title(f"Packet Loss: {loss}%", fontsize=12, fontweight="bold")
        ax.set_xticks(sorted(df["lambda"].unique()))
        ax.set_xticklabels([f"{l:.1f}" for l in sorted(df["lambda"].unique())])
        ax.set_ylim(0, Y_LIMIT)

        # Add stats annotation
        for lam in sorted(df["lambda"].unique()):
            lam_data = subset[subset["lambda"] == lam]["aoi"]
            if len(lam_data) > 0:
                var = lam_data.var()
                n_outliers = (lam_data > Y_LIMIT).sum()
                ax.annotate(
                    f"σ²={var:.0f}\n({n_outliers} >250ms)",
                    xy=(lam, Y_LIMIT - 10),
                    fontsize=8,
                    ha="center",
                    va="top",
                )

    plt.tight_layout()
    fig1.savefig(
        OUTPUT_DIR / "fig_aoi_boxplot_by_loss.png", dpi=150, bbox_inches="tight"
    )
    print(f"Saved: {OUTPUT_DIR / 'fig_aoi_boxplot_by_loss.png'}")

    # Figure 2: Side-by-side comparison (similar to attached image style)
    fig2, axes2 = plt.subplots(1, 3, figsize=(16, 5))
    fig2.suptitle(
        "AoI Variance Comparison Across Lambda Values\n(Y-axis limited to 250ms for clarity)",
        fontsize=14,
        fontweight="bold",
    )

    lambda_colors = {0.0: "#1abc9c", 0.5: "#3498db", 1.0: "#9b59b6"}

    for idx, lam in enumerate(sorted(df["lambda"].unique())):
        ax = axes2[idx]
        subset = df[df["lambda"] == lam]

        positions = list(range(len(loss_values)))
        bp = ax.boxplot(
            [subset[subset["loss"] == loss]["aoi"].values for loss in loss_values],
            positions=positions,
            widths=0.5,
            patch_artist=True,
            showfliers=False,
        )  # Hide fliers for cleaner look

        for patch in bp["boxes"]:
            patch.set_facecolor(lambda_colors[lam])
            patch.set_alpha(0.7)

        ax.set_xlabel("Packet Loss (%)", fontsize=11)
        ax.set_ylabel("AoI (ms)", fontsize=11)
        ax.set_title(f"Lambda (λ) = {lam}", fontsize=12, fontweight="bold")
        ax.set_xticks(positions)
        ax.set_xticklabels([f"{l}%" for l in loss_values])
        ax.set_ylim(0, Y_LIMIT)

        # Annotate number of outliers above limit
        for i, loss in enumerate(loss_values):
            loss_data = subset[subset["loss"] == loss]["aoi"]
            if len(loss_data) > 0:
                n_above = (loss_data > Y_LIMIT).sum()
                if n_above > 0:
                    ax.annotate(
                        f"↑{n_above}",
                        xy=(i, Y_LIMIT - 5),
                        fontsize=9,
                        ha="center",
                        va="top",
                        color=lambda_colors[lam],
                        fontweight="bold",
                    )

    plt.tight_layout()
    fig2.savefig(
        OUTPUT_DIR / "fig_aoi_boxplot_by_lambda.png", dpi=150, bbox_inches="tight"
    )
    print(f"Saved: {OUTPUT_DIR / 'fig_aoi_boxplot_by_lambda.png'}")

    # Figure 2b: Direct λ=0 vs λ=1 comparison
    fig2b, axes2b = plt.subplots(1, 2, figsize=(14, 5))
    fig2b.suptitle(
        "Direct Comparison: λ=0 (No Discarding) vs λ=1.0 (Aggressive Discarding)",
        fontsize=14,
        fontweight="bold",
    )

    # Filter to only λ=0 and λ=1
    df_compare = df[df["lambda"].isin([0.0, 1.0])]

    # Left plot: Side by side boxplots
    ax = axes2b[0]
    positions_0 = [i - 0.2 for i in range(len(loss_values))]
    positions_1 = [i + 0.2 for i in range(len(loss_values))]

    bp0 = ax.boxplot(
        [
            df_compare[(df_compare["lambda"] == 0.0) & (df_compare["loss"] == loss)][
                "aoi"
            ].values
            for loss in loss_values
        ],
        positions=positions_0,
        widths=0.35,
        patch_artist=True,
        showfliers=False,
    )
    bp1 = ax.boxplot(
        [
            df_compare[(df_compare["lambda"] == 1.0) & (df_compare["loss"] == loss)][
                "aoi"
            ].values
            for loss in loss_values
        ],
        positions=positions_1,
        widths=0.35,
        patch_artist=True,
        showfliers=False,
    )

    for patch in bp0["boxes"]:
        patch.set_facecolor("#e74c3c")
        patch.set_alpha(0.7)
    for patch in bp1["boxes"]:
        patch.set_facecolor("#3498db")
        patch.set_alpha(0.7)

    ax.set_xlabel("Packet Loss (%)", fontsize=11)
    ax.set_ylabel("AoI (ms)", fontsize=11)
    ax.set_title("AoI Distribution Comparison", fontsize=12, fontweight="bold")
    ax.set_xticks(range(len(loss_values)))
    ax.set_xticklabels([f"{l}%" for l in loss_values])
    ax.set_ylim(0, Y_LIMIT)
    ax.legend(
        [bp0["boxes"][0], bp1["boxes"][0]],
        ["λ=0 (No Discard)", "λ=1.0 (Aggressive)"],
        loc="upper right",
    )

    # Right plot: Variance comparison
    ax = axes2b[1]
    var_0 = [
        df_compare[(df_compare["lambda"] == 0.0) & (df_compare["loss"] == loss)][
            "aoi"
        ].var()
        for loss in loss_values
    ]
    var_1 = [
        df_compare[(df_compare["lambda"] == 1.0) & (df_compare["loss"] == loss)][
            "aoi"
        ].var()
        for loss in loss_values
    ]

    x = np.arange(len(loss_values))
    width = 0.35
    bars0 = ax.bar(
        x - width / 2,
        var_0,
        width,
        label="λ=0 (No Discard)",
        color="#e74c3c",
        alpha=0.7,
    )
    bars1 = ax.bar(
        x + width / 2,
        var_1,
        width,
        label="λ=1.0 (Aggressive)",
        color="#3498db",
        alpha=0.7,
    )

    ax.set_xlabel("Packet Loss (%)", fontsize=11)
    ax.set_ylabel("Variance (ms²)", fontsize=11)
    ax.set_title("Variance Comparison: λ=0 vs λ=1.0", fontsize=12, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{l}%" for l in loss_values])
    ax.legend()
    ax.set_yscale("log")  # Log scale to see differences better

    # Add ratio annotations
    for i, (v0, v1) in enumerate(zip(var_0, var_1)):
        ratio = v0 / v1 if v1 > 0 else float("inf")
        winner = "λ=0" if v0 < v1 else "λ=1"
        color = "#e74c3c" if v0 < v1 else "#3498db"
        ax.annotate(
            f"{winner}\n{abs(1 - ratio) * 100:.0f}% better",
            xy=(i, max(v0, v1) * 1.2),
            ha="center",
            fontsize=9,
            color=color,
            fontweight="bold",
        )

    plt.tight_layout()
    fig2b.savefig(
        OUTPUT_DIR / "fig_aoi_lambda0_vs_lambda1.png", dpi=150, bbox_inches="tight"
    )
    print(f"Saved: {OUTPUT_DIR / 'fig_aoi_lambda0_vs_lambda1.png'}")

    # Figure 3: Combined heatmap of variance
    fig3, ax3 = plt.subplots(figsize=(10, 6))

    # Calculate variance for each combination
    variance_matrix = df.groupby(["loss", "lambda"])["aoi"].var().unstack()

    sns.heatmap(
        variance_matrix,
        annot=True,
        fmt=".1f",
        cmap="YlOrRd",
        ax=ax3,
        cbar_kws={"label": "Variance (ms²)"},
    )
    ax3.set_xlabel("Lambda (λ)", fontsize=12)
    ax3.set_ylabel("Packet Loss (%)", fontsize=12)
    ax3.set_title(
        "AoI Variance Heatmap\n(Lower is better - more consistent latency)",
        fontsize=14,
        fontweight="bold",
    )

    plt.tight_layout()
    fig3.savefig(
        OUTPUT_DIR / "fig_aoi_variance_heatmap.png", dpi=150, bbox_inches="tight"
    )
    print(f"Saved: {OUTPUT_DIR / 'fig_aoi_variance_heatmap.png'}")

    # Figure 4: IQR comparison (similar to attached style)
    fig4, axes4 = plt.subplots(1, 2, figsize=(14, 5))

    # Left: Median AoI by Lambda (grouped by loss)
    ax = axes4[0]
    width = 0.2
    x = np.arange(len(loss_values))

    for i, lam in enumerate(sorted(df["lambda"].unique())):
        medians = [
            df[(df["lambda"] == lam) & (df["loss"] == loss)]["aoi"].median()
            for loss in loss_values
        ]
        ax.bar(x + i * width, medians, width, label=f"λ={lam}", alpha=0.8)

    ax.set_xlabel("Packet Loss (%)", fontsize=11)
    ax.set_ylabel("Median AoI (ms)", fontsize=11)
    ax.set_title("Median AoI by Packet Loss", fontsize=12, fontweight="bold")
    ax.set_xticks(x + width)
    ax.set_xticklabels([f"{l}%" for l in loss_values])
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # Right: Standard Deviation by Lambda (grouped by loss)
    ax = axes4[1]
    for i, lam in enumerate(sorted(df["lambda"].unique())):
        stds = [
            df[(df["lambda"] == lam) & (df["loss"] == loss)]["aoi"].std()
            for loss in loss_values
        ]
        ax.bar(x + i * width, stds, width, label=f"λ={lam}", alpha=0.8)

    ax.set_xlabel("Packet Loss (%)", fontsize=11)
    ax.set_ylabel("Std Deviation (ms)", fontsize=11)
    ax.set_title(
        "AoI Standard Deviation by Packet Loss", fontsize=12, fontweight="bold"
    )
    ax.set_xticks(x + width)
    ax.set_xticklabels([f"{l}%" for l in loss_values])
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    fig4.savefig(
        OUTPUT_DIR / "fig_aoi_median_std_bars.png", dpi=150, bbox_inches="tight"
    )
    print(f"Saved: {OUTPUT_DIR / 'fig_aoi_median_std_bars.png'}")

    plt.close("all")


def compute_summary_stats(df):
    """Compute and print summary statistics."""
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS (After filtering bad iterations)")
    print("=" * 80)

    summary = (
        df.groupby(["loss", "lambda"])
        .agg(
            {
                "aoi": [
                    "count",
                    "mean",
                    "median",
                    "std",
                    "var",
                    lambda x: x.quantile(0.25),
                    lambda x: x.quantile(0.75),
                    lambda x: x.quantile(0.75) - x.quantile(0.25),
                ]
            }
        )
        .round(3)
    )

    summary.columns = [
        "Count",
        "Mean",
        "Median",
        "Std",
        "Variance",
        "P25",
        "P75",
        "IQR",
    ]
    print("\n", summary.to_string())

    # Save summary
    summary.to_csv(OUTPUT_DIR / "aoi_variance_filtered_summary.csv")

    # Key findings
    print("\n" + "=" * 80)
    print("KEY FINDINGS")
    print("=" * 80)

    # Best performer at each loss level
    print("\n📊 Best Lambda (lowest variance) at each packet loss level:")
    for loss in sorted(df["loss"].unique()):
        subset = df[df["loss"] == loss]
        variances = subset.groupby("lambda")["aoi"].var()
        best_lambda = variances.idxmin()
        best_var = variances.min()
        worst_var = variances.max()
        improvement = ((worst_var - best_var) / worst_var) * 100
        print(
            f"  • {loss}% loss: λ={best_lambda} (variance={best_var:.1f} ms², {improvement:.1f}% better than worst)"
        )

    # Variance increase with packet loss
    print("\n📈 Variance increase factor from 0% to 50% loss:")
    for lam in sorted(df["lambda"].unique()):
        var_0 = df[(df["lambda"] == lam) & (df["loss"] == 0)]["aoi"].var()
        var_50 = df[(df["lambda"] == lam) & (df["loss"] == 50)]["aoi"].var()
        factor = var_50 / var_0 if var_0 > 0 else float("inf")
        print(f"  • λ={lam}: {factor:.1f}x increase")

    # IQR comparison
    print("\n📐 IQR (Interquartile Range) - measure of spread:")
    for loss in sorted(df["loss"].unique()):
        print(f"\n  {loss}% packet loss:")
        for lam in sorted(df["lambda"].unique()):
            subset = df[(df["lambda"] == lam) & (df["loss"] == loss)]["aoi"]
            iqr = subset.quantile(0.75) - subset.quantile(0.25)
            print(f"    λ={lam}: IQR={iqr:.2f} ms")

    # λ=0 vs λ=1 direct comparison
    print("\n" + "=" * 80)
    print("λ=0 vs λ=1.0 DIRECT COMPARISON")
    print("(No Discarding vs Aggressive Discarding)")
    print("=" * 80)

    comparison_data = []
    for loss in sorted(df["loss"].unique()):
        data_0 = df[(df["lambda"] == 0.0) & (df["loss"] == loss)]["aoi"]
        data_1 = df[(df["lambda"] == 1.0) & (df["loss"] == loss)]["aoi"]

        if len(data_0) > 0 and len(data_1) > 0:
            var_0, var_1 = data_0.var(), data_1.var()
            std_0, std_1 = data_0.std(), data_1.std()
            mean_0, mean_1 = data_0.mean(), data_1.mean()
            med_0, med_1 = data_0.median(), data_1.median()
            p95_0, p95_1 = data_0.quantile(0.95), data_1.quantile(0.95)
            outliers_0 = (data_0 > 250).sum()
            outliers_1 = (data_1 > 250).sum()

            # Winner determination
            var_winner = "λ=0" if var_0 < var_1 else "λ=1.0"
            var_diff = abs(var_0 - var_1) / max(var_0, var_1) * 100

            comparison_data.append(
                {
                    "loss": loss,
                    "var_0": var_0,
                    "var_1": var_1,
                    "std_0": std_0,
                    "std_1": std_1,
                    "mean_0": mean_0,
                    "mean_1": mean_1,
                    "outliers_0": outliers_0,
                    "outliers_1": outliers_1,
                    "winner": var_winner,
                    "improvement": var_diff,
                }
            )

            print(f"\n  {loss}% Packet Loss:")
            print(f"    ┌─────────────────┬────────────┬────────────┐")
            print(f"    │ Metric          │ λ=0        │ λ=1.0      │")
            print(f"    ├─────────────────┼────────────┼────────────┤")
            print(f"    │ Variance (ms²)  │ {var_0:>10.1f} │ {var_1:>10.1f} │")
            print(f"    │ Std Dev (ms)    │ {std_0:>10.2f} │ {std_1:>10.2f} │")
            print(f"    │ Mean (ms)       │ {mean_0:>10.2f} │ {mean_1:>10.2f} │")
            print(f"    │ Median (ms)     │ {med_0:>10.2f} │ {med_1:>10.2f} │")
            print(f"    │ 95th %ile (ms)  │ {p95_0:>10.2f} │ {p95_1:>10.2f} │")
            print(f"    │ Outliers >250ms │ {outliers_0:>10} │ {outliers_1:>10} │")
            print(f"    └─────────────────┴────────────┴────────────┘")
            print(
                f"    → Winner (lower variance): {var_winner} ({var_diff:.1f}% better)"
            )

    # Overall correlation analysis
    print("\n" + "-" * 60)
    print("CORRELATION SUMMARY: λ=0 vs λ=1.0")
    print("-" * 60)

    wins_0 = sum(1 for c in comparison_data if c["winner"] == "λ=0")
    wins_1 = sum(1 for c in comparison_data if c["winner"] == "λ=1.0")

    print(f"\n  Wins by variance:")
    print(f"    λ=0 (No Discarding):    {wins_0}/4 loss levels")
    print(f"    λ=1.0 (Aggressive):     {wins_1}/4 loss levels")

    # When each strategy is better
    print(f"\n  When λ=0 is better:")
    for c in comparison_data:
        if c["winner"] == "λ=0":
            print(f"    • {c['loss']}% loss: {c['improvement']:.1f}% lower variance")

    print(f"\n  When λ=1.0 is better:")
    for c in comparison_data:
        if c["winner"] == "λ=1.0":
            print(f"    • {c['loss']}% loss: {c['improvement']:.1f}% lower variance")

    # Outlier analysis
    total_outliers_0 = sum(c["outliers_0"] for c in comparison_data)
    total_outliers_1 = sum(c["outliers_1"] for c in comparison_data)
    print(f"\n  Total outliers (>250ms) across all loss levels:")
    print(f"    λ=0:   {total_outliers_0} outliers")
    print(f"    λ=1.0: {total_outliers_1} outliers")
    print(
        f"    → {'λ=0' if total_outliers_0 < total_outliers_1 else 'λ=1.0'} produces fewer extreme delays"
    )


def main():
    print("Collecting AoI data from all iterations...")
    df, iter_stats = collect_all_data()

    valid, invalid = print_iteration_report(iter_stats)

    print(f"\nTotal valid AoI samples: {len(df)}")
    print(f"Lambda values: {sorted(df['lambda'].unique())}")
    print(f"Loss values: {sorted(df['loss'].unique())}%")

    print("\nCreating visualizations...")
    create_boxplots(df)

    compute_summary_stats(df)

    print("\n✅ All plots saved to analysis/ directory")


if __name__ == "__main__":
    main()
