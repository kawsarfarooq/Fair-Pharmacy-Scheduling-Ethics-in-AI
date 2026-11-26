from trustworthy_common import *
from r1_stress_test import disrupted
from fair_scheduling.robustness import repair_comparison
from fair_scheduling.factor_graph import build_factor_graph
from fair_scheduling.maxsum import MaxSum
from fair_scheduling.metrics import global_utility


def main():
    args = options("Paired full/minimal CP-SAT and warm/cold Max-Sum repair")
    rows = []
    for seed in range(args.seeds):
        base = audit_scenario(seed)
        initial = solve(base, time_limit=args.time_limit, use_fte=False, seed=seed)
        if initial.status not in {"OPTIMAL", "FEASIBLE"}:
            rows.append({"seed": seed, "k": 0, "method": "initial", "legal": False, "status": initial.status})
            continue
        previous_solver = MaxSum(build_factor_graph(base), seed=seed)
        previous_solver.run(iterations=30, evaluator=lambda a: global_utility(base, a))
        for k in range(1, 11):
            inst = disrupted(base, initial.assignment, k, "availability")
            for row in repair_comparison(inst, initial.assignment, time_limit=args.time_limit, prev_solver=previous_solver, seed=seed):
                rows.append({"seed": seed, "k": k, **row})
    save(rows, args, "r2_repair_strategies", ["k", "method"], "stability")


if __name__ == "__main__":
    main()
