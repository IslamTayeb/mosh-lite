#!/usr/bin/env python3
"""
Analyze AoI (Age of Information) variance across packet loss test results.
Separates by packet loss percentage and lambda value.
Excludes outliers above 8 seconds.
"""

import os
import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path(__file__).parent.parent / "packetloss_test_results"
OUTLIER_THRESHOLD = 8.0  # seconds


def parse_log_file(filepath):
    """Parse a log file with format: timestamp, sequence_number"""
    data = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                if len(parts) >= 2:
                    timestamp = float(parts[0].strip())
                    seq_num = int(parts[1].strip())
                    data[seq_num] = timestamp
    except FileNotFoundError:
        return None
    return data


def calculate_aoi_for_iteration(iteration_path):
    """
    Calculate AoI values for a single iteration.
    AoI = received_time - sent_time for each sequence number.
    """
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
            # Only include positive AoI values (sanity check)
            if aoi > 0:
                aoi_values.append(aoi)

    return aoi_values


def filter_outliers(values, threshold=OUTLIER_THRESHOLD):
    """Remove values above the threshold."""
    return [v for v in values if v <= threshold]


def analyze_variance():
    """
    Analyze AoI variance across all test results.
    Returns a dictionary with statistics for each (lambda, loss) combination.
    """
    results = defaultdict(lambda: {"all_aoi": [], "iterations": []})

    # Find all test directories
    for dir_name in os.listdir(RESULTS_DIR):
        dir_path = RESULTS_DIR / dir_name
        if not dir_path.is_dir() or not dir_name.startswith("lambda_"):
            continue

        # Parse lambda and loss from directory name
        # Format: lambda_X.X_loss_Xpct
        parts = dir_name.split("_")
        try:
            lambda_idx = parts.index("lambda") + 1
            loss_idx = parts.index("loss") + 1
            lambda_val = parts[lambda_idx]
            loss_val = parts[loss_idx].replace("pct", "")
        except (ValueError, IndexError):
            continue

        key = (lambda_val, loss_val)

        # Process each iteration
        for iter_name in os.listdir(dir_path):
            iter_path = dir_path / iter_name
            if not iter_path.is_dir() or not iter_name.startswith("iteration_"):
                continue

            aoi_values = calculate_aoi_for_iteration(iter_path)
            if aoi_values:
                # Filter outliers before adding
                filtered_aoi = filter_outliers(aoi_values)
                results[key]["all_aoi"].extend(filtered_aoi)
                results[key]["iterations"].append({
                    "iteration": iter_name,
                    "aoi_values": filtered_aoi,
                    "original_count": len(aoi_values),
                    "filtered_count": len(filtered_aoi)
                })

    return results


def compute_statistics(aoi_values):
    """Compute variance and other statistics for AoI values."""
    if not aoi_values:
        return None

    arr = np.array(aoi_values)
    return {
        "count": len(arr),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "variance": float(np.var(arr)),
        "std_dev": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
        "p95": float(np.percentile(arr, 95)),
        "iqr": float(np.percentile(arr, 75) - np.percentile(arr, 25)),
        "cv": float(np.std(arr) / np.mean(arr)) if np.mean(arr) > 0 else 0  # Coefficient of variation
    }


def main():
    print("=" * 80)
    print("AoI VARIANCE ANALYSIS")
    print(f"Outlier threshold: {OUTLIER_THRESHOLD}s")
    print("=" * 80)

    results = analyze_variance()

    # Organize by loss percentage, then by lambda
    loss_values = sorted(set(loss for _, loss in results.keys()), key=lambda x: int(x))
    lambda_values = sorted(set(lam for lam, _ in results.keys()), key=lambda x: float(x))

    # Create summary tables
    summary_data = []

    print("\n" + "=" * 80)
    print("DETAILED RESULTS (By Packet Loss %, then Lambda)")
    print("=" * 80)

    for loss in loss_values:
        print(f"\n{'─' * 80}")
        print(f"PACKET LOSS: {loss}%")
        print(f"{'─' * 80}")

        for lam in lambda_values:
            key = (lam, loss)
            if key not in results:
                continue

            data = results[key]
            stats = compute_statistics(data["all_aoi"])

            if stats is None:
                print(f"\n  Lambda {lam}: No data available")
                continue

            print(f"\n  Lambda {lam}:")
            print(f"    Samples:          {stats['count']}")
            print(f"    Mean AoI:         {stats['mean']*1000:.3f} ms")
            print(f"    Median AoI:       {stats['median']*1000:.3f} ms")
            print(f"    Variance:         {stats['variance']*1e6:.6f} ms²")
            print(f"    Std Deviation:    {stats['std_dev']*1000:.3f} ms")
            print(f"    Min:              {stats['min']*1000:.3f} ms")
            print(f"    Max:              {stats['max']*1000:.3f} ms")
            print(f"    25th Percentile:  {stats['p25']*1000:.3f} ms")
            print(f"    75th Percentile:  {stats['p75']*1000:.3f} ms")
            print(f"    95th Percentile:  {stats['p95']*1000:.3f} ms")
            print(f"    IQR:              {stats['iqr']*1000:.3f} ms")
            print(f"    CV (Coef. Var):   {stats['cv']:.4f}")
            print(f"    Iterations:       {len(data['iterations'])}")

            # Add to summary
            summary_data.append({
                "Lambda": lam,
                "Loss (%)": loss,
                "Samples": stats['count'],
                "Mean (ms)": round(stats['mean']*1000, 3),
                "Median (ms)": round(stats['median']*1000, 3),
                "Variance (ms²)": round(stats['variance']*1e6, 6),
                "Std Dev (ms)": round(stats['std_dev']*1000, 3),
                "CV": round(stats['cv'], 4),
                "Min (ms)": round(stats['min']*1000, 3),
                "Max (ms)": round(stats['max']*1000, 3),
                "IQR (ms)": round(stats['iqr']*1000, 3),
                "P95 (ms)": round(stats['p95']*1000, 3)
            })

    # Print summary table
    print("\n\n" + "=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)

    df = pd.DataFrame(summary_data)
    print(df.to_string(index=False))

    # Save to CSV
    output_csv = RESULTS_DIR.parent / "analysis" / "aoi_variance_summary.csv"
    df.to_csv(output_csv, index=False)
    print(f"\n\nSummary saved to: {output_csv}")

    # Additional analysis: Compare variance across lambdas for each loss level
    print("\n\n" + "=" * 80)
    print("VARIANCE COMPARISON (Grouped by Loss %)")
    print("=" * 80)

    pivot_variance = df.pivot(index='Loss (%)', columns='Lambda', values='Variance (ms²)')
    print("\nVariance (ms²) by Lambda and Loss:")
    print(pivot_variance.to_string())

    pivot_std = df.pivot(index='Loss (%)', columns='Lambda', values='Std Dev (ms)')
    print("\n\nStd Deviation (ms) by Lambda and Loss:")
    print(pivot_std.to_string())

    pivot_cv = df.pivot(index='Loss (%)', columns='Lambda', values='CV')
    print("\n\nCoefficient of Variation by Lambda and Loss:")
    print(pivot_cv.to_string())

    # Save pivoted tables
    pivot_variance.to_csv(RESULTS_DIR.parent / "analysis" / "aoi_variance_pivot.csv")
    pivot_std.to_csv(RESULTS_DIR.parent / "analysis" / "aoi_stddev_pivot.csv")

    return df


if __name__ == "__main__":
    main()

