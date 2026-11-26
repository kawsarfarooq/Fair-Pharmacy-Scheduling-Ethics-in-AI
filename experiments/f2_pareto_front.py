from trustworthy_common import *
from fair_scheduling.fairness import price_of_fairness


def main():
    args = options("Exact epsilon-constraint frontier and weight sensitivity")
    rows = []
    for seed in range(args.seeds):
        inst = audit_scenario(seed)
        baseline, base = measured(inst, args, fairness="utilitarian")
        # Explicit positive shift-service benefit; its arbitrary scale is recorded.
        benefit = len(inst.slots) * (inst.pref_penalty + inst.travel_weight * 20 + 1)
        for cap in (2, 2.5, 3, 3.5, 4, 5, 6, 7):
            result, row = measured(inst, args, fairness="utilitarian", max_load=cap)
            certified = baseline.proven_optimal and result.proven_optimal
            rows.append({"seed": seed, "experiment": "load_cap", "value": cap,
                         "benefit_constant": benefit, **row,
                         "extra_efficiency_cost": row["cost"] - base["cost"] if certified else None,
                         "price_of_fairness": price_of_fairness(benefit - base["cost"], benefit - row["cost"]) if certified else None})
        reference = None
        for weight in (0, .1, .5, 1, 2, 5, 10):
            inst.fairness_lambda = weight
            result, row = measured(inst, args)
            if reference is None:
                reference = result.assignment
            rows.append({"seed": seed, "experiment": "lambda", "value": weight, **row,
                         "changed_from_reference": sum(reference.get(s) != result.assignment.get(s) for s in inst.slots)
                             if result.status in {"OPTIMAL", "FEASIBLE"} else None})
        inst.fairness_lambda = 1
        preference_reference = solve(inst, time_limit=args.time_limit).assignment
        for penalty in (0, 1, 3, 6, 10):
            inst.pref_penalty = penalty
            result, row = measured(inst, args)
            rows.append({"seed": seed, "experiment": "preference_penalty", "value": penalty, **row,
                         "changed_from_reference": sum(preference_reference.get(s) != result.assignment.get(s) for s in inst.slots)
                             if result.status in {"OPTIMAL", "FEASIBLE"} else None})
    df = save(rows, args, "f2_pareto_front", ["experiment", "value"], "fte_jain")
    front = df[(df.experiment == "load_cap") & (df.proven_optimal == True)]
    if len(front):
        fig, ax = plt.subplots(figsize=(6, 4))
        for seed, part in front.groupby("seed"):
            ax.plot(part.value, part.cost, ".-", alpha=.25)
        ax.set(xlabel="Permitted maximum FTE-relative load", ylabel="Optimal efficiency cost", title="Certified load-cap sweep by seed")
        fig.tight_layout()
        fig.savefig(args.output / "f2_frontier.png", dpi=150)
        plt.close(fig)


if __name__ == "__main__":
    main()
