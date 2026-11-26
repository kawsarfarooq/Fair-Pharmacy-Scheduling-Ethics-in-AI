"""Scheduling entities, hard eligibility domains and synthetic data.

The exact model assigns one worker to each required pharmacy-night. FTE,
calendar types and reserve availability are explicit. Groups are audit-only."""

from __future__ import annotations

import random
import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pharmacy:
    pid: int
    district: int
    name: str = ""
    source_id: str = ""
    address: str = ""
    latitude: float | None = None
    longitude: float | None = None


@dataclass
class Worker:
    wid: int
    district: int
    name: str = ""
    # nights (day indices) on which the worker is unavailable (hard constraint)
    unavailable: set[int] = field(default_factory=set)
    # nights the worker would PREFER not to work (soft constraint, utility -pref_penalty)
    disliked: set[int] = field(default_factory=set)
    # target number of night shifts over the horizon (soft workload anchor)
    target_shifts: int = 0
    contract_fte: float = 1.0
    groups: dict[str, bool] = field(default_factory=dict)
    home_latitude: float | None = None
    home_longitude: float | None = None
    reserve: bool = False


@dataclass
class Instance:
    """A complete problem instance = entities + eligibility + parameters."""
    pharmacies: list[Pharmacy]
    workers: list[Worker]
    horizon: int                          # number of nights
    adjacency: dict[int, set[int]]        # district -> set of adjacent districts
    seed: int
    required_slots: list[tuple[int, int]] | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    # ---- utility weights (the "objective function knobs") -----------------
    HARD: float = -1e6      # big-M penalty standing in for -infinity
    pref_penalty: float = 3.0    # cost of assigning a disliked night
    fairness_lambda: float = 1.0  # weight of the pairwise fairness penalty (see below)

    # Filled by __post_init__:
    eligible: dict[int, list[int]] = field(default_factory=dict)  # pid -> [wid...]
    shift_types: dict[int, str] = field(default_factory=dict)
    travel_weight: float = 0.0
    reserves_enabled: bool = False

    def __post_init__(self) -> None:
        if [w.wid for w in self.workers] != list(range(len(self.workers))):
            raise ValueError("Worker IDs must be contiguous and ordered from zero")
        if self.horizon < 0 or len({p.pid for p in self.pharmacies}) != len(self.pharmacies):
            raise ValueError("Invalid horizon or duplicate pharmacy IDs")
        if any(not math.isfinite(w.contract_fte) or w.contract_fte <= 0 for w in self.workers):
            raise ValueError("contract_fte must be finite and positive")
        for day in range(self.horizon):
            self.shift_types.setdefault(day, "weekend" if day % 7 in (5, 6) else "weekday")
        if any(t not in {"weekday", "weekend", "holiday"} for t in self.shift_types.values()):
            raise ValueError("Unknown shift type")
        # A worker may serve pharmacies in their own or an adjacent district.
        # This geographic restriction also keeps domains small and prunes the
        # factor graph (fewer shared-worker pairs => fewer factors).
        for p in self.pharmacies:
            elig = [w.wid for w in self.workers
                    if w.district == p.district
                    or w.district in self.adjacency.get(p.district, set())]
            self.eligible[p.pid] = elig

        if self.required_slots is not None:
            valid_pids = {p.pid for p in self.pharmacies}
            if len(set(self.required_slots)) != len(self.required_slots):
                raise ValueError("required_slots contains duplicates")
            for pid, day in self.required_slots:
                if pid not in valid_pids:
                    raise ValueError(f"Unknown pharmacy id in required slot: {pid}")
                if not 0 <= day < self.horizon:
                    raise ValueError(f"Night outside planning horizon: {day}")

    # ------------------------------------------------------------------ API
    @property
    def slots(self) -> list[tuple[int, int]]:
        """All decision variables as (pharmacy_id, day) pairs."""
        if self.required_slots is not None:
            return list(self.required_slots)
        return [(p.pid, d) for p in self.pharmacies for d in range(self.horizon)]

    def domain(self, pid: int, day: int) -> list[int]:
        """Eligible workers who are available for ``x[pid][day]``."""
        return [w for w in self.eligible[pid]
                if day not in self.workers[w].unavailable
                and (self.reserves_enabled or not self.workers[w].reserve)]


# --------------------------------------------------------------------------
# Synthetic data generation ("Bologna-like" instances)
# --------------------------------------------------------------------------
def generate_instance(n_pharmacies: int = 10,
                      n_workers: int = 28,
                      n_districts: int = 5,
                      horizon: int = 14,
                      seed: int = 42,
                      fairness_lambda: float = 1.0) -> Instance:
    """
    Generates a random but structured instance.

    Structural assumptions:
      * districts arranged on a ring, each adjacent to its two neighbours
        (a simplified synthetic geography);
      * each worker is unavailable ~15% of nights (holidays, other jobs);
      * each worker dislikes ~10% of the remaining nights (weekends, etc.);
      * target workload = total slots / workers (perfectly fair reference).
    """
    rng = random.Random(seed)

    adjacency = {k: {(k - 1) % n_districts, (k + 1) % n_districts}
                 for k in range(n_districts)}

    pharmacies = [Pharmacy(pid=i, district=i % n_districts, name=f"PH-{i:02d}")
                  for i in range(n_pharmacies)]

    total_slots = n_pharmacies * horizon
    target = round(total_slots / n_workers)

    workers = []
    for i in range(n_workers):
        unavailable = {d for d in range(horizon) if rng.random() < 0.15}
        disliked = {d for d in range(horizon)
                    if d not in unavailable and rng.random() < 0.10}
        workers.append(Worker(wid=i, district=i % n_districts,
                              name=f"W-{i:02d}",
                              unavailable=unavailable,
                              disliked=disliked,
                              target_shifts=target))

    return Instance(pharmacies=pharmacies, workers=workers, horizon=horizon,
                    adjacency=adjacency, seed=seed,
                    fairness_lambda=fairness_lambda)
