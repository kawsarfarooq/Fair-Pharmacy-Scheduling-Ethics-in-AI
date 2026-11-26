"""Greedy construction followed by local search for comparison.

Uses the raw-count variance graph utility and has no optimality certificate.
Every output must pass the independent safety gate."""

from __future__ import annotations

from .metrics import global_utility
from .model import Instance

Slot = tuple[int, int]


def _feasible(inst: Instance, assign: dict[Slot, int],
              slot: Slot, w: int) -> bool:
    """Would assigning worker w to `slot` keep hard constraints satisfied?"""
    pid, d = slot
    if d in inst.workers[w].unavailable:
        return False
    for (pid2, d2), w2 in assign.items():
        if (pid2, d2) == slot or w2 != w:
            continue
        if d2 == d:                # double booking that night
            return False
        if abs(d2 - d) == 1:       # consecutive nights
            return False
    return True


def greedy(inst: Instance) -> dict[Slot, int]:
    assign: dict[Slot, int] = {}
    counts = {w.wid: 0 for w in inst.workers}
    for slot in sorted(inst.slots, key=lambda s: (s[1], s[0])):
        pid, d = slot
        cands = [w for w in inst.domain(pid, d)
                 if _feasible(inst, assign, slot, w)]
        if not cands:
            cands = inst.domain(pid, d)
        if not cands:
            raise ValueError(f"No available worker for {slot}")
        w = min(cands, key=lambda w: (counts[w],
                                      d in inst.workers[w].disliked))
        assign[slot] = w
        counts[w] += 1
    return assign


def local_search(inst: Instance, assign: dict[Slot, int],
                 max_passes: int = 30) -> dict[Slot, int]:
    assign = dict(assign)
    best = global_utility(inst, assign)
    for _ in range(max_passes):
        improved = False
        for slot in list(assign.keys()):
            pid, d = slot
            current = assign[slot]
            for w in inst.domain(pid, d):
                if w == current:
                    continue
                assign[slot] = w
                u = global_utility(inst, assign)
                if u > best:
                    best, improved, current = u, True, w
                else:
                    assign[slot] = current
        if not improved:
            break
    return assign


def solve_centralised(inst: Instance) -> dict[Slot, int]:
    return local_search(inst, greedy(inst))
