"""Shared reproducible experiment runner and seed-level uncertainty summaries."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from time import perf_counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fair_scheduling import solve, violations, audit
from fair_scheduling.scenarios import audit_scenario
from fair_scheduling.explain import objective_breakdown


def options(name):
    parser = argparse.ArgumentParser(description=name)
    parser.add_argument("--seeds", type=int, default=25)
    parser.add_argument("--time-limit", type=float, default=3.0)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "trustworthy_results")
    args = parser.parse_args()
    if args.seeds < 1 or args.time_limit <= 0:
        parser.error("seeds and time-limit must be positive")
    return args


def measured(inst, args, **kwargs):
    result = solve(inst, time_limit=args.time_limit, seed=inst.seed, **kwargs)
    row = {"status": result.status, "proven_optimal": result.proven_optimal,
           "seconds": result.wall_time, "objective": result.objective, "best_bound": result.best_bound,
           "legal": not violations(inst, result.assignment)}
    if result.status in {"OPTIMAL", "FEASIBLE"}:
        row.update(audit(inst, result.assignment))
        row["cost"] = objective_breakdown(inst, result.assignment, fairness=kwargs.get("fairness", "variance"),
                                          use_fte=kwargs.get("use_fte", True),
                                          fairness_weight=kwargs.get("fairness_weight"))["total_cost"]
    return result, row


def save(rows, args, name, group, metric):
    """Bootstrap independent seed means; repeated rows within a seed stay together."""
    args.output.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    for col in df.columns:
        if df[col].map(lambda x: isinstance(x, (dict, list))).any():
            df[col] = df[col].map(lambda x: json.dumps(x, sort_keys=True) if isinstance(x, (dict, list)) else x)
    df.to_csv(args.output / f"{name}.csv", index=False)
    numeric = [c for c in df.select_dtypes(include=["number", "bool"]).columns if c not in group + ["seed"]]
    summary = []
    rng = np.random.default_rng(2026)
    for key, part in df.groupby(group, dropna=False):
        key = key if isinstance(key, tuple) else (key,)
        for col in numeric:
            seed_means = part.groupby("seed")[col].mean().dropna().to_numpy(dtype=float)
            if not len(seed_means):
                continue
            boot = rng.choice(seed_means, (2000, len(seed_means)), replace=True).mean(axis=1)
            summary.append({**dict(zip(group, key)), "metric": col, "n_seeds": len(seed_means),
                            "mean": seed_means.mean(), "ci_low": np.quantile(boot, .025),
                            "ci_high": np.quantile(boot, .975)})
    summary = pd.DataFrame(summary)
    summary.to_csv(args.output / f"{name}_summary.csv", index=False)
    if len(summary) and (summary.metric == metric).any():
        plot = summary[summary.metric == metric]
        if "k" in group:
            facets = sorted(plot["kind"].unique()) if "kind" in group else [None]
            fig, axes = plt.subplots(1, len(facets), figsize=(6 * len(facets), 4.5), squeeze=False)
            hue = [g for g in group if g not in {"kind", "k"}]
            for ax, facet in zip(axes[0], facets):
                part = plot[plot["kind"] == facet] if facet is not None else plot
                for key, line in part.groupby(hue, dropna=False):
                    line = line.sort_values("k")
                    ax.errorbar(line.k, line["mean"],
                                yerr=np.vstack([np.maximum(0, line["mean"] - line.ci_low), np.maximum(0, line.ci_high - line["mean"])]),
                                fmt="o-", capsize=3, label=str(key))
                ax.set(xlabel="Number of disruption events", ylabel=metric, title=str(facet or name))
                ax.legend(title=" / ".join(hue), fontsize=8)
                if metric == "legal":
                    ax.set_ylim(0, 1.05)
            fig.suptitle("Seed means with 95% bootstrap intervals")
            fig.tight_layout()
            fig.savefig(args.output / f"{name}.png", dpi=150)
            plt.close(fig)
            print(f"{name}: {len(df)} rows -> {args.output}", flush=True)
            return df
        fig, ax = plt.subplots(figsize=(max(7, min(len(plot) * .35, 15)), 4.5))
        labels = [" / ".join(str(row[g]) for g in group) for _, row in plot.iterrows()]
        ax.errorbar(np.arange(len(plot)), plot["mean"],
                    yerr=np.vstack([np.maximum(0, plot["mean"] - plot.ci_low), np.maximum(0, plot.ci_high - plot["mean"])]),
                    fmt="o", capsize=3)
        ax.set_xticks(np.arange(len(plot)), labels, rotation=75, ha="right")
        ax.set_ylabel(metric)
        ax.set_title(f"{name}: seed means with 95% bootstrap intervals")
        fig.tight_layout()
        fig.savefig(args.output / f"{name}.png", dpi=150)
        plt.close(fig)
    print(f"{name}: {len(df)} rows -> {args.output}", flush=True)
    return df
