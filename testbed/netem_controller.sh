#!/bin/bash

set -e

# Default values
SCENARIO_FILE=""
TARGETS=""
CONTROLLER_LOG="artifacts/controller_log.txt"
INTERFACE="eth0"

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --scenario)
            SCENARIO_FILE="$2"
            shift 2
            ;;
        --targets)
            TARGETS="$2"
            shift 2
            ;;
        --interface)
            INTERFACE="$2"
            shift 2
            ;;
        --log)
            CONTROLLER_LOG="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 --scenario <file> --targets <container1,container2,...> [--interface <iface>] [--log <logfile>]"
            exit 1
            ;;
    esac
done

# Validate arguments
if [ -z "$SCENARIO_FILE" ] || [ -z "$TARGETS" ]; then
    echo "Error: --scenario and --targets are required"
    echo "Usage: $0 --scenario <file> --targets <container1,container2,...> [--interface <iface>] [--log <logfile>]"
    exit 1
fi

if [ ! -f "$SCENARIO_FILE" ]; then
    echo "Error: Scenario file not found: $SCENARIO_FILE"
    exit 1
fi

# Create log directory
mkdir -p "$(dirname "$CONTROLLER_LOG")"

# Convert comma-separated targets to array
IFS=',' read -ra TARGET_ARRAY <<< "$TARGETS"

log_message() {
    local msg="$1"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$timestamp] $msg" | tee -a "$CONTROLLER_LOG"
}

# Cleanup function to reset qdiscs
cleanup() {
    log_message "Cleaning up tc qdiscs..."
    for target in "${TARGET_ARRAY[@]}"; do
        log_message "Resetting qdisc on $target"
        docker exec "$target" tc qdisc del dev "$INTERFACE" root 2>/dev/null || true
    done
    log_message "Cleanup complete"
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Detect all interfaces in container
detect_all_interfaces() {
    local container=$1
    docker exec "$container" bash -c "ip -o -4 addr show | grep -v '127.0.0.1' | awk '{print \$2}' | sort -u"
}

# Map interface name to network name based on subnet
get_network_for_interface() {
    local container=$1
    local iface=$2
    local ip=$(docker exec "$container" ip -4 addr show "$iface" | awk '/inet / {print $2}' | cut -d'/' -f1 | head -1)

    case "$ip" in
        10.1.*) echo "wifi" ;;
        10.2.*) echo "cellular_1" ;;
        10.3.*) echo "cellular_2" ;;
        *) echo "unknown" ;;
    esac
}

# Apply tc rule to a container
apply_tc_rule() {
    local container=$1
    local delay_ms=$2
    local jitter_ms=$3
    local loss_pct=$4
    local rate_kbit=$5
    local iface=$6

    log_message "Applying to $container: delay=${delay_ms}ms jitter=${jitter_ms}ms loss=${loss_pct}% rate=${rate_kbit}kbit"

    # First, try to delete any existing qdisc
    docker exec "$container" tc qdisc del dev "$iface" root 2>/dev/null || true

    # Build netem parameters
    local netem_params="delay ${delay_ms}ms"

    if [ "$jitter_ms" != "0" ]; then
        netem_params="$netem_params ${jitter_ms}ms distribution normal"
    fi

    if [ "$loss_pct" != "0" ]; then
        netem_params="$netem_params loss ${loss_pct}%"
    fi

    # Apply with or without rate limiting
    if [ "$rate_kbit" != "0" ] && [ ! -z "$rate_kbit" ]; then
        # Use tbf (token bucket filter) for rate limiting + netem
        local rate="${rate_kbit}kbit"
        local burst="32kbit"
        local latency="400ms"

        # Apply tbf as root, then netem as child
        local cmd1="tc qdisc add dev $iface root handle 1: tbf rate $rate burst $burst latency $latency"
        local cmd2="tc qdisc add dev $iface parent 1:1 handle 10: netem $netem_params"

        log_message "  CMD: $cmd1"
        if docker exec "$container" bash -c "$cmd1" 2>&1 | tee -a "$CONTROLLER_LOG"; then
            log_message "  ✓ TBF applied"
        else
            log_message "  ✗ TBF failed, retrying with replace..."
            docker exec "$container" bash -c "tc qdisc replace dev $iface root handle 1: tbf rate $rate burst $burst latency $latency" 2>&1 | tee -a "$CONTROLLER_LOG"
        fi

        log_message "  CMD: $cmd2"
        if docker exec "$container" bash -c "$cmd2" 2>&1 | tee -a "$CONTROLLER_LOG"; then
            log_message "  ✓ Netem applied"
        else
            log_message "  ✗ Netem failed"
            return 1
        fi
    else
        # Just apply netem
        local cmd="tc qdisc add dev $iface root netem $netem_params"

        log_message "  CMD: $cmd"
        if docker exec "$container" bash -c "$cmd" 2>&1 | tee -a "$CONTROLLER_LOG"; then
            log_message "  ✓ Applied successfully"
        else
            log_message "  ✗ Failed, retrying with replace..."
            docker exec "$container" bash -c "tc qdisc replace dev $iface root netem $netem_params" 2>&1 | tee -a "$CONTROLLER_LOG"
        fi
    fi
}

# Apply roaming rules - make one interface active, others dead
apply_roaming_rules() {
    local container=$1
    local active_network=$2
    local delay_ms=$3
    local jitter_ms=$4
    local loss_pct=$5
    local rate_kbit=$6

    log_message "Roaming: $container using $active_network as active interface"

    # Get all interfaces
    local interfaces=$(detect_all_interfaces "$container")

    for iface in $interfaces; do
        local network=$(get_network_for_interface "$container" "$iface")
        log_message "  Interface $iface -> network $network"

        if [ "$network" = "$active_network" ]; then
            # Active interface - apply specified rules
            log_message "  $iface (ACTIVE): applying normal rules"
            apply_tc_rule "$container" "$delay_ms" "$jitter_ms" "$loss_pct" "$rate_kbit" "$iface"
        else
            # Inactive interface - make it dead (100% loss)
            log_message "  $iface (INACTIVE): applying 100% loss"
            docker exec "$container" tc qdisc del dev "$iface" root 2>/dev/null || true
            docker exec "$container" tc qdisc add dev "$iface" root netem loss 100% 2>&1 | tee -a "$CONTROLLER_LOG"
        fi
    done
}

# Main execution
log_message "=== Netem Controller Starting ==="
log_message "Scenario: $SCENARIO_FILE"
log_message "Targets: ${TARGET_ARRAY[*]}"
log_message "Interface: $INTERFACE"

# Copy scenario to artifacts for reproducibility
cp "$SCENARIO_FILE" "artifacts/scenario_used.json"

# Parse and execute scenario
num_steps=$(jq '.steps | length' "$SCENARIO_FILE")
log_message "Scenario has $num_steps steps"

for ((i=0; i<num_steps; i++)); do
    step=$(jq ".steps[$i]" "$SCENARIO_FILE")

    duration=$(echo "$step" | jq -r '.duration_s')
    delay=$(echo "$step" | jq -r '.delay_ms // 0')
    jitter=$(echo "$step" | jq -r '.jitter_ms // 0')
    loss=$(echo "$step" | jq -r '.loss_pct // 0')
    rate=$(echo "$step" | jq -r '.rate_kbit // 0')
    active_network=$(echo "$step" | jq -r '.active_interface // ""')

    log_message ""
    log_message "--- Step $((i+1))/$num_steps (duration: ${duration}s) ---"

    # Apply to all targets
    for target in "${TARGET_ARRAY[@]}"; do
        if [ -n "$active_network" ]; then
            # Roaming mode: apply rules based on active network
            apply_roaming_rules "$target" "$active_network" "$delay" "$jitter" "$loss" "$rate"
        else
            # Normal mode: apply to specified interface
            apply_tc_rule "$target" "$delay" "$jitter" "$loss" "$rate" "$INTERFACE"
        fi
    done

    log_message "Waiting ${duration}s before next step..."
    sleep "$duration"
done

log_message ""
log_message "=== Scenario Complete ==="
log_message "All steps executed successfully"

# Don't exit yet - keep running until interrupted
# This allows manual testing to continue
log_message "Controller staying active. Press Ctrl+C to cleanup and exit."
while true; do
    sleep 10
done
