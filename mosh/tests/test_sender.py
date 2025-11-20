import asyncio
import sys
import termios
import tty
import sender
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

async def keyboard_listener(queue):
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)
    
    fd = sys.stdin.fileno()
    original_settings = termios.tcgetattr(fd)
    tty.setraw(fd)
    input_buffer = []
    try:
        while True:
            # TODO: Switch terminal to raw mode so we're not buffered 
            ch = await reader.read(1)
            if not ch:
                continue
            c = ch.decode(errors='ignore')
            if c == '\x03':
                await queue.put(TerminationEvent())
                break
            input_buffer.append(ch.decode(errors='ignore'))
            sys.stdout.write(c)
            sys.stdout.flush()
            await queue.put(LocalEvent(message="".join(input_buffer)))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original_settings)

async def network_listener(t: Transporter, queue):
    loop = asyncio.get_running_loop()
    while True:
        instruction = await t.async_recv(loop)
        await queue.put(RemoteEvent(instruction))

async def event_processor(queue):
    while True:
        ev = await queue.get()

        if isinstance(ev, LocalEvent):
            logging.debug(f'Keyboard event: {ev.message}')
            sender.send_message(ev.message)

        elif isinstance(ev, RemoteEvent):
            logging.debug(f'Network event: {ev.instruction}')

            sender.on_receive(ev.instruction)
        else:
            logging.error("QUITTING")
            for task in asyncio.all_tasks():
                task.cancel()
            return

async def main():
    queue = asyncio.Queue()
    sender.init('127.0.0.1', 53001) 
    await asyncio.gather(
            keyboard_listener(queue),
            network_listener(sender.transport, queue),
            event_processor(queue)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

