from trustworthy_common import *
from fair_scheduling.explain import candidate_breakdown, counterfactual, minimal_conflict


def overlap(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 1.0


def main():
    args = options("Explanation faithfulness, size, runtime and perturbation stability")
    rows = []
    for seed in range(args.seeds):
        inst = audit_scenario(seed)
        result = solve(inst, time_limit=args.time_limit, use_fte=False, seed=seed)
        if not result.proven_optimal:
            rows.append({"seed": seed, "technique": "initial", "status": result.status})
            continue
        baseline = result.assignment
        perturbed = deepcopy(inst)
        # A small soft-input change leaves policy constraints identical.
        perturbed.workers[-1].disliked.symmetric_difference_update({0})
        slot = inst.slots[0]
        start = perf_counter()
        local = candidate_breakdown(inst, baseline, slot)
        local_time = perf_counter() - start
        local_other = candidate_breakdown(perturbed, baseline, slot)
        for worker in range(len(inst.workers)):
            cf = counterfactual(inst, baseline, slot, worker, use_fte=False, time_limit=args.time_limit)
            cf2 = counterfactual(perturbed, baseline, slot, worker, use_fte=False, time_limit=args.time_limit)
            row = next((r for r in local if r["worker"] == worker), None)
            row2 = next((r for r in local_other if r["worker"] == worker), None)
            certified = cf["proven_optimal"] or cf["status"] == "INFEASIBLE"
            if row is not None:
                # Test the tempting global interpretation of a fixed-rota conflict.
                globally_possible = cf["status"] in {"OPTIMAL", "FEASIBLE"}
                rows.append({"seed": seed, "worker": worker, "technique": "local", "seconds": local_time,
                             "size": len(row["conflicts"]) + 2,
                             "global_feasibility_agreement": row["legal"] == globally_possible if certified else None,
                             "stability": overlap(row["conflicts"], row2["conflicts"]),
                             "audience": "worker; fixed-rota scope"})
            rows.append({"seed": seed, "worker": worker, "technique": "counterfactual", "seconds": cf["seconds"],
                         "size": len(cf["changed_slots"]), "status": cf["status"],
                         "faithful": not violations(inst, cf["assignment"]) if cf["proven_optimal"] else None,
                         "stability": overlap(cf["changed_slots"], cf2["changed_slots"]) if cf["proven_optimal"] and cf2["proven_optimal"] else None,
                         "audience": "manager / worker appeal"})
            core = minimal_conflict(inst, slot, worker, time_limit=args.time_limit)
            core2 = minimal_conflict(perturbed, slot, worker, time_limit=args.time_limit)
            rows.append({"seed": seed, "worker": worker, "technique": "conflict", "seconds": core["seconds"],
                         "size": len(core["constraints"]), "status": core["status"], "minimal": core["minimal"],
                         "faithful": core["status"] == cf["status"] if certified else None,
                         "stability": overlap(core["constraints"], core2["constraints"]),
                         "audience": "manager / policy owner"})
        start = perf_counter()
        breakdown = objective_breakdown(inst, baseline, use_fte=False)
        elapsed = perf_counter() - start
        other = objective_breakdown(perturbed, baseline, use_fte=False)
        # Component-value stability: share of unchanged worker preference costs.
        stability = np.mean([a["preference_cost"] == b["preference_cost"] for a, b in zip(breakdown["workers"], other["workers"])])
        rows.append({"seed": seed, "technique": "breakdown", "seconds": elapsed, "size": len(breakdown["workers"]) * 3,
                     "faithful": abs(breakdown["total_cost"] - result.objective) < 1e-5,
                     "stability": stability, "audience": "manager / auditor"})
    save(rows, args, "x1_explanation_comparison", ["technique"], "seconds")


if __name__ == "__main__":
    main()
