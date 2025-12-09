#!/bin/bash
#
# Packet Loss Test Suite
# Tests across packet loss values (0%, 10%, 25%, 50%)
#

# Don't exit on errors - continue with remaining tests
set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTBED_DIR="$SCRIPT_DIR/testbed"
ANALYSIS_DIR="$SCRIPT_DIR/analysis"
RESULTS_DIR="$SCRIPT_DIR/packetloss_test_results"
ITERATIONS=${ITERATIONS:-10}
LOSS_VALUES="${LOSS_VALUES:-0 10 25 50}"
LAMBDA_VALUES="${LAMBDA_VALUES:-0 0.5 1.0}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Packet Loss Test Suite${NC}"
echo "Iterations: $ITERATIONS"
echo "Lambda values: $LAMBDA_VALUES"
echo "Loss values: $LOSS_VALUES"
echo ""

rm -rf "$RESULTS_DIR"
mkdir -p "$RESULTS_DIR"
mkdir -p "$TESTBED_DIR/scenarios/generated"

# Aggregation script
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
PYEOF

chmod +x "$RESULTS_DIR/aggregate.py"

# Track overall progress
total_tests=$(($(echo $LAMBDA_VALUES | wc -w) * $(echo $LOSS_VALUES | wc -w) * ITERATIONS))
current_test=0
failed_tests=0
successful_tests=0

# Run tests for each lambda and loss combination
for LAMBDA in $LAMBDA_VALUES; do
    for LOSS in $LOSS_VALUES; do
        echo -e "\n${YELLOW}Testing Lambda=${LAMBDA}, Loss=${LOSS}%${NC}"

        TEST_DIR="$RESULTS_DIR/lambda_${LAMBDA}_loss_${LOSS}pct"
        mkdir -p "$TEST_DIR"

        # Create scenario file for this loss rate
        SCENARIO_FILE="$TESTBED_DIR/scenarios/generated/loss_${LOSS}pct.json"
        cat > "$SCENARIO_FILE" << SCENARIO_EOF
{
  "scenario_name": "Packet Loss ${LOSS}%",
  "description": "Test with ${LOSS}% packet loss",
  "created_by": "packetloss_test_suite",
  "seed": 42,
  "notes": "10s test with ${LOSS}% packet loss, 50ms delay",
  "steps": [
    {
      "duration_s": 10,
      "delay_ms": 50,
      "jitter_ms": 5,
      "loss_pct": ${LOSS},
      "rate_kbit": 10000,
      "description": "${LOSS}% packet loss with 50ms delay"
    }
  ]
}
SCENARIO_EOF

        for i in $(seq 1 $ITERATIONS); do
            current_test=$((current_test + 1))
            ITER_DIR="$TEST_DIR/iteration_$i"
            mkdir -p "$ITER_DIR"

            echo -e "\n${GREEN}[Test $current_test/$total_tests] Lambda=${LAMBDA}, Loss=${LOSS}%, Iter $i${NC}"

            # Export LAMBDA for the mosh sender
            export MOSH_LAMBDA=$LAMBDA

            # Run the test
            echo "  Running testbed..."
            cd "$TESTBED_DIR" || { echo -e "  ${RED}✗ Could not cd to testbed${NC}"; failed_tests=$((failed_tests + 1)); continue; }

            if SCENARIO="scenarios/generated/loss_${LOSS}pct.json" ./run-python-test.sh > "$ITER_DIR/test_output.log" 2>&1; then
                echo -e "  ${GREEN}✓ Test completed${NC}"
                successful_tests=$((successful_tests + 1))
            else
                echo -e "  ${RED}✗ Test failed (check $ITER_DIR/test_output.log)${NC}"
                failed_tests=$((failed_tests + 1))
                # Still try to copy any logs that exist
                cp -f logs/client_out.log "$ITER_DIR/" 2>/dev/null || true
                cp -f logs/output.log "$ITER_DIR/" 2>/dev/null || true
                cp -f artifacts/discard_stats.txt "$ITER_DIR/" 2>/dev/null || true
                cd "$SCRIPT_DIR"
                sleep 2
                continue
            fi

            # Copy logs for analysis
            cp -f logs/client_out.log "$ITER_DIR/" 2>/dev/null || true
            cp -f logs/output.log "$ITER_DIR/" 2>/dev/null || true
            cp -f artifacts/discard_stats.txt "$ITER_DIR/" 2>/dev/null || true

            # Run latency analysis
            echo "  Analyzing latency..."
            cd "$ANALYSIS_DIR" || { echo -e "  ${RED}✗ Could not cd to analysis${NC}"; continue; }

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
done

# Aggregate results
echo -e "\n${BLUE}Aggregating Results${NC}"
if python3 "$RESULTS_DIR/aggregate.py" "$RESULTS_DIR"; then
    echo -e "\n${GREEN}Aggregation complete${NC}"
else
    echo -e "\n${RED}Aggregation had errors${NC}"
fi

echo -e "\n${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}Complete! Results in: $RESULTS_DIR/${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo "  Successful: $successful_tests"
echo "  Failed: $failed_tests"
echo "  Total: $total_tests"
