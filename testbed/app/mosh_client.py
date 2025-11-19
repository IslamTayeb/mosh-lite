#!/usr/bin/env python3
"""Mosh Client for Testbed - wraps sender.py"""

import sys
import os
import time
import json
sys.path.insert(0, '/app/mosh')

import sender

def main():
    SERVER_HOST = os.getenv("PEER_NAME", "server")
    UDP_PORT = int(os.getenv("UDP_PORT", "5000"))
    SCENARIO_FILE = os.getenv("SCENARIO_FILE", "/scenarios/quick_test.json")

    print(f"[MOSH CLIENT] Connecting to {SERVER_HOST}:{UDP_PORT}")

    # Load scenario for timing
    with open(SCENARIO_FILE, 'r') as f:
        scenario = json.load(f)

    sender.init(SERVER_HOST, UDP_PORT)

    # Simple demo: send state updates based on scenario phases
    test_messages = ["Hello", "Hello World", "Hello World!", "Testing Mosh"]

    for i, step in enumerate(scenario.get('steps', [])):
        duration = step['duration_s']
        signal_dbm = step.get('signal_strength_dbm', -50)
        print(f"\n[PHASE {i+1}] Duration: {duration}s - Signal: {signal_dbm}dBm - {step.get('description', '')}")

        sender.transport.set_signal_strength(signal_dbm)

        phase_start = time.time()
        msg_idx = 0

        while time.time() - phase_start < duration:
            from state import State
            new_state = State(test_messages[msg_idx % len(test_messages)])
            sender.on_send(new_state, sender.inflight)
            sender.receive_acks()

            time.sleep(0.5)
            msg_idx += 1

    print("\n[MOSH CLIENT] Test complete")

if __name__ == "__main__":
    main()
