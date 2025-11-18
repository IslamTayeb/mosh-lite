from inflight import InflightTracker
from transport import Transporter, TransportInstruction
from state import State
from typing import Optional
import time

class Sender:
    def __init__(self, host: str, port: int):
        self.inflight = InflightTracker()
        self.transport = Transporter(host, port, self.on_ack)
        self.current_state: Optional[State] = None
        self.pending_states: list[State] = []
        
    def on_ack(self, instruction: TransportInstruction):
        """Handle acknowledgment from receiver"""
        state_number = instruction.ack_num
        print(f"Received ACK for state {state_number}")
        self.inflight.acked(state_number)
        
    def send_state(self, new_state: State) -> None:
        """Send a new state to the receiver"""
        if self.current_state is None:
            # First state - send raw string as diff (receiver handles this specially)
            old_num = 0
            diff = new_state.string
            depends_on = None
        else:
            old_num = self.current_state.num
            diff = self.current_state.generate_patch(new_state)
            depends_on = old_num
        
        new_num = new_state.num
        
        # Determine what can be thrown away
        min_inflight = self.inflight.min_inflight_dependency()
        if min_inflight is not None:
            throwaway_num = min_inflight - 1
        else:
            throwaway_num = self.inflight.highest_ack if self.inflight.highest_ack >= 0 else 0
        
        # Send the packet
        self.transport.send(
            old_num=old_num,
            new_num=new_num,
            ack_num=self.inflight.highest_ack if self.inflight.highest_ack >= 0 else 0,
            throwaway_num=throwaway_num,
            diff=diff
        )
        
        print(f"Sent state {new_num} (depends on {old_num})")
        
        # Update tracking
        self.inflight.sent(new_num, depends_on)
        self.current_state = new_state
        
    def listen_for_acks(self):
        """Listen for acknowledgments (non-blocking check)"""
        try:
            self.transport.socket.settimeout(0.1)  # 100ms timeout
            self.transport.recv()
        except:
            pass  # Timeout or no data

if __name__ == "__main__":
    sender = Sender('127.0.0.1', 53001)
    
    # Example: send a sequence of states
    state1 = State('hello')
    sender.send_state(state1)
    time.sleep(0.5)
    sender.listen_for_acks()
    
    state2 = State('hello world')
    sender.send_state(state2)
    time.sleep(0.5)
    sender.listen_for_acks()
    
    state3 = State('hello world!')
    sender.send_state(state3)
    time.sleep(0.5)
    sender.listen_for_acks()