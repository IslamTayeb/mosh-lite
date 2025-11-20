#!/usr/bin/env python3
"""
UDP Server - Receives packets and sends responses back to client
"""

import socket
import json
import time
import sys
import os
import signal
from datetime import datetime
sys.path.insert(0, '/app/mosh')
import asyncio
from receiver import update_listener, init
from transport import TransportInstruction

def hook(f, ti: TransportInstruction) -> None:
    ts = time.time()
    state_num = ti.new_num
    f.write(f'{ts}, {state_num}\n')
    f.flush()
         

async def main():
    UDP_PORT = int(os.getenv("UDP_PORT", "5000"))
    init(UDP_PORT)
    with open('/logs/output.log', 'w') as fout:
        await update_listener(receive_hook=hook, extra_context=fout)
    

if __name__ == "__main__":
    asyncio.run(main())
