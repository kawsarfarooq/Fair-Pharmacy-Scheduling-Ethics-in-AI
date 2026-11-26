"""Audits are descriptive; group attributes never enter solver objectives."""
import math
import numpy as np
from .model import Instance


def gini(values) -> float:
    x = np.sort(np.asarray(list(values), dtype=float))
    if np.any(x < 0):
        raise ValueError("Gini expects nonnegative burdens")
    if len(x) == 0 or x.sum() == 0:
        return 0.0
    return float(np.dot(2 * np.arange(1, len(x) + 1) - len(x) - 1, x) / (len(x) * x.sum()))


def jain(values) -> float:
    x = np.asarray(list(values), dtype=float)
    return float(x.sum() ** 2 / (len(x) * np.dot(x, x))) if np.any(x) else 1.0


def travel_km(inst: Instance, slot, wid: int) -> float:
    w = inst.workers[wid]
    p = next(p for p in inst.pharmacies if p.pid == slot[0])
    coords = (w.home_latitude, w.home_longitude, p.latitude, p.longitude)
    if any(c is None for c in coords):
        if inst.travel_weight:
            raise ValueError("Travel optimisation requires all home and pharmacy coordinates")
        return 0.0
    a, b, c, d = map(math.radians, coords)
    hav = math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2
    return 6371 * 2 * math.asin(min(1.0, math.sqrt(hav)))


def worker_burdens(inst: Instance, assignment: dict) -> list[dict]:
    rows = []
    for w in inst.workers:
        slots = [s for s, wid in assignment.items() if wid == w.wid]
        rows.append({"worker": w.wid, "load": len(slots),
                     "fte_load": len(slots) / w.contract_fte,
                     "undesirable": sum(inst.shift_types[s[1]] != "weekday" for s in slots),
                     "preference_cost": inst.pref_penalty * sum(s[1] in w.disliked for s in slots),
                     "travel_km": sum(travel_km(inst, s, w.wid) for s in slots)})
    return rows


def audit(inst: Instance, assignment: dict) -> dict:
    rows = worker_burdens(inst, assignment)
    # Inactive reserves are outside the regular workforce denominator.
    rows = [r for r in rows if inst.reserves_enabled or not inst.workers[r["worker"]].reserve]
    loads = [r["fte_load"] for r in rows]
    raw_loads = [r["load"] for r in rows]
    prefs = [r["preference_cost"] for r in rows]
    districts = sorted({inst.workers[r["worker"]].district for r in rows})
    district_loads = [[r for r in rows if inst.workers[r["worker"]].district == district]
                      for district in districts]
    # Compare average burdens per worker, not pharmacy coverage totals, which
    # are fixed by the demand pattern. Include workers with zero shifts.
    district_means = [sum(r["load"] for r in members) / len(members) for members in district_loads]
    district_fte_rates = [sum(r["load"] for r in members)
                          / sum(inst.workers[r["worker"]].contract_fte for r in members)
                          for members in district_loads]
    result = {"fte_jain": jain(loads), "fte_variance": float(np.var(loads)) if loads else 0.0,
              "workload_variance": float(np.var(raw_loads)) if raw_loads else 0.0,
              "workload_jain": jain(raw_loads),
              "district_gini": gini(district_means),
              "district_fte_gini": gini(district_fte_rates),
              "max_fte_load": max(loads, default=0.0),
              "preference_gini": gini(prefs),
              "preference_range": max(prefs, default=0) - min(prefs, default=0),
              "undesirable_gini": gini(r["undesirable"] for r in rows),
              "travel_km": sum(r["travel_km"] for r in rows),
              "preference_cost": sum(prefs)}
    for group in sorted({g for w in inst.workers for g in w.groups}):
        for measure in ("fte_load", "undesirable", "preference_cost", "travel_km"):
            yes = [r[measure] for r in rows if inst.workers[r["worker"]].groups.get(group, False)]
            no = [r[measure] for r in rows if not inst.workers[r["worker"]].groups.get(group, False)]
            result[f"{group}_{measure}_gap"] = float(np.mean(yes) - np.mean(no)) if yes and no else None
    return result


def efficiency_cost(inst: Instance, assignment: dict) -> float:
    return sum((inst.pref_penalty if s[1] in inst.workers[w].disliked else 0)
               + inst.travel_weight * travel_km(inst, s, w) for s, w in assignment.items())


def price_of_fairness(best_utility: float, fair_utility: float) -> float | None:
    """Relative loss only for positive baseline utility; zero/negative is undefined."""
    return (best_utility - fair_utility) / best_utility if best_utility > 0 else None
