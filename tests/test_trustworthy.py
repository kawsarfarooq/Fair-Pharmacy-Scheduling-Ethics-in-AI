from copy import deepcopy
from itertools import product

import pytest

from fair_scheduling import Instance, Pharmacy, Worker, solve, violations, publish_schedule
from fair_scheduling.explain import counterfactual, minimal_conflict, objective_breakdown
from fair_scheduling.fairness import audit, price_of_fairness
from fair_scheduling.robustness import disrupt_demand, add_reserves


def tiny():
    return Instance([Pharmacy(0, 0)], [Worker(0, 0, disliked={0}, contract_fte=.5),
                    Worker(1, 0), Worker(2, 0)], 4, {0: set()}, 0)


def legal_assignments(inst):
    for values in product(*(inst.domain(*s) for s in inst.slots)):
        a = dict(zip(inst.slots, values))
        if not violations(inst, a):
            yield a


@pytest.mark.parametrize("fairness", ["utilitarian", "egalitarian", "variance", "lexicographic"])
@pytest.mark.parametrize("use_fte", [False, True])
def test_exact_objectives_match_enumeration(fairness, use_fte):
    inst = tiny()
    def key(a):
        b = objective_breakdown(inst, a, fairness=fairness, use_fte=use_fte)
        return tuple(b["lexicographic_loads"]) + (b["total_cost"],) if fairness == "lexicographic" else (b["total_cost"],)
    best = min(key(a) for a in legal_assignments(inst))
    result = solve(inst, fairness=fairness, use_fte=use_fte)
    assert result.proven_optimal
    assert not violations(inst, result.assignment)
    assert key(result.assignment) == pytest.approx(best)


def test_independent_gate_rejects_incomplete_and_ineligible():
    inst = tiny()
    with pytest.raises(ValueError, match="missing coverage"):
        publish_schedule(inst, {})
    inst.eligible[0] = [1, 2]
    assert any("ineligible" in e for e in violations(inst, {(0, 0): 0}))
    with pytest.raises(ValueError, match="Human review"):
        publish_schedule(inst, {(0, d): 0 for d in range(4)})


def test_geography_never_silently_relaxes():
    inst = Instance([Pharmacy(0, 0)], [Worker(0, 1)], 1, {}, 0)
    assert inst.domain(0, 0) == []
    assert solve(inst).status == "INFEASIBLE"


def test_minimal_repair_matches_enumeration():
    inst = tiny()
    previous = solve(inst).assignment
    inst.workers[previous[(0, 0)]].unavailable.add(0)
    expected = min(sum(a[s] != previous[s] for s in inst.slots) for a in legal_assignments(inst))
    result = solve(inst, previous=previous, minimal_change=True)
    assert result.proven_optimal and result.changes == expected


def test_counterfactual_is_a_global_resolve():
    inst = tiny()
    previous = {(0, 0): 1, (0, 1): 2, (0, 2): 1, (0, 3): 2}
    result = counterfactual(inst, previous, (0, 0), 2)
    assert result["proven_optimal"]
    assert result["assignment"][(0, 0)] == 2
    assert (0, 1) in result["changed_slots"]


def test_conflict_core_is_deletion_minimal():
    from fair_scheduling.cpsat_solver import build_model
    from ortools.sat.python import cp_model
    inst = tiny()
    inst.workers[0].unavailable.add(0)
    result = minimal_conflict(inst, (0, 0), 0)
    assert result["status"] == "INFEASIBLE" and result["minimal"]
    assert len(result["constraints"]) == 1
    model, _, assumptions = build_model(inst, forced={(0, 0): 0}, diagnostic=True)
    core = [v for v, label in assumptions.values() if label in result["constraints"]]
    model.clear_assumptions()
    model.add_assumptions(core)
    assert cp_model.CpSolver().solve(model) == cp_model.INFEASIBLE
    model.clear_assumptions()
    assert cp_model.CpSolver().solve(model) == cp_model.OPTIMAL


def test_demand_mutations_are_atomic_and_repair_handles_removed_slots():
    from fair_scheduling.dynamics import repair
    inst = tiny()
    previous = solve(inst).assignment
    with pytest.raises(ValueError):
        disrupt_demand(inst, add=[(99, 0)])
    assert len(inst.slots) == 4
    disrupt_demand(inst, remove=[(0, 0)])
    a, _, _ = repair(inst, previous, iterations=3)
    assert (0, 0) not in a


def test_groups_are_audit_only_and_reserves_are_explicit():
    inst = tiny()
    before = solve(inst).assignment
    inst.workers[0].groups["carer"] = True
    assert solve(inst).assignment == before
    assert "carer_fte_load_gap" in audit(inst, before)
    add_reserves(inst, 1)
    assert 3 not in inst.domain(0, 0)
    inst.reserves_enabled = True
    assert 3 in inst.domain(0, 0)


def test_timeouts_never_claim_optimum_or_infeasibility():
    inst = tiny()
    result = solve(inst, time_limit=1e-9)
    assert result.status == "UNKNOWN" and not result.proven_optimal
    assert result.human_review_required


def test_price_requires_positive_utility_and_valid_fte():
    assert price_of_fairness(10, 8) == pytest.approx(.2)
    assert price_of_fairness(0, -1) is None
    with pytest.raises(ValueError, match="contract_fte"):
        Instance([Pharmacy(0, 0)], [Worker(0, 0, contract_fte=0)], 1, {}, 0)


def test_common_raw_variance_objective_matches_factor_graph():
    from fair_scheduling.factor_graph import build_factor_graph
    from fair_scheduling.metrics import global_utility
    inst = tiny()
    inst.fairness_lambda = .7
    graph = build_factor_graph(inst)
    offsets = []
    for a in legal_assignments(inst):
        graph_cost = -sum(f.table[graph.variables[f.var].index[a[f.var]]] for f in graph.unary)
        graph_cost -= sum(f.table[graph.variables[f.var_a].index[a[f.var_a]], graph.variables[f.var_b].index[a[f.var_b]]] for f in graph.binary)
        assert graph_cost == pytest.approx(-global_utility(inst, a))
        offsets.append(objective_breakdown(inst, a, use_fte=False)["total_cost"] - graph_cost)
    assert max(offsets) - min(offsets) < 1e-8


def test_rational_fte_weights_and_rounded_travel_match_enumeration():
    from dataclasses import replace
    inst = tiny()
    inst.workers[1].contract_fte = .75
    inst.fairness_lambda = .125
    inst.travel_weight = .3
    inst.pharmacies = [replace(inst.pharmacies[0], latitude=44.5, longitude=11.3)]
    for w in inst.workers:
        w.home_latitude, w.home_longitude = 44.5 + w.wid * .01, 11.32
    expected = min(objective_breakdown(inst, a)["total_cost"] for a in legal_assignments(inst))
    result = solve(inst)
    assert result.proven_optimal
    assert result.objective == pytest.approx(expected)
    lex = solve(inst, fairness="lexicographic")
    def key(a):
        b = objective_breakdown(inst, a, fairness="lexicographic")
        return tuple(b["lexicographic_loads"]) + (b["total_cost"],)
    assert lex.proven_optimal and key(lex.assignment) == min(key(a) for a in legal_assignments(inst))


def test_exact_load_cap_can_prove_insufficient_total_capacity():
    from fair_scheduling.scenarios import audit_scenario
    result = solve(audit_scenario(), fairness="utilitarian", max_load=2.5, time_limit=2)
    assert result.status == "INFEASIBLE"


def test_district_equity_audits_worker_burden_not_fixed_coverage():
    inst = Instance([Pharmacy(0, 0)],
                    [Worker(0, 0, contract_fte=.5), Worker(1, 1)],
                    3, {0: {1}, 1: {0}}, 0, required_slots=[(0, 0), (0, 2)])
    unequal = audit(inst, {(0, 0): 0, (0, 2): 0})
    equal_counts = audit(inst, {(0, 0): 0, (0, 2): 1})
    assert unequal["district_gini"] == pytest.approx(.5)
    assert equal_counts["district_gini"] == 0
    assert equal_counts["district_fte_gini"] == pytest.approx(1 / 6)
    assert unequal["workload_variance"] > equal_counts["workload_variance"]
