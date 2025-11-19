from inflight import InflightTracker
from state import State
from transport import Transporter, TransportInstruction
import socket


states = {} # for now we store all states
states[0] = State("")
inflight = InflightTracker()
transport = None
next_state_num = 1

def on_receive(instruction: TransportInstruction):
    print("\nReceived packet from receiver:")
    print(f"  Their ACK: {instruction.ack_num}")
    inflight.acked(instruction.ack_num)

def on_send(new_state: State, inf: InflightTracker):
    # instead of only relying on the last state
    # we rely on the last acked state
    global states, transport, next_state_num
    old_num = inf.highest_ack
    diff = states[old_num].generate_patch(new_state)
    new_num = next_state_num
    next_state_num += 1

    print(f"\nSending: State #{old_num} -> #{new_num} ('{states[old_num].string}' -> '{new_state.string}')")
    print(f"  Diff: {diff}")

    transport.send(old_num, new_num, inf.highest_ack, min(0, inf.highest_ack - 1, (inf.min_inflight_dependency() if inf.min_inflight_dependency() is not None else float('inf')) - 1), diff)
    inf.sent(new_num, old_num)
    current_state = new_state

def init(host, port):
    global transport
    transport = Transporter('', 0, host, port, on_receive)

def receive_acks():
    transport.socket.settimeout(0.1)
    while True:
        try:
            transport.recv()
        except socket.timeout:
            break
