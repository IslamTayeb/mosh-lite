# Network Testing Testbed

Docker-based testbed for testing UDP applications under controlled network conditions using Linux `tc`/`netem`.

## Quick Start

```bash
# Run test with default scenario
./run-python-test.sh

# Run with specific scenario
SCENARIO=scenarios/quick_test.json ./run-python-test.sh

# View results
cat artifacts/client_summary.txt
cat artifacts/client_results.json
```

## Architecture

```
┌─────────────────────┐         ┌─────────────────────┐
│  server container   │◄───────►│  client container   │
│  (udp_server.py)    │   UDP   │  (udp_client.py)    │
└─────────────────────┘         └─────────────────────┘
         │                               │
         └───────────────┬───────────────┘
                         │
              tc/netem (controlled by
              netem_controller.sh)
```

- **Server**: Receives UDP packets, sends responses back
- **Client**: Sends UDP packets at ~100/sec, measures latency and loss
- **Controller**: Applies network impairments (delay, jitter, loss, bandwidth) based on scenario file

## Key Files

### Core Scripts
- `run-python-test.sh` - Main test orchestrator
- `netem_controller.sh` - Applies tc/netem rules from scenario file
- `docker-compose.yml` - Container configuration
- `Dockerfile` - Container image with Python, tc, etc.

### Application
- `app/udp_server.py` - UDP server (receives packets, sends responses)
- `app/udp_client.py` - UDP client (sends packets, measures metrics)
- `app/run_app.sh` - Container entrypoint

### Scenarios
- `scenarios/quick_test.json` - 15 second test (3 phases × 5s)
- `scenarios/variable_link.json` - 30 second test (3 phases × 10s)

## Scenario Format

Scenarios define time-varying network conditions:

```json
{
  "scenario_name": "My Test",
  "description": "Description of test",
  "steps": [
    {
      "duration_s": 10,
      "delay_ms": 50,
      "jitter_ms": 10,
      "loss_pct": 2,
      "rate_kbit": 5000,
      "description": "Phase description"
    }
  ]
}
```

**Parameters:**
- `duration_s` - How long to apply this configuration
- `delay_ms` - Base RTT delay
- `jitter_ms` - Variation in delay
- `loss_pct` - Packet loss percentage (0-100)
- `rate_kbit` - Bandwidth limit (0 = unlimited)

## Replacing Client/Server

The current Python client/server are examples. To replace them:

### 1. Update Dockerfile
Ensure your dependencies are installed:
```dockerfile
RUN apt-get update && apt-get install -y \
    your-dependencies \
    iproute2 \
    && rm -rf /var/lib/apt/lists/*
```

### 2. Replace Python Scripts
- Replace `app/udp_server.py` with your server
- Replace `app/udp_client.py` with your client

### 3. Update run_app.sh
Change the entrypoint commands:
```bash
if [ "$ROLE" = "server" ]; then
    exec your-server-command
else
    exec your-client-command
fi
```

### Requirements for Your Client/Server

**Server must:**
- Listen on `$UDP_PORT` (default: 1337)
- Stay running (foreground process)
- Optionally: write metrics to `/artifacts/`

**Client must:**
- Connect to `$PEER_NAME:$UDP_PORT`
- Read scenario from `$SCENARIO_FILE`
- Send packets for each phase duration
- Write results to `/artifacts/client_results.json` and `/artifacts/client_summary.txt`

**Both must:**
- Handle SIGTERM gracefully
- Support concurrent send/receive for accurate RTT measurement

## Environment Variables

Containers receive these environment variables:

- `ROLE` - "server" or "client"
- `NODE_NAME` - Container hostname
- `PEER_NAME` - Other container hostname
- `UDP_PORT` - Port number (default: 1337)
- `SCENARIO_FILE` - Path to scenario JSON (client only)

## Output Files

After running tests, `artifacts/` contains:

- `client_results.json` - Detailed metrics per phase
- `client_summary.txt` - Human-readable summary
- `server_stats.json` - Server-side counters
- `controller_log.txt` - Record of tc commands applied
- `scenario_used.json` - Copy of scenario file

## Manual Usage

```bash
# Start containers
docker compose up -d

# View logs
docker logs server
docker logs client

# Manually apply tc rules (example)
docker exec server tc qdisc add dev eth0 root netem delay 100ms loss 5%

# Check current tc rules
docker exec server tc qdisc show dev eth0
docker exec client tc qdisc show dev eth0

# Reset tc rules
docker exec server tc qdisc del dev eth0 root
docker exec client tc qdisc del dev eth0 root

# Stop containers
docker compose down
```

## Common tc/netem Commands

```bash
# Add delay + jitter
tc qdisc add dev eth0 root netem delay 100ms 20ms distribution normal

# Add packet loss
tc qdisc add dev eth0 root netem delay 50ms loss 5%

# Add bandwidth limit
tc qdisc add dev eth0 root handle 1: tbf rate 1mbit burst 32kbit latency 400ms
tc qdisc add dev eth0 parent 1:1 handle 10: netem delay 50ms

# Reset
tc qdisc del dev eth0 root
```

## Troubleshooting

**Containers won't start:**
- `docker compose build --no-cache`
- Check logs: `docker compose logs`

**tc commands fail:**
- Ensure `cap_add: NET_ADMIN` in docker-compose.yml
- Check tc is installed: `docker exec server which tc`

**High packet loss:**
- Client may not be receiving responses concurrently while sending
- Ensure client uses threading or async I/O

## Requirements

- Linux host (or macOS/Windows with Docker Desktop)
- Docker & Docker Compose
- bash 3.2+ (for scripts)
- jq (for JSON parsing)

## License

MIT
