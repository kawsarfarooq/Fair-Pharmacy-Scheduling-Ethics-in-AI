"""Independent validation before a candidate schedule can be published."""
from .model import Instance


def violations(inst: Instance, assignment: dict) -> list[str]:
    errors = []
    expected = set(inst.slots)
    for slot in sorted(expected - assignment.keys()):
        errors.append(f"missing coverage: {slot}")
    for slot in sorted(assignment.keys() - expected):
        errors.append(f"unexpected slot: {slot}")
    valid = []
    for slot, wid in assignment.items():
        if slot not in expected:
            continue
        if not isinstance(wid, int) or not 0 <= wid < len(inst.workers):
            errors.append(f"unknown worker: {wid}")
            continue
        if wid not in inst.domain(*slot):
            errors.append(f"ineligible, unavailable or inactive reserve: {slot}, worker {wid}")
        valid.append((slot, wid))
    for i, (slot, wid) in enumerate(valid):
        for other, other_wid in valid[i + 1:]:
            if wid == other_wid and abs(slot[1] - other[1]) <= 1:
                errors.append(f"booking/rest conflict: worker {wid}, {slot}, {other}")
    return errors


def publish_schedule(inst: Instance, assignment: dict) -> dict:
    errors = violations(inst, assignment)
    if errors:
        raise ValueError("Human review required; schedule withheld: " + "; ".join(errors))
    return dict(assignment)
