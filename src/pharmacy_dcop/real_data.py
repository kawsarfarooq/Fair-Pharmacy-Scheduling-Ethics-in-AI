"""Bologna-grounded case-study data preparation and instance construction.

Public pharmacy locations and district demographics are processed into small,
versioned tables. Worker availability and preferences remain synthetic. The
demographic data defines an experimental service-allocation scenario; it is
not interpreted as observed night-pharmacy demand.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .model import Instance, Pharmacy, Worker


DISTRICT_NAMES = [
    "Borgo Panigale - Reno",
    "Navile",
    "Porto - Saragozza",
    "San Donato - San Vitale",
    "Santo Stefano",
    "Savena",
]
DISTRICT_ID = {name: i for i, name in enumerate(DISTRICT_NAMES)}

BOLOGNA_ADJACENCY = {
    0: {1, 2},
    1: {0, 2, 3},
    2: {0, 1, 4},
    3: {1, 4, 5},
    4: {2, 3, 5},
    5: {3, 4},
}

SOURCE_URLS = {
    "pharmacies": (
        "https://opendata.comune.bologna.it/explore/dataset/farmacie/"
    ),
    "population": (
        "https://opendata.comune.bologna.it/explore/dataset/"
        "popolazione-residente-per-eta-sesso-cittadinanza-quartiere-zona-"
        "area-statistica-/"
    ),
    "districts": (
        "https://opendata.comune.bologna.it/explore/dataset/"
        "quartieri-di-bologna/export/"
    ),
}


@dataclass(frozen=True)
class DistrictPopulation:
    district_id: int
    district: str
    year: int
    residents: int
    age_65_plus: int

    @property
    def age_65_plus_share(self) -> float:
        return self.age_65_plus / self.residents


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_coordinate(value: str) -> float:
    return float(value.strip().replace(",", "."))


def _point_in_ring(longitude: float, latitude: float, ring: list[list[float]]) -> bool:
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = previous[:2]
        x2, y2 = current[:2]
        crosses = (y1 > latitude) != (y2 > latitude)
        if crosses:
            boundary_x = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < boundary_x:
                inside = not inside
        previous = current
    return inside


def _point_in_polygon(longitude: float, latitude: float,
                      polygon: list[list[list[float]]]) -> bool:
    return (_point_in_ring(longitude, latitude, polygon[0])
            and not any(_point_in_ring(longitude, latitude, hole)
                        for hole in polygon[1:]))


def _point_in_geometry(longitude: float, latitude: float,
                       geometry: dict) -> bool:
    if geometry["type"] == "Polygon":
        return _point_in_polygon(longitude, latitude, geometry["coordinates"])
    if geometry["type"] == "MultiPolygon":
        return any(_point_in_polygon(longitude, latitude, polygon)
                   for polygon in geometry["coordinates"])
    raise ValueError(f"Unsupported geometry type: {geometry['type']}")


def _load_district_geometries(path: Path) -> list[tuple[int, str, dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    districts = []
    for feature in data["features"]:
        name = feature["properties"]["quartiere"].strip()
        if name not in DISTRICT_ID:
            raise ValueError(f"Unexpected quartiere in GeoJSON: {name}")
        districts.append((DISTRICT_ID[name], name, feature["geometry"]))
    if {district_id for district_id, _, _ in districts} != set(range(6)):
        raise ValueError("Quartiere GeoJSON must contain Bologna's six districts")
    return districts


def _prepare_pharmacies(pharmacies_path: Path,
                        districts_path: Path) -> list[dict[str, object]]:
    """Map the Comune pharmacy snapshot to official quartiere polygons."""
    geometries = _load_district_geometries(districts_path)
    records: list[dict[str, object]] = []
    unresolved: list[str] = []
    seen_ids: set[str] = set()

    with pharmacies_path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            source_id = row["civkey"].strip()
            if source_id in seen_ids:
                raise ValueError(f"Duplicate pharmacy id: {source_id}")
            seen_ids.add(source_id)

            try:
                latitude_text, longitude_text = row["geo_point_2d"].split(",")
                latitude = _parse_coordinate(latitude_text)
                longitude = _parse_coordinate(longitude_text)
            except (ValueError, KeyError):
                unresolved.append(source_id)
                continue

            district = next(
                ((district_id, name) for district_id, name, geometry in geometries
                 if _point_in_geometry(longitude, latitude, geometry)),
                None,
            )
            if district is None:
                unresolved.append(source_id)
                continue

            district_id, district_name = district
            records.append({
                "source_id": source_id,
                "name": row["farmacia"].strip(),
                "address": row["indirizzo"].strip(),
                "latitude": latitude,
                "longitude": longitude,
                "district_id": district_id,
                "district": district_name,
            })

    if unresolved:
        raise ValueError(
            "Bologna pharmacies could not be mapped to a quartiere: "
            + ", ".join(unresolved)
        )
    records.sort(key=lambda row: str(row["source_id"]))
    return records


def _prepare_population(path: Path, year: int | None) -> list[DistrictPopulation]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream, delimiter=";")
        # The downloaded file currently contains two UTF-8 BOM markers.
        reader.fieldnames = [name.lstrip("\ufeff").strip()
                             for name in reader.fieldnames or []]
        rows = list(reader)
    available_years = {int(row["Anno"]) for row in rows}
    selected_year = max(available_years) if year is None else year
    if selected_year not in available_years:
        raise ValueError(f"Population year {selected_year} is not available")

    residents = defaultdict(int)
    older = defaultdict(int)
    for row in rows:
        if int(row["Anno"]) != selected_year:
            continue
        name = row["Quartiere"].strip()
        if name not in DISTRICT_ID:
            continue
        value = int(row["Residenti"])
        district_id = DISTRICT_ID[name]
        residents[district_id] += value
        if row["Età"].strip() == "65 e oltre":
            older[district_id] += value

    result = [
        DistrictPopulation(
            district_id=district_id,
            district=name,
            year=selected_year,
            residents=residents[district_id],
            age_65_plus=older[district_id],
        )
        for name, district_id in DISTRICT_ID.items()
    ]
    if any(item.residents <= 0 or item.age_65_plus <= 0 for item in result):
        raise ValueError("Population data is incomplete for one or more quartieri")
    return result


def prepare_bologna_data(pharmacies_csv: str | Path,
                         population_csv: str | Path,
                         districts_geojson: str | Path,
                         output_dir: str | Path,
                         snapshot_date: date = date(2026, 7, 21),
                         population_year: int | None = None) -> dict[str, object]:
    """Create compact, reproducible Bologna case-study input tables."""
    registry_path = Path(pharmacies_csv)
    population_path = Path(population_csv)
    districts_path = Path(districts_geojson)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    pharmacies = _prepare_pharmacies(registry_path, districts_path)
    population = _prepare_population(population_path, population_year)

    pharmacy_output = output_path / "bologna_pharmacies.csv"
    with pharmacy_output.open("w", newline="", encoding="utf-8") as stream:
        fields = ["pid", "source_id", "name", "address", "latitude",
                  "longitude", "district_id", "district"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for pid, row in enumerate(pharmacies):
            writer.writerow({"pid": pid, **row})

    population_output = output_path / "bologna_demographics.csv"
    with population_output.open("w", newline="", encoding="utf-8") as stream:
        fields = ["district_id", "district", "year", "residents",
                  "age_65_plus", "age_65_plus_share"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in population:
            writer.writerow({
                "district_id": item.district_id,
                "district": item.district,
                "year": item.year,
                "residents": item.residents,
                "age_65_plus": item.age_65_plus,
                "age_65_plus_share": f"{item.age_65_plus_share:.6f}",
            })

    metadata: dict[str, object] = {
        "case_study": "Bologna-grounded demographic sensitivity scenario",
        "pharmacy_snapshot_date": snapshot_date.isoformat(),
        "population_year": population[0].year,
        "listed_pharmacies": len(pharmacies),
        "districts": len(population),
        "residents": sum(item.residents for item in population),
        "age_65_plus": sum(item.age_65_plus for item in population),
        "source_urls": SOURCE_URLS,
        "source_sha256": {
            "farmacie_bologna.csv": _sha256(registry_path),
            "popolazione.csv": _sha256(population_path),
            "quartieri.geojson": _sha256(districts_path),
        },
        "limitations": [
            "The municipal pharmacy list is not a night-duty schedule.",
            "Age 65+ population is a sensitivity proxy, not observed demand.",
            "Worker availability, preferences, and home districts are synthetic.",
        ],
    }
    (output_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata


def _allocate_district_slots(population: list[DistrictPopulation],
                             slots_per_night: int) -> dict[int, int]:
    if slots_per_night < len(population):
        raise ValueError("slots_per_night must allow at least one slot per district")
    allocation = {item.district_id: 1 for item in population}
    remaining = slots_per_night - len(population)
    if remaining == 0:
        return allocation

    total_need = sum(item.age_65_plus for item in population)
    raw = {item.district_id: remaining * item.age_65_plus / total_need
           for item in population}
    for district_id, value in raw.items():
        allocation[district_id] += math.floor(value)
    left = slots_per_night - sum(allocation.values())
    order = sorted(raw, key=lambda district_id: raw[district_id] % 1,
                   reverse=True)
    for district_id in order[:left]:
        allocation[district_id] += 1
    return allocation


def build_bologna_case_study(data_dir: str | Path,
                             horizon: int = 14,
                             slots_per_night: int = 8,
                             worker_ratio: float = 3.0,
                             seed: int = 42,
                             fairness_lambda: float = 1.0) -> Instance:
    """Build a hybrid E5 instance from processed public and synthetic data."""
    data_path = Path(data_dir)
    with (data_path / "bologna_pharmacies.csv").open(
            newline="", encoding="utf-8") as stream:
        pharmacy_rows = list(csv.DictReader(stream))
    with (data_path / "bologna_demographics.csv").open(
            newline="", encoding="utf-8") as stream:
        demographic_rows = list(csv.DictReader(stream))

    pharmacies = [
        Pharmacy(
            pid=int(row["pid"]),
            district=int(row["district_id"]),
            name=row["name"],
            source_id=row["source_id"],
            address=row["address"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
        )
        for row in pharmacy_rows
    ]
    population = [
        DistrictPopulation(
            district_id=int(row["district_id"]),
            district=row["district"],
            year=int(row["year"]),
            residents=int(row["residents"]),
            age_65_plus=int(row["age_65_plus"]),
        )
        for row in demographic_rows
    ]
    allocation = _allocate_district_slots(population, slots_per_night)

    by_district: dict[int, list[Pharmacy]] = defaultdict(list)
    for pharmacy in pharmacies:
        by_district[pharmacy.district].append(pharmacy)
    for pool in by_district.values():
        pool.sort(key=lambda pharmacy: pharmacy.source_id)

    required_slots = []
    for day in range(horizon):
        for district_id in range(len(DISTRICT_NAMES)):
            pool = by_district[district_id]
            count = allocation[district_id]
            if len(pool) < count:
                raise ValueError(f"Not enough pharmacies in district {district_id}")
            offset = day * count
            for index in range(count):
                pharmacy = pool[(offset + index) % len(pool)]
                required_slots.append((pharmacy.pid, day))

    n_workers = max(math.ceil(worker_ratio * slots_per_night),
                    2 * slots_per_night + 2)
    home_cycle = [district_id for district_id, count in allocation.items()
                  for _ in range(count)]
    rng = random.Random(seed)
    total_slots = len(required_slots)
    target = round(total_slots / n_workers)
    workers = []
    for worker_id in range(n_workers):
        home = home_cycle[worker_id % len(home_cycle)]
        unavailable = {day for day in range(horizon) if rng.random() < 0.15}
        disliked = {day for day in range(horizon)
                    if day not in unavailable and rng.random() < 0.10}
        workers.append(Worker(
            wid=worker_id,
            district=home,
            name=f"W-{worker_id:02d}",
            unavailable=unavailable,
            disliked=disliked,
            target_shifts=target,
        ))

    metadata_path = data_path / "metadata.json"
    source_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata = {
        **source_metadata,
        "data_mode": "real infrastructure and demographics; synthetic workforce",
        "slot_policy": (
            "At least one service location per quartiere; additional locations "
            "allocated by age-65+ population proxy and rotated nightly."
        ),
        "slots_per_night": slots_per_night,
        "district_slot_allocation": {
            DISTRICT_NAMES[district_id]: count
            for district_id, count in allocation.items()
        },
        "synthetic_workers": n_workers,
    }
    return Instance(
        pharmacies=pharmacies,
        workers=workers,
        horizon=horizon,
        adjacency=BOLOGNA_ADJACENCY,
        seed=seed,
        required_slots=required_slots,
        metadata=metadata,
        fairness_lambda=fairness_lambda,
    )
