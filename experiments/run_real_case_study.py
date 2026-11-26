"""Run E5, the Bologna-grounded demographic sensitivity case study."""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pharmacy_dcop import (MaxSum, build_bologna_case_study,
                           build_factor_graph, global_utility, report,
                           solve_centralised)


def main() -> None:
    instance = build_bologna_case_study(ROOT / "data" / "processed")
    graph = build_factor_graph(instance)

    print("=== E5: Bologna-grounded case study ===")
    print({
        "listed_pharmacies": len(instance.pharmacies),
        "required_slots": len(instance.slots),
        "slots_per_night": instance.metadata["slots_per_night"],
        "synthetic_workers": len(instance.workers),
        "district_slot_allocation": instance.metadata["district_slot_allocation"],
    })
    print(f"  graph: {graph.stats()}")

    rows = []
    started = time.time()
    maxsum = MaxSum(graph, seed=1)
    assignment, _, _ = maxsum.run(
        iterations=40,
        evaluator=lambda value: global_utility(instance, value),
    )
    rows.append({
        "experiment": "E5",
        "solver": "maxsum",
        "seconds": round(time.time() - started, 2),
        "messages": maxsum.messages_sent,
        **report(instance, assignment),
    })

    started = time.time()
    centralised = solve_centralised(instance)
    rows.append({
        "experiment": "E5",
        "solver": "centralised",
        "seconds": round(time.time() - started, 2),
        "messages": 0,
        **report(instance, centralised),
    })

    for row in rows:
        print(f"  {row}")
    output = ROOT / "experiments" / "results_real.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows -> {output}")


if __name__ == "__main__":
    main()
