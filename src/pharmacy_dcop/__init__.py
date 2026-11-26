"""Multi-Agent System for fair, constraint-aware pharmacy night-shift
scheduling, formulated as a DCOP and solved with Max-Sum."""

from .baseline import solve_centralised
from .dynamics import disrupt, repair
from .explain import candidate_breakdown, explain
from .factor_graph import build_factor_graph
from .maxsum import MaxSum
from .metrics import global_utility, report
from .model import generate_instance
from .real_data import build_bologna_case_study, prepare_bologna_data

__all__ = ["generate_instance", "build_factor_graph", "MaxSum",
           "solve_centralised", "global_utility", "report",
           "disrupt", "repair", "explain", "candidate_breakdown",
           "build_bologna_case_study", "prepare_bologna_data"]
