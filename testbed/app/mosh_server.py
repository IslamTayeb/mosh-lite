#!/usr/bin/env python3
"""
UDP Server - Receives packets and sends responses back to client
"""

import json
import time
import sys
import os
import signal

sys.path.insert(0, "/app/mosh")
import asyncio
from receiver import update_listener, init, get_discard_stats
from transport import TransportInstruction


def hook(f, ti: TransportInstruction) -> None:
    ts = time.time()
    state_num = ti.new_num
    f.write(f"{ts}, {state_num}\n")
    f.flush()


def wait_for_network_ready(sentinel_path="/artifacts/netem_ready.json", timeout=60):
    """Wait for netem controller to signal network is ready"""
    print("[SERVER] Waiting for network conditions to be ready...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if os.path.exists(sentinel_path):
            try:
                with open(sentinel_path, "r") as f:
                    sentinel = json.load(f)
                if sentinel.get("ready", False):
                    print(
                        f"[SERVER] Network ready: step {sentinel['step']}/{sentinel['total_steps']}"
                    )
                    return sentinel
            except (json.JSONDecodeError, IOError):
                # File might be mid-write, try again
                pass
        time.sleep(0.5)

    raise TimeoutError(f"Network conditions not ready after {timeout}s")


def save_discard_stats():
    """Save packet discard statistics to file"""
    try:
        stats = get_discard_stats()
        stats_file = "/artifacts/discard_stats.txt"
        with open(stats_file, "w") as f:
            f.write(f"Total packets received: {stats['total_packets_received']}\n")
            f.write(f"Packets discarded: {stats['packets_discarded']}\n")
            f.write(f"Packets accepted: {stats['packets_accepted']}\n")
            f.write(f"Packets discarded (%): {stats['discard_percentage']:.4f}\n")
        print(
            f"[SERVER] Saved discard stats: {stats['packets_discarded']}/{stats['total_packets_received']} = {stats['discard_percentage']:.2f}%"
        )
    except Exception as e:
        print(f"[SERVER] Error saving discard stats: {e}")


async def main():
    UDP_PORT = int(os.getenv("UDP_PORT", "5000"))

    # Wait for network conditions to be ready
    print("[SERVER] Starting mosh server")
    wait_for_network_ready()

    init(UDP_PORT)

    # Setup signal handler to save stats on exit
    def signal_handler(signum, frame):
        print(f"[SERVER] Received signal {signum}, saving stats...")
        save_discard_stats()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        with open("/logs/output.log", "w") as fout:
            await update_listener(receive_hook=hook, extra_context=fout)
    finally:
        save_discard_stats()


if __name__ == "__main__":
    asyncio.run(main())
