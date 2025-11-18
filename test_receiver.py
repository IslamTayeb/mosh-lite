import socket
from datagram import Packet
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('', 53001))
while True:
    j = s.recv(1500)
    p = Packet.unpack(j)
    print(p)
