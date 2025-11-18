import json
from dataclasses import dataclass
import difflib
import time
from typing import Optional
from datagram import Packet
import socket

class Transporter:
    def __init__(self, host: Optional[str], port: Optional[int], on_receive):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.seq = 0 # this is the number of packets we have sent
        self.last_timestamp: Optional[float] = None # this is the last timestamp we received from the other party
        self.on_receive = on_receive
        self.other_addr: Optional[tuple] = (host, port) if (host is not None and port is not None) else None

    def send(self, old_num: int, new_num: int, ack_num: int, throwaway_num: int, diff: str) -> None:
        assert self.other_addr is not None, "Other address must be initialized to send"
        t: TransportInstruction = TransportInstruction(old_num, new_num, ack_num, throwaway_num, diff)
        payload: bytes = t.marshall().encode('utf-8')
        curr_timestamp = int(1000 * time.time()) & 0xFFFF
        old_timestamp = self.last_timestamp or 0
        direction = True
        packet = Packet(direction, self.seq, curr_timestamp, old_timestamp, payload)
        self.seq += 1
        self.socket.sendto(packet.pack(), self.other_addr)

    def recv(self):
        raw_response, addr = self.socket.recvfrom(1500)
        self.other_addr = addr
        packet = Packet.unpack(raw_response)
        self.last_timestamp = packet.ts
        self.on_receive(TransportInstruction.unmarshal(packet.payload.decode('utf-8')))

@dataclass
class TransportInstruction:
    old_num: int
    new_num: int 
    ack_num: int
    throwaway_num: int
    diff: str

    def marshall(self):
        return json.dumps(self.__dict__)

    @staticmethod
    def unmarshal(json_str: str) -> 'TransportInstruction':
        return TransportInstruction(**json.loads(json_str)) 


if __name__ == "__main__":
    str1 = 'abc'
    str2 = 'bcdef'
    diff = list(difflib.unified_diff(str1.splitlines(keepends=True), str2.splitlines(keepends=True)))
    t: TransportInstruction = TransportInstruction(1, 2, 1, 1, json.dumps(diff))
    t2 = TransportInstruction.unmarshal(t.marshall())
    assert t.ack_num == t2.ack_num
    assert t.diff == t2.diff
    assert t.old_num == t2.old_num
    assert t.new_num == t2.new_num
    assert t.throwaway_num == t2.throwaway_num

