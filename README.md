# Mosh-Lite: Testing Reference State Selection in SSP

A simplified ground-up implementation of the Mobile Shell (Mosh) State Synchronization Protocol (SSP) with a configurable λ parameter and test-bed for evaluating reference state selection strategies under high packet loss conditions.

## Overview

This project investigates Mosh's choice to always use the "assumed receiver state" (most recently sent state within RTO window) as the reference for differential updates. We propose a λ-parameterized extension that probabilistically selects between the assumed receiver state and the "known receiver state" (last acknowledged state) to potentially improve Age of Information (AoI) under high packet loss.

**Key Finding:** Testing showed that reference state selection strategy has minimal impact on AoI under moderate to extreme packet loss (75%), suggesting SSP's original timeout-based approach is near-optimal for this metric in typical mobile environments.

For detailed implementation analysis and design decisions, see [`final_report.pdf`](final_report.pdf).

## Quick Start

### Run a Test with Docker

```bash
cd testbed

# Run default high delay test (1s delay, 75% loss)
./basic_test.sh

# Run with specific scenario
SCENARIO=scenarios/quick_test.json ./basic_test.sh

# Run with different λ values (0 = original Mosh, 1 = always known state)
MOSH_LAMBDA=0.5 SCENARIO=scenarios/variable_link.json ./basic_test.sh
```

### Run Bulk Experiments

```bash
cd testbed

# Generate test states
python3 bulk_test.py --generate-states

# Run tests for all λ values (0, 0.5, 1.0) with 10 iterations each
python3 bulk_test.py --lambda-values 0 0.5 1.0 --iterations 10

# Results saved to lambda_results/
```

### Analyze Results

```bash
cd analysis

# Analyze a single test
python3 analyze_latency.py

# Generate figures from bulk experiments
python3 figures/scripts/plot_lambda_results.py
python3 figures/scripts/paper_analysis.py
```

## Project Structure

```
.
├── mosh/                   # Core SSP implementation
│   ├── sender.py           # SSP sender with λ parameter
│   ├── receiver.py         # SSP receiver
│   ├── transport.py        # UDP transport layer with RTT/RTO estimation
│   ├── state.py            # State objects with diff generation
│   ├── inflight.py         # In-flight state tracking
│   ├── datagram.py         # Packet format
│   └── tests/              # Unit tests
├── testbed/                # Docker-based testing infrastructure
│   ├── app/                # Testbed application wrappers
│   │   ├── mosh_client.py  # Client wrapper for automated testing
│   │   └── mosh_server.py  # Server wrapper
│   ├── scenarios/          # Network condition scenarios (JSON)
│   ├── basic_test.sh       # Single test runner
│   ├── bulk_test.py        # Bulk experiment orchestrator
│   ├── netem_controller.sh # Network emulation controller
│   └── README.md           # Detailed testbed documentation
├── analysis/               # Analysis scripts and results
│   ├── analyze_latency.py  # AoI calculation from logs
│   ├── figures/            # Generated plots
│   └── tables/             # Results tables
└── final_report.pdf        # Full research paper

```

## Implementation Details

### Core SSP Components

Our simplified implementation preserves essential SSP mechanisms:

- **UDP-based communication** with sequence numbers and timestamps
- **RTT estimation** using TCP-style SRTT and RTTVAR (α=0.125, β=0.25, K=4, G=0.1)
- **Dynamic RTO calculation** with 50ms minimum threshold
- **Differential updates** using Python's `difflib.SequenceMatcher`
- **In-flight state tracking** to maintain dependency graphs
- **λ-parameterized reference selection**: Probabilistically choose between assumed vs. known receiver state

### Simplifications from Original Mosh

- Simple string states instead of full terminal emulation
- No timing controls (framerate intervals, delayed ACKs, heartbeats)
- No packet fragmentation (states kept under 250 chars)
- No local echo prediction

These simplifications isolate the effect of reference state selection on AoI without confounding factors.

### The λ Parameter

Set via the `MOSH_LAMBDA` environment variable (default: 0):

- **λ = 0**: Original Mosh behavior (always use assumed receiver state)
- **λ = 1**: Conservative strategy (always use known receiver state)
- **0 < λ < 1**: Probabilistic mix of both strategies

## Testing Infrastructure

The Docker-based testbed emulates mobile network conditions using Linux `tc`/`netem`. See [`testbed/README.md`](testbed/README.md) for detailed documentation.

### Network Scenarios

Scenarios define network conditions over time:

- `high_delay_test.json` - 1000ms delay, 75% loss (extreme stress test)
- `variable_link.json` - Alternating good/bad conditions (30s)
- `quick_test.json` - Fast 15s baseline → degraded → recovery test
- `zero_loss_test.json` - Zero loss baseline

### Metrics

**Age of Information (AoI)**: Primary metric measuring information staleness at the receiver. For each sent state, AoI is calculated as the time between transmission and when the receiver's state catches up to or surpasses it.

**Packet Discard Rate**: Secondary metric tracking packets discarded due to missing dependency states.

## Results Summary

Testing with 1000ms base delay and 75% packet loss across 10 iterations per configuration:

| λ Value | Median AoI | Avg AoI | Outliers |
|---------|------------|---------|----------|
| 0.0 (Original) | ~1.1s | 1.7s | 4.0-13.1s |
| 0.5 (Mixed) | ~1.1s | 2.1s | 14.2s |
| 1.0 (Conservative) | ~1.1s | 1.8s | 14.2s |

**Conclusion**: Reference state selection strategy has minimal impact on typical-case AoI performance. The λ = 0.5 mixed strategy showed slightly elevated average latency without clear benefits.

See [`final_report.pdf`](final_report.pdf) for complete analysis.

## Development

### Prerequisites

- Docker & Docker Compose (for testbed)
- Python 3.13+ (for local development)
- `jq` (for scenario parsing in shell scripts)

### Local Development Setup

```bash
cd mosh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run unit tests
python3 -m pytest tests/
```

### Running Individual Components

```bash
# Terminal 1 - Receiver
cd mosh
python3 -c "import receiver; receiver.init(5000); import asyncio; asyncio.run(receiver.update_listener())"

# Terminal 2 - Sender
cd mosh
python3 -c "import sender; sender.init('localhost', 5000); sender.send_message('hello')"
```

## Key Files Reference

- **`mosh/sender.py:23`** - λ parameter configuration
- **`mosh/sender.py:43-95`** - Reference state selection logic
- **`mosh/transport.py:39-63`** - RTT/RTO estimation
- **`mosh/receiver.py:22-52`** - Packet acceptance/discard logic
- **`testbed/bulk_test.py`** - Experiment orchestration
- **`analysis/analyze_latency.py`** - AoI calculation algorithm
