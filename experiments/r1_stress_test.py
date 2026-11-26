from trustworthy_common import *
from fair_scheduling.robustness import disrupt_demand, add_reserves
from fair_scheduling.fairness import efficiency_cost, jain, worker_burdens


def disrupted(original, previous, k, kind):
    inst = deepcopy(original)
    ordered = sorted(previous, key=lambda s: (s[1], s[0]))
    if kind == "availability":
        for slot in ordered[:k]:
            inst.workers[previous[slot]].unavailable.add(slot[1])
    elif kind == "demand_remove":
        disrupt_demand(inst, remove=ordered[:k])
    else:
        # Start from reduced demand, restoring one omitted pharmacy-night per event.
        omitted = sorted(inst.metadata["omitted_slots"])
        disrupt_demand(inst, add=omitted[:k])
    return inst


def main():
    args = options("Stress tests: 1..10 availability/demand events and reserves")
    rows = []
    for seed in range(args.seeds):
        for kind in ("availability", "demand_remove", "demand_add"):
            base = audit_scenario(seed)
            if kind == "demand_add":
                omitted = base.slots[:10]
                disrupt_demand(base, remove=omitted)
                base.metadata["omitted_slots"] = omitted
            initial = solve(base, time_limit=args.time_limit, use_fte=False, seed=seed)
            if initial.status not in {"OPTIMAL", "FEASIBLE"}:
                rows.append({"seed": seed, "kind": kind, "k": 0, "reserve_count": 0,
                             "method": "initial", "status": initial.status, "legal": False})
                continue
            for reserve_count in (0, 2):
                reserved = deepcopy(base)
                add_reserves(reserved, reserve_count)
                for k in range(1, 11):
                    inst = disrupted(reserved, initial.assignment, k, kind)
                    inst.reserves_enabled = bool(reserve_count)
                    result = solve(inst, time_limit=args.time_limit, previous=initial.assignment, minimal_change=True, use_fte=False, seed=seed)
                    legal = result.status in {"OPTIMAL", "FEASIBLE"} and not violations(inst, result.assignment)
                    shared = set(initial.assignment) & set(inst.slots)
                    changed = sum(initial.assignment[s] != result.assignment.get(s) for s in shared)
                    prior = audit(base, initial.assignment)
                    after = audit(inst, result.assignment) if legal else {}
                    benefit = len(base.slots) * (base.pref_penalty + base.travel_weight * 20 + 1)
                    base_utility = benefit - efficiency_cost(base, initial.assignment)
                    rows.append({"seed": seed, "kind": kind, "k": k, "reserve_count": reserve_count,
                                 "method": "minimal", "status": result.status, "proven_optimal": result.proven_optimal,
                                 "legal": legal, "seconds": result.wall_time,
                                 "changed_slots": changed if legal else None,
                                 "stability": 1 - changed / len(shared) if legal and shared else None,
                                 "jain_before": prior["fte_jain"], "jain_after": after.get("fte_jain"),
                                 "readiness_cost": reserve_count * 5,
                                 "price_of_robustness": reserve_count * 5 / base_utility if kind == "availability" and base_utility > 0 else None,
                                 "regular_jain_after": jain(r["fte_load"] for r in worker_burdens(inst, result.assignment)
                                                            if not inst.workers[r["worker"]].reserve) if legal else None,
                                 "reserve_shifts": sum(inst.workers[w].reserve for w in result.assignment.values()) if legal else None,
                                 "change_burden": {w.wid: sum(result.assignment.get(s) == w.wid and initial.assignment.get(s) != w.wid for s in inst.slots) for w in inst.workers} if legal else None})
    save(rows, args, "r1_stress_test", ["kind", "k", "reserve_count", "method"], "legal")


if __name__ == "__main__":
    main()
