from inflight import InflightTracker
from state import State
from transport import Transporter, TransportInstruction
import socket

current_state = State("")
inflight = InflightTracker()
receiver_ack = -1
transport = None
# SHOULDN'T BE NECESSARY ONCE WE HAVE A RECEIVER ACK
last_state_num = 0

def on_receive(instruction: TransportInstruction):
    global receiver_ack
    if instruction.ack_num > receiver_ack:
        inflight.acked(instruction.ack_num)
        receiver_ack = instruction.ack_num

def on_send(new_state: State, inf: InflightTracker):
    global current_state, transport, last_state_num
    diff = current_state.generate_patch(new_state)
    old_num = last_state_num
    new_num = old_num + 1
    last_state_num = new_num

    min_dep = inf.min_inflight_dependency()
    throwaway_num = (min_dep - 1) if min_dep else -1

    transport.send(old_num, new_num, receiver_ack, throwaway_num, diff)
    inf.sent(new_num, old_num - 1 if old_num > 0 else None)
    current_state = new_state

def init(host, port):
    global transport
    transport = Transporter(host, port, on_receive)
    transport.socket.settimeout(0.1)

def receive_acks():
    while True:
        try:
            transport.recv()
        except socket.timeout:
            break
