#!/bin/bash
#
# Container entrypoint - launches UDP server or client based on ROLE
#

set -e

# Configuration from environment
ROLE=${ROLE:-server}
NODE_NAME=${NODE_NAME:-node}
PEER_NAME=${PEER_NAME:-peer}
UDP_PORT=${UDP_PORT:-1337}
SCENARIO_FILE=${SCENARIO_FILE:-/scenarios/variable_link.json}

# Cleanup function
cleanup() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Shutting down $ROLE on $NODE_NAME"
    exit 0
}

trap cleanup SIGTERM SIGINT

# Print startup info
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting $NODE_NAME as $ROLE"
echo "Network interfaces:"
ip addr show | grep -E "inet |^\S"
echo "---"

# Export variables for Python scripts
export PEER_NAME
export UDP_PORT
export SCENARIO_FILE

# Launch appropriate role
if [ "$ROLE" = "server" ]; then
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting UDP server on port $UDP_PORT"
    exec python3 /app/mosh_server.py
else
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Starting UDP client, connecting to $PEER_NAME:$UDP_PORT"
    exec python3 /app/mosh_client.py
fi
