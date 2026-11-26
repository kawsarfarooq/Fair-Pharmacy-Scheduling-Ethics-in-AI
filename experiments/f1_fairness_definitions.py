from trustworthy_common import *
from fair_scheduling.factor_graph import build_factor_graph
from fair_scheduling.maxsum import MaxSum
from fair_scheduling.metrics import global_utility
from fair_scheduling.baseline import solve_centralised


def main():
    args = options("Fairness definitions and matched-objective solver comparison")
    rows = []
    for seed in range(args.seeds):
        inst = audit_scenario(seed)
        assignments = {}
        for definition in ("utilitarian", "egalitarian", "variance", "lexicographic"):
            result, row = measured(inst, args, fairness=definition)
            assignments[definition] = result.assignment
            rows.append({"seed": seed, "comparison": "definitions", "method": definition, **row})
        for row in rows:
            if row["seed"] == seed and row["comparison"] == "definitions":
                row["different_from_utilitarian"] = assignments[row["method"]] != assignments["utilitarian"]
        # The pairwise comparison graph represents raw-count variance only.
        exact, row = measured(inst, args, use_fte=False)
        rows.append({"seed": seed, "comparison": "solvers_raw_counts", "method": "cpsat", **row, "cost_gap": 0 if exact.proven_optimal else None})
        for method in ("greedy_local", "maxsum"):
            start = perf_counter()
            try:
                if method == "maxsum":
                    ms = MaxSum(build_factor_graph(inst), seed=seed)
                    assignment, _, _ = ms.run(iterations=40, evaluator=lambda a: global_utility(inst, a))
                else:
                    assignment = solve_centralised(inst)
                legal = not violations(inst, assignment)
                cost = objective_breakdown(inst, assignment, use_fte=False)["total_cost"] if legal else None
                rows.append({"seed": seed, "comparison": "solvers_raw_counts", "method": method,
                             "legal": legal, "status": "HEURISTIC", "seconds": perf_counter() - start,
                             "cost": cost, "cost_gap": cost - row["cost"] if legal and exact.proven_optimal else None,
                             **(audit(inst, assignment) if legal else {})})
            except ValueError:
                rows.append({"seed": seed, "comparison": "solvers_raw_counts", "method": method, "legal": False, "status": "REJECTED"})
    save(rows, args, "f1_fairness_definitions", ["comparison", "method"], "fte_jain")


if __name__ == "__main__":
    main()
