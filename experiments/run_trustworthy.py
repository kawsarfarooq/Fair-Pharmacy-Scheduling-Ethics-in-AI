"""Run every evaluation sequentially to avoid competing timing measurements."""
import importlib.metadata
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from trustworthy_common import options


def main():
    args = options("Run all trustworthy-scheduling experiments")
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {"seeds": list(range(args.seeds)), "time_limit_per_solve": args.time_limit,
                "python": sys.version, "platform": platform.platform(),
                "packages": {p: importlib.metadata.version(p) for p in ("ortools", "numpy", "pandas", "matplotlib")},
                "solver_workers": 1, "scenario": "2 pharmacies, 8 workers, 7 nights, 2 synthetic districts",
                "intervals": "2000 seed-cluster bootstrap resamples, percentile 95%; not simultaneous intervals"}
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "src" / "fair_scheduling").glob("*.py")) + sorted((root / "experiments").glob("*.py"))
    manifest["source_sha256"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for name in ("f1_fairness_definitions", "f2_pareto_front", "f3_group_audit", "r1_stress_test",
                 "r2_repair_strategies", "r3_strategic_prefs", "x1_explanation_comparison"):
        subprocess.run([sys.executable, str(Path(__file__).with_name(name + ".py")),
                        "--seeds", str(args.seeds), "--time-limit", str(args.time_limit),
                        "--output", str(args.output.resolve())], check=True)


if __name__ == "__main__":
    main()
