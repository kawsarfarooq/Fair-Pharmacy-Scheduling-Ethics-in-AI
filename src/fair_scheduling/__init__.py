"""Trustworthy scheduling; legacy Max-Sum remains a comparison algorithm."""
from .model import Instance, Pharmacy, Worker, generate_instance
from .cpsat_solver import SolveResult, solve
from .safety import publish_schedule, violations
from .fairness import audit, efficiency_cost, worker_burdens

__all__ = ["Instance", "Pharmacy", "Worker", "generate_instance", "solve", "SolveResult",
           "publish_schedule", "violations", "audit", "efficiency_cost", "worker_burdens"]
