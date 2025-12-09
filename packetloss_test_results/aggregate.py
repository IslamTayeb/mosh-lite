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

def parse_discard_stats(filepath):
    """Parse discard stats file."""
    stats = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                if ':' in line:
                    key, value = line.strip().split(':', 1)
                    stats[key.strip()] = float(value.strip())
    except Exception as e:
        print(f"Warning: Could not parse {filepath}: {e}", file=sys.stderr)
    return stats

def remove_outliers(values):
    """Remove outliers using IQR method."""
    if len(values) < 4:
        return values
    sorted_vals = sorted(values)
    q1 = sorted_vals[len(sorted_vals) // 4]
    q3 = sorted_vals[3 * len(sorted_vals) // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return [v for v in values if lower <= v <= upper]

def aggregate_stats(stats_list):
    """Aggregate a list of stats dictionaries, removing outliers."""
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
            # Remove outliers
            filtered = remove_outliers(values)
            if filtered:
                aggregated[key] = {
                    'min': min(filtered),
                    'max': max(filtered),
                    'mean': sum(filtered) / len(filtered),
                    'median': sorted(filtered)[len(filtered) // 2],
                    'count': len(filtered),
                    'outliers_removed': len(values) - len(filtered)
                }
    return aggregated

def main():
    results_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')

    # Find all lambda/loss directories
    test_dirs = sorted([d for d in results_dir.iterdir()
                       if d.is_dir() and d.name.startswith('lambda_')])

    all_results = {}

    for test_dir in test_dirs:
        # Parse lambda_X_loss_Ypct
        parts = test_dir.name.split('_loss_')
        lambda_val = parts[0].replace('lambda_', '')
        loss_val = parts[1].replace('pct', '') if len(parts) > 1 else '0'

        key = f"lambda_{lambda_val}_loss_{loss_val}"
        iteration_latency_stats = []
        iteration_discard_stats = []

        # Find all iteration files
        for iter_dir in sorted(test_dir.glob('iteration_*')):
            # Parse latency
            latency_file = iter_dir / 'latency.csv'
            if latency_file.exists():
                stats = parse_latency_file(latency_file)
                if stats:
                    iteration_latency_stats.append(stats)

            # Parse discard stats
            discard_file = iter_dir / 'discard_stats.txt'
            if discard_file.exists():
                stats = parse_discard_stats(discard_file)
                if stats:
                    iteration_discard_stats.append(stats)

        all_results[key] = {
            'lambda': lambda_val,
            'loss': loss_val,
            'latency': aggregate_stats(iteration_latency_stats),
            'discards': aggregate_stats(iteration_discard_stats)
        }

    # Print summary
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"\n{'Lambda':<10} {'Loss %':<10} {'Avg Latency':<15} {'Discard %':<15}")
    print("-" * 50)

    for key, data in sorted(all_results.items(), key=lambda x: (float(x[1]['lambda']), float(x[1]['loss']))):
        avg_latency = data['latency'].get('average', {}).get('mean', 'N/A')
        discard_pct = data['discards'].get('Packets discarded (%)', {}).get('mean', 'N/A')

        if isinstance(avg_latency, float):
            avg_latency = f"{avg_latency:.6f}"
        if isinstance(discard_pct, float):
            discard_pct = f"{discard_pct:.2f}%"

        print(f"{data['lambda']:<10} {data['loss']:<10} {avg_latency:<15} {discard_pct:<15}")

    # Save JSON
    output_file = results_dir / 'aggregated_results.json'
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {output_file}")

if __name__ == '__main__':
    main()
