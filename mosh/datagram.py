import struct
from dataclasses import dataclass

DATAGRAM_FORMAT_STRING = '!QHHh'

@dataclass
class Packet:
    direction: bool
    seq: int
    ts: int
    ts_reply: int
    signal_strength_dbm: int
    payload: bytes

    def pack(self) -> bytes:
        direction = self.direction
        seq = self.seq
        ts = self.ts
        ts_reply = self.ts_reply
        signal_strength_dbm = self.signal_strength_dbm
        payload = self.payload

        assert 0 <= seq < (1 << 63)

        dir_bit = int(direction)
        nonce = (dir_bit << 63) | seq

        ts = ts & 0xFFFF
        assert 0 <= ts_reply <= 0xFFFF
        assert -127 <= signal_strength_dbm <= 0

        header = struct.pack(DATAGRAM_FORMAT_STRING, nonce, ts, ts_reply, signal_strength_dbm)

        # TODO: What do we do if this is larger than the MTU of the network?
        return header + payload

    @staticmethod
    def unpack(value: bytes) -> 'Packet':
        header_length = struct.calcsize(DATAGRAM_FORMAT_STRING)

        nonce, ts, ts_reply, signal_strength_dbm = struct.unpack_from(DATAGRAM_FORMAT_STRING, value, offset=0)
        payload = value[header_length:]

        return Packet(
                    bool(nonce & (1 << 63)),
                    nonce & ((1 << 63) - 1),
                    ts,
                    ts_reply,
                    signal_strength_dbm,
                    payload
              )

if __name__ == "__main__":
    original_packet = Packet(True, 7, 10, 5, -50, 'abc'.encode('utf-8'))
    back = Packet.unpack(original_packet.pack())
    assert original_packet.direction == back.direction
    assert original_packet.seq == back.seq
    assert original_packet.ts == back.ts
    assert original_packet.ts_reply == back.ts_reply
    assert original_packet.signal_strength_dbm == back.signal_strength_dbm
    assert original_packet.payload == back.payload
