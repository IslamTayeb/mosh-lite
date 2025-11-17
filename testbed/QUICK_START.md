# Quick Start Guide

## Running the Testbed

### Basic Usage (Recommended - Python Mode)

```bash
# Run with default scenario (variable_link.json)
./run-python-test.sh

# Run with a specific scenario
SCENARIO=scenarios/high_latency.json ./run-python-test.sh

# Keep containers running after test (for inspection)
CLEANUP=false ./run-python-test.sh
```

### View Results

```bash
# Human-readable summary
cat artifacts/client_summary.txt

# Detailed JSON results
cat artifacts/client_results.json

# Network conditions log
cat artifacts/controller_log.txt
```

## Available Scenarios

### Basic Testing
- **`baseline_perfect.json`** - Ideal conditions for baseline performance testing
- **`quick_test.json`** - Fast 15-second test (good for development iteration)
- **`stress_test.json`** - Worst-case conditions combining all impairments

### Network Impairments
- **`high_latency.json`** - High constant latency (satellite-like, 500ms)
- **`packet_loss.json`** - Escalating packet loss (0% → 20%)
- **`high_jitter.json`** - High jitter/variable latency (more challenging than constant delay)
- **`low_bandwidth.json`** - Severe bandwidth limitations (dial-up to normal)

### Real-World Scenarios
- **`variable_link.json`** - Good → Bad → Good link quality changes
- **`intermittent_connectivity.json`** - Network disconnections and reconnections
- **`burst_loss.json`** - Bursty packet loss patterns (congestion simulation)
- **`mobile_network.json`** - Mobile network conditions (4G/5G handoffs)
- **`wifi_roaming.json`** - WiFi AP handoff scenarios
- **`satellite_link.json`** - Satellite internet simulation (geostationary & LEO)
- **`congestion_collapse.json`** - Progressive network degradation

## Usage Examples

### Run a specific scenario
```bash
SCENARIO=scenarios/intermittent_connectivity.json ./run-python-test.sh
SCENARIO=scenarios/baseline_perfect.json ./run-python-test.sh
SCENARIO=scenarios/stress_test.json ./run-python-test.sh
```

### Quick iteration during development
```bash
# Fast 15-second test
SCENARIO=scenarios/quick_test.json ./run-python-test.sh
```

### Test connection recovery
```bash
SCENARIO=scenarios/intermittent_connectivity.json ./run-python-test.sh
```

### Test under congestion
```bash
SCENARIO=scenarios/congestion_collapse.json ./run-python-test.sh
```

### Baseline performance test
```bash
SCENARIO=scenarios/baseline_perfect.json ./run-python-test.sh
```

## Manual Control

### Start containers manually
```bash
docker compose up -d
```

### Apply network conditions manually
```bash
# Check current tc rules
docker exec server tc qdisc show dev eth0

# Apply delay
docker exec server tc qdisc add dev eth0 root netem delay 100ms

# Apply packet loss
docker exec server tc qdisc add dev eth0 root netem loss 10%

# Reset (remove impairments)
docker exec server tc qdisc del dev eth0 root
```

### Monitor logs
```bash
# Watch client output
docker logs -f client

# Watch server output
docker logs -f server
```

### Stop containers
```bash
docker compose down
```

## Scenario File Format

Scenarios are JSON files with this structure:

```json
{
  "scenario_name": "My Scenario",
  "description": "What this tests",
  "created_by": "your_name",
  "seed": 42,
  "notes": "Additional notes",
  "steps": [
    {
      "duration_s": 30,
      "delay_ms": 20,
      "jitter_ms": 5,
      "loss_pct": 0,
      "rate_kbit": 10000,
      "description": "Step description"
    }
  ]
}
```

### Parameters
- `duration_s`: Duration of this network condition (seconds)
- `delay_ms`: Base RTT delay (milliseconds)
- `jitter_ms`: Jitter/variation in delay (milliseconds)
- `loss_pct`: Packet loss percentage (0-100)
- `rate_kbit`: Bandwidth limit (kilobits/sec, 0 = unlimited)

## Creating Custom Scenarios

1. Copy an existing scenario file
2. Modify the JSON to your needs
3. Test it:
   ```bash
   SCENARIO=scenarios/my_scenario.json ./run-python-test.sh
   ```

## Understanding Results

After running a test, check `artifacts/client_summary.txt` for:
- Overall packet loss percentage
- Mean/median/min/max latency
- Per-phase statistics showing how the protocol handled each network condition phase

The test sends 1000 packets per phase, so you get statistically meaningful results for each network condition.

