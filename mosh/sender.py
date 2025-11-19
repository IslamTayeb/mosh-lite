from inflight import InflightTracker
from state import State
from transport import Transporter, TransportInstruction
import socket

current_state = State("")
inflight = InflightTracker()
transport = None
next_state_num = 0

def on_receive(instruction: TransportInstruction):
    print("\nReceived packet from receiver:")
    print(f"  Their ACK: {instruction.ack_num}")
    inflight.acked(instruction.ack_num)

def on_send(new_state: State, inf: InflightTracker):
    global current_state, transport, next_state_num
    diff = current_state.generate_patch(new_state)
    old_num = next_state_num
    new_num = old_num + 1
    next_state_num = new_num

    print(f"\nSending: State #{old_num} -> #{new_num} ('{current_state.string}' -> '{new_state.string}')")
    print(f"  Diff: {diff}")

    transport.send(old_num, new_num, -1, -1, diff)
    inf.sent(new_num, old_num - 1 if old_num > 0 else None)
    current_state = new_state

def init(host, port):
    global transport
    transport = Transporter(host, port, on_receive)
    transport.socket.bind(('', 0))

def receive_acks():
    transport.socket.settimeout(0.1)
    while True:
        try:
            transport.recv()
        except socket.timeout:
            break
