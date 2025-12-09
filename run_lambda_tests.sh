#!/bin/bash
#
# Lambda Parameter Test Suite
# Runs tests across LAMBDA values (0, 0.5, 1.0), 10 iterations each
# Aggregates latency statistics for comparison
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBED_DIR="$SCRIPT_DIR/testbed"
ANALYSIS_DIR="$SCRIPT_DIR/analysis"
RESULTS_DIR="$SCRIPT_DIR/lambda_test_results"
ITERATIONS=${ITERATIONS:-10}
LAMBDA_VALUES="${LAMBDA_VALUES:-0 0.5 1.0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}  Lambda Parameter Test Suite${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
echo "Configuration:"
echo "  Iterations per lambda: $ITERATIONS"
echo "  Lambda values: $LAMBDA_VALUES"
echo "  Results directory: $RESULTS_DIR"
echo ""

# Clean up old results
rm -rf "$RESULTS_DIR"
mkdir -p "$RESULTS_DIR"

# Create aggregation Python script
cat > "$RESULTS_DIR/aggregate.py" << 'PYEOF'
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
PYEOF

chmod +x "$RESULTS_DIR/aggregate.py"

# Track overall progress
total_tests=$(($(echo $LAMBDA_VALUES | wc -w) * ITERATIONS))
current_test=0

# Run tests for each lambda value
for LAMBDA in $LAMBDA_VALUES; do
    echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  Testing LAMBDA = $LAMBDA${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    LAMBDA_DIR="$RESULTS_DIR/lambda_$LAMBDA"
    mkdir -p "$LAMBDA_DIR"

    for i in $(seq 1 $ITERATIONS); do
        current_test=$((current_test + 1))
        ITER_DIR="$LAMBDA_DIR/iteration_$i"
        mkdir -p "$ITER_DIR"

        echo -e "\n${GREEN}[Test $current_test/$total_tests] Lambda=$LAMBDA, Iteration $i/$ITERATIONS${NC}"

        # Export LAMBDA for the mosh sender
        export MOSH_LAMBDA=$LAMBDA

        # Run the test
        echo "  Running testbed..."
        cd "$TESTBED_DIR"

        if ./run-python-test.sh > "$ITER_DIR/test_output.log" 2>&1; then
            echo -e "  ${GREEN}✓ Test completed${NC}"
        else
            echo -e "  ${RED}✗ Test failed (check $ITER_DIR/test_output.log)${NC}"
            continue
        fi

        # Copy logs for analysis
        cp -f logs/client_out.log "$ITER_DIR/" 2>/dev/null || true
        cp -f logs/output.log "$ITER_DIR/" 2>/dev/null || true

        # Run latency analysis
        echo "  Analyzing latency..."
        cd "$ANALYSIS_DIR"

        # Temporarily modify analyze_latency.py to output to specific location
        python3 - "$ITER_DIR" << 'ANALYSIS_SCRIPT'
import csv
import sys
import os

def parse_csv(filename: str) -> dict:
    with open(filename, "r") as f:
        reader = csv.reader(f)
        data = [(int(row[1]), float(row[0])) for row in reader]
        return dict(data)

def backfill(latency, client_log, server_log):
    latest_time = None
    for key in sorted(latency.keys(), reverse=True):
        if key in server_log and server_log[key] is not None:
            latest_time = server_log[key]
        if latency[key] is None and latest_time is not None:
            latency[key] = latest_time - client_log[key]

def calculate_latency(client_log, server_log):
    latency = dict()
    for key, value in client_log.items():
        if key in server_log:
            latency[key] = server_log[key] - value
        else:
            latency[key] = None
    backfill(latency, client_log, server_log)
    return latency

def calculate_statistics(latency):
    values = [v for v in latency.values() if v is not None]
    if not values:
        return {"min": 0, "max": 0, "average": 0}
    average = sum(values) / len(values)
    median = sorted(values)[len(values) // 2]
    return {"average": average, "median": median}

def main():
    output_dir = sys.argv[1]

    # Try iteration-specific logs first, fall back to testbed logs
    client_log_path = os.path.join(output_dir, "client_out.log")
    server_log_path = os.path.join(output_dir, "output.log")

    if not os.path.exists(client_log_path):
        client_log_path = "../testbed/logs/client_out.log"
    if not os.path.exists(server_log_path):
        server_log_path = "../testbed/logs/output.log"

    try:
        client_log = parse_csv(client_log_path)
        server_log = parse_csv(server_log_path)
    except Exception as e:
        print(f"Error reading logs: {e}", file=sys.stderr)
        return

    latency = calculate_latency(client_log, server_log)
    stats = calculate_statistics(latency)

    output_file = os.path.join(output_dir, "latency.csv")
    with open(output_file, "w") as f:
        for stat, value in stats.items():
            f.write(f"{stat},{value}\n")

    print(f"  Stats: avg={stats['average']:.6f}, median={stats['median']:.6f}")

if __name__ == "__main__":
    main()
ANALYSIS_SCRIPT

        cd "$SCRIPT_DIR"

        # Small delay between tests
        sleep 2
    done
done

# Aggregate all results
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Aggregating Results${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

python3 "$RESULTS_DIR/aggregate.py" "$RESULTS_DIR"

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Test Suite Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Results saved to: $RESULTS_DIR/"
echo "  - Per-iteration logs: lambda_X/iteration_Y/"
echo "  - Aggregated JSON: aggregated_results.json"
