#!/usr/bin/env python3
"""
UDP Client - Sends packets and measures latency and packet loss
"""

import socket
import json
import time
import sys
import os
import signal
import statistics
import threading
from datetime import datetime
from collections import defaultdict

# Configuration
SERVER_HOST = os.getenv("PEER_NAME", "server")
UDP_PORT = int(os.getenv("UDP_PORT", "5000"))
SCENARIO_FILE = os.getenv("SCENARIO_FILE", "/scenarios/variable_link.json")
LOG_FILE = "/var/log/udp_client.log"
RESULTS_FILE = "/artifacts/client_results.json"
SUMMARY_FILE = "/artifacts/client_summary.txt"

# Test parameters
SEND_RATE = 0.01  # seconds between packets (100 pps)
SOCKET_TIMEOUT = 2.0  # seconds to wait for response after phase ends
RESPONSE_WAIT_TIME = 3.0  # extra seconds to wait for all responses after sending stops

# Global data structures
all_results = []
should_exit = False

def log(message):
    """Log message with timestamp"""
    timestamp = datetime.utcnow().isoformat() + "Z"
    log_line = f"[{timestamp}] {message}\n"
    print(log_line, end='')
    sys.stdout.flush()
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_line)
    except Exception as e:
        print(f"Error writing to log: {e}", file=sys.stderr)

def signal_handler(sig, frame):
    """Handle shutdown signal"""
    global should_exit
    log("Received shutdown signal")
    should_exit = True

def wait_for_server(sock, timeout=30):
    """Wait for server to be reachable"""
    log(f"Waiting for server {SERVER_HOST}:{UDP_PORT} to be reachable...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            # Send a test packet
            test_packet = json.dumps({"seq": -1, "timestamp": time.time(), "test": True}).encode('utf-8')
            sock.sendto(test_packet, (SERVER_HOST, UDP_PORT))

            # Try to receive response
            sock.settimeout(1.0)
            data, addr = sock.recvfrom(4096)
            log(f"Server {SERVER_HOST}:{UDP_PORT} is reachable!")
            return True
        except (socket.timeout, socket.gaierror, OSError) as e:
            time.sleep(1)

    log(f"Timeout waiting for server after {timeout}s")
    return False

def calculate_jitter(rtts):
    """Calculate jitter (variance in RTT)"""
    if len(rtts) < 2:
        return 0.0

    differences = [abs(rtts[i] - rtts[i-1]) for i in range(1, len(rtts))]
    return statistics.mean(differences) if differences else 0.0

def run_phase(sock, phase_num, phase_config, sent_packets, received_packets, seq_counter):
    """Run a single test phase - send packets continuously for phase duration

    Assumes receiver thread is already running in the background.
    """
    phase_duration = phase_config['duration_s']

    log(f"\n{'='*60}")
    log(f"Phase {phase_num}: {phase_config.get('description', 'No description')}")
    log(f"  Duration: {phase_duration}s")
    log(f"  Network: delay={phase_config.get('delay_ms', 0)}ms, "
        f"jitter={phase_config.get('jitter_ms', 0)}ms, "
        f"loss={phase_config.get('loss_pct', 0)}%, "
        f"rate={phase_config.get('rate_kbit', 0)}kbit")
    log(f"  Sending packets continuously for {phase_duration}s at ~{int(1/SEND_RATE)} pps...")
    log(f"{'='*60}")

    phase_start = time.time()
    phase_end = phase_start + phase_duration
    phase_sent_count = 0
    phase_start_seq = seq_counter[0]

    # Send packets continuously for the phase duration
    log(f"  Starting packet transmission...")
    while time.time() < phase_end and not should_exit:
        send_time = time.time()
        seq = seq_counter[0]
        packet = {
            "seq": seq,
            "timestamp": send_time,
            "phase": phase_num
        }

        try:
            data = json.dumps(packet).encode('utf-8')
            sock.sendto(data, (SERVER_HOST, UDP_PORT))
            sent_packets[seq] = send_time
            seq_counter[0] += 1
            phase_sent_count += 1

            if phase_sent_count % 100 == 0 and phase_sent_count > 0:
                elapsed = time.time() - phase_start
                log(f"  Sent {phase_sent_count} packets ({elapsed:.1f}s / {phase_duration}s)")

            # Control send rate
            time.sleep(SEND_RATE)

        except Exception as e:
            log(f"Error sending packet {seq}: {e}")
            seq_counter[0] += 1

    send_complete_time = time.time()
    send_duration = send_complete_time - phase_start
    log(f"  Phase transmission complete: {phase_sent_count} packets sent in {send_duration:.2f}s")

    # Calculate phase statistics (only for packets sent in this phase)
    phase_received = {s: received_packets[s] for s in range(phase_start_seq, seq_counter[0]) if s in received_packets}
    rtts = [r["rtt_ms"] for r in phase_received.values()]

    packets_sent = phase_sent_count
    packets_received = len(phase_received)
    packets_lost = packets_sent - packets_received
    loss_percent = (packets_lost / packets_sent * 100) if packets_sent > 0 else 0

    results = {
        "phase": phase_num,
        "config": phase_config,
        "packets_sent": packets_sent,
        "packets_received": packets_received,
        "packets_lost": packets_lost,
        "loss_percent": round(loss_percent, 2),
        "phase_duration_s": round(send_duration, 2),
        "send_duration_s": round(send_duration, 2)
    }

    if rtts:
        results["latency_ms"] = {
            "min": round(min(rtts), 3),
            "max": round(max(rtts), 3),
            "mean": round(statistics.mean(rtts), 3),
            "median": round(statistics.median(rtts), 3),
            "stdev": round(statistics.stdev(rtts), 3) if len(rtts) > 1 else 0,
            "jitter": round(calculate_jitter(rtts), 3)
        }
    else:
        results["latency_ms"] = None

    # Log summary
    log(f"\n  Phase {phase_num} Results:")
    log(f"    Packets: {packets_sent} sent, {packets_received} received, {packets_lost} lost ({loss_percent:.2f}%)")
    if results["latency_ms"]:
        lat = results["latency_ms"]
        log(f"    Latency: min={lat['min']}ms, max={lat['max']}ms, "
            f"mean={lat['mean']}ms, median={lat['median']}ms")
        log(f"    Jitter: {lat['jitter']}ms, StdDev: {lat['stdev']}ms")

    return results

def save_results(results, scenario_info):
    """Save results to JSON and text files"""
    output = {
        "test_timestamp": datetime.utcnow().isoformat() + "Z",
        "server": f"{SERVER_HOST}:{UDP_PORT}",
        "scenario": scenario_info,
        "test_config": {
            "send_rate_s": SEND_RATE,
            "packets_per_second": int(1/SEND_RATE),
            "socket_timeout_s": SOCKET_TIMEOUT,
            "response_wait_time_s": RESPONSE_WAIT_TIME
        },
        "phases": results
    }

    # Calculate overall statistics
    total_sent = sum(r["packets_sent"] for r in results)
    total_received = sum(r["packets_received"] for r in results)
    total_lost = total_sent - total_received
    overall_loss = (total_lost / total_sent * 100) if total_sent > 0 else 0

    all_rtts = []
    for r in results:
        if r.get("latency_ms"):
            # We don't have individual RTTs, so use the mean for overall calculation
            # This is approximate but gives a sense of overall performance
            all_rtts.append(r["latency_ms"]["mean"])

    output["overall"] = {
        "total_packets_sent": total_sent,
        "total_packets_received": total_received,
        "total_packets_lost": total_lost,
        "overall_loss_percent": round(overall_loss, 2),
        "mean_latency_ms": round(statistics.mean(all_rtts), 3) if all_rtts else None
    }

    # Save JSON
    try:
        with open(RESULTS_FILE, 'w') as f:
            json.dump(output, f, indent=2)
        log(f"\nResults saved to {RESULTS_FILE}")
    except Exception as e:
        log(f"Error saving results JSON: {e}")

    # Save human-readable summary
    try:
        with open(SUMMARY_FILE, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("UDP CLIENT TEST RESULTS\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Test Time: {output['test_timestamp']}\n")
            f.write(f"Server: {output['server']}\n")
            f.write(f"Scenario: {scenario_info.get('scenario_name', 'Unknown')}\n\n")

            f.write("OVERALL RESULTS\n")
            f.write("-" * 80 + "\n")
            f.write(f"Total Packets Sent:     {output['overall']['total_packets_sent']}\n")
            f.write(f"Total Packets Received: {output['overall']['total_packets_received']}\n")
            f.write(f"Total Packets Lost:     {output['overall']['total_packets_lost']}\n")
            f.write(f"Overall Loss:           {output['overall']['overall_loss_percent']:.2f}%\n")
            if output['overall']['mean_latency_ms']:
                f.write(f"Mean Latency:           {output['overall']['mean_latency_ms']:.3f}ms\n")
            f.write("\n")

            f.write("PER-PHASE RESULTS\n")
            f.write("=" * 80 + "\n\n")

            for r in results:
                f.write(f"Phase {r['phase']}: {r['config'].get('description', 'No description')}\n")
                f.write("-" * 80 + "\n")
                f.write(f"Network Conditions:\n")
                f.write(f"  Delay:     {r['config'].get('delay_ms', 0)}ms\n")
                f.write(f"  Jitter:    {r['config'].get('jitter_ms', 0)}ms\n")
                f.write(f"  Loss:      {r['config'].get('loss_pct', 0)}%\n")
                f.write(f"  Bandwidth: {r['config'].get('rate_kbit', 0)}kbit\n")
                f.write(f"  Duration:  {r['config']['duration_s']}s\n\n")

                f.write(f"Results:\n")
                f.write(f"  Packets Sent:     {r['packets_sent']}\n")
                f.write(f"  Packets Received: {r['packets_received']}\n")
                f.write(f"  Packets Lost:     {r['packets_lost']} ({r['loss_percent']:.2f}%)\n")

                if r.get("latency_ms"):
                    lat = r["latency_ms"]
                    f.write(f"\n  Latency Statistics:\n")
                    f.write(f"    Min:    {lat['min']:.3f}ms\n")
                    f.write(f"    Max:    {lat['max']:.3f}ms\n")
                    f.write(f"    Mean:   {lat['mean']:.3f}ms\n")
                    f.write(f"    Median: {lat['median']:.3f}ms\n")
                    f.write(f"    StdDev: {lat['stdev']:.3f}ms\n")
                    f.write(f"    Jitter: {lat['jitter']:.3f}ms\n")

                f.write("\n")

            f.write("=" * 80 + "\n")

        log(f"Summary saved to {SUMMARY_FILE}")
    except Exception as e:
        log(f"Error saving summary: {e}")

def main():
    global should_exit

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log(f"UDP Client starting")
    log(f"Server: {SERVER_HOST}:{UDP_PORT}")
    log(f"Scenario: {SCENARIO_FILE}")

    # Load scenario
    try:
        with open(SCENARIO_FILE, 'r') as f:
            scenario = json.load(f)
        log(f"Loaded scenario: {scenario.get('scenario_name', 'Unknown')}")
    except FileNotFoundError:
        log(f"ERROR: Scenario file not found: {SCENARIO_FILE}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        log(f"ERROR: Invalid JSON in scenario file: {e}")
        sys.exit(1)

    steps = scenario.get('steps', [])
    if not steps:
        log("ERROR: No steps found in scenario")
        sys.exit(1)

    log(f"Scenario has {len(steps)} phases")

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Wait for server
    if not wait_for_server(sock):
        log("ERROR: Server not reachable")
        sys.exit(1)

    # Give server a moment to stabilize
    time.sleep(2)

    # Wait for tc rules to be applied by netem_controller.sh
    # The orchestrator script sleeps 5s after starting containers,
    # then starts netem_controller which takes ~3s to apply rules.
    # We've already waited ~2-3s for server + 2s stabilization = ~5s total.
    # Wait an additional 5s to ensure tc rules are fully applied before sending.
    log("Waiting 5s for network conditions to be applied...")
    time.sleep(5)

    # Shared data structures for all phases
    sent_packets = {}  # seq -> send_time
    received_packets = {}  # seq -> response_data
    seq_counter = [0]  # Use list to allow mutation in nested function
    receiver_stop = threading.Event()

    # Receiver thread function (runs for ALL phases)
    def receiver():
        """Continuously receive responses while sending"""
        sock.settimeout(0.1)  # Short timeout to allow checking stop flag
        while not receiver_stop.is_set():
            try:
                data, addr = sock.recvfrom(4096)
                recv_time = time.time()

                response = json.loads(data.decode('utf-8'))
                resp_seq = response['seq']

                # Skip test packets
                if resp_seq == -1:
                    continue

                if resp_seq in sent_packets and resp_seq not in received_packets:
                    send_time = sent_packets[resp_seq]
                    rtt = (recv_time - send_time) * 1000  # Convert to ms
                    received_packets[resp_seq] = {
                        "rtt_ms": rtt,
                        "send_time": send_time,
                        "recv_time": recv_time,
                        "client_send_time": response.get('client_send_time', 0),
                        "server_recv_time": response.get('server_recv_time', 0),
                        "server_send_time": response.get('server_send_time', 0)
                    }

                    if len(received_packets) % 100 == 0:
                        log(f"  [Receiver] {len(received_packets)} responses received total")

            except socket.timeout:
                continue  # This is normal, just check the stop flag and retry
            except json.JSONDecodeError as e:
                log(f"Error decoding response: {e}")
            except Exception as e:
                if not receiver_stop.is_set():  # Only log if we're supposed to be running
                    log(f"Error in receiver: {e}")

    # Start receiver thread (runs for all phases)
    log("Starting receiver thread...")
    receiver_thread = threading.Thread(target=receiver, daemon=True)
    receiver_thread.start()

    # Run each phase
    phase_results = []
    for i, step in enumerate(steps):
        if should_exit:
            log("Exiting early due to signal")
            break

        phase_num = i + 1
        result = run_phase(sock, phase_num, step, sent_packets, received_packets, seq_counter)
        phase_results.append(result)

    # All phases complete - wait for remaining responses
    log(f"\n{'='*60}")
    log(f"All phases complete. Waiting {RESPONSE_WAIT_TIME}s for remaining responses...")
    time.sleep(RESPONSE_WAIT_TIME)

    # Stop receiver thread
    receiver_stop.set()
    receiver_thread.join(timeout=2)
    log(f"Receiver stopped. Total responses: {len(received_packets)}/{len(sent_packets)}")

    # Save results
    log("Saving results...")
    save_results(phase_results, scenario)

    log(f"\n{'='*60}")
    log("Client finished successfully")
    log(f"{'='*60}\n")

    sock.close()

if __name__ == "__main__":
    main()
