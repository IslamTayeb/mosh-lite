import json
from dataclasses import dataclass
import difflib

@dataclass
class TransportInstruction:
    old_num: int
    new_num: int 
    ack_num: int
    throwaway_num: int
    diff: str

    def marshall(self):
        return json.dumps(self.__dict__)

    @staticmethod
    def unmarshal(json_str: str) -> 'TransportInstruction':
        return TransportInstruction(**json.loads(json_str)) 


if __name__ == "__main__":
    str1 = 'abc'
    str2 = 'bcdef'
    diff = list(difflib.unified_diff(str1.splitlines(keepends=True), str2.splitlines(keepends=True)))
    t: TransportInstruction = TransportInstruction(1, 2, 1, 1, json.dumps(diff))
    t2 = TransportInstruction.unmarshal(t.marshall())
    assert t.ack_num == t2.ack_num
    assert t.diff == t2.diff
    assert t.old_num == t2.old_num
    assert t.new_num == t2.new_num
    assert t.throwaway_num == t2.throwaway_num

