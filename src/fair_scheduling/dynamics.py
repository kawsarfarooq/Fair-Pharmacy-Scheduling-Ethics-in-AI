"""Dynamic rescheduling after worker unavailability.

``disrupt`` adds a worker's unavailable night to the problem instance.
``repair`` then rebuilds the factor graph, adds a unary utility for retaining
each previous assignment, and runs Max-Sum for a limited number of iterations.

When a previous solver is supplied, messages are copied for binary factors
whose endpoint domains are unchanged. Factors affected by the disruption
start with zero messages. The repair statistics report feasibility, schedule
stability, message count, and the number of warm-started factors.
"""

from __future__ import annotations

from .factor_graph import build_factor_graph
from .maxsum import MaxSum
from .metrics import global_utility, hard_violations
from .model import Instance

Slot = tuple[int, int]


def disrupt(inst: Instance, wid: int, day: int) -> None:
    """Worker `wid` becomes unavailable on `day` (in-place model update)."""
    inst.workers[wid].unavailable.add(day)


def repair(inst: Instance, previous: dict[Slot, int],
           iterations: int = 25, seed: int = 0,
           prev_solver: "MaxSum | None" = None
           ) -> tuple[dict[Slot, int], dict, MaxSum]:
    """Repair a schedule while rewarding assignments that remain unchanged."""
    g = build_factor_graph(inst)

    # stability bonus: +0.5 for keeping the previous worker (if still legal)
    import numpy as np
    from .factor_graph import UnaryFactor
    for slot, w_prev in previous.items():
        if slot not in g.variables:
            continue
        v = g.variables[slot]
        if w_prev in v.index:
            t = np.zeros(len(v.domain))
            t[v.index[w_prev]] = 0.5
            g.unary.append(UnaryFactor(var=slot, table=t, owner="pharmacy"))

    ms = MaxSum(g, seed=seed)

    # Carry over converged messages from the previous
    # solver for every factor whose endpoint domains are unchanged. Factors
    # are keyed by (var_a, var_b, owner), which is unique by construction.
    carried = 0
    if prev_solver is not None:
        old_key = {(f.var_a, f.var_b, f.owner): fid
                   for fid, f in enumerate(prev_solver.g.binary)}
        for fid, f in enumerate(g.binary):
            ofid = old_key.get((f.var_a, f.var_b, f.owner))
            if ofid is None:
                continue
            of = prev_solver.g.binary[ofid]
            if (prev_solver.g.variables[of.var_a].domain == g.variables[f.var_a].domain
                    and prev_solver.g.variables[of.var_b].domain == g.variables[f.var_b].domain
                    and np.array_equal(of.table, f.table)):
                for end in (0, 1):
                    ms.q[(fid, end)] = prev_solver.q[(ofid, end)].copy()
                    ms.r[(fid, end)] = prev_solver.r[(ofid, end)].copy()
                carried += 1

    # The anytime evaluator must include the same stability utility that was
    # added to the graph, otherwise it may select a less stable assignment.
    def repair_utility(assign: dict[Slot, int]) -> float:
        kept = sum(assign.get(slot) == worker
                   for slot, worker in previous.items())
        return global_utility(inst, assign) + 0.5 * kept

    new_assign, _, _ = ms.run(
        iterations=iterations,
        evaluator=repair_utility,
        reset=False,
    )

    changed = sum(1 for s in previous
                  if new_assign.get(s) != previous[s])
    return new_assign, {
        "hard_violations_after": hard_violations(inst, new_assign),
        "stability": 1 - changed / len(previous) if previous else 1.0,
        "changed_slots": changed,
        "messages": ms.messages_sent,
        "factors_warm_started": carried,
    }, ms
