"""Regenerate the results discussion after experiments/run_trustworthy.py finishes."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "experiments" / "trustworthy_results"


def table(frame):
    def fmt(value):
        return f"{value:.4f}" if isinstance(value, float) else str(value)
    head = "| " + " | ".join(map(str, frame.columns)) + " |\n"
    head += "| " + " | ".join("---" for _ in frame.columns) + " |\n"
    return head + "\n".join("| " + " | ".join(map(fmt, row)) + " |" for row in frame.itertuples(index=False, name=None))


def main():
    names = ("f1_fairness_definitions", "f2_pareto_front", "f3_group_audit", "r1_stress_test",
             "r2_repair_strategies", "r3_strategic_prefs", "x1_explanation_comparison")
    datasets = {name: pd.read_csv(DATA / f"{name}.csv") for name in names}
    f1, r2, r3, x = (datasets[name] for name in (names[0], names[4], names[5], names[6]))
    total = sum(len(d) for d in datasets.values())
    normative = f1[f1.comparison == "definitions"].copy()
    normative["efficiency_cost"] = normative.preference_cost + .2 * normative.travel_km
    norms = normative.groupby("method")[["fte_jain", "workload_variance", "district_gini", "district_fte_gini", "efficiency_cost"]].mean().reset_index()
    solvers = f1[f1.comparison == "solvers_raw_counts"].groupby("method")[["cost", "cost_gap"]].mean().reset_index()
    repairs = r2[r2.legal == True].groupby("method")[["stability", "objective_loss_vs_full", "seconds"]].mean().reset_index()
    gaming = r3.groupby("treatment")[["attacker_load", "true_efficiency_cost"]].mean().reset_index()
    statuses = []
    for name, d in datasets.items():
        counts = d.status.value_counts().to_dict() if "status" in d else {}
        statuses.append({"experiment": name, "rows": len(d), "seeds": d.seed.nunique(), "statuses": str(counts)})
    agreement = x.loc[x.technique == "local", "global_feasibility_agreement"].astype(float).mean()
    report = f"""# Recorded evaluation results

The recorded run uses seeds 0-24, a two-second CP-SAT budget per solve and one
search worker. It contains **{total:,} raw rows** across seven experiments.
See the [protocol](evaluation.md), [configuration manifest](../experiments/trustworthy_results/manifest.json)
and individual/summary CSVs for the definitions, uncertainty intervals and scope.
The tables below give descriptive means; they are not statistical superiority tests.

## Certificates and coverage

{table(pd.DataFrame(statuses))}

Heuristic rows cannot have exact-solver certificates. Explanation rows for local
and breakdown methods have no CP-SAT status. Infeasible load caps and disrupted
rotas are retained; they are expected experimental outcomes, not exceptions that
were removed from the data. A certificate applies only to the encoded model.

## Different ethical definitions

{table(norms)}

Higher Jain values indicate more equal FTE-relative workloads. Efficiency here
is preference cost plus travel cost, excluding the fairness penalty; audit travel
uses unrounded distance, differing from solver costs by at most rounding error.
The utilitarian result distributes burden less equally. Variance and
lexicographic fairness can achieve similar aggregate fairness on this small
scenario while expressing different normative priorities. This does not imply
that their solutions coincide on all inputs or that Jain is a complete fairness
criterion. The weighted egalitarian cost includes a different fairness term, so
objective values from different definitions should not be directly ranked.

![Fairness comparisons](../experiments/trustworthy_results/f1_fairness_definitions.png)

## Shared-objective algorithm comparison

{table(solvers)}

These costs use the same raw-count variance objective. Exact reference gaps are
computed only against certified optima. Both heuristic methods have positive
mean cost gaps in this scenario; this is not a claim about all problem sizes.

![Certified trade-off sweep](../experiments/trustworthy_results/f2_frontier.png)

The cap sweep distinguishes infeasibility from optimal efficiency under a cap.
Its eight sampled caps do not enumerate the complete Pareto set. Price ratios
depend on the explicitly declared service-benefit scale; consult absolute extra
costs as well. Group audit results are synthetic outcome differences, not findings
about actual carers or pharmacy workers.

## Repair and robustness

The following quality means use **legal repair rows only**. Legality rates and
failures remain in the raw and summary CSVs. All methods use the same initial rota
and disruption sets; stability concerns shared required slots.

{table(repairs)}

Minimal-change repair preserves more assignments while accepting a cost increase
relative to full re-optimisation. Warm Max-Sum has no guaranteed advantage over a
cold restart on these instances. Its actual reuse count is reported separately.
Reserves are assessed under a declared standby cost, with regular-worker and
whole-active-workforce Jain separated to expose denominator changes. The study
does not optimise reserve contracts or establish real staffing prices.

![Stress tests](../experiments/trustworthy_results/r1_stress_test.png)

## Strategic preference declarations

{table(gaming)}

The tested worker's mean shift count does not fall under exaggerated dislikes.
The cap increases true aggregate efficiency cost in this scenario. This is a
negative result for this particular mitigation, not evidence of general
strategy-proofness. The attacker and cap policy are fixed experimental choices.

## Explanation scope

Local fixed-rota feasibility agrees with the exact global feasibility answer in
**{agreement:.1%}** of the tested candidate questions. This measures the danger of
interpreting a local conflict globally; the local check is valid within its
stated fixed-rota scope. Reassignment elsewhere can make a blocked worker feasible.

Whole-rota breakdowns reconstruct the certified objective. Counterfactuals and
conflict checks record their own status and certificate. Infeasible queries cite
policy cores, with deletion-minimality checked explicitly. Size and stability
have technique-specific definitions and should not be treated as a common score.
Audience labels are intended uses, not empirical comprehension findings.

## What these results establish

The tests and experiments establish reproducible behaviour for this controlled
prototype. They expose competing values, repair costs and explanation scope.
They do not establish production readiness, complete labour-law compliance,
causal demographic fairness or legal certification. Broader workloads, actual
staffing requirements and stakeholder review remain necessary before deployment.
"""
    (ROOT / "report" / "results.md").write_text(report, encoding="utf-8")
    print(f"Wrote report/results.md from {total} rows")


if __name__ == "__main__":
    main()
