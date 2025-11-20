from inflight import InflightTracker
from state import State
from transport import Transporter, TransportInstruction
import socket
import random
import time
import logging

logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        filename='sender.log'
        )

states = {} # for now we store all states
states[0] = State("")
inflight = InflightTracker()
transport = None
next_state_num = 1

LAMBDA = 0.3 # TODO: tune this later
             # defines probability that we pull last known receiver state instead of the assumed receiver state

def send_message(message: str) -> None:
    global states
    new_state = State(message)
    on_send(new_state, inflight)

def on_receive(instruction: TransportInstruction):
    logging.debug("\nReceived packet from receiver:")
    logging.debug(f"  Their ACK: {instruction.ack_num}")
    inflight.acked(instruction.ack_num)

def on_send(new_state: State, inf: InflightTracker):
    # We differ from Mosh here
    # Mosh always refers by the most recent state that has been sent
    # We soften this, taking the most recent state with some probability and taking the known receiver state with some other probability
    # The intention for this is to help cope with high packet loss
    # We offset the packet loss by being less aggressive in our reference state, meaning the chain of dependencies is shorter

    global states, transport, next_state_num
    assumed_receiver_state_num: int = next_state_num - 1
    known_receiver_state_num: int = inf.highest_ack

    if states[assumed_receiver_state_num].time_sent is not None and transport.timeout_threshold is not None and time.time() - states[assumed_receiver_state_num].time_sent < transport.timeout_threshold:
        old_num = random.choices([known_receiver_state_num, assumed_receiver_state_num], weights=[LAMBDA, 1 - LAMBDA], k = 1)[0]
    else:
        old_num = known_receiver_state_num

    old_num = inf.highest_ack
    diff = states[old_num].generate_patch(new_state)
    new_num = next_state_num
    next_state_num += 1
    states[new_num] = new_state
    logging.debug(f"\nSending: State #{old_num} -> #{new_num} ('{states[old_num].string}' -> '{new_state.string}')")
    logging.debug(f"  Diff: {diff}")

    transport.send(old_num, new_num, inf.highest_ack, min(0, inf.highest_ack - 1, (inf.min_inflight_dependency() if inf.min_inflight_dependency() is not None else float('inf')) - 1), diff)
    inf.sent(new_num, old_num)
    new_state.mark_sent()

def init(host, port):
    global transport
    transport = Transporter('', 0, host, port)
    logging.debug(f'Initialized transport {type(transport)}')
