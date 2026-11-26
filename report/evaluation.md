# Evaluation protocol

## Reproduction and statistical unit

Run `python experiments/run_trustworthy.py --seeds 25 --time-limit 2` from the
repository root after installation. The run records seeds 0-24, package versions,
platform, per-solve time limit and one CP-SAT search worker. The same configuration
is used for all methods. Exact solver limits include model construction and all
lexicographic stages; minimal-conflict limits include core shrinking. Wall-clock
measurements reflect this machine and solver build and are not portable speed
guarantees. Max-Sum uses an iteration budget, so it does not receive the same
wall-clock budget as CP-SAT.

The independent replicate is the random seed. Each summary first averages
repeated observations within the same seed and grouping, then bootstraps those
seed means 2,000 times for a percentile 95% interval. Counts accompany estimates.
These intervals describe variability across this generator's seeds, not a
population of real workers. They are not simultaneous intervals and do not
replace paired statistical analysis for a deployment claim. Degenerate 0/1
bootstrap intervals can occur when every observed seed has the same outcome.

## Shared scenario

The controlled scenario has two pharmacies, eight workers, two adjacent synthetic
districts and seven nights. Workers have seeded availability and preferences.
Workers with IDs divisible by three have FTE 0.5; those divisible by four have a
synthetic carer label and an injected weekday availability restriction. Both
groups remain audit-only fields. FTE and availability are legitimate model
inputs whose normative meaning is exposed rather than hidden. Weekend/holiday
preferences and the proxy are designed, not sampled from an empirical workforce.
One-way haversine distances use synthetic Bologna-area coordinates. Travel cost
is 0.2 per km and the default dislike cost is 3. Day 6 is labelled a holiday.

## F1-F3: definitions, efficiency and groups

F1 compares utilitarian, weighted egalitarian, variance and lexicographic
objectives with FTE-relative loads. An additional comparison uses raw-count
variance for CP-SAT, Max-Sum and greedy/local search. All three then optimise
the same preferences/travel/variance objective; a constant offset in the graph
does not change schedule rankings. The independent safety gate evaluates every
candidate. Optimality gaps are absolute costs, populated only when the exact
reference is certified and the candidate is legal. An infeasible heuristic
cannot be scored as an improvement over the legal optimum.

F2 minimises efficiency under eight maximum FTE-load caps. This is a discrete
epsilon-constraint sweep; certified points are exact optima for the sampled
caps, not an exhaustive enumeration of all Pareto schedules. A fairness-weight
sweep and a preference-penalty sweep measure schedule changes and audits.
For the price ratio, define benefit per covered slot as `pref_penalty +
travel_weight * 20 + 1` and utility as total benefit minus efficiency cost.
The constant is explicit and arbitrary; it makes the baseline positive in this
scenario, but the ratio changes when this utility scale changes. Absolute cost
increases are therefore retained. A zero/negative baseline utility yields no ratio.
Only proven optima populate exact prices.

F3 audits all objectives with and without the deliberately injected availability
proxy. The new audits also report raw workload variance/Jain and two district
Gini measures: mean shifts per worker by home district, and shifts divided by
the district's total contracted FTE. Both include zero-shift regular workers;
inactive reserves are excluded. Pharmacy coverage totals are not a fairness
outcome because they are determined by required slots.

The group ablation removes the deliberately injected availability
proxy while retaining the same group labels. Group gaps are group-mean burden
minus complement-mean burden; an empty group/complement is undefined. Preference
and undesirable-shift Gini indices include zero-burden workers. FTE Jain includes
regular workers, plus reserves when explicitly activated. Gaps are descriptive;
the synthetic proxy ablation is not causal evidence about real protected groups.

## R1-R3: repair, reserves and gaming

R1 varies k from 1 to 10 independently from each original schedule, using
availability losses, demand removal and demand addition. Demand-add instances
start with ten slots omitted and progressively restore them. Each event set
is deterministic and nested; results are not a random distribution of all
possible disruptions. Reserve arms copy two synthetic profiles before events,
then activate them. Their extra readiness cost is 10 illustrative units; the
price of robustness divides it by baseline positive service utility for the
fixed-demand availability scenario. This is a declared staffing price, not a
wage estimate or an endogenous optimisation of reserve commitments.

R2 uses the same initial schedule and event sets for full CP-SAT, staged
minimal-change CP-SAT, cold Max-Sum and compatible-message warm Max-Sum.
Initial Max-Sum messages come from the same undisrupted model; the published
initial rota is the exact solver's schedule. Objective losses use a raw-count
variance reference and record whether full re-optimisation was certified.
Warm reuse verifies domain identities and factor values.

Changed-slot stability is computed over shared required slots; additions and
removals are reported separately. Added shifts contribute to absorption burden.
Jain before/after, reserve shifts, regular-workforce Jain and per-worker absorbed
changes are retained. These are independent repairs, not a longitudinal study
of repeated burden accumulation. Failed/infeasible repairs remain in legality
rates; objective-loss estimates apply only when legal candidates exist. R2 also
retains numeric change/stability diagnostics for rejected candidates in raw
summaries; compare stability on legal rows when making quality claims. An initial
instance without a feasible solution receives a separate `k=0` record rather
than silently disappearing.

R3 compares honest, exaggerated-dislike, honest-capped and attack-capped
declarations. The attacker is worker 0. The cap keeps the two earliest disliked
days and applies to all workers. True costs are evaluated with the original
preferences, so reported claims are not confused with welfare. Capping can hurt
honest workers and is evaluated as an intervention, not endorsed as policy.

## X1: explanation comparison

For each certified initial rota, X1 asks about every worker for the first slot.
The four techniques have different scopes and size units:

| Technique | Faithfulness test | Size | Perturbation stability |
|---|---|---|---|
| Local | Agreement of fixed-rota feasibility with global feasibility, explicitly testing a tempting overinterpretation | Conflict count plus two soft terms | Jaccard overlap of cited conflicts |
| Breakdown | Reconstructed total equals the solver's objective | Three component categories per worker | Share of unchanged worker preference costs |
| Counterfactual | Whole-rota legality of a certified forced solution | Changed slots | Jaccard overlap of changed-slot sets |
| Conflict core | Agreement with exact counterfactual feasibility; deletion-minimality recorded separately | Cited policy constraints | Jaccard overlap of cited policies |

The perturbation toggles one disliked day of the last worker. Baseline decisions
are held fixed for the question. Perfect local/core stability is plausible
because hard constraints do not change in this perturbation; this does not prove
stability under availability or regulatory changes. Two empty citation sets have
Jaccard similarity 1. Feasible counterfactuals have no infeasibility core, so empty
core size is not proof of a better explanation. Audience labels express intended
use; they are not a human comprehension evaluation. Faithfulness metrics are
scope-specific and should not be ranked as interchangeable percentages.

## Certificates and results

`OPTIMAL` certifies the reported objective only if the complete staged objective
finished; `proven_optimal` is the definitive flag. A lexicographic timeout can
retain a legal incumbent from an earlier stage, with no bound for the remaining
stages. `INFEASIBLE` proves no solution in the encoded model. `UNKNOWN` is not
infeasibility. Conflict cores are sufficient and certified minimal only when
every necessary deletion check completed. Numerical results and limitations
are summarised in `results.md`; raw CSVs remain the auditable source.
