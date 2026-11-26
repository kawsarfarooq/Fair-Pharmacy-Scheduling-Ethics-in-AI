# Trustworthy pharmacy scheduling: ethics and limitations

## System overview

The system combines constraint-based scheduling, exact optimisation and
comparative evaluation of fairness, robustness, safety and explanations.
CP-SAT supplies certified reference solutions; Max-Sum and greedy/local search
provide algorithmic comparisons. Audits examine contract-normalised workloads,
worker preferences, district equity and synthetic group outcomes. Numerical
findings are recorded in [results.md](results.md).

## People affected and value tensions

Workers bear fatigue, travel and disruption costs. Part-time workers may need
proportional burdens rather than identical shift counts. Carers may have
restricted availability that a formally group-blind policy nevertheless
transforms into unequal weekend work. Managers need predictable staffing and
legal coverage. Patients need reliable night access; missing a required slot
cannot be compensated by an improvement in a fairness score. Worker
representatives should participate in choosing definitions and weights.

These interests conflict. Minimising total dissatisfaction can concentrate
burden. Equalising counts can overload part-time staff. Minimising the worst
burden can increase travel or assign more disliked shifts. Preserving yesterday's
rota may preserve an unfair distribution. Reserves improve resilience but require
staffing expenditure and impose availability obligations on people outside the
published rota. No scalar objective resolves these questions by itself.

The experiment compares four explicit positions. Utilitarian optimisation
minimises aggregate costs. Weighted egalitarian optimisation adds a penalty on
the largest FTE-relative load. Variance minimises dispersion of those loads.
Lexicographic minimisation first protects the worst burden, then the next,
with efficiency used only after the fairness vector is fixed. For a practical
pilot, FTE-relative variance is a defensible starting point with a hard maximum
load set through consultation. This is a proposed policy, not an empirical
finding or a universal ethical preference. Worker-level preference and
undesirable-shift inequality still require separate inspection.

## Trustworthy AI and ALTAI self-assessment

The EU expert guidelines identify seven requirements. This study focuses on
robustness/safety, transparency and fairness while recording gaps in the others.
The [Commission guidelines](https://digital-strategy.ec.europa.eu/en/library/ethics-guidelines-trustworthy-ai)
provide the framework. The following is a scoped self-assessment informed by
[ALTAI](https://digital-strategy.ec.europa.eu/en/library/assessment-list-trustworthy-artificial-intelligence-altai-self-assessment),
not completion of its full questionnaire or a compliance certification.

| Requirement | Evidence in this prototype | Remaining gap |
|---|---|---|
| Human agency and oversight | Invalid schedules are withheld; counterfactual appeals can be investigated | No manager/worker approval interface, appeal workflow or logged override process |
| Robustness and safety | Exact constraints, certificates, independent gate, demand/availability stress tests | Rules omit qualifications, contractual weekly limits and production service continuity |
| Privacy and governance | Synthetic employee records; audit groups excluded from optimisation | No production access controls, retention policy, lawful-basis assessment or DPIA |
| Transparency | Cost breakdowns, counterfactuals, policy conflicts and explicit certificate states | Audience fit is an argued design choice, not a user-study result |
| Diversity and fairness | Multiple objectives, FTE burdens, group/proxy audits | Synthetic labels cannot establish real discrimination or its absence |
| Societal/environmental well-being | Travel distance measured alongside preferences | Straight-line distances do not measure emissions, transport access or patient travel |
| Accountability | Seed/configuration manifest, reproducible outputs and tests | No operational incident register, independent audit or assigned deployment owner |

## Legal relevance

Annex III 4(b) of the [EU AI Act](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng)
addresses specified employment decisions and task allocation based on individual
behaviour or characteristics. It motivates assessing a deployed worker scheduler;
classification depends on intended use and applicable definitions and exceptions.
Article 86 concerns meaningful explanations for qualifying decisions based on
certain high-risk systems that significantly and adversely affect people.
An explanation function alone does not establish compliance.

[GDPR Article 22](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng)
addresses solely automated decisions with legal or similarly significant effects,
subject to exceptions and safeguards. Meaningful human review is therefore a
design consideration; an automatic validator is not human oversight. These
provisions do not create an unconditional explanation right for every draft rota.
No statement here certifies legal compliance or the commencement date of duties.

## Safety and explanations

Feasibility has priority over soft cost. A large heuristic penalty is not a hard
guarantee. The independent publication gate checks coverage, worker identity,
availability, geographic eligibility, reserve activation, double booking and
the encoded consecutive-night rest rule. When no legal candidate is available,
the caller must escalate staffing or policy changes to a responsible person.
An `INFEASIBLE` certificate proves an inconsistency in the encoded model;
`UNKNOWN` and `FEASIBLE` do not prove infeasibility or optimality.

A local conflict means an alternative fails with other assignments fixed.
A global counterfactual can move those other assignments and make it possible.
Conflict explanations explicitly separate a sufficient assumption core from a
deletion-minimal core, and never claim minimum cardinality. Multiple equally
valid counterfactuals or minimal cores can exist, making stability a separate
quality criterion. Objective breakdowns are faithful accounting but do not
establish that the chosen ethical objective is justified.

## Interpretation limits and next deployment steps

The synthetic carer proxy is an intentional experimental intervention, not an
observation about carers. Group gaps show outcomes, not a causal finding about
actual workers. A declaration cap can suppress truthful preferences as well as
gaming; it requires an equitable exception process and should not restrict hard
availability. A zero measured gaming benefit in one scenario does not establish
strategy-proofness.

The rest rule is a simplified model assumption, not a complete statement of
Italian employment law. Day zero is Monday unless shift types are explicitly
supplied; real holidays must be supplied. Home locations and travel burdens in
the audit scenario are synthetic. On-call costs are illustrative, and reserves
are copied synthetic worker profiles rather than a labour-market model.

Before an operational pilot, obtain stakeholder agreement on burdens and
weights, validate all legal/qualification rules, set actual shift calendars,
establish privacy controls and a manager approval/appeal process, and evaluate
with representative historical cases. These are outstanding deployment tasks,
not claims that this academic implementation has completed them.
