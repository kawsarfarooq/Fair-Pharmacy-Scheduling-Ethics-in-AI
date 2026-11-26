from trustworthy_common import *
from fair_scheduling.robustness import cap_dislikes
from fair_scheduling.fairness import worker_burdens, efficiency_cost


def main():
    args = options("Preference gaming: evaluate allocations using truthful preferences")
    rows = []
    for seed in range(args.seeds):
        truth = audit_scenario(seed)
        for treatment in ("honest", "attack", "honest_capped", "attack_capped"):
            inst = deepcopy(truth)
            if treatment.startswith("attack"):
                inst.workers[0].disliked = set(range(inst.horizon)) - inst.workers[0].unavailable
            if treatment.endswith("capped"):
                cap_dislikes(inst, 2)
            result, row = measured(inst, args)
            if result.status in {"OPTIMAL", "FEASIBLE"}:
                burden = worker_burdens(truth, result.assignment)[0]
                row.update({"attacker_load": burden["load"], "attacker_true_pref_cost": burden["preference_cost"],
                            "true_efficiency_cost": efficiency_cost(truth, result.assignment)})
            rows.append({"seed": seed, "treatment": treatment, **row})
    save(rows, args, "r3_strategic_prefs", ["treatment"], "attacker_load")


if __name__ == "__main__":
    main()
