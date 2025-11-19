import difflib
import json
import time
from typing import Optional

class State:
    curr_stateno = 1
    def __init__(self, s: str):
        self.string = s
        self.num = State.curr_stateno
        State.curr_stateno += 1
        self.time_sent: Optional[float] = None

    def mark_sent(self) -> None:
        self.time_sent = time.time()

    def generate_patch(self, other: 'State'):
        """Generate a self-contained patch from old -> new."""
        patch = []

        sm = difflib.SequenceMatcher(None, self.string, other.string)

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                patch.append(("equal", i1, i2, j1, j2))
            elif tag == "delete":
                patch.append(("delete", i1, i2, self.string[i1:i2]))
            elif tag == "insert":
                patch.append(("insert", j1, j2, other.string[j1:j2]))
            elif tag == "replace":
                patch.append(("replace", i1, i2, j1, j2, self.string[i1:i2], other.string[j1:j2]))

        return json.dumps(patch)

    def apply(self, patch: str) -> 'State':
        result = []

        for op in json.loads(patch):
            tag = op[0]

            if tag == "equal":
                _, i1, i2, _, _ = op
                result.extend(self.string[i1:i2])

            elif tag == "delete":
                _, i1, i2, _ = op
                # skip these lines

            elif tag == "insert":
                _, _, _, new_chunk = op
                result.extend(new_chunk)

            elif tag == "replace":
                *_, _, new_chunk = op[-2:]
                result.extend(new_chunk)

        return State("".join(result))

if __name__ == '__main__':
    s1: State = State('abc')
    s2: State = State('cde')
    assert s1.num == 1
    assert s2.num == 2
    delta = s1.generate_patch(s2)
    assert s1.apply(delta).string == s2.string
