#!/usr/bin/env python3
"""
UDP Server - Receives packets and sends responses back to client
"""

import socket
import json
import time
import sys
import os
import signal
from datetime import datetime
sys.path.insert(0, '/app/mosh')
import asyncio
from receiver import update_listener, init
from transport import TransportInstruction

def hook(f, ti: TransportInstruction) -> None:
    ts = time.time()
    state_num = ti.new_num
    f.write(f'{ts}, {state_num}\n')
    f.flush()

def wait_for_network_ready(sentinel_path='/artifacts/netem_ready.json', timeout=60):
    """Wait for netem controller to signal network is ready"""
    print(f"[SERVER] Waiting for network conditions to be ready...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if os.path.exists(sentinel_path):
            try:
                with open(sentinel_path, 'r') as f:
                    sentinel = json.load(f)
                if sentinel.get('ready', False):
                    print(f"[SERVER] Network ready: step {sentinel['step']}/{sentinel['total_steps']}")
                    return sentinel
            except (json.JSONDecodeError, IOError) as e:
                # File might be mid-write, try again
                pass
        time.sleep(0.5)

    raise TimeoutError(f"Network conditions not ready after {timeout}s")

async def main():
    UDP_PORT = int(os.getenv("UDP_PORT", "5000"))

    # Wait for network conditions to be ready
    print(f"[SERVER] Starting mosh server")
    wait_for_network_ready()

    init(UDP_PORT)
    with open('/logs/output.log', 'w') as fout:
        await update_listener(receive_hook=hook, extra_context=fout)
    

if __name__ == "__main__":
    asyncio.run(main())
