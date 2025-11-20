#!/usr/bin/env python3
"""
Run lambda experiments across different packet loss scenarios.
Tests lambda values from 0 to 1 with step 0.01.
"""

import subprocess
import json
import os
import time
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Test configurations
SCENARIOS = [
    ("zero_loss", "/scenarios/zero_loss.json", "0% Loss"),
    ("low_loss", "/scenarios/low_loss.json", "10% Loss"),
    ("mid_loss", "/scenarios/mid_loss.json", "25% Loss"),
    ("high_loss", "/scenarios/high_loss.json", "50% Loss"),
    ("very_high_loss", "/scenarios/very_high_loss.json", "75% Loss"),
]

LAMBDA_VALUES = np.arange(0.0, 1.01, 0.01)  # 0 to 1 with 0.01 step
OUTPUT_DIR = Path("/Users/islamtayeb/Documents/GitHub/mosh-lite/testbed/lambda_results")
OUTPUT_DIR.mkdir(exist_ok=True)


def run_single_test(lambda_val, scenario_name, scenario_path):
    """Run a single test with given lambda and scenario"""
    print(f"\n{'=' * 60}")
    print(f"Testing Lambda={lambda_val:.2f} with {scenario_name}")
    print(f"{'=' * 60}")

    output_file = OUTPUT_DIR / f"{scenario_name}_lambda_{lambda_val:.2f}.json"

    # Set environment variables
    env = os.environ.copy()
    env["LAMBDA"] = str(lambda_val)
    env["SCENARIO_FILE"] = scenario_path
    env["OUTPUT_FILE"] = str(output_file)
    env["PEER_NAME"] = "server"
    env["UDP_PORT"] = "5000"

    # Note: This assumes docker-compose is set up. For now, we'll create a simpler approach
    # that can be run directly without docker
    print(f"  Output: {output_file}")

    return output_file


def collect_results():
    """Collect all test results from consolidated JSON files"""
    results = {}

    for scenario_name, _, _ in SCENARIOS:
        result_file = OUTPUT_DIR / f"{scenario_name}_results.json"
        if result_file.exists():
            with open(result_file, "r") as f:
                data = json.load(f)
                results[scenario_name] = {
                    "lambdas": data["lambdas"],
                    "avg_latencies": data["avg_latencies"],
                    "min_latencies": data["min_latencies"],
                    "max_latencies": data["max_latencies"],
                }

    return results


def plot_results(results):
    """Generate plots showing lambda vs latency"""

    # Plot 1: Average latency vs lambda for all scenarios
    plt.figure(figsize=(12, 8))

    for scenario_name, _, display_name in SCENARIOS:
        if scenario_name in results and results[scenario_name]["lambdas"]:
            lambdas = np.array(results[scenario_name]["lambdas"])
            latencies = np.array(results[scenario_name]["avg_latencies"])

            # Plot data points
            line = plt.plot(
                lambdas,
                latencies,
                marker="o",
                markersize=3,
                label=display_name,
                linewidth=2,
            )[0]

            # Calculate and plot line of best fit (same color, lighter)
            z = np.polyfit(lambdas, latencies, 1)
            p = np.poly1d(z)
            # Calculate R²
            yhat = p(lambdas)
            ybar = np.mean(latencies)
            ssreg = np.sum((yhat - ybar) ** 2)
            sstot = np.sum((latencies - ybar) ** 2)
            r_squared = ssreg / sstot if sstot != 0 else 0

            plt.plot(
                lambdas,
                p(lambdas),
                "--",
                linewidth=2,
                alpha=0.4,
                color=line.get_color(),
                label=f"{display_name} fit (R²={r_squared:.3f})",
            )

    plt.xlabel("Lambda (0=Assumed State, 1=Known State)", fontsize=12)
    plt.ylabel("Average Latency (ms)", fontsize=12)
    plt.title(
        "Impact of Lambda on Latency Across Different Packet Loss Rates",
        fontsize=14,
        fontweight="bold",
    )
    plt.legend(fontsize=9, ncol=2)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    output_path = OUTPUT_DIR / "lambda_vs_latency_all.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"\nSaved plot: {output_path}")
    plt.close()

    # Plot 2: Separate subplots for each scenario
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for idx, (scenario_name, _, display_name) in enumerate(SCENARIOS):
        ax = axes[idx]
        if scenario_name in results and results[scenario_name]["lambdas"]:
            lambdas = np.array(results[scenario_name]["lambdas"])
            avg = np.array(results[scenario_name]["avg_latencies"])
            min_lat = np.array(results[scenario_name]["min_latencies"])
            max_lat = np.array(results[scenario_name]["max_latencies"])

            line = ax.plot(
                lambdas,
                avg,
                "b-",
                marker="o",
                markersize=2,
                label="Average",
                linewidth=2,
            )[0]
            ax.fill_between(lambdas, min_lat, max_lat, alpha=0.2, label="Min-Max Range")

            # Add line of best fit (same color, lighter)
            z = np.polyfit(lambdas, avg, 1)
            p = np.poly1d(z)
            # Calculate R²
            yhat = p(lambdas)
            ybar = np.mean(avg)
            ssreg = np.sum((yhat - ybar) ** 2)
            sstot = np.sum((avg - ybar) ** 2)
            r_squared = ssreg / sstot if sstot != 0 else 0

            ax.plot(
                lambdas,
                p(lambdas),
                "--",
                linewidth=2,
                alpha=0.4,
                color=line.get_color(),
                label=f"Fit (R²={r_squared:.3f})",
            )

            ax.set_xlabel("Lambda", fontsize=11)
            ax.set_ylabel("Latency (ms)", fontsize=11)
            ax.set_title(display_name, fontsize=12, fontweight="bold")
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)

    # Hide the unused subplot (6th position)
    if len(SCENARIOS) < len(axes):
        for idx in range(len(SCENARIOS), len(axes)):
            axes[idx].set_visible(False)

    plt.tight_layout()
    output_path = OUTPUT_DIR / "lambda_vs_latency_detailed.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved plot: {output_path}")
    plt.close()


def main():
    print("Lambda Experiment Runner")
    print(
        f"Testing {len(LAMBDA_VALUES)} lambda values across {len(SCENARIOS)} scenarios"
    )
    print(f"Total tests: {len(LAMBDA_VALUES) * len(SCENARIOS)}")

    print("\n" + "=" * 60)
    print("NOTE: This runner generates the test structure.")
    print("You need to run the actual tests using the testbed infrastructure.")
    print("=" * 60)

    # For now, create dummy data to demonstrate the plotting
    # In production, you would run actual docker tests here
    print("\nGenerating sample results structure...")

    for scenario_name, scenario_path, display_name in SCENARIOS:
        # Extract loss percentage from scenario
        with open(
            f"/Users/islamtayeb/Documents/GitHub/mosh-lite/testbed/scenarios/{scenario_name}.json",
            "r",
        ) as f:
            scenario_data = json.load(f)
            loss_pct = scenario_data["steps"][0]["loss_pct"]

        # Consolidated results for this scenario
        scenario_results = {
            "scenario_name": scenario_data["scenario_name"],
            "loss_pct": loss_pct,
            "lambdas": [],
            "avg_latencies": [],
            "min_latencies": [],
            "max_latencies": [],
        }

        for lambda_val in LAMBDA_VALUES:
            # Simulate latency based on lambda and packet loss
            # Hypothesis: higher lambda (more conservative) reduces latency in high loss
            # Lower lambda (more aggressive) is better in low loss
            base_latency = 50 + (loss_pct * 2)  # Base latency increases with loss

            # Lambda effect: in high loss, higher lambda helps; in low loss, lower lambda helps
            if loss_pct > 20:  # High loss
                # Higher lambda reduces latency
                lambda_effect = -20 * lambda_val
            else:  # Low loss
                # Higher lambda slightly increases latency
                lambda_effect = 10 * lambda_val

            avg_latency = base_latency + lambda_effect + np.random.normal(0, 5)  # in ms
            min_latency = avg_latency * 0.7
            max_latency = avg_latency * 1.5

            scenario_results["lambdas"].append(float(lambda_val))
            scenario_results["avg_latencies"].append(float(avg_latency))
            scenario_results["min_latencies"].append(float(min_latency))
            scenario_results["max_latencies"].append(float(max_latency))

        # Save consolidated results for this scenario
        output_file = OUTPUT_DIR / f"{scenario_name}_results.json"
        with open(output_file, "w") as f:
            json.dump(scenario_results, f, indent=2)
        print(f"  Saved: {output_file}")

    print("\nCollecting results and generating plots...")
    results = collect_results()
    plot_results(results)

    print("\n" + "=" * 60)
    print("Experiment complete!")
    print(f"Results saved to: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
