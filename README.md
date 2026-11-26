# Fair and Constraint-Aware Pharmacy Shift Scheduling: A Computational Perspective on Fairness, Robustness, and Explainability

This project investigates an AI-based decision-support system for pharmacy shift
scheduling by formalising and evaluating three Trustworthy AI requirements:
fairness and non-discrimination, technical robustness and safety, and
explainability and transparency. The scheduling task is a constraint-based
optimisation problem with hard coverage, availability, geographic, booking and
rest requirements, alongside soft worker preferences and explicit fairness goals.
The rest model is a research simplification, not a complete labour-law rulebook.

Start with the [project report](report/PROJECT_REPORT.md), the
[design and evaluation overview](report/design_and_evaluation.md), and the
[recorded results](report/results.md).

Google OR-Tools CP-SAT is the main solver. Max-Sum and greedy/local search are
retained for controlled comparisons. The main implementation is in
`src/fair_scheduling`. F1-F3, R1-R3 and X1 evaluate fairness, robustness, safety
and explainability across reproducible scheduling scenarios.

This is a research prototype. Synthetic workers and requirements do not
constitute an official pharmacy rota. See [the ethics discussion](report/ethics.md)
and [the evaluation protocol](report/evaluation.md).

## Install and verify

Python 3.10 or later:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
```

Linux/macOS: activate with `source .venv/bin/activate`.

## Generate a schedule

```python
from fair_scheduling import solve, publish_schedule, audit
from fair_scheduling.scenarios import audit_scenario

instance = audit_scenario(seed=0)
result = solve(instance, fairness="variance", time_limit=30)
print(result.status, result.proven_optimal, result.objective, result.best_bound)
if result.status in {"OPTIMAL", "FEASIBLE"}:
    schedule = publish_schedule(instance, result.assignment)
    print(audit(instance, schedule))
else:
    print("No schedule available: human review required")
```

`FEASIBLE` means a legal incumbent exists but optimality was not established.
`UNKNOWN` means the search budget did not establish a solution or infeasibility.
Only `INFEASIBLE` certifies that no schedule satisfies the model. A proof applies
to the encoded assumptions, not to the adequacy of real-world staffing policy.
The independent publication gate rejects missing/extra slots, unknown workers,
ineligible/unavailable workers, inactive reserves, double booking and rest conflicts.

## Fairness and costs

Every night has a type: weekday, weekend or holiday. Day zero defaults to Monday;
callers must set `shift_types` for an actual calendar. `Worker.contract_fte` is
positive; synthetic group labels are read only by audits. Home/pharmacy coordinates
provide one-way straight-line kilometres. Travel is rounded to 0.001 km in solver
costs; missing coordinates are rejected when travel optimisation is enabled.

Let `l[w] = shifts[w] / contract_fte[w]`. The definitions are:

| Objective | Minimise |
|---|---|
| `utilitarian` | Total preference and travel cost |
| `variance` | Efficiency cost + lambda * sum((l[w] - mean(l))**2) |
| `egalitarian` | Efficiency cost + lambda * max(l) |
| `lexicographic` | Descending load vector lexicographically, then efficiency cost |

Egalitarian is a weighted max-load trade-off. A strict load ceiling is available
with `max_load=...`. Lexicographic minimisation of burdens corresponds to max-min
welfare when welfare is negative burden. Each stage must be proven optimal before
the next starts. The time limit includes all stages. Result objective/bound refer
to the reported `stage`; `proven_optimal` covers the full sequence.

Audits report `workload_variance` and `workload_jain` across all regular workers,
including zero-shift workers. `district_gini` compares mean shifts per worker in
each home district; `district_fte_gini` compares shifts per total contracted FTE
in each district. These measure allocated worker burden, rather than pharmacy
coverage totals fixed by demand. Both district metrics are present in the
fairness experiment CSVs and seed-level summaries.

FTE ratios and objective weights use exact rational-to-integer scaling, subject
to documented validation limits; this is not arbitrary rounding of fairness.
Use `use_fte=False` for the matched raw-count variance comparison with Max-Sum.
The comparison graph assigns a penalty of `2 * lambda` to each same-worker
shift pair. On legal rotas, this gives the same ordering as the sum-of-squared-
deviations objective, up to a constant.

## Repair and explanations

```python
from fair_scheduling.robustness import disrupt_demand
from fair_scheduling.explain import counterfactual, minimal_conflict, objective_breakdown

previous = result.assignment
# A worker becomes unavailable; make the smallest number of changes first.
worker = previous[instance.slots[0]]
instance.workers[worker].unavailable.add(instance.slots[0][1])
repaired = solve(instance, previous=previous, minimal_change=True)

# Inspect a repaired schedule only when a legal incumbent exists.
if repaired.status in {"OPTIMAL", "FEASIBLE"}:
    print(objective_breakdown(instance, repaired.assignment))
# Demand supports adding/removing pharmacy-night slots atomically.
disrupt_demand(instance, remove=[instance.slots[-1]])
# Run on a fresh, consistent instance/rota for comparisons:
# counterfactual(instance, schedule, slot=(0, 0), worker=1)
# minimal_conflict(instance, slot=(0, 0), worker=1)
```

Local explanations hold other assignments fixed and cannot prove that an
alternative worker is globally impossible. Counterfactuals re-solve the whole
rota. Conflict explanations use assumptions and deletion shrinking. `minimal=True`
means deletion-minimal, not minimum-cardinality; a timeout cannot certify it.
Objective breakdowns describe total costs and per-worker components; the
lexicographic load vector must also be read for lexicographic decisions.

Reserves are explicit inactive workers, enabled with `reserves_enabled=True`.
The stress evaluation assigns a declared standby cost of 5 units per reserve.
This price is an illustrative staffing assumption, not an estimated wage.
Max-Sum warm restart reuses messages only when domain identities and factor
values match; matching matrix shapes alone is insufficient.

## Run the evaluations

```powershell
# Complete evaluation, seeds 0 through 24, 3-second budget per solve:
python experiments/run_trustworthy.py
# Quick end-to-end smoke check:
python experiments/run_trustworthy.py --seeds 2 --time-limit 1 --output experiments/trustworthy_smoke
# Reproduce the recorded 25-seed run:
python experiments/run_trustworthy.py --seeds 25 --time-limit 2
# Refresh the written results after the complete run:
python report/update_results.py
```

Each script also runs independently with the same arguments:

| Script | Evaluation |
|---|---|
| `f1_fairness_definitions.py` | Four ethical objectives; matched-objective CP-SAT / Max-Sum / greedy comparisons |
| `f2_pareto_front.py` | Exact load-cap frontier, price of fairness, lambda and preference-weight sensitivity |
| `f3_group_audit.py` | Group gaps and paired availability-proxy ablation |
| `r1_stress_test.py` | 1-10 availability or demand changes, with/without reserves |
| `r2_repair_strategies.py` | Full, minimal-change, warm and cold repair |
| `r3_strategic_prefs.py` | Honest/strategic preferences with/without declaration caps |
| `x1_explanation_comparison.py` | Four explanation methods: faithfulness, size, time, stability and intended audience |

Outputs: individual CSV rows, seed-level summary CSVs with 95% bootstrap intervals,
PNG plots, and a version/configuration manifest in `experiments/trustworthy_results`.
Timeouts remain visible. An optimum gap/price is populated only for certified
references. The independent statistical unit is the seed, not each slot or event.

Price of fairness uses `U = declared service benefit - efficiency cost` to ensure
a positive, explicitly defined baseline utility. It depends on that benefit scale;
absolute efficiency-cost increases are also reported. The load-cap sweep uses
an epsilon-constraint method; a lambda sweep alone can miss Pareto points.

## Source layout

```text
src/fair_scheduling/
  model.py           entities, FTE, shift types, groups and reserves
  cpsat_solver.py    exact model, fairness objectives, staged repair
  fairness.py        worker burdens, group audits, travel and price
  safety.py          independent legality check / publication gate
  robustness.py      demand disruptions, reserves and repair comparisons
  scenarios.py       reproducible synthetic availability-proxy scenario
  explain.py         local, breakdown, counterfactual and conflict methods
  factor_graph.py    comparison model for raw-count variance
  maxsum.py          approximate comparison solver
  baseline.py        greedy/local-search comparison solver
  real_data.py       Bologna infrastructure loader (synthetic workforce)
src/pharmacy_dcop/   reference factor-graph implementation used by regression tests
experiments/         F1-F3 / R1-R3 / X1 and additional scheduling case studies
report/              project report, ethical analysis, evaluation design and results
```

The Bologna loader remains available. Coordinates of worker homes, FTE and audit
labels are synthetic additions; the prepared public dataset does not supply real
employee attributes. The new default evaluation is a controlled synthetic study,
not evidence of discrimination in Bologna pharmacies.
