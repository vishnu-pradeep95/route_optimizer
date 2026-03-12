#!/usr/bin/env python3
"""Build Kerala place name dictionary from OSM Overpass + India Post APIs + manual seeds.

Generates data/place_names_vatakara.json with 200+ place name entries for the
Vatakara delivery zone. Used by the dictionary-powered address splitter in
core/data_import/address_splitter.py.

Usage:
    python scripts/build_place_dictionary.py            # Full build (calls APIs)
    python scripts/build_place_dictionary.py --dry-run   # Use cached data if available
    python scripts/build_place_dictionary.py --help      # Show help
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEPOT_LAT = 11.6244
DEPOT_LON = 75.5796
RADIUS_M = 30000
RADIUS_KM = RADIUS_M // 1000

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "place_names_vatakara.json"
SAMPLE_CSV_PATH = PROJECT_ROOT / "data" / "sample_cdcms_export.csv"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_QUERY = f"""
[out:json][timeout:30];
(
  node["place"~"^(village|hamlet|town|neighbourhood|suburb|locality)$"]
    (around:{RADIUS_M},{DEPOT_LAT},{DEPOT_LON});
);
out body;
"""

VATAKARA_PINS = ["673101", "673102", "673103", "673104", "673105", "673106"]
INDIA_POST_URL = "https://api.postalpincode.in/pincode/{pin}"

# Manual seeds: CDCMS-specific names not found in either API
MANUAL_SEEDS = [
    {"name": "VALLIKKADU", "aliases": ["VALLIKADU", "VALLIKKAD"], "type": "locality"},
    {"name": "BALAVADI", "type": "locality"},
    {"name": "KAINATY", "aliases": ["KAINATTY"], "type": "locality"},
    {"name": "K.T.BAZAR", "aliases": ["KT BAZAR", "KTBAZAR", "K T BAZAR"], "type": "locality"},
    {"name": "SARAMBI", "type": "locality"},
    {"name": "EYYAMKUTTI", "type": "locality"},
    {"name": "PALLIVATAKARA", "type": "locality"},
    {"name": "MEATHALA", "type": "locality"},
    {"name": "KALARIKKANDI", "type": "locality"},
    {"name": "PADINJARA", "type": "locality"},
    {"name": "ONTHAMKAINATTY", "aliases": ["ONTHAM KAINATTY"], "type": "locality"},
    {"name": "SREESHYLAM", "type": "house_name"},
    # Compound area names critical for longest-match splitting
    {"name": "CHORODE EAST", "aliases": ["CHORODEEAST"], "type": "locality"},
    {"name": "MUTTUNGAL WEST", "aliases": ["MUTTUNGALWEST"], "type": "locality"},
    {"name": "RAYARANGOTH", "type": "locality"},
    {"name": "MUTTUNGAL", "aliases": ["MUTUNGAL"], "type": "locality"},
    {"name": "CHORODE", "type": "locality"},
    {"name": "VATAKARA", "aliases": ["VADAKARA"], "type": "town"},
    {"name": "MUTTUNGALPARA", "type": "locality"},
    {"name": "MADAMCHORODE", "aliases": ["MADAM CHORODE"], "type": "locality"},
    {"name": "CHEKKIPURATH", "type": "locality"},
]

MAX_RETRIES = 3
RETRY_DELAY_S = 2

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def _request_with_retry(method: str, url: str, **kwargs) -> requests.Response | None:
    """Make an HTTP request with retry logic.  Returns None on total failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.request(method, url, timeout=60, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            log.warning("Attempt %d/%d for %s failed: %s", attempt, MAX_RETRIES, url, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S)
    return None


def fetch_osm_places() -> list[dict]:
    """Fetch place nodes from OSM Overpass API within radius of depot."""
    log.info("Fetching OSM place nodes (radius=%dkm from depot)...", RADIUS_KM)
    resp = _request_with_retry("POST", OVERPASS_URL, data={"data": OVERPASS_QUERY})
    if resp is None:
        log.warning("OSM Overpass API unavailable -- skipping OSM data")
        return []

    data = resp.json()
    elements = data.get("elements", [])
    log.info("OSM returned %d place nodes", len(elements))

    entries = []
    for elem in elements:
        tags = elem.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue
        entries.append({
            "name": name.upper(),
            "name_original": name,
            "name_ml": tags.get("name:ml"),
            "type": tags.get("place", "locality"),
            "source": "osm_overpass",
            "lat": elem.get("lat"),
            "lon": elem.get("lon"),
            "pincode": None,
            "aliases": [],
            "coordinates_approximate": False,
        })
    return entries


def fetch_india_post_offices() -> list[dict]:
    """Fetch post offices from India Post API for Vatakara PIN codes."""
    log.info("Fetching India Post offices for PINs %s...", ", ".join(VATAKARA_PINS))
    entries = []
    seen_names: set[str] = set()

    for pin in VATAKARA_PINS:
        url = INDIA_POST_URL.format(pin=pin)
        resp = _request_with_retry("GET", url)
        if resp is None:
            log.warning("India Post API unavailable for PIN %s -- skipping", pin)
            continue

        data = resp.json()
        if not data or data[0].get("Status") != "Success":
            log.warning("No data for PIN %s", pin)
            continue

        post_offices = data[0].get("PostOffice") or []
        for po in post_offices:
            name = po.get("Name", "").strip().upper()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            entries.append({
                "name": name,
                "name_original": po.get("Name", "").strip(),
                "name_ml": None,
                "type": "post_office",
                "source": "india_post",
                "lat": None,  # India Post API does NOT return coordinates
                "lon": None,
                "pincode": po.get("Pincode"),
                "aliases": [],
                "coordinates_approximate": True,
            })

    log.info("India Post returned %d unique post offices", len(entries))
    return entries


def get_manual_seeds() -> list[dict]:
    """Return hardcoded CDCMS-specific place names not found in either API."""
    entries = []
    for seed in MANUAL_SEEDS:
        entries.append({
            "name": seed["name"].upper(),
            "name_original": seed["name"],
            "name_ml": None,
            "type": seed.get("type", "locality"),
            "source": "manual_seed",
            "lat": None,
            "lon": None,
            "pincode": None,
            "aliases": [a.upper() for a in seed.get("aliases", [])],
            "coordinates_approximate": True,
        })
    return entries


# ---------------------------------------------------------------------------
# Merging and deduplication
# ---------------------------------------------------------------------------
def _fuzzy_match(name_a: str, name_b: str, threshold: float = 85.0) -> bool:
    """Check if two names are fuzzy duplicates using RapidFuzz."""
    score = fuzz.ratio(name_a, name_b, score_cutoff=threshold)
    return score > 0


def merge_and_deduplicate(
    osm: list[dict],
    india_post: list[dict],
    seeds: list[dict],
) -> list[dict]:
    """Merge three sources and deduplicate using fuzzy matching.

    Priority order for coordinate data: OSM > India Post > seeds.
    If an India Post or seed entry fuzzy-matches an OSM entry, OSM coordinates
    are assigned to the merged result.
    """
    log.info("Merging: %d OSM + %d India Post + %d seeds", len(osm), len(india_post), len(seeds))

    # Start with OSM entries (they have the best coordinates)
    merged: dict[str, dict] = {}
    for entry in osm:
        name = entry["name"]
        if name not in merged:
            merged[name] = entry.copy()

    # Merge India Post entries
    for entry in india_post:
        name = entry["name"]
        # Check exact match
        if name in merged:
            # Add pincode to existing entry
            if entry.get("pincode") and not merged[name].get("pincode"):
                merged[name]["pincode"] = entry["pincode"]
            continue

        # Check fuzzy match against existing entries
        matched = False
        for existing_name, existing_entry in merged.items():
            if _fuzzy_match(name, existing_name):
                # Merge: keep OSM coordinates, add pincode and alias
                if entry.get("pincode") and not existing_entry.get("pincode"):
                    existing_entry["pincode"] = entry["pincode"]
                if name != existing_name and name not in existing_entry.get("aliases", []):
                    existing_entry.setdefault("aliases", []).append(name)
                matched = True
                break

        if not matched:
            # New entry -- use depot coordinates as placeholder
            entry_copy = entry.copy()
            entry_copy["lat"] = DEPOT_LAT
            entry_copy["lon"] = DEPOT_LON
            entry_copy["coordinates_approximate"] = True
            merged[name] = entry_copy

    # Merge manual seeds
    for entry in seeds:
        name = entry["name"]
        seed_aliases = entry.get("aliases", [])

        # Check exact match (name or alias)
        if name in merged:
            # Add any new aliases from seed
            existing = merged[name]
            for alias in seed_aliases:
                if alias not in existing.get("aliases", []) and alias != existing["name"]:
                    existing.setdefault("aliases", []).append(alias)
            continue

        # Check if any alias matches
        alias_matched = False
        for alias in seed_aliases:
            if alias in merged:
                # Add seed name as alias to existing entry
                existing = merged[alias]
                if name not in existing.get("aliases", []) and name != existing["name"]:
                    existing.setdefault("aliases", []).append(name)
                alias_matched = True
                break

        if alias_matched:
            continue

        # Check fuzzy match
        matched = False
        for existing_name, existing_entry in merged.items():
            if _fuzzy_match(name, existing_name):
                # Add as alias
                if name not in existing_entry.get("aliases", []) and name != existing_name:
                    existing_entry.setdefault("aliases", []).append(name)
                for alias in seed_aliases:
                    if alias not in existing_entry.get("aliases", []) and alias != existing_name:
                        existing_entry.setdefault("aliases", []).append(alias)
                matched = True
                break

        if not matched:
            # New entry -- use depot coordinates as placeholder
            entry_copy = entry.copy()
            entry_copy["lat"] = DEPOT_LAT
            entry_copy["lon"] = DEPOT_LON
            entry_copy["coordinates_approximate"] = True
            merged[name] = entry_copy

    # Sort alphabetically by name
    sorted_entries = sorted(merged.values(), key=lambda e: e["name"])

    # Clean up entries: remove name_original from output (internal only)
    for entry in sorted_entries:
        entry.pop("name_original", None)

    log.info("After deduplication: %d entries", len(sorted_entries))
    return sorted_entries


# ---------------------------------------------------------------------------
# Coverage validation
# ---------------------------------------------------------------------------
def validate_coverage(entries: list[dict], sample_csv_path: Path) -> float:
    """Validate dictionary coverage against sample CDCMS area names.

    Returns coverage percentage (0-100).
    """
    if not sample_csv_path.exists():
        log.warning("Sample CSV not found at %s -- skipping coverage validation", sample_csv_path)
        return 100.0  # Don't block if no sample data

    # Extract distinct area names from CSV
    area_names: set[str] = set()
    with open(sample_csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            area = row.get("AreaName", "").strip().upper()
            if area:
                area_names.add(area)

    if not area_names:
        log.warning("No area names found in sample CSV")
        return 100.0

    # Build lookup set from dictionary (names + aliases)
    dict_names: set[str] = set()
    dict_entries_list: list[str] = []
    for entry in entries:
        dict_names.add(entry["name"])
        dict_entries_list.append(entry["name"])
        for alias in entry.get("aliases", []):
            dict_names.add(alias)
            dict_entries_list.append(alias)

    # Check coverage
    covered = set()
    not_covered = set()

    for area in area_names:
        # Exact match
        if area in dict_names:
            covered.add(area)
            continue

        # Fuzzy match (85% threshold for 7+ char names)
        fuzzy_matched = False
        for dict_name in dict_entries_list:
            name_len = max(len(area), len(dict_name))
            if name_len <= 4:
                threshold = 95
            elif name_len <= 6:
                threshold = 90
            else:
                threshold = 85

            if fuzz.ratio(area, dict_name, score_cutoff=threshold) > 0:
                covered.add(area)
                fuzzy_matched = True
                break

        if not fuzzy_matched:
            not_covered.add(area)

    coverage_pct = (len(covered) / len(area_names)) * 100

    # Print coverage report
    log.info("=" * 60)
    log.info("CDCMS AREA NAME COVERAGE REPORT")
    log.info("=" * 60)
    log.info("Total distinct area names in sample: %d", len(area_names))
    log.info("Covered: %d (%.1f%%)", len(covered), coverage_pct)
    if covered:
        for name in sorted(covered):
            log.info("  [OK] %s", name)
    if not_covered:
        log.info("NOT covered: %d", len(not_covered))
        for name in sorted(not_covered):
            log.info("  [MISSING] %s", name)
    log.info("=" * 60)

    return coverage_pct


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Kerala place name dictionary from OSM + India Post + manual seeds."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use cached JSON if available instead of calling APIs.",
    )
    args = parser.parse_args()

    if args.dry_run and OUTPUT_PATH.exists():
        log.info("Dry-run: loading cached dictionary from %s", OUTPUT_PATH)
        with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        log.info("Cached dictionary has %d entries", data["metadata"]["entry_count"])

        # Still run coverage validation
        coverage = validate_coverage(data["entries"], SAMPLE_CSV_PATH)
        if coverage < 80:
            log.error("Coverage %.1f%% is below 80%% threshold!", coverage)
            sys.exit(1)
        log.info("Dry-run complete. Coverage: %.1f%%", coverage)
        return

    if args.dry_run:
        log.info("Dry-run: no cached dictionary found. Would fetch from APIs:")
        log.info("  - OSM Overpass: %d place nodes (30km radius)", 367)
        log.info("  - India Post: %d PINs (%s)", len(VATAKARA_PINS), ", ".join(VATAKARA_PINS))
        log.info("  - Manual seeds: %d entries", len(MANUAL_SEEDS))
        log.info("  - Output: %s", OUTPUT_PATH)
        return

    # Fetch from all sources
    osm_entries = fetch_osm_places()
    india_post_entries = fetch_india_post_offices()
    seed_entries = get_manual_seeds()

    # Merge and deduplicate
    entries = merge_and_deduplicate(osm_entries, india_post_entries, seed_entries)

    # Build output
    output = {
        "metadata": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "depot": {"lat": DEPOT_LAT, "lon": DEPOT_LON},
            "radius_km": RADIUS_KM,
            "sources": ["osm_overpass", "india_post", "manual_seeds"],
            "entry_count": len(entries),
        },
        "entries": entries,
    }

    # Write JSON
    os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    log.info("Dictionary written to %s (%d entries)", OUTPUT_PATH, len(entries))

    # Validate coverage
    coverage = validate_coverage(entries, SAMPLE_CSV_PATH)
    if coverage < 80:
        log.error("Coverage %.1f%% is below 80%% threshold!", coverage)
        sys.exit(1)

    log.info("Build complete. %d entries, %.1f%% coverage.", len(entries), coverage)


if __name__ == "__main__":
    main()
