import asyncio
import sys
import sender
from transport import TransportInstruction, Transporter
from dataclasses import dataclass

@dataclass
class LocalEvent:
    message: str

@dataclass
class RemoteEvent:
    instruction: TransportInstruction

async def keyboard_listener(queue):
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        # TODO: Switch terminal to raw mode so we're not buffered 
        line = await reader.readline()
        if not line:
            continue

        await queue.put(LocalEvent(message=line.decode().rstrip())) 


async def network_listener(t: Transporter, queue):
    loop = asyncio.get_running_loop()
    while True:
        instruction = await t.async_recv(loop)
        await queue.put(RemoteEvent(instruction))

async def event_processor(queue):
    while True:
        ev = await queue.get()

        if isinstance(ev, LocalEvent):
            print(f'Keyboard event: {ev.message}')
            sender.send_message(ev.message)

        elif isinstance(ev, RemoteEvent):
            print(f'Network event: {ev.instruction}')

            sender.on_receive(ev.instruction)

async def main():
    queue = asyncio.Queue()
    sender.init('127.0.0.1', 53001) 
    await asyncio.gather(
            keyboard_listener(queue),
            network_listener(sender.transport, queue),
            event_processor(queue)
        )

if __name__ == "__main__":
    asyncio.run(main())

