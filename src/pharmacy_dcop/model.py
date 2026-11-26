"""Scheduling model and synthetic instance generator.

The DCOP uses one variable ``x[p][d]`` for each required pharmacy-night slot.
Its value is the worker assigned to pharmacy ``p`` on night ``d``. The domain
contains workers who are geographically eligible and available for that slot.

Representing one worker choice per slot makes coverage structural: every
variable receives exactly one value. It also keeps domains smaller than a
Boolean worker-slot formulation, which reduces Max-Sum message cost.

Pharmacy roles conceptually own their shift variables. The implementation
records this ownership while simulating the complete model in one process.
"""

from __future__ import annotations

import random
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

    def __post_init__(self) -> None:
        # A worker may serve pharmacies in their own or an adjacent district.
        # This geographic restriction also keeps domains small and prunes the
        # factor graph (fewer shared-worker pairs => fewer factors).
        for p in self.pharmacies:
            elig = [w.wid for w in self.workers
                    if w.district == p.district
                    or w.district in self.adjacency.get(p.district, set())]
            if not elig:  # safety: never allow an empty domain
                elig = [w.wid for w in self.workers]
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
                if day not in self.workers[w].unavailable]


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
