import json
from dataclasses import dataclass
import difflib
import time
from typing import Optional, Callable
from datagram import Packet
import socket
import logging

# copied from the lab
MinRTO = 0.05
G = 0.1
K = 4
alpha = 0.125
beta = 0.25

class Transporter:
    def __init__(self, binding_host: str, binding_port: int, other_host: Optional[str], other_port: Optional[int], is_receiver=False):
        self.socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind((binding_host, binding_port))
        self.socket.setblocking(False)
        self.seq = 0
        self.last_timestamp: Optional[float] = None
        self.other_addr: Optional[tuple] = (other_host, other_port) if (other_host is not None and other_port is not None) else None
        self.current_signal_strength = -50
        self.remote_signal_strength = -50
        self.srtt: Optional[float] = None
        self.rttvar: Optional[float] = None
        self.rto: Optional[float] = None
        self.is_receiver = is_receiver

    def fileno(self):
        return self.socket.fileno()
    
    @property
    def timeout_threshold(self) -> Optional[float]:
        return self.rto

    async def async_recv(self, loop) -> 'TransportInstruction':
        raw, addr = await loop.sock_recvfrom(self.socket, 1500)
        self.other_addr = addr
        packet = Packet.unpack(raw)
        self.last_timestamp = packet.ts
        self.remote_signal_strength = packet.signal_strength_dbm

        # RTO estimation copied from our TCP lab (lab 1)
        
        if (not self.is_receiver):
            curr_ms_time = self._time_to_int()
            R_ms = (curr_ms_time - packet.ts_reply) & 0xFFFF
            R = self._int_to_seconds(R_ms) # Convert back to seconds
            logging.debug(f'R: {R}')

            if self.rttvar is None:
                self.srtt = R
                self.rttvar = R / 2
                self.rto = self.srtt + max(G, K * self.rttvar)
            else:
                self.rttvar = (1 - beta) * self.rttvar + beta * abs(self.srtt - R)
                self.srtt = (1 - alpha) * self.srtt + alpha * R
                self.rto = self.srtt + max(G, K * self.rttvar)
            
            logging.debug(f'RTO estimate: {self.rto}')

        return TransportInstruction.unmarshal(packet.payload.decode('utf-8'))

    def set_signal_strength(self, dbm: int):
        self.current_signal_strength = dbm

    def _time_to_int(self) -> int:
        return int(1000 * time.time()) & 0xFFFF

    def _int_to_seconds(self, mils: int) -> float:
        return mils / 1000

    def send(self, old_num: int, new_num: int, ack_num: int, throwaway_num: int, diff: str) -> None:
        assert self.other_addr is not None, "Other address must be initialized to send"
        t: TransportInstruction = TransportInstruction(old_num, new_num, ack_num, throwaway_num, diff)
        payload: bytes = t.marshall().encode('utf-8')
        curr_timestamp = self._time_to_int()
        old_timestamp = self.last_timestamp or self._time_to_int()
        direction = True
        packet = Packet(direction, self.seq, curr_timestamp, old_timestamp, self.current_signal_strength, payload)
        self.seq += 1
        self.socket.sendto(packet.pack(), self.other_addr)


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
