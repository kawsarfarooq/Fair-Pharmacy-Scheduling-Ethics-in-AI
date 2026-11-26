"""Model, solver, metric, repair, and explanation regression tests.

The suite checks domain construction, factor/evaluator consistency, agreement
with brute-force enumeration on a small instance, schedule feasibility,
district fairness sensitivity, warm-started repair, and explanation coverage.
"""

import itertools

import numpy as np
import pytest

from pharmacy_dcop import (MaxSum, build_factor_graph, disrupt,
                           generate_instance, global_utility, repair, report,
                           solve_centralised)


def tiny_instance():
    """2 pharmacies, 6 workers, 3 nights — small enough to brute-force,
    and FEASIBLE: 2 workers needed per night, the rest rule blocks at most
    2 of the 6 on any given night, so a violation-free schedule exists.
    A smaller worker pool would be structurally infeasible under the
    consecutive-night rest constraint."""
    return generate_instance(n_pharmacies=2, n_workers=6, n_districts=2,
                             horizon=3, seed=7)


def test_domains_respect_availability():
    inst = tiny_instance()
    for (pid, d) in inst.slots:
        for w in inst.domain(pid, d):
            assert d not in inst.workers[w].unavailable


def test_empty_domain_reports_infeasible_instance():
    inst = tiny_instance()
    pid, day = inst.slots[0]
    for worker in inst.eligible[pid]:
        inst.workers[worker].unavailable.add(day)

    with pytest.raises(ValueError, match="No available worker"):
        build_factor_graph(inst)


def graph_utility(inst, g, assign):
    """Evaluate an assignment DIRECTLY on the factor tables (independent
    path from metrics.global_utility)."""
    u = 0.0
    for f in g.unary:
        v = g.variables[f.var]
        u += f.table[v.index[assign[f.var]]]
    for f in g.binary:
        va, vb = g.variables[f.var_a], g.variables[f.var_b]
        u += f.table[va.index[assign[f.var_a]], vb.index[assign[f.var_b]]]
    return u


def test_factor_graph_consistency():
    """graph utility and evaluator must differ only by a CONSTANT
    (the constant is λ·Σn_w = λ·|slots|, dropped in the decomposition —
    plus, both must rank any two assignments identically)."""
    inst = tiny_instance()
    g = build_factor_graph(inst)
    rng = np.random.default_rng(0)
    assigns = []
    for _ in range(20):
        a = {s: rng.choice(inst.domain(*s)) for s in inst.slots}
        assigns.append(a)
    diffs = [global_utility(inst, a) - graph_utility(inst, g, a) for a in assigns]
    assert max(diffs) - min(diffs) < 1e-6   # constant offset => same ranking


def test_maxsum_matches_bruteforce():
    inst = tiny_instance()
    g = build_factor_graph(inst)

    # brute force over the full joint domain
    slots = inst.slots
    domains = [inst.domain(*s) for s in slots]
    best_u = -np.inf
    for combo in itertools.product(*domains):
        a = dict(zip(slots, combo))
        u = global_utility(inst, a)
        if u > best_u:
            best_u = u

    ms = MaxSum(g, seed=1)
    a, u, _ = ms.run(iterations=80, evaluator=lambda x: global_utility(inst, x))
    # anytime Max-Sum must reach the true optimum on this tiny instance
    assert u == pytest.approx(best_u)


def test_full_pipeline_feasible():
    inst = generate_instance(n_pharmacies=6, n_workers=18, horizon=7, seed=3)
    g = build_factor_graph(inst)
    ms = MaxSum(g, seed=2)
    a, _, _ = ms.run(iterations=60, evaluator=lambda x: global_utility(inst, x))
    r = report(inst, a)
    assert r["hard_violations"] == 0
    # sanity: centralised baseline is also feasible
    b = solve_centralised(inst)
    assert report(inst, b)["hard_violations"] == 0


def test_repair_restores_feasibility():
    inst = generate_instance(n_pharmacies=6, n_workers=18, horizon=7, seed=3)
    g = build_factor_graph(inst)
    ms = MaxSum(g, seed=2)
    a, _, _ = ms.run(iterations=60, evaluator=lambda x: global_utility(inst, x))

    # disrupt: the worker covering slot (0, 3) becomes unavailable that night
    victim = a[(0, 3)]
    disrupt(inst, victim, 3)
    new_a, stats, _ = repair(inst, a, iterations=30, prev_solver=ms)
    assert stats["hard_violations_after"] == 0
    assert new_a[(0, 3)] != victim or 3 not in inst.workers[victim].unavailable
    assert stats["stability"] > 0.5      # most of the schedule survived


def test_district_gini_depends_on_schedule():
    """District workload inequality must depend on the assignment."""
    inst = generate_instance(n_pharmacies=6, n_workers=18, horizon=7, seed=3)
    g = build_factor_graph(inst)
    ms = MaxSum(g, seed=2)
    a, _, _ = ms.run(iterations=40, evaluator=lambda x: global_utility(inst, x))
    fair_gini = report(inst, a)["district_gini"]
    # Construct an intentionally unequal district assignment.
    d0 = [w.wid for w in inst.workers if w.district == 0]
    import itertools
    bad = {}
    for i, s in enumerate(sorted(inst.slots)):
        bad[s] = d0[i % len(d0)]
    unfair_gini = report(inst, bad)["district_gini"]
    assert unfair_gini > fair_gini      # metric now discriminates


def test_repair_warm_start_carries_messages():
    inst = generate_instance(n_pharmacies=6, n_workers=18, horizon=7, seed=3)
    g = build_factor_graph(inst)
    ms = MaxSum(g, seed=2)
    a, _, _ = ms.run(iterations=40, evaluator=lambda x: global_utility(inst, x))
    victim = a[(0, 3)]
    disrupt(inst, victim, 3)
    new_a, stats, new_ms = repair(inst, a, iterations=20, prev_solver=ms)
    assert stats["hard_violations_after"] == 0
    assert stats["factors_warm_started"] > 0.8 * len(g.binary)  # most carried
    assert new_ms.messages_sent > 0


def test_explain_runs_on_every_slot():
    from pharmacy_dcop import explain
    inst = generate_instance(n_pharmacies=4, n_workers=12, horizon=5, seed=1)
    g = build_factor_graph(inst)
    ms = MaxSum(g, seed=1)
    a, _, _ = ms.run(iterations=40, evaluator=lambda x: global_utility(inst, x))
    for slot in inst.slots:
        text = explain(inst, a, slot)
        assert "assigned to" in text
