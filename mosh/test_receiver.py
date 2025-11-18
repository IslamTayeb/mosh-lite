import socket
import json
from datagram import Packet
from transport import TransportInstruction
from state import State

states = {0: State("")}  # Initialize State #0 as empty
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('', 53001))
while True:
    j = s.recv(1500)
    p = Packet.unpack(j)
    ti = TransportInstruction.unmarshal(p.payload.decode('utf-8'))

    print(f"\nState #{ti.old_num} -> State #{ti.new_num}")
    print(f"ACK: {ti.ack_num}, Throwaway: {ti.throwaway_num}")

    # Show diff operations
    diff_ops = json.loads(ti.diff)
    print("Diff operations:")
    for op in diff_ops:
        print(f"  {op[0]}: {op}")

    # Apply diff
    if ti.old_num in states:
        old_state = states[ti.old_num]
        new_state = old_state.apply(ti.diff)
        states[ti.new_num] = new_state
        print(f"Result: '{old_state.string}' -> '{new_state.string}'")
    else:
        print(f"Warning: State #{ti.old_num} not found, cannot apply diff")
