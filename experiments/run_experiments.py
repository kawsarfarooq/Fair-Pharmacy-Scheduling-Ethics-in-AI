"""Reproducible experiment suite.

E1 compares Max-Sum with the centralised baseline.
E2 measures sensitivity to the fairness weight.
E3 evaluates feasibility and stability after sequential disruptions.
E4 measures runtime and message count as instance size increases.

Running this module prints each result and writes ``experiments/results.csv``.
"""

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pharmacy_dcop import (MaxSum, build_factor_graph, disrupt,
                           generate_instance, global_utility, repair, report,
                           solve_centralised)

ROWS = []


def log(exp, **kw):
    ROWS.append({"experiment": exp, **kw})
    print(f"  {kw}")


def e1_price_of_decentralisation():
    print("\n=== E1: Max-Sum (DCOP) vs centralised baseline ===")
    inst = generate_instance(n_pharmacies=10, n_workers=28, horizon=14, seed=42)
    g = build_factor_graph(inst)
    print(f"  graph: {g.stats()}")

    t0 = time.time()
    ms = MaxSum(g, seed=1)
    a_dcop, _, _ = ms.run(iterations=50,
                          evaluator=lambda x: global_utility(inst, x))
    t_dcop = time.time() - t0

    t0 = time.time()
    a_cent = solve_centralised(inst)
    t_cent = time.time() - t0

    for name, a, t, msgs in [("maxsum", a_dcop, t_dcop, ms.messages_sent),
                             ("centralised", a_cent, t_cent, 0)]:
        r = report(inst, a)
        log("E1", solver=name, seconds=round(t, 2), messages=msgs, **{
            k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()})


def e2_fairness_knob():
    print("\n=== E2: fairness weight lambda sweep ===")
    for lam in [0.0, 0.5, 1.0, 2.0, 5.0]:
        inst = generate_instance(n_pharmacies=8, n_workers=24, horizon=10,
                                 seed=7, fairness_lambda=lam)
        g = build_factor_graph(inst)
        ms = MaxSum(g, seed=1)
        a, _, _ = ms.run(iterations=40,
                         evaluator=lambda x: global_utility(inst, x))
        r = report(inst, a)
        log("E2", fairness_lambda=lam,
            workload_var=round(r["workload_var"], 3),
            jain=round(r["jain_index"], 4),
            pref_cost=r["preference_cost"],
            hard=r["hard_violations"])


def e3_dynamic_repair():
    print("\n=== E3: disruption -> local repair ===")
    inst = generate_instance(n_pharmacies=8, n_workers=24, horizon=10, seed=11)
    g = build_factor_graph(inst)
    ms = MaxSum(g, seed=1)
    a, _, _ = ms.run(iterations=40, evaluator=lambda x: global_utility(inst, x))
    base = report(inst, a)
    print(f"  before: hard={base['hard_violations']} var={base['workload_var']:.2f}")

    for k, (slot_p, slot_d) in enumerate([(0, 4), (3, 7), (5, 2)]):
        victim = a[(slot_p, slot_d)]
        disrupt(inst, victim, slot_d)
        a, stats, ms = repair(
            inst,
            a,
            iterations=20,
            seed=k,
            prev_solver=ms,
        )
        log("E3", event=k + 1, sick_worker=victim, night=slot_d,
            hard_after=stats["hard_violations_after"],
            stability=round(stats["stability"], 3),
            changed_slots=stats["changed_slots"],
            repair_messages=stats["messages"],
            factors_warm_started=stats["factors_warm_started"])


def e4_scalability():
    print("\n=== E4: scalability ===")
    for (np_, nw, h) in [(6, 18, 7), (10, 28, 14), (14, 40, 14), (18, 50, 14)]:
        inst = generate_instance(n_pharmacies=np_, n_workers=nw, horizon=h, seed=5)
        g = build_factor_graph(inst)
        t0 = time.time()
        ms = MaxSum(g, seed=1)
        a, _, _ = ms.run(iterations=30,
                         evaluator=lambda x: global_utility(inst, x))
        t = time.time() - t0
        r = report(inst, a)
        log("E4", pharmacies=np_, workers=nw, horizon=h,
            slots=np_ * h, binary_factors=g.stats()["binary_factors"],
            seconds=round(t, 1), messages=ms.messages_sent,
            hard=r["hard_violations"], jain=round(r["jain_index"], 4))


if __name__ == "__main__":
    e1_price_of_decentralisation()
    e2_fairness_knob()
    e3_dynamic_repair()
    e4_scalability()

    out = Path(__file__).parent / "results.csv"
    keys = sorted({k for row in ROWS for k in row})
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(ROWS)
    print(f"\nSaved {len(ROWS)} rows -> {out}")
