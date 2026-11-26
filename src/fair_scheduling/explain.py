"""Factor-based explanations for individual assignments.

For a selected shift slot, the module compares the assigned worker with each
eligible alternative while holding the rest of the completed schedule fixed.
The comparison reports:

* hard-constraint conflicts, including availability, double booking, and rest;
* disliked-night preference cost;
* workload and its associated pairwise fairness cost.

These values provide a transparent post-hoc local justification. They describe
the factors relevant to the assignment rather than reconstructing the complete
causal history of Max-Sum messages.
"""

from __future__ import annotations

from .metrics import shift_counts
from .model import Instance

Slot = tuple[int, int]


def candidate_breakdown(inst: Instance, assign: dict[Slot, int],
                        slot: Slot) -> list[dict]:
    """Fixed-rota comparison for the raw-count variance objective.

    Use global counterfactuals/breakdowns to explain FTE or other objectives.
    """
    from .fairness import travel_km
    pid, d = slot
    counts = shift_counts(inst, assign)
    chosen = assign[slot]
    rows = []
    for w in inst.eligible[pid]:
        # Check legality against the rest of the schedule, excluding this slot.
        conflicts = []
        if d in inst.workers[w].unavailable:
            conflicts.append("unavailable that night")
        for (pid2, d2), w2 in assign.items():
            if (pid2, d2) == slot or w2 != w:
                continue
            if d2 == d:
                conflicts.append(f"already covering PH-{pid2:02d} that night")
            elif abs(d2 - d) == 1:
                conflicts.append(f"works the {'previous' if d2 < d else 'next'} night at PH-{pid2:02d}")
        load = int(counts[w]) - (1 if w == chosen else 0)  # load EXCLUDING this slot
        travel = inst.travel_weight * round(travel_km(inst, slot, w) * 1000) / 1000
        rows.append({
            "worker": w,
            "name": inst.workers[w].name,
            "chosen": w == chosen,
            "legal": not conflicts,
            "conflicts": conflicts,
            "dislikes_night": d in inst.workers[w].disliked,
            "pref_penalty": inst.pref_penalty if d in inst.workers[w].disliked else 0.0,
            "current_load": load,
            "fairness_penalty": 2 * inst.fairness_lambda * load,
            "travel_penalty": travel,
            "total_soft_cost": (inst.pref_penalty if d in inst.workers[w].disliked else 0.0)
                               + 2 * inst.fairness_lambda * load + travel,
        })
    rows.sort(key=lambda r: (not r["legal"], r["total_soft_cost"]))
    return rows


def explain(inst: Instance, assign: dict[Slot, int], slot: Slot) -> str:
    """Human-readable justification for the assignment of `slot`."""
    pid, d = slot
    rows = candidate_breakdown(inst, assign, slot)
    chosen = next(r for r in rows if r["chosen"])
    legal_others = [r for r in rows if r["legal"] and not r["chosen"]]

    lines = [f"Slot: pharmacy PH-{pid:02d}, night {d} -> assigned to "
             f"{chosen['name']} (worker {chosen['worker']})."]
    lines.append(
        f"  {chosen['name']}: "
        f"{'no conflicts' if chosen['legal'] else 'CONFLICTS: ' + '; '.join(chosen['conflicts'])}, "
        f"{'dislikes this night (+' + str(chosen['pref_penalty']) + ')' if chosen['dislikes_night'] else 'no preference against it'}, "
        f"already carries {chosen['current_load']} other shift(s) "
        f"(fairness cost {chosen['fairness_penalty']:.1f}).")

    if not legal_others:
        lines.append("  No alternative is legal while holding the other assignments fixed. "
                     "A global re-solve may still permit a different worker.")
    else:
        best_alt = legal_others[0]
        lines.append(
            f"  Best legal alternative was {best_alt['name']}: soft cost "
            f"{best_alt['total_soft_cost']:.1f} vs {chosen['total_soft_cost']:.1f} "
            f"for {chosen['name']} "
            f"({'higher load: ' + str(best_alt['current_load']) + ' shifts' if best_alt['current_load'] > chosen['current_load'] else ''}"
            f"{'; dislikes the night' if best_alt['dislikes_night'] else ''}).")
        n_illegal = sum(1 for r in rows if not r["legal"])
        lines.append(f"  Of {len(rows)} eligible workers: {n_illegal} were "
                     f"blocked by hard constraints, {len(legal_others) + 1} were legal.")
    return "\n".join(lines)


def objective_breakdown(inst, assignment, *, fairness="variance", use_fte=True, fairness_weight=None):
    """Whole-rota contributions under the CP-SAT objective, including travel rounding."""
    from .fairness import worker_burdens, travel_km
    import numpy as np
    rows = worker_burdens(inst, assignment)
    rows = [r for r in rows if inst.reserves_enabled or not inst.workers[r["worker"]].reserve]
    loads = [r["fte_load"] if use_fte else r["load"] for r in rows]
    if fairness == "variance":
        penalty = float(sum((v - np.mean(loads)) ** 2 for v in loads)) if loads else 0.0
    elif fairness == "egalitarian":
        penalty = max(loads, default=0.0)
    else:
        penalty = 0.0
    pref = sum(r["preference_cost"] for r in rows)
    weight = inst.fairness_lambda if fairness_weight is None else fairness_weight
    travel = inst.travel_weight * sum(round(travel_km(inst, s, w) * 1000) / 1000 for s, w in assignment.items())
    return {"workers": rows, "preference_cost": pref, "travel_cost": travel,
            "fairness_cost": weight * penalty,
            "total_cost": pref + travel + weight * penalty,
            "lexicographic_loads": sorted(loads, reverse=True) if fairness == "lexicographic" else None}


def counterfactual(inst, assignment, slot, worker, **solve_options):
    from .cpsat_solver import solve
    from .fairness import efficiency_cost
    from time import perf_counter
    started = perf_counter()
    result = solve(inst, forced={slot: worker}, **solve_options)
    has_solution = result.status in {"OPTIMAL", "FEASIBLE"}
    return {"status": result.status, "proven_optimal": result.proven_optimal,
            "assignment": result.assignment,
            "changed_slots": [s for s in inst.slots if has_solution and assignment.get(s) != result.assignment[s]],
            "efficiency_cost_delta": efficiency_cost(inst, result.assignment) - efficiency_cost(inst, assignment) if has_solution else None,
            "objective_delta": (objective_breakdown(inst, result.assignment, fairness=solve_options.get("fairness", "variance"), use_fte=solve_options.get("use_fte", True), fairness_weight=solve_options.get("fairness_weight"))["total_cost"]
                                - objective_breakdown(inst, assignment, fairness=solve_options.get("fairness", "variance"), use_fte=solve_options.get("use_fte", True), fairness_weight=solve_options.get("fairness_weight"))["total_cost"]) if has_solution else None,
            "seconds": perf_counter() - started}


def minimal_conflict(inst, slot, worker, *, time_limit=10.0):
    """Deletion-minimal policy core conditional on forcing the candidate.

    Minimal means no cited constraint can be removed while retaining this
    proof. It does not mean globally smallest. Timeout never certifies minimality.
    """
    from time import perf_counter
    from ortools.sat.python import cp_model
    from .cpsat_solver import build_model
    start = perf_counter()
    if time_limit <= 0:
        raise ValueError("time_limit must be positive")
    model, _, assumptions = build_model(inst, forced={slot: worker}, diagnostic=True)

    def check(indices):
        model.clear_assumptions()
        model.add_assumptions([assumptions[i][0] for i in indices])
        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        solver.parameters.max_time_in_seconds = max(0.001, time_limit - (perf_counter() - start))
        status = solver.solve(model)
        return solver, status

    solver, status = check(list(assumptions))
    if status != cp_model.INFEASIBLE:
        return {"status": solver.status_name(status), "constraints": [], "minimal": False,
                "seconds": perf_counter() - start}
    core = list(solver.sufficient_assumptions_for_infeasibility())
    certified = True
    for index in list(core):
        if perf_counter() - start >= time_limit:
            certified = False
            break
        trial = [i for i in core if i != index]
        _, trial_status = check(trial)
        if trial_status == cp_model.INFEASIBLE:
            core = trial
        elif trial_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            certified = False
    return {"status": "INFEASIBLE", "constraints": [assumptions[i][1] for i in core],
            "minimal": certified, "seconds": perf_counter() - start}
