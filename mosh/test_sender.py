from transport import Transporter
from state import State

t = Transporter('127.0.0.1', 53001, lambda x: None)

str1 = State('abc')
str2 = State('bcdef')
str3 = State('abc')

delta1 = State("").generate_patch(str1)
t.send(0, 1, 0, 0, delta1)
delta2 = str1.generate_patch(str2)
t.send(1, 2, 0, 0, delta2)
delta3 = str2.generate_patch(str3)
t.send(2, 3, 0, 0, delta3)
