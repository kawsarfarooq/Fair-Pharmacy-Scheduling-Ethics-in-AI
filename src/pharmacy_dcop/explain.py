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
    """One row per eligible candidate for `slot`, with every score term."""
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
        rows.append({
            "worker": w,
            "name": inst.workers[w].name,
            "chosen": w == chosen,
            "legal": not conflicts,
            "conflicts": conflicts,
            "dislikes_night": d in inst.workers[w].disliked,
            "pref_penalty": inst.pref_penalty if d in inst.workers[w].disliked else 0.0,
            "current_load": load,
            "fairness_penalty": inst.fairness_lambda * load,
            "total_soft_cost": (inst.pref_penalty if d in inst.workers[w].disliked else 0.0)
                               + inst.fairness_lambda * load,
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
        lines.append("  No other eligible worker was legally available for "
                     "this slot — the assignment was forced.")
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
