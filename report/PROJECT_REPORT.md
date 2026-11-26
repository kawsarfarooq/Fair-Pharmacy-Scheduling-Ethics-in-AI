# Fair and Constraint-Aware Pharmacy Shift Scheduling: A Computational Perspective on Fairness, Robustness, and Explainability

## Abstract

This project investigates how three Trustworthy AI requirements can be formalised
and evaluated in a constraint-based pharmacy night-shift scheduling system.
CP-SAT provides legal schedules and exact references for comparing fairness
definitions and efficiency. Controlled experiments test availability losses,
demand changes and repair stability, and compare four explanation techniques.
The evaluation uses 25 independent seeds and preserves infeasible outcomes.
It shows how explicit modelling choices expose value trade-offs rather than
settling ethical questions automatically. The system is an academic prototype
with synthetic employee attributes and a simplified legal/operational model.

## Research questions

1. How do utilitarian, egalitarian, variance-based and lexicographic fairness
   change workload distribution and efficiency?
2. How much schedule quality or stability is sacrificed when repairing
   disruptions, and what do reserves contribute?
3. Which explanation methods faithfully answer local, global and policy-level
   questions, and how do their size, runtime and stability differ?

## Problem and computational approach

Each required pharmacy-night receives exactly one eligible, available worker.
No worker may cover two pharmacies on the same night or work consecutive nights.
Hard availability is distinguished from soft dislikes. Efficiency combines
preference cost with one-way geographic travel cost. CP-SAT enforces the hard
model and reports certificate states; an independent gate checks a candidate
before publication. Approximate Max-Sum and greedy/local search provide
comparisons under a matched raw-count variance objective.

The main implementation is `src/fair_scheduling`. Its complete model and numerical
definitions are documented in the [README](../README.md). The
[design and evaluation overview](design_and_evaluation.md) connects the research
questions to implementation and experimental evidence.

## Fairness and non-discrimination

Equal shift counts need not imply equal burdens. A half-time worker assigned
the same number of nights as a full-time worker carries twice the FTE-relative
load. The implementation therefore measures both raw workload variance and
contract-normalised burdens. It also audits unequal preference violations,
weekend/holiday work, worker equity indices and geographic district equity.
District measures compare worker burdens in home districts; required coverage
totals alone would be fixed and could not reveal allocation differences.

Four objectives express competing ethical commitments. Utilitarian scheduling
minimises total cost. Weighted egalitarian scheduling adds a penalty on the
maximum burden. Variance scheduling penalises dispersion. Lexicographic
scheduling prioritises successive worst burdens before efficiency. F2 also
uses hard burden ceilings to measure certified efficiency trade-offs.

Synthetic part-time/carer labels are excluded from solver objectives but retained
for outcome audits. A paired availability-proxy ablation explores how constraints
can redistribute undesirable work without explicit use of group labels. This is
a controlled mechanism study, not evidence about actual carers.

## Technical robustness and safety

R1 varies 1-10 events for worker unavailability, demand increases and demand
decreases, with and without an explicit reserve pool. R2 compares full exact
re-optimisation, exact minimal-change repair, cold Max-Sum and warm Max-Sum.
Measures include legality, shared-slot stability, utility loss, repair time,
fairness changes and who absorbs additional assignments. R3 examines exaggerated
dislike declarations and an illustrative cap, evaluating true preferences rather
than treating declared costs as actual welfare.

Minimal-change repair gives continuity priority; full optimisation gives schedule
quality priority. Neither priority is ethically neutral. Safety also means
refusing to confuse a solver timeout with proof that no rota exists. A legal
solution is published only through independent validation. Operational deployment
would still need a responsible human approval and appeal process.

## Explainability and transparency

The four methods answer different questions:

| Method | Question | Main limitation |
|---|---|---|
| Local contrastive | Why this worker rather than another with all other shifts fixed? | A local conflict is not global impossibility; raw-count comparison scope |
| Objective breakdown | Which workers and cost components account for the rota's score? | Accounting alone does not justify the objective |
| Counterfactual re-solve | What else changes if another worker must take this shift? | Multiple optimal counterfactuals can exist; certification can time out |
| Minimal policy conflict | Which rules conflict with forcing this worker into the shift? | Deletion-minimal does not mean smallest possible core |

X1 measures scope-specific faithfulness, explanation size, computation time and
stability after a small preference perturbation. It discusses audience fit:
workers may prefer a contrastive answer, managers may need global rearrangements,
and policy owners may need conflict cores. No user study was conducted.

## Experimental results

The complete recorded evidence is in [results.md](results.md), including tables,
plots, certificate counts and links to raw CSVs. The protocol, confidence interval
construction, utility scaling and conditional quality metrics are defined in
[evaluation.md](evaluation.md). All seven experiments use seeds 0-24, and the
reproduction command is recorded in the README and configuration manifest.

Across this controlled scenario, exact scheduling improves average cost relative
to the two heuristic comparisons. Stronger burden equity can increase efficiency
cost. Minimal-change repair preserves more assignments at a cost relative to
full re-optimisation. The tested preference cap does not reduce the attacker's
workload and can increase true aggregate cost. Local fixed-rota feasibility can
disagree with global feasibility; this highlights the need to communicate each
explanation's scope. These are scenario-specific computational findings.

## Ethical interpretation and limitations

The [ethics discussion](ethics.md) identifies affected workers, patients, managers
and representatives; competing values; a scoped ALTAI self-assessment; relevant
EU AI Act/GDPR considerations; and remaining deployment gaps. It links to primary
sources. The project does not claim legal certification or complete labour-law
coverage. Synthetic group gaps are descriptive, not proof of discrimination in
actual pharmacies. Straight-line travel and illustrative standby costs are
modelling assumptions. Only small controlled instances are evaluated in the
controlled study; wider workloads and stakeholder review are future work.
