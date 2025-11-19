from state import State
from transport import TransportInstruction
from datagram import Packet
import socket
import time

states = {0: State("")}
socket_obj = None
sender_addr = None
highest_received = -1
ack_seq = 0

def on_receive(instruction: TransportInstruction):
    global highest_received, sender_addr

    print(f"\nReceived: State #{instruction.old_num} -> #{instruction.new_num}")
    print(f"  Diff: {instruction.diff}")
    print(f"  ACK: {instruction.ack_num}, Throwaway: {instruction.throwaway_num}")

    if instruction.old_num in states:
        old_state = states[instruction.old_num]
        new_state = old_state.apply(instruction.diff)
        states[instruction.new_num] = new_state
        print(f"  Result: '{old_state.string}' -> '{new_state.string}'")

        if instruction.new_num > highest_received:
            highest_received = instruction.new_num

        send_ack(instruction.new_num)
        print(f"  Sent ACK for State #{instruction.new_num}")
    else:
        print(f"  ERROR: State #{instruction.old_num} not found")

def send_ack(ack_num: int):
    global socket_obj, sender_addr, ack_seq
    if sender_addr is None:
        return

    ack_diff = State("").generate_patch(State(""))
    ack_ti = TransportInstruction(0, 0, ack_num, -1, ack_diff)
    payload = ack_ti.marshall().encode('utf-8')
    curr_ts = int(1000 * time.time()) & 0xFFFF
    ack_packet = Packet(False, ack_seq, curr_ts, 0, payload)
    ack_seq += 1
    print(f"  ACK packet: old=0, new=0, ack_num={ack_num} (acknowledging State #{ack_num})")
    socket_obj.sendto(ack_packet.pack(), sender_addr)

def init(port):
    global socket_obj
    socket_obj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socket_obj.bind(('', port))

def receive_loop():
    global sender_addr
    while True:
        data, addr = socket_obj.recvfrom(1500)
        sender_addr = addr
        packet = Packet.unpack(data)
        instruction = TransportInstruction.unmarshal(packet.payload.decode('utf-8'))
        on_receive(instruction)
