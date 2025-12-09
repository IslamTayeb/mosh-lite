#!/usr/bin/env python3
"""
Paper-ready analysis of packet loss test results.
Generates figures and tables suitable for academic publication.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import csv
from glob import glob


def remove_outliers_iqr(values, k=1.5):
    """Remove outliers using IQR method."""
    if len(values) < 4:
        return values
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    return [v for v in values if lower <= v <= upper]


# Publication-quality settings
plt.rcParams.update(
    {
        "font.size": 11,
        "font.family": "serif",
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.figsize": (8, 5),
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    }
)


def load_results(results_file):
    with open(results_file, "r") as f:
        return json.load(f)


def load_raw_iterations(results_dir):
    """Load raw per-iteration data and compute stats with outlier removal."""
    results_dir = Path(results_dir)
    data = []

    for test_dir in sorted(results_dir.glob("lambda_*_loss_*pct")):
        # Parse directory name
        parts = test_dir.name.split("_loss_")
        lambda_val = float(parts[0].replace("lambda_", ""))
        loss_val = float(parts[1].replace("pct", ""))

        latencies_avg = []
        latencies_med = []
        discard_pcts = []
        packets_recv = []
        packets_disc = []

        for iter_dir in test_dir.glob("iteration_*"):
            # Parse latency.csv
            lat_file = iter_dir / "latency.csv"
            if lat_file.exists():
                try:
                    with open(lat_file) as f:
                        for line in f:
                            parts = line.strip().split(",")
                            if len(parts) == 2:
                                if parts[0] == "average":
                                    latencies_avg.append(float(parts[1]))
                                elif parts[0] == "median":
                                    latencies_med.append(float(parts[1]))
                except:
                    pass

            # Parse discard_stats.txt
            disc_file = iter_dir / "discard_stats.txt"
            if disc_file.exists():
                try:
                    with open(disc_file) as f:
                        for line in f:
                            if "Packets discarded (%):" in line:
                                val = float(line.split(":")[1].strip())
                                discard_pcts.append(val)
                            elif "Total packets received:" in line:
                                val = float(line.split(":")[1].strip())
                                packets_recv.append(val)
                            elif line.startswith("Packets discarded:"):
                                val = float(line.split(":")[1].strip())
                                packets_disc.append(val)
                except:
                    pass

        # Remove outliers from each metric
        latencies_avg = remove_outliers_iqr(latencies_avg)
        latencies_med = remove_outliers_iqr(latencies_med)
        discard_pcts = remove_outliers_iqr(discard_pcts)
        packets_recv = remove_outliers_iqr(packets_recv)
        packets_disc = remove_outliers_iqr(packets_disc)

        data.append(
            {
                "lambda": lambda_val,
                "loss": loss_val,
                "latency_avg": np.mean(latencies_avg) if latencies_avg else None,
                "latency_median": np.mean(latencies_med) if latencies_med else None,
                "discard_pct": np.mean(discard_pcts) if discard_pcts else None,
                "packets_received": np.mean(packets_recv) if packets_recv else None,
                "packets_discarded": np.mean(packets_disc) if packets_disc else None,
                "n_samples": len(discard_pcts),
            }
        )

    return sorted(data, key=lambda x: (x["lambda"], x["loss"]))


def extract_data(results):
    """Extract structured data from results (legacy, uses pre-aggregated)."""
    data = []
    for key, val in results.items():
        lam = float(val["lambda"])
        loss = float(val["loss"])

        lat_avg = val["latency"].get("average", {}).get("mean", None)
        lat_med = val["latency"].get("median", {}).get("mean", None)

        discard_pct = val["discards"].get("Packets discarded (%)", {}).get("mean", None)
        pkts_recv = val["discards"].get("Total packets received", {}).get("mean", None)
        pkts_disc = val["discards"].get("Packets discarded", {}).get("mean", None)

        data.append(
            {
                "lambda": lam,
                "loss": loss,
                "latency_avg": lat_avg,
                "latency_median": lat_med,
                "discard_pct": discard_pct,
                "packets_received": pkts_recv,
                "packets_discarded": pkts_disc,
            }
        )

    return sorted(data, key=lambda x: (x["lambda"], x["loss"]))


def plot_discard_rate(data, output_dir):
    """Plot discard rate vs packet loss for different lambda values."""
    fig, ax = plt.subplots(figsize=(8, 5))

    lambdas = sorted(set(d["lambda"] for d in data))
    losses = sorted(set(d["loss"] for d in data))

    colors = ["#2E86AB", "#A23B72", "#F18F01"]
    markers = ["o", "s", "^"]

    for i, lam in enumerate(lambdas):
        subset = [d for d in data if d["lambda"] == lam]
        subset = sorted(subset, key=lambda x: x["loss"])

        x = [d["loss"] for d in subset]
        y = [d["discard_pct"] for d in subset]

        ax.plot(
            x,
            y,
            f"{markers[i]}-",
            color=colors[i],
            linewidth=2,
            markersize=8,
            label=f"λ = {lam}",
        )

    ax.set_xlabel("Network Packet Loss (%)")
    ax.set_ylabel("Application-Layer Discard Rate (%)")
    ax.set_title("Packet Discard Rate vs Network Loss")
    ax.legend(title="Lambda (λ)")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(losses)
    ax.set_ylim(bottom=0)

    plt.tight_layout()
    plt.savefig(output_dir / "fig_discard_vs_loss.pdf")
    plt.savefig(output_dir / "fig_discard_vs_loss.png")
    plt.close()
    print(f"Saved: fig_discard_vs_loss.pdf/png")


def plot_latency(data, output_dir):
    """Plot latency vs packet loss for different lambda values."""
    fig, ax = plt.subplots(figsize=(8, 5))

    lambdas = sorted(set(d["lambda"] for d in data))
    losses = sorted(set(d["loss"] for d in data))

    colors = ["#2E86AB", "#A23B72", "#F18F01"]
    markers = ["o", "s", "^"]

    for i, lam in enumerate(lambdas):
        subset = [d for d in data if d["lambda"] == lam]
        subset = sorted(subset, key=lambda x: x["loss"])

        x = [d["loss"] for d in subset]
        y = [d["latency_median"] * 1000 for d in subset]  # Convert to ms

        ax.plot(
            x,
            y,
            f"{markers[i]}-",
            color=colors[i],
            linewidth=2,
            markersize=8,
            label=f"λ = {lam}",
        )

    ax.set_xlabel("Network Packet Loss (%)")
    ax.set_ylabel("Median Latency (ms)")
    ax.set_title("State Synchronization Latency vs Network Loss")
    ax.legend(title="Lambda (λ)")
    ax.grid(True, alpha=0.3)
    ax.set_xticks(losses)

    plt.tight_layout()
    plt.savefig(output_dir / "fig_latency_vs_loss.pdf")
    plt.savefig(output_dir / "fig_latency_vs_loss.png")
    plt.close()
    print(f"Saved: fig_latency_vs_loss.pdf/png")


def plot_combined(data, output_dir):
    """Combined 2-panel figure for paper."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))

    lambdas = sorted(set(d["lambda"] for d in data))
    losses = sorted(set(d["loss"] for d in data))

    colors = ["#2E86AB", "#A23B72", "#F18F01"]
    markers = ["o", "s", "^"]

    # Panel A: Discard Rate
    for i, lam in enumerate(lambdas):
        subset = sorted(
            [d for d in data if d["lambda"] == lam], key=lambda x: x["loss"]
        )
        x = [d["loss"] for d in subset]
        y = [d["discard_pct"] for d in subset]
        ax1.plot(
            x,
            y,
            f"{markers[i]}-",
            color=colors[i],
            linewidth=2,
            markersize=8,
            label=f"λ = {lam}",
        )

    ax1.set_xlabel("Network Packet Loss (%)")
    ax1.set_ylabel("Application-Layer Discard Rate (%)")
    ax1.set_title("(a) Packet Discard Rate")
    ax1.legend(title="Lambda")
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(losses)
    ax1.set_ylim(bottom=0)

    # Panel B: Latency
    for i, lam in enumerate(lambdas):
        subset = sorted(
            [d for d in data if d["lambda"] == lam], key=lambda x: x["loss"]
        )
        x = [d["loss"] for d in subset]
        y = [d["latency_median"] * 1000 for d in subset]
        ax2.plot(
            x,
            y,
            f"{markers[i]}-",
            color=colors[i],
            linewidth=2,
            markersize=8,
            label=f"λ = {lam}",
        )

    ax2.set_xlabel("Network Packet Loss (%)")
    ax2.set_ylabel("Median Latency (ms)")
    ax2.set_title("(b) State Synchronization Latency")
    ax2.legend(title="Lambda")
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(losses)

    plt.tight_layout()
    plt.savefig(output_dir / "fig_combined.pdf")
    plt.savefig(output_dir / "fig_combined.png")
    plt.close()
    print(f"Saved: fig_combined.pdf/png")


def plot_heatmap(data, output_dir):
    """Heatmap of discard rate by lambda and loss."""
    lambdas = sorted(set(d["lambda"] for d in data))
    losses = sorted(set(d["loss"] for d in data))

    matrix = np.zeros((len(lambdas), len(losses)))
    for d in data:
        i = lambdas.index(d["lambda"])
        j = losses.index(d["loss"])
        matrix[i, j] = d["discard_pct"] if d["discard_pct"] else 0

    fig, ax = plt.subplots(figsize=(7, 4))
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(range(len(losses)))
    ax.set_yticks(range(len(lambdas)))
    ax.set_xticklabels([f"{int(l)}%" for l in losses])
    ax.set_yticklabels([f"λ={l}" for l in lambdas])
    ax.set_xlabel("Network Packet Loss")
    ax.set_ylabel("Lambda Parameter")
    ax.set_title("Application-Layer Discard Rate (%)")

    # Add values to cells
    for i in range(len(lambdas)):
        for j in range(len(losses)):
            text = f"{matrix[i, j]:.1f}%"
            color = "white" if matrix[i, j] > 30 else "black"
            ax.text(j, i, text, ha="center", va="center", color=color, fontsize=10)

    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Discard Rate (%)")

    plt.tight_layout()
    plt.savefig(output_dir / "fig_heatmap.pdf")
    plt.savefig(output_dir / "fig_heatmap.png")
    plt.close()
    print(f"Saved: fig_heatmap.pdf/png")


def generate_latex_table(data, output_dir):
    """Generate LaTeX table for paper."""
    lambdas = sorted(set(d["lambda"] for d in data))
    losses = sorted(set(d["loss"] for d in data))

    latex = r"""\begin{table}[htbp]
\centering
\caption{Performance metrics across lambda values and packet loss rates}
\label{tab:results}
\begin{tabular}{cc|cc}
\hline
\textbf{$\lambda$} & \textbf{Loss (\%)} & \textbf{Discard Rate (\%)} & \textbf{Median Latency (ms)} \\
\hline
"""
    for lam in lambdas:
        for i, loss in enumerate(losses):
            d = next(
                (x for x in data if x["lambda"] == lam and x["loss"] == loss), None
            )
            if d:
                discard = f"{d['discard_pct']:.2f}" if d["discard_pct"] else "N/A"
                latency = (
                    f"{d['latency_median'] * 1000:.2f}"
                    if d["latency_median"]
                    else "N/A"
                )
                latex += f"{lam} & {int(loss)} & {discard} & {latency} \\\\\n"
        latex += r"\hline" + "\n"

    latex += r"""\end{tabular}
\end{table}
"""

    with open(output_dir / "table_results.tex", "w") as f:
        f.write(latex)
    print(f"Saved: table_results.tex")


def generate_csv(data, output_dir):
    """Export data to CSV for external analysis."""
    with open(output_dir / "results_summary.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "lambda",
                "loss_pct",
                "discard_rate_pct",
                "latency_avg_ms",
                "latency_median_ms",
                "packets_received",
                "packets_discarded",
            ]
        )
        for d in data:
            writer.writerow(
                [
                    d["lambda"],
                    d["loss"],
                    f"{d['discard_pct']:.4f}" if d["discard_pct"] else "",
                    f"{d['latency_avg'] * 1000:.4f}" if d["latency_avg"] else "",
                    f"{d['latency_median'] * 1000:.4f}" if d["latency_median"] else "",
                    f"{d['packets_received']:.0f}" if d["packets_received"] else "",
                    f"{d['packets_discarded']:.0f}" if d["packets_discarded"] else "",
                ]
            )
    print(f"Saved: results_summary.csv")


def print_insights(data):
    """Print key insights for the paper."""
    print("\n" + "=" * 70)
    print("KEY INSIGHTS FOR PAPER")
    print("=" * 70)

    # Group by lambda
    by_lambda = {}
    for d in data:
        lam = d["lambda"]
        if lam not in by_lambda:
            by_lambda[lam] = []
        by_lambda[lam].append(d)

    # Insight 1: Effect of loss at each lambda
    print("\n1. DISCARD RATE BY LAMBDA AND LOSS:")
    print(
        f"   {'Lambda':<8} {'0% loss':<12} {'10% loss':<12} {'25% loss':<12} {'50% loss':<12}"
    )
    print("   " + "-" * 56)
    for lam in sorted(by_lambda.keys()):
        vals = sorted(by_lambda[lam], key=lambda x: x["loss"])
        row = f"   λ={lam:<5}"
        for v in vals:
            disc = v["discard_pct"]
            row += f" {disc:.1f}%{'':<7}"
        print(row)

    # Insight 2: Best lambda at high loss
    print("\n2. BEST LAMBDA AT HIGH PACKET LOSS (50%):")
    at_50 = [d for d in data if d["loss"] == 50]
    best = min(
        at_50, key=lambda x: x["discard_pct"] if x["discard_pct"] else float("inf")
    )
    print(f"   Best: λ={best['lambda']} with {best['discard_pct']:.2f}% discard rate")

    # Insight 3: Latency comparison
    print("\n3. LATENCY COMPARISON (median, at 0% loss):")
    at_0 = [d for d in data if d["loss"] == 0]
    for d in sorted(at_0, key=lambda x: x["lambda"]):
        lat = d["latency_median"] * 1000 if d["latency_median"] else 0
        print(f"   λ={d['lambda']}: {lat:.2f} ms")

    print("\n" + "=" * 70)


def main():
    results_dir = Path(__file__).parent.parent / "packetloss_test_results"
    output_dir = Path(__file__).parent

    if not results_dir.exists():
        print(f"Error: {results_dir} not found")
        return

    print(f"Loading raw iterations from: {results_dir}")
    print("Applying IQR outlier removal to each metric...")
    data = load_raw_iterations(results_dir)

    print(f"\nData points per condition:")
    for d in data:
        print(
            f"  λ={d['lambda']}, loss={d['loss']}%: {d.get('n_samples', 'N/A')} samples after outlier removal"
        )

    print(f"\nGenerating figures and tables...")
    plot_discard_rate(data, output_dir)
    plot_latency(data, output_dir)
    plot_combined(data, output_dir)
    plot_heatmap(data, output_dir)
    generate_latex_table(data, output_dir)
    generate_csv(data, output_dir)

    print_insights(data)

    print(f"\nAll outputs saved to: {output_dir}/")


if __name__ == "__main__":
    main()
