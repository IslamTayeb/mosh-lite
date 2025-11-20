#!/usr/bin/env python3
"""Latency testing client for lambda experiments"""

import sys
import os
import time
import json
import asyncio

sys.path.insert(0, "/app/mosh")

import sender
from state import State

# Track latency metrics
latencies = []


def main():
    SERVER_HOST = os.getenv("PEER_NAME", "server")
    UDP_PORT = int(os.getenv("UDP_PORT", "5000"))
    SCENARIO_FILE = os.getenv("SCENARIO_FILE", "/scenarios/quick_test.json")
    LAMBDA_VALUE = float(os.getenv("LAMBDA", "0.5"))
    OUTPUT_FILE = os.getenv("OUTPUT_FILE", "/artifacts/latency_results.json")

    print(
        f"[LAMBDA TEST CLIENT] Lambda={LAMBDA_VALUE}, Connecting to {SERVER_HOST}:{UDP_PORT}"
    )

    # Set lambda value
    sender.set_lambda(LAMBDA_VALUE)

    # Load scenario
    with open(SCENARIO_FILE, "r") as f:
        scenario = json.load(f)

    sender.init(SERVER_HOST, UDP_PORT)

    # Test messages - variety of lengths
    test_messages = [
        "A",
        "Hello",
        "Hello World",
        "Testing Mosh Protocol",
        "The quick brown fox jumps over the lazy dog",
    ]

    # Run async event loop for receiving
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Track state send times and latencies
    state_send_times = {}

    async def receive_acks():
        """Receive ACKs and track latency"""
        while True:
            try:
                instruction = await sender.transport.async_recv(loop)
                ack_num = instruction.ack_num
                ack_time = time.time()

                # Calculate latency for all acked states
                for state_num in list(state_send_times.keys()):
                    if state_num <= ack_num and state_num in state_send_times:
                        latency = ack_time - state_send_times[state_num]
                        latencies.append(
                            {
                                "state_num": state_num,
                                "latency": latency,
                                "lambda": LAMBDA_VALUE,
                            }
                        )
                        del state_send_times[state_num]

                sender.on_receive(instruction)
            except BlockingIOError:
                await asyncio.sleep(0.01)
            except Exception as e:
                print(f"Error receiving: {e}")
                await asyncio.sleep(0.01)

    # Start receiver task
    recv_task = loop.create_task(receive_acks())

    async def run_test():
        """Run the test sending messages"""
        for i, step in enumerate(scenario.get("steps", [])):
            duration = step["duration_s"]
            signal_dbm = step.get("signal_strength_dbm", -50)
            print(
                f"\n[PHASE {i + 1}] Duration: {duration}s - Signal: {signal_dbm}dBm - {step.get('description', '')}"
            )

            sender.transport.set_signal_strength(signal_dbm)

            phase_start = time.time()
            msg_idx = 0

            while time.time() - phase_start < duration:
                new_state = State(test_messages[msg_idx % len(test_messages)])

                # Track when state is sent
                state_num = sender.next_state_num
                state_send_times[state_num] = time.time()

                sender.on_send(new_state, sender.inflight)

                await asyncio.sleep(0.2)  # Send ~5 messages per second
                msg_idx += 1

        # Wait a bit for final ACKs
        await asyncio.sleep(2)

    # Run test
    loop.run_until_complete(run_test())
    recv_task.cancel()

    print(
        f"\n[LAMBDA TEST CLIENT] Test complete. Collected {len(latencies)} latency samples"
    )

    # Calculate statistics
    if latencies:
        lat_values = [l["latency"] for l in latencies]
        avg_latency = sum(lat_values) / len(lat_values)
        min_latency = min(lat_values)
        max_latency = max(lat_values)

        print(f"  Avg Latency: {avg_latency * 1000:.2f}ms")
        print(f"  Min Latency: {min_latency * 1000:.2f}ms")
        print(f"  Max Latency: {max_latency * 1000:.2f}ms")

        # Save results
        results = {
            "lambda": LAMBDA_VALUE,
            "scenario": scenario["scenario_name"],
            "latencies": latencies,
            "avg_latency": avg_latency,
            "min_latency": min_latency,
            "max_latency": max_latency,
            "num_samples": len(latencies),
        }

        with open(OUTPUT_FILE, "w") as f:
            json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
