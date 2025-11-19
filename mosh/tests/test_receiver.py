from receiver import init, receive_loop

init(53001)
print("Receiver listening on port 53001...")
receive_loop()
