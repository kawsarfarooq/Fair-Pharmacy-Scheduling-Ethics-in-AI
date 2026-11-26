"""Declared synthetic audit scenario; no demographic observations are inferred."""
from dataclasses import replace
import random
from .model import generate_instance


def audit_scenario(seed=0, *, n_pharmacies=2, n_workers=8, horizon=7):
    inst = generate_instance(n_pharmacies, n_workers, 2, horizon, seed)
    rng = random.Random(seed + 1000)
    centers = {0: (44.50, 11.32), 1: (44.51, 11.37)}
    inst.pharmacies = [replace(p, latitude=centers[p.district][0] + rng.uniform(-.01, .01),
                              longitude=centers[p.district][1] + rng.uniform(-.01, .01)) for p in inst.pharmacies]
    for w in inst.workers:
        part_time = w.wid % 3 == 0
        carer = w.wid % 4 == 0
        w.contract_fte = .5 if part_time else 1.0
        w.groups = {"part_time": part_time, "carer": carer}
        w.home_latitude, w.home_longitude = centers[w.district]
        if carer:
            # Deliberately controlled availability proxy, not an empirical claim.
            w.unavailable.update(d for d in range(horizon) if d % 7 in (1, 2))
        w.disliked.update(d for d in range(horizon) if d % 7 in (5, 6) and d not in w.unavailable)
    if horizon > 6:
        inst.shift_types[6] = "holiday"
    inst.travel_weight = .2
    inst.metadata["scenario"] = "synthetic FTE/carer availability proxy; straight-line travel"
    return inst
