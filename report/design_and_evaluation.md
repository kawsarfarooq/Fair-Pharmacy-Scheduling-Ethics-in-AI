# Design and evaluation overview

Project title: **Fair and Constraint-Aware Pharmacy Shift Scheduling: A
Computational Perspective on Fairness, Robustness, and Explainability**.

This overview connects the system's research objectives to its implementation
and experimental evidence. It covers fairness and non-discrimination,
technical robustness and safety, and explainability and transparency.

| Research objective | Implementation | Evaluation evidence |
|---|---|---|
| AI-based pharmacy scheduling decision support | Exact CP-SAT model in `src/fair_scheduling/cpsat_solver.py` | Certified status, objective, bound, runtime and independent legality checks |
| Constraint-based optimisation | Coverage, availability, district eligibility, no double booking and consecutive-night rest; explicit preference/travel costs | Brute-force regression checks and legal-schedule validation |
| Quantitative fairness / variance in night shifts | Raw workload variance and Jain; FTE-relative variance, Jain and maximum burden | F1 definitions comparison and F2 weight/cap sweeps |
| Equity across workers and districts | Preference/undesirable-shift Gini, group gaps, district mean-burden Gini and district shifts-per-FTE Gini | Per-instance audits and multi-seed CSV/summary outputs in F1-F3 |
| Fairness versus efficiency trade-offs | Four normative definitions; efficiency combines preferences and travel | Certified epsilon-constraint frontier, absolute extra costs and declared price-of-fairness scale in F2 |
| Last-minute unavailability | Worker availability disruption plus exact and heuristic repair | R1 and R2, k = 1-10 events over 25 seeds |
| Demand fluctuations | Atomic addition/removal of required pharmacy-night slots | R1 demand-add and demand-remove arms |
| Stability and resilience | Shared-slot change counts, legality, repair runtime, utility loss, absorbed changes and reserve activation | R1/R2 raw rows, seed-level confidence intervals and plots |
| Technical safety | Independent publication gate and explicit distinction between optimal, feasible, infeasible and unknown | Safety, infeasibility, timeout and demand-validation tests |
| Interpretable reasons for assignments | Fixed-rota contrastive explanation, objective breakdown, global counterfactual and policy conflict core | X1 certificate checks, scope-specific faithfulness, size, time and stability |
| Comparison of explanation techniques | Four techniques with distinct audiences and limitations | X1 plus explanation comparison in `evaluation.md` and `results.md` |

## Evaluation structure

F1-F3 compare normative objectives, efficiency trade-offs, and worker/group/district
outcomes. R1-R3 examine disruptions, repair strategies, reserves and strategic
preference declarations. X1 compares four explanation techniques. Results include
raw observations, seed-level summaries, confidence intervals and plots.

## Boundaries of the claim

All shifts in the current model are night shifts, so raw night-shift variance is
the same as workload variance. Weekend/holiday burdens add a distinct audit.
Preferences are soft goals; unavailability is hard. The encoded rest/geography
requirements are simplified research rules, not a complete statement of Italian
employment law. Qualifications, full contractual limits and operational human
approval workflows require further modelling before real deployment.

Group labels and workers are synthetic. The controlled evaluation cannot establish
real-world discrimination, legal compliance or operational readiness. Audience fit
is discussed conceptually; no human comprehension study was performed.
