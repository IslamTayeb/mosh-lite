#!/bin/bash
# Verify IP addresses and network interfaces for server and client

set -e

echo "======================================"
echo "Network Interface Verification"
echo "======================================"
echo ""

for container in server client; do
    echo "Container: $container"
    echo "--------------------------------------"

    # Get all interfaces except loopback
    interfaces=$(docker exec "$container" ip -o -4 addr show | grep -v '127.0.0.1' | awk '{print $2}' | sort -u)

    for iface in $interfaces; do
        # Get IP address
        ip=$(docker exec "$container" ip -4 addr show "$iface" | awk '/inet / {print $2}' | cut -d'/' -f1 | head -1)
        [ -z "$ip" ] && ip="N/A"

        # Determine network name based on subnet
        case "$ip" in
            10.1.*) network="wifi" ;;
            10.2.*) network="cellular_1" ;;
            10.3.*) network="cellular_2" ;;
            *) network="unknown" ;;
        esac

        # Check tc qdisc to see if interface has rules applied
        tc_output=$(docker exec "$container" tc qdisc show dev "$iface" 2>/dev/null || echo "")

        if echo "$tc_output" | grep -q "loss 100%"; then
            status="INACTIVE (100% loss)"
        elif echo "$tc_output" | grep -q "netem\|tbf"; then
            status="ACTIVE (tc rules applied)"
        else
            status="No tc rules"
        fi

        printf "  %-10s %-15s %-15s %s\n" "$iface" "$ip" "($network)" "$status"
    done

    echo ""
done

echo "======================================"
echo ""
echo "To monitor in real-time, run:"
echo "  watch -n 1 ./verify-ips.sh"
