"""Exact scheduling with explicit certificates and bounded solve time.

Variance is sum of squared deviations of FTE-relative loads. Lexicographic
fairness minimises the descending vector of burdens, then efficiency cost.
Each lexicographic stage must be proven optimal before advancing.
"""
from dataclasses import dataclass, field
from fractions import Fraction
from functools import reduce
from math import lcm, isfinite
from time import perf_counter

from ortools.sat.python import cp_model

from .fairness import travel_km
from .model import Instance
from .safety import violations

Slot = tuple[int, int]
FAIRNESS = ("utilitarian", "egalitarian", "variance", "lexicographic")


@dataclass
class SolveResult:
    status: str
    assignment: dict[Slot, int] = field(default_factory=dict)
    objective: float | None = None
    best_bound: float | None = None
    wall_time: float = 0.0
    proven_optimal: bool = False
    changes: int = 0
    stage: str = ""
    completed_stages: int = 0
    human_review_required: bool = True


def load_scaling(inst: Instance, use_fte=True):
    ftes = [Fraction(str(w.contract_fte)) if use_fte else Fraction(1) for w in inst.workers]
    scale = reduce(lcm, (f.numerator for f in ftes), 1)
    multipliers = [scale * f.denominator // f.numerator for f in ftes]
    if scale > 100000 or max(multipliers, default=1) > 100000:
        raise ValueError("FTE precision exceeds exact integer scaling limit")
    return scale, multipliers


def _linear_objective(terms):
    """Scale rational coefficients without rounding fairness weights."""
    converted = [(v, Fraction(str(c))) for v, c in terms if c]
    denominator = reduce(lcm, (c.denominator for _, c in converted), 1)
    coefficients = [int(c * denominator) for _, c in converted]
    if denominator > 10**15 or any(abs(c) > 10**15 for c in coefficients):
        raise ValueError("Objective precision exceeds exact integer scaling limit")
    return sum(c * v for (v, _), c in zip(converted, coefficients)), denominator


def build_model(inst: Instance, *, forced=None, diagnostic=False):
    model = cp_model.CpModel()
    x = {(s, w.wid): model.new_bool_var(f"x_{s[0]}_{s[1]}_{w.wid}")
         for s in inst.slots for w in inst.workers}
    assumptions = {}

    def rule(constraint, label):
        if diagnostic:
            a = model.new_bool_var(label)
            constraint.only_enforce_if(a)
            assumptions[a.index] = (a, label)
            model.add_assumption(a)

    for s in inst.slots:
        rule(model.add(sum(x[s, w.wid] for w in inst.workers) == 1), f"coverage:{s}")
        for w in inst.workers:
            if w.wid not in inst.eligible[s[0]]:
                rule(model.add(x[s, w.wid] == 0), f"geography:{s}:worker={w.wid}")
            if s[1] in w.unavailable:
                rule(model.add(x[s, w.wid] == 0), f"availability:{s}:worker={w.wid}")
            if w.reserve and not inst.reserves_enabled:
                rule(model.add(x[s, w.wid] == 0), f"inactive-reserve:{s}:worker={w.wid}")
    for w in inst.workers:
        daily = [sum(x[s, w.wid] for s in inst.slots if s[1] == day) for day in range(inst.horizon)]
        for day, count in enumerate(daily):
            rule(model.add(count <= 1), f"no-double-booking:worker={w.wid}:day={day}")
        for day in range(inst.horizon - 1):
            rule(model.add(daily[day] + daily[day + 1] <= 1), f"rest:worker={w.wid}:days={day},{day+1}")
    for s, wid in (forced or {}).items():
        if (s, wid) not in x:
            raise ValueError("Forced assignment references an unknown slot or worker")
        # Counterfactual stays hard while policy constraints are diagnosed.
        model.add(x[s, wid] == 1)
    return model, x, assumptions


def solve(inst: Instance, *, fairness="variance", fairness_weight=None, use_fte=True,
          time_limit=30.0, seed=0, forced=None, previous=None,
          minimal_change=False, max_load=None) -> SolveResult:
    start = perf_counter()
    weight = inst.fairness_lambda if fairness_weight is None else fairness_weight
    if fairness not in FAIRNESS:
        raise ValueError(f"fairness must be one of {FAIRNESS}")
    if not isfinite(time_limit) or time_limit <= 0:
        raise ValueError("time_limit must be positive and finite")
    if any(not isfinite(v) or v < 0 for v in (weight, inst.pref_penalty, inst.travel_weight)):
        raise ValueError("Objective weights must be finite and nonnegative")
    model, x, _ = build_model(inst, forced=forced)
    n = len(inst.slots)
    scale, multipliers = load_scaling(inst, use_fte)
    # Inactive reserves must not change the fairness denominator.
    active = [w for w in inst.workers if inst.reserves_enabled or not w.reserve]
    loads = []
    counts = []
    for w in active:
        count = model.new_int_var(0, min(n, (inst.horizon + 1) // 2), f"count_{w.wid}")
        model.add(count == sum(x[s, w.wid] for s in inst.slots))
        counts.append(count)
        bound = n * multipliers[w.wid]
        load = model.new_int_var(0, bound, f"load_{w.wid}")
        model.add(load == multipliers[w.wid] * count)
        loads.append(load)
        if max_load is not None:
            model.add(load <= int(Fraction(str(max_load)) * scale))
    # Redundant conservation strengthens proofs under tight FTE load ceilings.
    model.add(sum(counts) == n)
    bound = n * max(multipliers, default=1)
    stages = []
    changes = sum(1 - x[s, wid] if (s, wid) in x else 1
                  for s, wid in (previous or {}).items() if s in inst.slots)
    if minimal_change:
        if previous is None:
            raise ValueError("minimal_change requires a previous schedule")
        stages.append(("changes", changes, 1))
    efficiency = [(v, Fraction(str(inst.pref_penalty)) * (s[1] in inst.workers[wid].disliked)
                      + Fraction(str(inst.travel_weight)) * Fraction(round(travel_km(inst, s, wid) * 1000), 1000))
                  for (s, wid), v in x.items() if wid in inst.domain(*s)]
    terms = list(efficiency)
    if fairness == "variance" and loads and weight:
        coefficient = Fraction(str(weight)) / (scale * scale)
        for i, load in enumerate(loads):
            sq = model.new_int_var(0, bound * bound, f"sq_{i}")
            model.add_multiplication_equality(sq, [load, load])
            terms.append((sq, coefficient))
        if len({multipliers[w.wid] for w in active}) == 1:
            total = n * multipliers[active[0].wid]
            terms.append((1, -coefficient * total * total / len(loads)))
        else:
            total = model.new_int_var(0, bound, "total_normalised_load")
            total_sq = model.new_int_var(0, bound * bound, "total_normalised_load_sq")
            model.add(total == sum(loads))
            model.add_multiplication_equality(total_sq, [total, total])
            terms.append((total_sq, -coefficient / len(loads)))
    elif fairness == "egalitarian" and loads:
        maximum = model.new_int_var(0, bound, "maximum_load")
        model.add_max_equality(maximum, loads)
        terms.append((maximum, Fraction(str(weight)) / scale))
    elif fairness == "lexicographic" and loads:
        maximum = model.new_int_var(0, bound, "maximum_load")
        model.add_max_equality(maximum, loads)
        stages.append(("lex_maximum", maximum, scale))
    objective, denominator = _linear_objective(terms)
    stages.append(("cost", objective, denominator))
    result = SolveResult(status="UNKNOWN")
    for stage_index, (stage, objective, denominator) in enumerate(stages):
        remaining = time_limit - (perf_counter() - start)
        if remaining <= 0:
            result.status = "FEASIBLE" if result.assignment or not inst.slots else "UNKNOWN"
            result.proven_optimal = False
            break
        model.minimize(objective)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = remaining
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = seed
        status = solver.solve(model)
        result.stage = stage
        result.status = solver.status_name(status)
        result.proven_optimal = False
        result.objective = None
        result.best_bound = None
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            result.assignment = {s: w.wid for s in inst.slots for w in inst.workers if solver.value(x[s, w.wid])}
            result.objective = solver.objective_value / denominator
            result.best_bound = solver.best_objective_bound / denominator
            result.changes = sum(result.assignment[s] != wid for s, wid in (previous or {}).items() if s in result.assignment)
            result.human_review_required = bool(violations(inst, result.assignment))
            if status == cp_model.OPTIMAL:
                result.completed_stages += 1
                model.add(objective == int(round(solver.objective_value)))
                if stage == "lex_maximum":
                    # For fixed maximum, descending histogram counts encode
                    # exactly the same order as the descending burden vector.
                    cap = solver.value(maximum)
                    levels = sorted({i * multipliers[w.wid] for w in active
                                     for i in range(1, n + 1) if i * multipliers[w.wid] <= cap}, reverse=True)
                    histogram = []
                    for level in levels:
                        flags = []
                        for i, load in enumerate(loads):
                            flag = model.new_bool_var(f"at_least_{level}_{i}")
                            model.add(load >= level).only_enforce_if(flag)
                            model.add(load < level).only_enforce_if(flag.Not())
                            flags.append(flag)
                        histogram.append((f"workers_at_least_{level}/{scale}", sum(flags), 1))
                    stages[stage_index + 1:stage_index + 1] = histogram
                model.clear_hints()
                for var in x.values():
                    model.add_hint(var, solver.value(var))
            else:
                break
        else:
            # A previous lexicographic stage may still provide a legal incumbent.
            if result.assignment and status == cp_model.UNKNOWN:
                result.status = "FEASIBLE"
            break
    result.proven_optimal = result.completed_stages == len(stages)
    result.wall_time = perf_counter() - start
    return result
