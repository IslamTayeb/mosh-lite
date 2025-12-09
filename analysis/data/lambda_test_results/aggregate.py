#!/usr/bin/env python3
import os
import sys
import csv
import json
from pathlib import Path

def parse_latency_file(filepath):
    """Parse a latency CSV file and return stats dict."""
    stats = {}
    try:
        with open(filepath, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    stats[row[0]] = float(row[1])
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}", file=sys.stderr)
    return stats

def aggregate_stats(stats_list):
    """Aggregate a list of stats dictionaries."""
    if not stats_list:
        return {}

    # Get all keys
    all_keys = set()
    for stats in stats_list:
        all_keys.update(stats.keys())

    aggregated = {}
    for key in all_keys:
        values = [s[key] for s in stats_list if key in s]
        if values:
            aggregated[key] = {
                'min': min(values),
                'max': max(values),
                'mean': sum(values) / len(values),
                'median': sorted(values)[len(values) // 2],
                'count': len(values),
                'all_values': values
            }
    return aggregated

def main():
    results_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')

    # Find all lambda directories
    lambda_dirs = sorted([d for d in results_dir.iterdir() if d.is_dir() and d.name.startswith('lambda_')])

    all_results = {}

    for lambda_dir in lambda_dirs:
        lambda_val = lambda_dir.name.replace('lambda_', '')
        iteration_stats = []

        # Find all iteration latency files
        for latency_file in sorted(lambda_dir.glob('iteration_*/latency.csv')):
            stats = parse_latency_file(latency_file)
            if stats:
                iteration_stats.append(stats)

        if iteration_stats:
            all_results[lambda_val] = aggregate_stats(iteration_stats)

    # Print summary
    print("\n" + "=" * 70)
    print("AGGREGATED RESULTS SUMMARY")
    print("=" * 70)

    for lambda_val, stats in sorted(all_results.items(), key=lambda x: float(x[0])):
        print(f"\n{'─' * 70}")
        print(f"LAMBDA = {lambda_val}")
        print(f"{'─' * 70}")

        for metric, values in stats.items():
            print(f"\n  {metric.upper()}:")
            print(f"    Mean:   {values['mean']:.6f}")
            print(f"    Median: {values['median']:.6f}")
            print(f"    Min:    {values['min']:.6f}")
            print(f"    Max:    {values['max']:.6f}")
            print(f"    Count:  {values['count']}")

    # Save JSON results
    output_file = results_dir / 'aggregated_results.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n\nDetailed results saved to: {output_file}")

    # Create comparison table
    print("\n" + "=" * 70)
    print("COMPARISON TABLE (Average Latency)")
    print("=" * 70)
    print(f"\n{'Lambda':<10} {'Avg Mean':<15} {'Avg Median':<15}")
    print("-" * 40)

    for lambda_val, stats in sorted(all_results.items(), key=lambda x: float(x[0])):
        avg_mean = stats.get('average', {}).get('mean', 'N/A')
        avg_median = stats.get('median', {}).get('mean', 'N/A')

        if isinstance(avg_mean, float):
            avg_mean = f"{avg_mean:.6f}"
        if isinstance(avg_median, float):
            avg_median = f"{avg_median:.6f}"

        print(f"{lambda_val:<10} {avg_mean:<15} {avg_median:<15}")

if __name__ == '__main__':
    main()
