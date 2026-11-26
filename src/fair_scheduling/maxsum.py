"""Max-Sum coordination on the scheduling factor graph.

Two vector-valued messages are exchanged on each graph edge:

* ``q(x -> f)`` sums messages received by variable ``x`` from factors other
  than ``f``.
* ``r(f -> x)`` maximises the factor utility and incoming ``q`` messages over
  the other variable's values while holding ``x`` fixed.

For a binary factor with utility matrix ``U``:

    r(f -> x)(v) = max_u [U[v, u] + q(y -> f)(u)]

The implementation applies damping and mean normalisation to reduce
oscillation on loopy graphs. After each iteration it evaluates both standard
and value-propagation decodings and retains the best complete assignment
observed so far.

Message passing is simulated synchronously in one Python process. Message
counts therefore represent algorithmic coordination cost rather than network
traffic from a physically distributed deployment. ``run(reset=False)`` keeps
existing messages and supports warm-started dynamic repair.
"""

from __future__ import annotations

import numpy as np

from .factor_graph import FactorGraph, Slot


class MaxSum:
    def __init__(self, graph: FactorGraph, damping: float = 0.5, seed: int = 0):
        self.g = graph
        self.damping = damping
        self.rng = np.random.default_rng(seed)
        self.messages_sent = 0
        self._init_messages()

    # ------------------------------------------------------------------ init
    def _init_messages(self) -> None:
        """All messages start at zero (the uninformative prior).
        Message storage:
          q[(fid, end)] : variable -> factor message
          r[(fid, end)] : factor  -> variable message
        where `end` is 0/1 for the two ends of a binary factor.
        """
        self.q: dict[tuple[int, int], np.ndarray] = {}
        self.r: dict[tuple[int, int], np.ndarray] = {}
        # tiny random noise breaks the perfect symmetry of identical slots —
        # without it, symmetric variables receive identical messages and
        # argmax ties are broken arbitrarily and unstably.
        self.noise: dict[Slot, np.ndarray] = {
            s: self.rng.uniform(0, 1e-3, len(v.domain))
            for s, v in self.g.variables.items()}

        for fid, f in enumerate(self.g.binary):
            na, nb = f.table.shape
            self.q[(fid, 0)] = np.zeros(na); self.q[(fid, 1)] = np.zeros(nb)
            self.r[(fid, 0)] = np.zeros(na); self.r[(fid, 1)] = np.zeros(nb)

        # Pre-index: for each variable, which (factor, end) pairs touch it,
        # and its total unary utility (unary factors never change messages —
        # they are constants added wherever the variable's belief is formed).
        self.touch: dict[Slot, list[tuple[int, int]]] = {s: [] for s in self.g.variables}
        for fid, f in enumerate(self.g.binary):
            self.touch[f.var_a].append((fid, 0))
            self.touch[f.var_b].append((fid, 1))

        self.unary_of: dict[Slot, np.ndarray] = {
            s: np.zeros(len(v.domain)) for s, v in self.g.variables.items()}
        for uf in self.g.unary:
            self.unary_of[uf.var] += uf.table

    # ----------------------------------------------------------------- steps
    def _belief(self, slot: Slot, exclude: tuple[int, int] | None = None) -> np.ndarray:
        """Sum of unary utility + all incoming r-messages (optionally leaving
        one factor out — that exclusion is precisely what makes it a
        *message* rather than a marginal)."""
        b = self.unary_of[slot] + self.noise[slot]
        for (fid, end) in self.touch[slot]:
            if (fid, end) != exclude:
                b = b + self.r[(fid, end)]
        return b

    def _totals(self) -> dict[Slot, np.ndarray]:
        """Compute each variable's unary utility and incoming ``r`` total.

        A ``q`` message excludes one incident ``r`` message. Computing the
        complete total once and subtracting that message avoids repeatedly
        traversing high-degree variables on dense fairness graphs.
        """
        total = {s: self.unary_of[s] + self.noise[s] for s in self.g.variables}
        for fid, f in enumerate(self.g.binary):
            total[f.var_a] = total[f.var_a] + self.r[(fid, 0)]
            total[f.var_b] = total[f.var_b] + self.r[(fid, 1)]
        return total

    def iterate(self) -> None:
        """One synchronous round: all q-messages, then all r-messages."""
        d = self.damping
        # ---- variable -> factor (via cached totals, see _totals)
        total = self._totals()
        for fid, f in enumerate(self.g.binary):
            for end, slot in ((0, f.var_a), (1, f.var_b)):
                msg = total[slot] - self.r[(fid, end)]
                msg = msg - msg.mean()                      # normalisation
                self.q[(fid, end)] = d * self.q[(fid, end)] + (1 - d) * msg
                self.messages_sent += 1
        # ---- factor -> variable
        for fid, f in enumerate(self.g.binary):
            U = f.table
            # to var_a: max over var_b of U[a, b] + q_b(b)
            ra = (U + self.q[(fid, 1)][None, :]).max(axis=1)
            # to var_b: max over var_a of U[a, b] + q_a(a)
            rb = (U + self.q[(fid, 0)][:, None]).max(axis=0)
            ra -= ra.mean(); rb -= rb.mean()
            self.r[(fid, 0)] = d * self.r[(fid, 0)] + (1 - d) * ra
            self.r[(fid, 1)] = d * self.r[(fid, 1)] + (1 - d) * rb
            self.messages_sent += 2

    def current_assignment(self) -> dict[Slot, int]:
        """Select each variable's highest-belief value independently.

        On dense hard-constraint cliques, near-tied beliefs can cause
        simultaneous choices to conflict. ``decode_vp`` provides a sequential
        alternative that accounts for already committed neighbours.
        """
        out = {}
        for slot, v in self.g.variables.items():
            out[slot] = v.domain[int(np.argmax(self._belief(slot)))]
        return out

    def decode_vp(self) -> dict[Slot, int]:
        """Decode sequentially using value propagation.

        Variables follow a deterministic order and maximise their belief plus
        utilities from already committed neighbours. A conflicting value then
        receives the corresponding hard-factor penalty. This models a local
        announcement phase; the current implementation executes it centrally
        within the single-process simulator.
        """
        # Deterministic ordering = (day, pharmacy): agents commit night by
        # night, which mirrors how a real rota would be announced.
        order = sorted(self.g.variables.keys(), key=lambda s: (s[1], s[0]))
        committed: dict[Slot, int] = {}
        # neighbour index: slot -> list of (fid, end_of_this_slot)
        for slot in order:
            v = self.g.variables[slot]
            score = self._belief(slot).copy()
            for (fid, end) in self.touch[slot]:
                f = self.g.binary[fid]
                other = f.var_b if end == 0 else f.var_a
                if other in committed:
                    w_other = committed[other]
                    ov = self.g.variables[other]
                    col = ov.index[w_other]
                    contrib = (f.table[:, col] if end == 0 else f.table[col, :])
                    score = score + contrib
            committed[slot] = v.domain[int(np.argmax(score))]
        return committed

    # ------------------------------------------------------------------- run
    def run(self, iterations: int = 60, evaluator=None, reset: bool = True):
        """Run Max-Sum; if `evaluator` is given, track the best-ever
        assignment (anytime behaviour). `reset=False` = warm restart."""
        if reset:
            self.messages_sent = 0
            self._init_messages()
        best, best_util, trace = None, -np.inf, []
        for it in range(iterations):
            self.iterate()
            if evaluator is not None:
                # anytime: evaluate BOTH decodings, keep the best ever seen.
                # VP decoding handles the hard cliques; plain decoding is
                # kept so experiments can measure how much VP actually buys.
                for a in (self.decode_vp(), self.current_assignment()):
                    u = evaluator(a)
                    if u > best_util:
                        best_util, best = u, dict(a)
                trace.append(best_util)
        return (best if best is not None else self.decode_vp()), best_util, trace
