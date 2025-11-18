from inflight import InflightTracker

def on_ack(state_number: int, inf: InflightTracker) -> None:
    # this ack acknowledges all inflights that were <= state_number
    inf.acked(state_number)
    

def on_send(new_state: 'State', inf: InflightTracker) -> None:
    old_num = inf.highest_ack 
    new_num = new_state.index
    ack_num = highest_ack
    throwaway_num = min(inf.min_inflight_dependency(), highest_ack) - 1
    # TODO: sending logic
    inf.sent(new_num, old_num)


def main():
    InflightTracker inf = InflightTracker()
    # need to register handlers for keystrokes and responses

if __name__ == "__main__":
    main()
