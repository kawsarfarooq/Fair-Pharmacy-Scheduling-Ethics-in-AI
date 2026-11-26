"""Single-process Max-Sum comparison model for raw-count variance.

Preference and rounded travel costs are unary. Booking and rest use large
penalties. Twice-lambda same-worker pair costs match the CP-SAT variance
objective up to a constant on legal schedules. Owner strings label factors
for legacy message reuse and have no distributed execution semantics."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .model import Instance
from .fairness import travel_km

Slot = tuple[int, int]  # (pharmacy_id, day)


@dataclass
class Variable:
    slot: Slot
    domain: list[int]                    # worker ids
    index: dict[int, int] = field(init=False)  # wid -> position in domain

    def __post_init__(self):
        self.index = {w: i for i, w in enumerate(self.domain)}


@dataclass
class UnaryFactor:
    """Utility vector u[i] for each value of one variable."""
    var: Slot
    table: np.ndarray            # shape (|domain|,)
    owner: str = "worker"        # agent role owning this factor


@dataclass
class BinaryFactor:
    """Utility matrix U[i, j] over the values of two variables."""
    var_a: Slot
    var_b: Slot
    table: np.ndarray            # shape (|dom_a|, |dom_b|)
    owner: str = "regulatory"


@dataclass
class FactorGraph:
    variables: dict[Slot, Variable]
    unary: list[UnaryFactor]
    binary: list[BinaryFactor]

    def stats(self) -> dict:
        by_owner: dict[str, int] = {}
        for f in self.binary:
            by_owner[f.owner] = by_owner.get(f.owner, 0) + 1
        return {"variables": len(self.variables),
                "unary_factors": len(self.unary),
                "binary_factors": len(self.binary),
                "binary_by_owner": by_owner}


# --------------------------------------------------------------------------
def _same_worker_matrix(va: Variable, vb: Variable, penalty: float) -> np.ndarray | None:
    """Matrix with `penalty` where both variables take the SAME worker.
    Returns None if domains do not intersect (factor would be constant 0
    and can be pruned)."""
    shared = set(va.domain) & set(vb.domain)
    if not shared:
        return None
    U = np.zeros((len(va.domain), len(vb.domain)))
    for w in shared:
        U[va.index[w], vb.index[w]] = penalty
    return U


def build_factor_graph(inst: Instance) -> FactorGraph:
    # ---- 1. Variables (one per shift slot; availability folded in) --------
    variables: dict[Slot, Variable] = {}
    for (pid, d) in inst.slots:
        dom = inst.domain(pid, d)
        if not dom:
            raise ValueError(
                f"No available worker for pharmacy {pid} on night {d}"
            )
        variables[(pid, d)] = Variable(slot=(pid, d), domain=dom)

    unary: list[UnaryFactor] = []
    binary: list[BinaryFactor] = []

    # ---- 2. Unary preference factors (Worker Agents' voice) ---------------
    # A worker who dislikes night d contributes -pref_penalty to any slot
    # on night d assigned to them.
    for v in variables.values():
        _, d = v.slot
        t = np.zeros(len(v.domain))
        for w in v.domain:
            t[v.index[w]] -= inst.travel_weight * round(travel_km(inst, v.slot, w) * 1000) / 1000
            if d in inst.workers[w].disliked:
                t[v.index[w]] = -inst.pref_penalty
        if t.any():
            unary.append(UnaryFactor(var=v.slot, table=t, owner="worker"))

    # ---- 3. HARD: no double booking (Regulatory Agent) --------------------
    # Same night, two different pharmacies, same worker -> big-M penalty.
    slots_by_day = {
        day: [slot for slot in variables if slot[1] == day]
        for day in range(inst.horizon)
    }
    for d in range(inst.horizon):
        day_slots = slots_by_day[d]
        for i in range(len(day_slots)):
            for j in range(i + 1, len(day_slots)):
                va, vb = variables[day_slots[i]], variables[day_slots[j]]
                U = _same_worker_matrix(va, vb, inst.HARD)
                if U is not None:
                    binary.append(BinaryFactor(va.slot, vb.slot, U, owner="regulatory"))

    # ---- 4. HARD: rest rule (Regulatory Agent) -----------------------------
    # No worker on two CONSECUTIVE nights (any pair of pharmacies).
    for d in range(inst.horizon - 1):
        for slot_a in slots_by_day[d]:
            for slot_b in slots_by_day[d + 1]:
                va, vb = variables[slot_a], variables[slot_b]
                U = _same_worker_matrix(va, vb, inst.HARD)
                if U is not None:
                    binary.append(BinaryFactor(va.slot, vb.slot, U, owner="regulatory"))

    # ---- 5. SOFT: fairness (Fairness Agent) --------------------------------
    # The exact pairwise decomposition of sum_w n_w² (see module docstring).
    # One factor per pair of slots with intersecting domains, EXCLUDING pairs
    # already forbidden by hard factors (same night / consecutive nights),
    # where the -λ would be dominated by big-M anyway.
    slots_list = list(variables.keys())
    for i in range(len(slots_list)):
        for j in range(i + 1, len(slots_list)):
            (pa, da), (pb, db) = slots_list[i], slots_list[j]
            if abs(da - db) <= 1:        # covered by hard factors above
                continue
            va, vb = variables[(pa, da)], variables[(pb, db)]
            U = _same_worker_matrix(va, vb, -2 * inst.fairness_lambda)
            if U is not None:
                binary.append(BinaryFactor(va.slot, vb.slot, U, owner="fairness"))

    return FactorGraph(variables=variables, unary=unary, binary=binary)
