from state import State
from transport import TransportInstruction, Transporter
from datagram import Packet
import socket
import time
from typing import Optional

states: dict[int, State] = {0: State("")}
transport: Optional[Transporter] = None
highest_received = 0

def on_receive(instruction: TransportInstruction) -> None:
    global highest_received

    print(f"\nReceived: State #{instruction.old_num} -> #{instruction.new_num}")
    print(f"  Diff: {instruction.diff}")
    print(f"  ACK: {instruction.ack_num}, Throwaway: {instruction.throwaway_num}")

    if instruction.old_num in states:
        old_state = states[instruction.old_num]
        new_state = old_state.apply(instruction.diff)
        states[instruction.new_num] = new_state
        print(f"  Result: '{old_state.string}' -> '{new_state.string}'")

        highest_received = max(highest_received, instruction.new_num)

        empty_diff = states[0].generate_patch(states[0])
        transport.send(0, 0, instruction.new_num, instruction.new_num, empty_diff)
        print(f"  Sent ACK for State #{instruction.new_num}")
    else:
        # TODO: Support for depending on instructions that are still in the pipeline
        print(f"  ERROR: State #{instruction.old_num} not found")

def init(port):
    global transport
    transport = Transporter(None, None, on_receive)
    transport.socket.bind(('', port))

def receive_loop():
    while True:
        transport.recv()
