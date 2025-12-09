import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

# Load the data
with open("../lambda_test_results/aggregated_results.json", "r") as f:
    data = json.load(f)

# Different thresholds for each metric
THRESHOLDS = {"Median": 2, "Average": 4}

# Prepare data for plotting (separate for each metric with different thresholds)
all_rows = {"Median": [], "Average": []}
all_outliers = {"Median": [], "Average": []}

for lambda_val, metrics in data.items():
    for metric_type in ["median", "average"]:
        metric_key = metric_type.capitalize()
        threshold = THRESHOLDS[metric_key]
        for value in metrics[metric_type]["all_values"]:
            if value >= threshold:
                all_outliers[metric_key].append(
                    {
                        "Lambda": float(lambda_val),
                        "Latency (ms)": value,
                    }
                )
            else:
                # Only add non-outlier values to boxplot
                all_rows[metric_key].append(
                    {
                        "Lambda": float(lambda_val),
                        "Latency (ms)": value,
                    }
                )

# Set up the aesthetic
sns.set_theme(style="whitegrid")
plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["font.size"] = 8  # Base font size for single column
plt.rcParams["axes.labelsize"] = 9
plt.rcParams["axes.titlesize"] = 10
plt.rcParams["xtick.labelsize"] = 8
plt.rcParams["ytick.labelsize"] = 8
plt.rcParams["legend.fontsize"] = 8

# Single column width: ~3.5 inches, height adjusted proportionally
fig, axes = plt.subplots(1, 2, figsize=(7, 2.5))

# Color palette - muted teal and coral
colors = {"Median": "#2a9d8f", "Average": "#e76f51"}
lambda_positions = {0.0: 0, 0.5: 1, 1.0: 2}
y_limits = {"Median": (0, 2), "Average": (0, 5)}

for idx, metric in enumerate(["Median", "Average"]):
    ax = axes[idx]
    metric_df = pd.DataFrame(all_rows[metric])
    metric_outliers = pd.DataFrame(all_outliers[metric])
    y_max = y_limits[metric][1]

    # Box plot for this metric
    sns.boxplot(
        data=metric_df,
        x="Lambda",
        y="Latency (ms)",
        color=colors[metric],
        ax=ax,
        linewidth=1.0,
        showfliers=False,
        width=0.5,
    )

    # Set y-axis limit
    ax.set_ylim(y_limits[metric])

    # Add X markers with actual values for outliers
    y_top = y_max * 0.92
    for lambda_val in [0.0, 0.5, 1.0]:
        if len(metric_outliers) > 0:
            lambda_outs = metric_outliers[metric_outliers["Lambda"] == lambda_val]
            if len(lambda_outs) > 0:
                x_pos = lambda_positions[lambda_val]
                # Get all outlier values for this lambda
                values = lambda_outs["Latency (ms)"].values
                values_str = ", ".join([f"{v:.1f}" for v in sorted(values)])

                # Draw X marker
                ax.scatter(
                    x_pos,
                    y_top,
                    marker="x",
                    s=100,
                    c=colors[metric],
                    linewidth=2,
                    zorder=10,
                )
                # Add values label below the X
                ax.annotate(
                    values_str,
                    xy=(x_pos, y_top - y_max * 0.06),
                    ha="center",
                    va="top",
                    fontsize=7,
                    fontweight="bold",
                    color=colors[metric],
                )

    ax.set_title(f"{metric} Latency by Lambda", fontsize=10, fontweight="bold", pad=8)
    ax.set_xlabel("Lambda (λ)", fontsize=9)
    ax.set_ylabel("Latency (ms)", fontsize=9)

    # Add annotation explaining X markers
    ax.annotate(
        "✕ = Outliers (ms values shown)",
        xy=(0.98, 0.02),
        xycoords="axes fraction",
        ha="right",
        va="bottom",
        fontsize=7,
        style="italic",
        bbox=dict(
            boxstyle="round,pad=0.2", facecolor="white", edgecolor="gray", alpha=0.8
        ),
    )

plt.tight_layout(pad=0.5)
plt.savefig(
    "lambda_latency_results.png", dpi=300, bbox_inches="tight", facecolor="white"
)
plt.savefig("lambda_latency_results.pdf", bbox_inches="tight", facecolor="white")

print("Saved: lambda_latency_results.png and lambda_latency_results.pdf")
