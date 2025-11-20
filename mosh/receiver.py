from state import State
from transport import TransportInstruction, Transporter
from datagram import Packet
import socket
import time
from typing import Optional, Any, Callable
import asyncio
import logging

logging.basicConfig(
    level=logging.DEBUG,              # Set minimum log level
    format="%(asctime)s [%(levelname)s] %(message)s",
)

states: dict[int, State] = {0: State("")}
transport: Optional[Transporter] = None
highest_received = 0

def on_receive(instruction: TransportInstruction) -> None:
    global highest_received

    logging.debug(f"\nReceived: State #{instruction.old_num} -> #{instruction.new_num}")
    logging.debug(f"  Diff: {instruction.diff}")
    logging.debug(f"  ACK: {instruction.ack_num}, Throwaway: {instruction.throwaway_num}")

    if instruction.old_num in states:
        old_state = states[instruction.old_num]
        new_state = old_state.apply(instruction.diff)
        states[instruction.new_num] = new_state
        highest_received = max(highest_received, instruction.new_num)
        
        logging.info(states[highest_received].string)
        empty_diff = states[0].generate_patch(states[0])
        transport.send(0, 0, instruction.new_num, instruction.new_num, empty_diff)
        logging.debug(f"  Sent ACK for State #{instruction.new_num}")
    else:
        # TODO: Support for depending on instructions that are still in the pipeline
        logging.error(f"  ERROR: State #{instruction.old_num} not found")

def init(port):
    global transport
    transport = Transporter('', port, None, None)

def hook(f, ti: TransportInstruction) -> None:
    ts = time.time()
    state_num = ti.new_num

    f.write(f'{ts}, {state_num}\n')
     

async def update_listener(receive_hook: Callable[[Any, TransportInstruction], None] = None, extra_context=None):
    loop = asyncio.get_running_loop()
    while True:
        update = await transport.async_recv(loop)
        on_receive(update)
        if receive_hook is not None:
            receive_hook(extra_context, update) 
