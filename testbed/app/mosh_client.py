#!/usr/bin/env python3
"""Mosh Client for Testbed - wraps sender.py"""

import sys
import os
import time
import json
sys.path.insert(0, '/app/mosh')

import sender
import asyncio
from transport import TransportInstruction, Transporter
from dataclasses import dataclass
import logging

@dataclass
class LocalEvent:
    message: str

@dataclass
class RemoteEvent:
    instruction: TransportInstruction

@dataclass
class TerminationEvent:
    pass


async def network_listener(t: Transporter, queue):
    loop = asyncio.get_running_loop()
    while True:
        instruction = await t.async_recv(loop)
        await queue.put(RemoteEvent(instruction))

def wait_for_network_ready(sentinel_path='/artifacts/netem_ready.json', timeout=60):
    """Wait for netem controller to signal network is ready"""
    print(f"[CLIENT] Waiting for network conditions to be ready...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        if os.path.exists(sentinel_path):
            try:
                with open(sentinel_path, 'r') as f:
                    sentinel = json.load(f)
                if sentinel.get('ready', False):
                    print(f"[CLIENT] Network ready: step {sentinel['step']}/{sentinel['total_steps']}")
                    return sentinel
            except (json.JSONDecodeError, IOError) as e:
                # File might be mid-write, try again
                pass
        time.sleep(0.5)

    raise TimeoutError(f"Network conditions not ready after {timeout}s")

async def automated_writer(queue, delay=0.05):
    states = ['abc', 'cde', 'edf', 'adsfhadsf', 'fgi']

    for state in states:
        await queue.put(LocalEvent(message=state))
        await asyncio.sleep(delay)

    await queue.put(TerminationEvent())

async def event_processor(queue):
    with open('/logs/client_out.log', 'w') as fout:
        while True:
            ev = await queue.get()

            if isinstance(ev, LocalEvent):
                logging.debug(f'Keyboard event: {ev.message}')
                sender.send_message(ev.message, hook, fout)

            elif isinstance(ev, RemoteEvent):
                logging.debug(f'Network event: {ev.instruction}')

                sender.on_receive(ev.instruction)
            else:
                logging.error("QUITTING")
                while True:
                    pass
                for task in asyncio.all_tasks():
                    task.cancel()
                return

def hook(fout, stateno):
    ts = time.time()
    fout.write(f'{ts}, {stateno}\n')
    fout.flush()

async def main():
    SERVER_HOST = os.getenv("PEER_NAME", "server")
    UDP_PORT = int(os.getenv("UDP_PORT", "5000"))

    # Wait for network conditions to be ready
    print(f"[CLIENT] Starting mosh client")
    wait_for_network_ready()

    sender.init(SERVER_HOST, UDP_PORT)

    queue = asyncio.Queue()

    await asyncio.gather(automated_writer(queue), network_listener(sender.transport, queue), event_processor(queue))

    while True:
        pass

if __name__ == "__main__":
    asyncio.run(main())
