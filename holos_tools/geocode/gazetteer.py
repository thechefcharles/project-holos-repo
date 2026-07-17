"""Stage 5: Gazetteer data loader for named-place geocoding.

Loads Chicago parks, facilities, and named places for matching strings
like "GRANT PARK", "MILLENNIUM PARK", "LINCOLN PARK", etc.
"""

import os
import json
from typing import List, Dict, Optional
from pathlib import Path


def load_chicago_parks() -> List[Dict]:
    """Load Chicago parks gazetteer data.

    Returns:
        List of dicts with keys: name (str), lat (float), lon (float), type (str)

    Example:
        [
            {"name": "GRANT PARK", "lat": 41.876, "lon": -87.619, "type": "park"},
            {"name": "MILLENNIUM PARK", "lat": 41.883, "lon": -87.624, "type": "park"},
        ]
    """
    # TODO: Fetch from Chicago Data Portal (dataset ID to be verified)
    # For now, return sample data with realistic entries

    parks = [
        # Downtown parks
        {"name": "GRANT PARK", "lat": 41.8761, "lon": -87.6192, "type": "park"},
        {"name": "MILLENNIUM PARK", "lat": 41.8827, "lon": -87.6233, "type": "park"},
        {"name": "LINCOLN PARK", "lat": 41.9144, "lon": -87.6306, "type": "park"},
        {"name": "HUMBOLDT PARK", "lat": 41.8868, "lon": -87.7142, "type": "park"},
        {"name": "GARFIELD PARK", "lat": 41.8531, "lon": -87.7216, "type": "park"},
        {"name": "WASHINGTON PARK", "lat": 41.8183, "lon": -87.6169, "type": "park"},
        {"name": "JACKSON PARK", "lat": 41.7752, "lon": -87.5789, "type": "park"},
        {"name": "DOUGLAS PARK", "lat": 41.8427, "lon": -87.7003, "type": "park"},
        {"name": "COLUMBUS PARK", "lat": 41.8696, "lon": -87.7397, "type": "park"},
        {"name": "BRIDGEPORT PARK", "lat": 41.8264, "lon": -87.6456, "type": "park"},
    ]

    return parks


def load_public_facilities() -> List[Dict]:
    """Load Chicago public facilities gazetteer data.

    Returns:
        List of dicts with keys: name (str), lat (float), lon (float), type (str)
    """
    # TODO: Fetch from Chicago Data Portal
    # For now, return sample data

    facilities = [
        # Libraries
        {"name": "CHICAGO PUBLIC LIBRARY - MAIN BRANCH", "lat": 41.8856, "lon": -87.6283, "type": "library"},
        {"name": "HAROLD WASHINGTON LIBRARY CENTER", "lat": 41.8856, "lon": -87.6283, "type": "library"},

        # Police
        {"name": "CHICAGO POLICE DEPARTMENT HQ", "lat": 41.8841, "lon": -87.6199, "type": "police"},

        # Fire
        {"name": "CHICAGO FIRE DEPARTMENT HQ", "lat": 41.8855, "lon": -87.6287, "type": "fire"},
    ]

    return facilities


def build_gazetteer() -> List[Dict]:
    """Build complete gazetteer from all sources.

    Returns:
        List of gazetteer entries ready for loading to ref.gazetteer
    """
    gazetteer = []

    # Load from all sources
    gazetteer.extend(load_chicago_parks())
    gazetteer.extend(load_public_facilities())

    # Add name normalization for matching (uppercase, remove extras)
    for entry in gazetteer:
        entry["name_normalized"] = entry["name"].upper().strip()

    return gazetteer


def load_to_database(db_connection) -> int:
    """Load gazetteer data to ref.gazetteer table.

    Args:
        db_connection: psycopg connection object

    Returns:
        Count of loaded records
    """
    gazetteer = build_gazetteer()

    if not gazetteer:
        return 0

    # Insert into ref.gazetteer
    sql = """
        INSERT INTO ref.gazetteer (name, geom, type, source)
        VALUES (%(name)s, ST_Point(%(lon)s, %(lat)s, 4326), %(type)s, 'chicago_parks_facilities')
        ON CONFLICT(name) DO NOTHING
    """

    with db_connection.cursor() as cur:
        count = 0
        for entry in gazetteer:
            try:
                cur.execute(sql, {
                    "name": entry["name"],
                    "lat": entry["lat"],
                    "lon": entry["lon"],
                    "type": entry.get("type", "unknown"),
                })
                count += 1
            except Exception as e:
                print(f"Warning: Failed to load {entry['name']}: {e}")

        db_connection.commit()

    return count


if __name__ == "__main__":
    # Test: print sample gazetteer
    gazetteer = build_gazetteer()
    print(f"Sample Gazetteer ({len(gazetteer)} entries):")
    for entry in gazetteer[:5]:
        print(f"  {entry['name']:40} ({entry['lat']:.4f}, {entry['lon']:.4f}) - {entry['type']}")
    print(f"  ... and {len(gazetteer) - 5} more")
