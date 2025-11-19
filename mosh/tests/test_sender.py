from sender import init, on_send, receive_acks, inflight
from state import State

init('127.0.0.1', 53001)

on_send(State("abc"), inflight)
on_send(State("bcdef"), inflight)
on_send(State("abc"), inflight)

receive_acks()
