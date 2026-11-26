"""Regression tests for the Bologna-grounded E5 case study."""

from collections import Counter
from pathlib import Path

from pharmacy_dcop import build_bologna_case_study, build_factor_graph


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def test_bologna_processed_snapshot_is_complete():
    instance = build_bologna_case_study(DATA_DIR)

    assert len(instance.pharmacies) == 125
    assert len({pharmacy.source_id for pharmacy in instance.pharmacies}) == 125
    assert all(pharmacy.latitude is not None for pharmacy in instance.pharmacies)
    assert all(pharmacy.longitude is not None for pharmacy in instance.pharmacies)
    assert {pharmacy.district for pharmacy in instance.pharmacies} == set(range(6))
    assert instance.metadata["population_year"] == 2024
    assert instance.metadata["residents"] == 392_044
    assert instance.metadata["age_65_plus"] == 95_962


def test_bologna_case_uses_only_required_service_locations():
    instance = build_bologna_case_study(DATA_DIR)
    slots_by_night = Counter(day for _, day in instance.slots)

    assert len(instance.slots) == 14 * 8
    assert set(slots_by_night.values()) == {8}
    assert len(instance.workers) == 24

    graph = build_factor_graph(instance)
    assert set(graph.variables) == set(instance.slots)
    assert len(graph.variables) == 112


def test_bologna_slot_policy_covers_every_district_each_night():
    instance = build_bologna_case_study(DATA_DIR)
    district_by_pharmacy = {
        pharmacy.pid: pharmacy.district for pharmacy in instance.pharmacies
    }

    for day in range(instance.horizon):
        covered = {
            district_by_pharmacy[pid]
            for pid, slot_day in instance.slots
            if slot_day == day
        }
        assert covered == set(range(6))
