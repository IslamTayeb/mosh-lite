#!/bin/bash
#
# Main test orchestrator - builds containers, runs scenario, collects results
#

set -e

SCENARIO=${SCENARIO:-scenarios/roaming.json}
CLEANUP=${CLEANUP:-true}

echo "Network Testing Testbed"
echo "Scenario: $SCENARIO"
echo "======================"

# Cleanup function
cleanup() {
    if [ "$CLEANUP" = "true" ]; then
        echo -e "\nCleaning up..."
        docker exec server tc qdisc del dev eth0 root 2>/dev/null || true
        docker exec client tc qdisc del dev eth0 root 2>/dev/null || true
        docker compose down
    fi
}

trap cleanup EXIT SIGINT SIGTERM

# Build and start
echo -e "\n[1/4] Building containers..."
docker compose build --quiet

echo "[2/4] Starting containers..."
export SCENARIO_FILE="/$SCENARIO"
docker compose up -d
sleep 5

# Verify containers started
if ! docker ps | grep -q "server.*Up" || ! docker ps | grep -q "client.*Up"; then
    echo "ERROR: Containers failed to start"
    docker compose ps
    exit 1
fi

# Start network controller
echo "[3/4] Applying network conditions..."
./netem_controller.sh --scenario "$SCENARIO" --targets server,client &
CONTROLLER_PID=$!
sleep 3

# Calculate and wait for test duration
TOTAL_DURATION=$(jq '[.steps[].duration_s] | add' "$SCENARIO")
echo "[4/4] Running test (${TOTAL_DURATION}s)..."
echo "  Monitor: docker logs -f client"

for ((i=1; i<=TOTAL_DURATION; i++)); do
    if [ $((i % 10)) -eq 0 ]; then
        echo "  Progress: ${i}/${TOTAL_DURATION}s"
    fi
    sleep 1
    ! kill -0 $CONTROLLER_PID 2>/dev/null && break
done

sleep 5  # Allow client to write results

# Display results
echo -e "\nResults:"
echo "========"
if [ -f artifacts/client_summary.txt ]; then
    cat artifacts/client_summary.txt
else
    echo "WARNING: Results file not found"
fi

if [ -f artifacts/client_results.json ]; then
    echo -e "\nQuick stats:"
    TOTAL_SENT=$(jq -r '.overall.total_packets_sent' artifacts/client_results.json)
    OVERALL_LOSS=$(jq -r '.overall.overall_loss_percent' artifacts/client_results.json)
    echo "  Packets sent: $TOTAL_SENT"
    echo "  Overall loss: ${OVERALL_LOSS}%"
fi

echo -e "\nDetailed results in artifacts/"
exit 0
