from transport import Transporter, TransportInstruction
from state import State
from typing import Optional

class Receiver:
    def __init__(self, port: int):
        self.transport = Transporter(None, None, self.on_receive)
        self.transport.socket.bind(('', port))
        self.current_state: Optional[State] = None
        self.last_acked_num = -1
        
    def on_receive(self, instruction: TransportInstruction):
        """Handle received instruction"""
        print(f"Received: old={instruction.old_num}, new={instruction.new_num}")
        
        # Handle the first state specially
        if self.current_state is None and instruction.old_num == 0:
            # First state - the diff is just the raw string content
            self.current_state = State(instruction.diff)
            print(f"Initialized with first state: {self.current_state.string}")
        elif self.current_state is not None and instruction.old_num == self.current_state.num:
            # This is the next expected state - apply the diff
            new_state = self.current_state.apply(instruction.diff)
            self.current_state = new_state
            print(f"Applied diff, new state: {self.current_state.string}")
        else:
            current_num = self.current_state.num if self.current_state else "None"
            print(f"Unexpected state transition: have state {current_num}, got old_num={instruction.old_num}")
        
        # Send acknowledgment
        self.send_ack(instruction.new_num)
    
    def send_ack(self, ack_num: int):
        """Send acknowledgment for received state"""
        # Send empty diff as ack
        self.transport.send(
            old_num=ack_num,
            new_num=ack_num,
            ack_num=ack_num,
            throwaway_num=ack_num - 1 if ack_num > 0 else 0,
            diff=""
        )
        print(f"Sent ACK for state {ack_num}")
        
    def run(self):
        """Main receiver loop"""
        print("Receiver running, waiting for packets...")
        while True:
            self.transport.recv()

if __name__ == "__main__":
    receiver = Receiver(53001)
    receiver.run()