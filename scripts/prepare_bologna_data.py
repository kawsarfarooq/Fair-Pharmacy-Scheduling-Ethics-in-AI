"""Prepare compact Bologna case-study tables from official raw downloads."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from pharmacy_dcop.real_data import prepare_bologna_data


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=root / "data" / "raw")
    parser.add_argument("--output-dir", type=Path,
                        default=root / "data" / "processed")
    parser.add_argument("--snapshot-date", type=date.fromisoformat,
                        default=date(2026, 7, 21))
    parser.add_argument("--population-year", type=int, default=None)
    args = parser.parse_args()

    metadata = prepare_bologna_data(
        pharmacies_csv=args.raw_dir / "farmacie_bologna.csv",
        population_csv=args.raw_dir / "popolazione.csv",
        districts_geojson=args.raw_dir / "quartieri.geojson",
        output_dir=args.output_dir,
        snapshot_date=args.snapshot_date,
        population_year=args.population_year,
    )
    print(f"Prepared {metadata['listed_pharmacies']} pharmacies")
    print(f"Population year: {metadata['population_year']}")
    print(f"Residents: {metadata['residents']}")
    print(f"Age 65+: {metadata['age_65_plus']}")
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
