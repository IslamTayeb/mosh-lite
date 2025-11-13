from sortedcontainers import SortedList
from transport import TransportInstruction
# once we have RTT estimates
# we can form a congestion window

class InflightTracker:
    def __init__(self):
        self.inflight_state_numbers: SortedList[int] = SortedList()
        self.dependencies: dict[int, int] = {}
        self.inflight_dependencies: SortedList[int] = SortedList()
        self.highest_ack = -1
        # TODO: discard old states and dependencies

    def acked(self, state_number: int) -> None:
        all_acked = []
        ind = self.inflight_state_numbers.bisect_left(state_number)
        while ind >= 0:
            all_acked.append(self.inflight_state_numbers[0])
            ind -= 1
        
        assert len(all_acked) >= 1

        for acked_state_number in all_acked:
            self.inflight_dependencies.remove(self.dependencies[acked_state_number])

        self.highest_ack = state_number

    def sent(self, state_number: int, depends_on: int):
        self.dependencies[state_number] = depends_on
        self.inflight_state_numbers.add(state_number)
        self.inflight_dependencies.add(depends_on)

    def min_inflight_dependency(self):
        return self.inflight_dependencies[0] if len(self.inflight_dependencies) > 0 else 2 ** 31 - 1

def on_ack(state_number: int, inf: InflightTracker) -> None:
    # this ack acknowledges all inflights that were <= state_number
    inf.acked(state_number)
    

def on_send(new_state: 'State', inf: InflightTracker) -> None:
    old_num = inf.highest_ack 
    new_num = new_state.index
    ack_num = highest_ack
    throwaway_num = min(inf.min_inflight_dependency(), highest_ack) - 1
    t: TransportInstruction = TransportInstruction(old_num, new_num, ack_num, throwaway_num, new_state.diff(states[highest_ack]))
    inf.sent(new_num, old_num)
    carrier.send(t)


def main():
    InflightTracker inf = InflightTracker()
    # need to register handlers for keystrokes and responses

if __name__ == "__main__":
    main()
