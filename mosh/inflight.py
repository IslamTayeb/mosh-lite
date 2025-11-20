from sortedcontainers import SortedList
from typing import Optional
# once we have RTT estimates
# we can form a congestion window

class InflightTracker:
    def __init__(self):
        self.inflight_state_numbers: SortedList[int] = SortedList()
        self.dependencies: dict[int, Optional[int]] = {}
        self.inflight_dependencies: SortedList[int] = SortedList()
        self.highest_ack: int = 0 # we start synced at state 0, which is State("") 
        # TODO: discard old states and dependencies
        # not important for correctness, just efficiency

    def acked(self, state_number: int) -> None:
        all_acked = []
        ind = self.inflight_state_numbers.bisect_left(state_number)
        while ind >= 0:
            all_acked.append(self.inflight_state_numbers[0])
            self.inflight_state_numbers.pop(index=0)
            ind -= 1
        
        assert len(all_acked) >= 1

        for acked_state_number in all_acked:
            match self.dependencies[acked_state_number]:
                case None:
                    pass
                case x:
                    self.inflight_dependencies.remove(self.dependencies[acked_state_number])

        self.highest_ack = state_number

    def sent(self, state_number: int, depends_on: Optional[int]):
        if depends_on is not None:
            self.inflight_dependencies.add(depends_on)

        self.dependencies[state_number] = depends_on
        self.inflight_state_numbers.add(state_number)

    def min_inflight_dependency(self) -> Optional[int]:
        return self.inflight_dependencies[0] if len(self.inflight_dependencies) > 0 else None 

if __name__ == "__main__":
    # test 1
    it: InflightTracker = InflightTracker()
    it.sent(0, None)
    it.sent(1, 0)
    assert it.min_inflight_dependency() == 0

    it.acked(0)
    assert it.min_inflight_dependency() == 0

    it.sent(2, 1)
    it.sent(3, 1)
    assert it.min_inflight_dependency() == 0
    it.acked(2)

    assert it.min_inflight_dependency() == 1, print(f'{it.min_inflight_dependency()}, expected 1')
    it.acked(3)
    assert it.min_inflight_dependency() is None

