# Network Testing Testbed

Docker-based testbed for testing UDP applications under controlled network conditions using `tc`/`netem`.

## Quick Start

```bash
./run-python-test.sh

# use specific scenario
SCENARIO=scenarios/quick_test.json ./run-python-test.sh

# view results
cat artifacts/client_summary.txt
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

Server receives UDP packets and sends responses. Client sends packets at ~100/sec and measures latency/loss. Controller applies network impairments from scenario file.

## Scenarios

- `quick_test.json` - 15s test (baseline → degraded → recovery)
- `variable_link.json` - 30s test (good → bad → good)
- `high_delay_test.json` - 30s high delay/loss test
- `zero_loss_test.json` - zero loss test

## Scenario Format

```json
{
  "scenario_name": "Test Name",
  "steps": [
    {
      "duration_s": 10,
      "delay_ms": 50,
      "jitter_ms": 10,
      "loss_pct": 2,
      "rate_kbit": 5000
    }
  ]
}
```

## Manual Control

```bash
# start
docker compose up -d

# apply tc rules
docker exec server tc qdisc add dev eth0 root netem delay 100ms loss 5%

# check rules
docker exec server tc qdisc show dev eth0

# reset
docker exec server tc qdisc del dev eth0 root

# stop
docker compose down
```

## Monitoring During Tests

View live output from client/server while a test is running:

```bash
# view server console
docker logs -f server

# view client console
docker logs -f client

# view both simultaneously (requires tmux/split terminal)
docker logs -f server &
docker logs -f client

# view specific container's recent output
docker logs --tail 50 server
docker logs --tail 50 client
```

## Files

- `run-python-test.sh` - test orchestrator
- `netem_controller.sh` - applies tc rules
- `docker-compose.yml` - container config
- `app/udp_server.py` - server
- `app/udp_client.py` - client

Results in `artifacts/`: `client_results.json`, `client_summary.txt`, `controller_log.txt`

## Replacing Client/Server

1. Update `Dockerfile` with dependencies
2. Replace `app/udp_server.py` and `app/udp_client.py`
3. Update `app/run_app.sh`

Server must listen on `$UDP_PORT`. Client must connect to `$PEER_NAME:$UDP_PORT`, read `$SCENARIO_FILE`, write to `/artifacts/`.
