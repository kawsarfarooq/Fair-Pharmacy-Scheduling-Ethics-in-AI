"""Global schedule evaluation and fairness metrics.

Max-Sum messages on a loopy graph are approximate, so complete assignments
are evaluated independently against the model definition. The evaluator is
used for anytime solution selection, comparison with the centralised baseline,
and experiment reporting.

Reported metrics include hard-constraint violations, preference cost,
workload variance, Jain's fairness index, and the Gini coefficient of average
worker workload grouped by home district.
"""

from __future__ import annotations

import numpy as np

from .model import Instance

Slot = tuple[int, int]


def hard_violations(inst: Instance, assign: dict[Slot, int]) -> int:
    """Counted PAIRWISE, mirroring the factor graph exactly:
      * each pair of same-night slots given the same worker  -> 1 violation
      * each pair of consecutive-night slots, same worker     -> 1 violation
      * each assignment to an unavailable worker              -> 1 violation
    (Pairwise counting matters: with 3 same-night slots on one worker the
    graph pays 3 big-M factors, so the evaluator must count 3 as well —
    tests/test_all.py::test_factor_graph_consistency enforces this.)"""
    v = 0
    items = list(assign.items())
    for (pid, d), w in items:
        if d in inst.workers[w].unavailable:
            v += 1
    for i in range(len(items)):
        (pa, da), wa = items[i]
        for j in range(i + 1, len(items)):
            (pb, db), wb = items[j]
            if wa == wb and abs(da - db) <= 1:
                v += 1
    return v


def shift_counts(inst: Instance, assign: dict[Slot, int]) -> np.ndarray:
    n = np.zeros(len(inst.workers))
    for w in assign.values():
        n[w] += 1
    return n


def preference_cost(inst: Instance, assign: dict[Slot, int]) -> float:
    return sum(inst.pref_penalty
               for (pid, d), w in assign.items()
               if d in inst.workers[w].disliked)


def global_utility(inst: Instance, assign: dict[Slot, int]) -> float:
    """The TRUE objective: hard penalties + preference cost + λ·(same-worker
    pairs at day distance >= 2). Same-worker pairs at distance <= 1 are hard
    violations, so on any FEASIBLE schedule this equals the full pairwise
    decomposition of Σ n_w² (see factor_graph.py) — while matching the graph
    utility EXACTLY (constant offset 0) on infeasible ones too."""
    items = list(assign.items())
    fair_pairs = 0
    for i in range(len(items)):
        (pa, da), wa = items[i]
        for j in range(i + 1, len(items)):
            (pb, db), wb = items[j]
            if wa == wb and abs(da - db) >= 2:
                fair_pairs += 1
    return (inst.HARD * hard_violations(inst, assign)
            - preference_cost(inst, assign)
            - inst.fairness_lambda * fair_pairs)


def report(inst: Instance, assign: dict[Slot, int]) -> dict:
    n = shift_counts(inst, assign)
    active = n[n > 0]
    jain = (n.sum() ** 2) / (len(n) * (n ** 2).sum()) if n.sum() > 0 else 0.0

    # District equity of WORKER burden: average shifts carried per worker,
    # grouped by the workers' home district, then Gini over those averages.
    # Measure burden by worker home district. Pharmacy-district totals are
    # fixed by the required coverage and therefore do not vary by assignment.
    dist_load: dict[int, float] = {}
    dist_workers: dict[int, int] = {}
    for w in inst.workers:
        dist_workers[w.district] = dist_workers.get(w.district, 0) + 1
    for (pid, d), w in assign.items():
        dist = inst.workers[w].district
        dist_load[dist] = dist_load.get(dist, 0) + 1
    avg = [dist_load.get(k, 0.0) / dist_workers[k] for k in dist_workers]
    loads = np.array(sorted(avg), dtype=float)
    if loads.sum() > 0:
        i = np.arange(1, len(loads) + 1)
        gini = float((2 * i - len(loads) - 1) @ loads / (len(loads) * loads.sum()))
    else:
        gini = 0.0

    return {
        "hard_violations": hard_violations(inst, assign),
        "preference_cost": preference_cost(inst, assign),
        "workload_var": float(n.var()),
        "workload_max": int(n.max()),
        "workload_min_active": int(active.min()) if len(active) else 0,
        "jain_index": float(jain),
        "district_gini": gini,
        "global_utility": global_utility(inst, assign),
    }
