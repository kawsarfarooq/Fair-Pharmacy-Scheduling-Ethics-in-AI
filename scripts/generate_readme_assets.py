"""Generate the README methodology figure and local technology badges."""
from html import escape
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]


def badge(name, label, value, colour):
    left = len(label) * 7 + 18
    right = len(value) * 7 + 18
    width = left + right
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="24" role="img" aria-label="{escape(label)}: {escape(value)}">
<title>{escape(label)}: {escape(value)}</title>
<clipPath id="r"><rect width="{width}" height="24" rx="4"/></clipPath>
<g clip-path="url(#r)"><rect width="{left}" height="24" fill="#334155"/><rect x="{left}" width="{right}" height="24" fill="{colour}"/></g>
<g fill="white" text-anchor="middle" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11">
<text x="{left / 2}" y="16">{escape(label)}</text><text x="{left + right / 2}" y="16">{escape(value)}</text></g></svg>
'''
    path = ROOT / "docs" / "badges" / f"{name}.svg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8", newline="\n")


def methodology():
    fig, ax = plt.subplots(figsize=(14, 5.8), facecolor="#f8fafc")
    ax.set(xlim=(0, 14), ylim=(0, 5.8))
    ax.axis("off")

    def box(x, y, width, height, title, body, colour):
        ax.add_patch(FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0.05,rounding_size=0.12",
                                   facecolor="white", edgecolor=colour, linewidth=1.6))
        ax.text(x + .2, y + height - .35, title, color=colour, fontsize=11, weight="bold", va="top")
        ax.text(x + .2, y + height - .86, body, color="#334155", fontsize=9.5, va="top", linespacing=1.65)

    def arrow(a, b, colour="#64748b"):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=15,
                                    linewidth=1.6, color=colour))

    ax.text(.25, 5.48, "FROM STAFFING REQUIREMENTS TO AN AUDITED SCHEDULE", fontsize=14,
            weight="bold", color="#0f172a", va="top")
    box(.25, 2.65, 2.85, 2.1, "1  Problem inputs", "Required pharmacy-night slots\nAvailability and rest rules\nPreferences, contracts, travel", "#2563eb")
    box(3.8, 2.65, 2.85, 2.1, "2  Exact optimisation", "CP-SAT scheduling model\nFour fairness objectives\nStatus, objective and bound", "#0f766e")
    box(7.35, 2.65, 2.85, 2.1, "3  Independent safety", "Coverage and eligibility\nBooking and rest validation\nReject invalid candidates", "#b45309")
    box(10.9, 2.65, 2.85, 2.1, "4  Decision support", "Validated candidate rota\nWorker and district audits\nInterpretable explanations", "#7c3aed")
    for x in (3.1, 6.65, 10.2):
        arrow((x + .06, 3.7), (x + .62, 3.7))
    box(.25, .35, 6.4, 1.45, "Disruption and repair", "Worker absence or demand change\nFull / minimal-change / Max-Sum repair", "#0f766e")
    box(7.35, .35, 6.4, 1.45, "Reproducible evaluation", "25 seeds · 7 experiments\nCSV records, confidence intervals and plots", "#7c3aed")
    arrow((5.2, 1.85), (5.2, 2.55), "#0f766e")
    arrow((12.3, 2.55), (12.3, 1.85), "#7c3aed")
    destination = ROOT / "docs" / "images"
    destination.mkdir(parents=True, exist_ok=True)
    fig.savefig(destination / "methodology.png", dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    fig.savefig(destination / "methodology.svg", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


if __name__ == "__main__":
    badge("python", "Python", "3.10+", "#2563eb")
    badge("ortools", "OR-Tools", "CP-SAT", "#0f766e")
    badge("task", "Focus", "Trustworthy AI", "#7c3aed")
    methodology()
    print("Generated README badges and methodology figure.")
