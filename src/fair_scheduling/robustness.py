"""Demand and availability disruptions, reserves and strategic declarations."""
from copy import deepcopy
from dataclasses import replace
from time import perf_counter

from .cpsat_solver import solve
from .fairness import audit, efficiency_cost
from .safety import violations


def disrupt_demand(inst, *, add=(), remove=()):
    """Atomically alter required pharmacy-night slots; one worker per slot."""
    current = set(inst.slots)
    added, removed = set(add), set(remove)
    if added & removed or not removed <= current or added & current:
        raise ValueError("Demand adds/removals must be disjoint and valid")
    slots = sorted((current - removed) | added)
    # Reuse instance validation before committing the mutation.
    replace(inst, required_slots=slots)
    inst.required_slots = slots


def add_reserves(inst, count=2):
    if count < 0 or (count and not inst.workers):
        raise ValueError("Reserves require a nonempty workforce and nonnegative count")
    for i in range(count):
        template = inst.workers[i % len(inst.workers)]
        reserve = deepcopy(template)
        reserve.wid = len(inst.workers)
        reserve.name = f"Reserve-{i}"
        reserve.reserve = True
        inst.workers.append(reserve)
    inst.__post_init__()


def cap_dislikes(inst, maximum):
    """Deterministic declaration cap, without altering hard unavailability."""
    if maximum < 0:
        raise ValueError("maximum must be nonnegative")
    for w in inst.workers:
        w.disliked = set(sorted(w.disliked)[:maximum])


def repair_comparison(inst, previous, *, time_limit=10, prev_solver=None, seed=0):
    """Compare exact full/minimal repair and Max-Sum warm/cold restarts."""
    from .dynamics import repair
    rows = []
    before = audit(inst, previous)
    exact = solve(inst, time_limit=time_limit, previous=previous, seed=seed, use_fte=False)
    for method in ("full", "minimal", "maxsum_cold", "maxsum_warm"):
        start = perf_counter()
        status = "HEURISTIC"
        optimal = False
        try:
            if method == "full":
                result = exact
            elif method == "minimal":
                result = solve(inst, time_limit=time_limit, previous=previous, minimal_change=True, seed=seed, use_fte=False)
            else:
                if method == "maxsum_warm" and prev_solver is None:
                    continue
                assignment, stats, _ = repair(inst, previous, iterations=25, seed=seed,
                                               prev_solver=prev_solver if method == "maxsum_warm" else None)
            if method in {"full", "minimal"}:
                assignment = result.assignment
                status, optimal = result.status, result.proven_optimal
            errors = violations(inst, assignment)
            legal = not errors and status not in {"INFEASIBLE", "UNKNOWN", "MODEL_INVALID"}
            shared = set(previous) & set(inst.slots)
            changed = sum(assignment.get(s) != previous[s] for s in shared)
            added, removed = len(set(inst.slots) - previous.keys()), len(previous.keys() - set(inst.slots))
            after = audit(inst, assignment) if legal else {}
            absorbed = {w.wid: sum(assignment.get(s) == w.wid and previous.get(s) != w.wid for s in inst.slots) for w in inst.workers}
            rows.append({"method": method, "status": status, "proven_optimal": optimal,
                         "legal": legal, "stability": 1 - changed / len(shared) if shared else 1.0,
                         "changed_slots": changed, "added_slots": added, "removed_slots": removed,
                         "seconds": result.wall_time if method in {"full", "minimal"} else perf_counter() - start,
                         "efficiency_loss_vs_full": efficiency_cost(inst, assignment) - efficiency_cost(inst, exact.assignment)
                             if legal and exact.status in {"OPTIMAL", "FEASIBLE"} else None,
                         "full_reference_optimal": exact.proven_optimal,
                         "objective_loss_vs_full": _cost(inst, assignment) - _cost(inst, exact.assignment)
                             if legal and exact.status in {"OPTIMAL", "FEASIBLE"} else None,
                         "jain_before": before["fte_jain"], "jain_after": after.get("fte_jain"),
                         "change_burden": absorbed,
                         "factors_warm_started": stats["factors_warm_started"] if method.startswith("maxsum") else 0})
        except ValueError as exc:
            rows.append({"method": method, "status": "REJECTED", "legal": False,
                         "error": str(exc), "seconds": perf_counter() - start})
    return rows


def _cost(inst, assignment):
    from .explain import objective_breakdown
    return objective_breakdown(inst, assignment, use_fte=False)["total_cost"]
