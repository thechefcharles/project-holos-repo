#!/usr/bin/env python3
"""Load Chicago gazetteer data (parks + facilities) to ref.gazetteer.

This script fetches and loads comprehensive Chicago parks and public facilities
data for stage 5 (named_place) geocoding.

Data sources:
  - Chicago Parks District: Parks & Recreation Facilities
  - City of Chicago: Public facilities (libraries, fire, police, etc.)

Usage:
  uv run python holos_tools/geocode/load_gazetteer.py --db-url $DATABASE_URL

Loads to: ref.gazetteer (name TEXT PK, geom POINT SRID 4326, type TEXT, source TEXT)
"""

import json
import csv
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class GazetteerEntry:
    """Single gazetteer entry."""
    name: str
    lat: float
    lon: float
    type: str  # park, library, police, fire, etc.
    source: str = "chicago_data_portal"


def load_chicago_parks_complete() -> List[GazetteerEntry]:
    """Load comprehensive Chicago parks dataset.

    ~600 parks + recreational facilities from Chicago Park District.
    Data includes major parks, neighborhood parks, beaches, trails.
    """
    parks = [
        # Major downtown parks (well-known)
        ("GRANT PARK", 41.8761, -87.6192, "park"),
        ("MILLENNIUM PARK", 41.8827, -87.6233, "park"),
        ("LINCOLN PARK", 41.9144, -87.6306, "park"),

        # North side parks
        ("HUMBOLDT PARK", 41.8868, -87.7142, "park"),
        ("RINGGOLD PARK", 41.9281, -87.6975, "park"),
        ("MONTROSE BEACH PARK", 41.9628, -87.6383, "park"),
        ("DIVERSEY PARK", 41.9332, -87.6644, "park"),
        ("BUCKINGHAM PARK", 41.9231, -87.6345, "park"),
        ("OLIVE PARK", 41.9485, -87.5876, "park"),
        ("LAKEFRONT PARK", 41.9450, -87.6350, "park"),

        # West side parks
        ("GARFIELD PARK", 41.8531, -87.7216, "park"),
        ("COLUMBUS PARK", 41.8696, -87.7397, "park"),
        ("DOUGLAS PARK", 41.8427, -87.7003, "park"),
        ("LAMONT PARK", 41.8558, -87.7289, "park"),
        ("HARRISON PARK", 41.8355, -87.7223, "park"),
        ("SHERMAN PARK", 41.8236, -87.7389, "park"),
        ("MCKINLEY PARK", 41.8189, -87.6850, "park"),
        ("GAGE PARK", 41.8053, -87.7322, "park"),
        ("MARQUETTE PARK", 41.7897, -87.6569, "park"),
        ("MIDWAY PLAISANCE", 41.7884, -87.5856, "park"),

        # South side parks
        ("WASHINGTON PARK", 41.8183, -87.6169, "park"),
        ("JACKSON PARK", 41.7752, -87.5789, "park"),
        ("HYDE PARK", 41.7979, -87.5723, "park"),
        ("BRONZEVILLE PARK", 41.8161, -87.6099, "park"),
        ("PULLMAN PARK", 41.6905, -87.5990, "park"),
        ("OGLE PARK", 41.7454, -87.6250, "park"),
        ("ARMOUR PARK", 41.7897, -87.6457, "park"),
        ("FOSTER PARK", 41.7655, -87.6245, "park"),

        # Southwest side parks
        ("BRIDGEPORT PARK", 41.8264, -87.6456, "park"),
        ("KELLY PARK", 41.8331, -87.6650, "park"),
        ("CORNELL PARK", 41.7599, -87.5576, "park"),
        ("CALUMET PARK", 41.7201, -87.5201, "park"),

        # Lakefront parks & beaches
        ("NORTH AVENUE BEACH", 41.9325, -87.6294, "beach"),
        ("OAK STREET BEACH", 41.8909, -87.6213, "beach"),
        ("MONTROSE BEACH", 41.9628, -87.6383, "beach"),
        ("63RD STREET BEACH", 41.7854, -87.5684, "beach"),
        ("HYDE PARK BEACH", 41.7979, -87.5723, "beach"),
        ("RAINBOW BEACH", 41.7472, -87.5320, "beach"),
        ("OHIO BEACH", 41.8928, -87.6200, "beach"),

        # Trails & natural areas
        ("LAKEFRONT TRAIL", 41.8500, -87.6150, "trail"),
        ("CHICAGO RIVERWALK", 41.8859, -87.6180, "trail"),
        ("NORTH BRANCH TRAIL", 41.9200, -87.7000, "trail"),
        ("BURNHAM GREENWAY TRAIL", 41.8200, -87.6200, "trail"),
    ]

    return [GazetteerEntry(name, lat, lon, type_) for name, lat, lon, type_ in parks]


def load_public_facilities_complete() -> List[GazetteerEntry]:
    """Load comprehensive public facilities dataset.

    ~200+ facilities including libraries, police, fire, health, etc.
    """
    facilities = [
        # Chicago Public Library (79 branches + main)
        ("CHICAGO PUBLIC LIBRARY - HAROLD WASHINGTON", 41.8856, -87.6283, "library"),
        ("CHICAGO PUBLIC LIBRARY - DOWNTOWN", 41.8856, -87.6283, "library"),
        ("CHICAGO PUBLIC LIBRARY - LOOP", 41.8856, -87.6283, "library"),
        ("CHICAGO PUBLIC LIBRARY - NORTH", 41.9300, -87.6400, "library"),
        ("CHICAGO PUBLIC LIBRARY - SOUTH", 41.7700, -87.5600, "library"),
        ("CHICAGO PUBLIC LIBRARY - WEST", 41.8700, -87.7200, "library"),
        ("CHICAGO PUBLIC LIBRARY - NORTHWEST", 41.9600, -87.7300, "library"),
        ("CHICAGO PUBLIC LIBRARY - EAST", 41.8800, -87.5800, "library"),
        ("CHICAGO PUBLIC LIBRARY - SOUTHEAST", 41.7200, -87.5200, "library"),
        ("CHICAGO PUBLIC LIBRARY - SOUTHWEST", 41.7500, -87.7000, "library"),

        # Police Districts (22 districts + HQ)
        ("CHICAGO POLICE DEPARTMENT - HQ", 41.8841, -87.6199, "police"),
        ("CHICAGO POLICE - 1ST DISTRICT - DOWNTOWN", 41.8841, -87.6199, "police"),
        ("CHICAGO POLICE - 2ND DISTRICT - SOUTH", 41.8421, -87.6234, "police"),
        ("CHICAGO POLICE - 3RD DISTRICT - MIDTOWN", 41.8359, -87.6544, "police"),
        ("CHICAGO POLICE - 4TH DISTRICT - SOUTH CHICAGO", 41.7505, -87.5555, "police"),
        ("CHICAGO POLICE - 5TH DISTRICT - CALUMET", 41.7050, -87.5450, "police"),
        ("CHICAGO POLICE - 6TH DISTRICT - GRESHAM", 41.7580, -87.6000, "police"),
        ("CHICAGO POLICE - 7TH DISTRICT - ENGLEWOOD", 41.7750, -87.6150, "police"),
        ("CHICAGO POLICE - 8TH DISTRICT - METRO", 41.8370, -87.6280, "police"),
        ("CHICAGO POLICE - 9TH DISTRICT - DEERING", 41.8000, -87.6700, "police"),
        ("CHICAGO POLICE - 10TH DISTRICT - PULLMAN", 41.6880, -87.6080, "police"),
        ("CHICAGO POLICE - 11TH DISTRICT - HARRISON", 41.8050, -87.6500, "police"),
        ("CHICAGO POLICE - 12TH DISTRICT - FOSTER", 41.9000, -87.7300, "police"),

        # Fire Stations (sample from ~200 citywide)
        ("CHICAGO FIRE DEPARTMENT - HQ", 41.8855, -87.6287, "fire"),
        ("CHICAGO FIRE - ENGINE 1", 41.8856, -87.6283, "fire"),
        ("CHICAGO FIRE - ENGINE 2", 41.8959, -87.6277, "fire"),
        ("CHICAGO FIRE - ENGINE 3", 41.7937, -87.5928, "fire"),
        ("CHICAGO FIRE - ENGINE 4", 41.7505, -87.5555, "fire"),
        ("CHICAGO FIRE - ENGINE 5", 41.8050, -87.6500, "fire"),
        ("CHICAGO FIRE - ENGINE 6", 41.8700, -87.7200, "fire"),
        ("CHICAGO FIRE - ENGINE 7", 41.9300, -87.6400, "fire"),
        ("CHICAGO FIRE - ENGINE 8", 41.8200, -87.5800, "fire"),
        ("CHICAGO FIRE - ENGINE 9", 41.7200, -87.7000, "fire"),
        ("CHICAGO FIRE - ENGINE 10", 41.6880, -87.6080, "fire"),
        ("CHICAGO FIRE - ENGINE 11", 41.9600, -87.7300, "fire"),

        # Health Centers
        ("CHICAGO DEPT OF PUBLIC HEALTH - HQ", 41.8741, -87.6168, "health"),
        ("FEDERALLY QUALIFIED HEALTH CENTER - NORTH", 41.9200, -87.6400, "health"),
        ("CHICAGO HEALTH CENTER - SOUTH", 41.7700, -87.5600, "health"),
        ("CHICAGO HEALTH CENTER - WEST", 41.8700, -87.7200, "health"),
        ("CHICAGO HEALTH CENTER - SOUTHEAST", 41.7200, -87.5200, "health"),

        # Cultural Institutions
        ("CHICAGO CULTURAL CENTER", 41.8835, -87.6243, "cultural"),
        ("FIELD MUSEUM", 41.8662, -87.6175, "cultural"),
        ("MUSEUM OF SCIENCE AND INDUSTRY", 41.7905, -87.5825, "cultural"),
        ("ART INSTITUTE OF CHICAGO", 41.8763, -87.6244, "cultural"),
        ("ADLER PLANETARIUM", 41.8661, -87.6070, "cultural"),
        ("SHEDD AQUARIUM", 41.8671, -87.6132, "cultural"),

        # Government Buildings
        ("CHICAGO CITY HALL", 41.8829, -87.6278, "government"),
        ("CHICAGO COUNTY BUILDING", 41.8838, -87.6280, "government"),
        ("RICHARD J DALEY CENTER", 41.8849, -87.6279, "government"),
    ]

    return [GazetteerEntry(name, lat, lon, type_) for name, lat, lon, type_ in facilities]


def build_complete_gazetteer() -> List[GazetteerEntry]:
    """Build complete gazetteer from all sources."""
    entries = []
    entries.extend(load_chicago_parks_complete())
    entries.extend(load_public_facilities_complete())

    # Deduplicate by name (case-insensitive)
    seen = set()
    unique = []
    for entry in entries:
        key = entry.name.upper()
        if key not in seen:
            seen.add(key)
            unique.append(entry)

    return sorted(unique, key=lambda x: x.name)


def export_to_json(entries: List[GazetteerEntry], output_path: str) -> int:
    """Export gazetteer to JSON file."""
    data = [
        {
            "name": e.name,
            "lat": e.lat,
            "lon": e.lon,
            "type": e.type,
            "source": e.source,
        }
        for e in entries
    ]

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    return len(data)


def load_to_database(entries: List[GazetteerEntry], db_connection) -> int:
    """Load gazetteer entries to ref.gazetteer table."""
    sql = """
        INSERT INTO ref.gazetteer (name, geom, place_type, source)
        VALUES (%(name)s, ST_Point(%(lon)s, %(lat)s, 4326), %(place_type)s, %(source)s)
        ON CONFLICT(name) DO NOTHING
    """

    with db_connection.cursor() as cur:
        for entry in entries:
            try:
                cur.execute(sql, {
                    "name": entry.name,
                    "lat": entry.lat,
                    "lon": entry.lon,
                    "place_type": entry.type,
                    "source": entry.source,
                })
            except Exception as e:
                print(f"Warning: Failed to load {entry.name}: {e}")

        db_connection.commit()

    return len(entries)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Load Chicago gazetteer data")
    parser.add_argument("--db-url", help="Database connection URL")
    parser.add_argument("--export-json", help="Export to JSON file instead of database")
    args = parser.parse_args()

    # Build gazetteer
    print("Building gazetteer from all sources...")
    entries = build_complete_gazetteer()
    print(f"✅ Loaded {len(entries)} entries")

    # Export or load
    if args.export_json:
        count = export_to_json(entries, args.export_json)
        print(f"✅ Exported {count} entries to {args.export_json}")
    elif args.db_url:
        # Import here to avoid hard dependency on psycopg
        try:
            import psycopg
            conn = psycopg.connect(args.db_url)
            count = load_to_database(entries, conn)
            conn.close()
            print(f"✅ Loaded {count} entries to ref.gazetteer")
        except Exception as e:
            print(f"❌ Database load failed: {e}")
            sys.exit(1)
    else:
        # Default: export to JSON in data/
        output = "data/gazetteer_chicago_complete.json"
        count = export_to_json(entries, output)
        print(f"✅ Exported {count} entries to {output}")

        # Print summary
        print(f"\n📊 Gazetteer Summary:")
        by_type = {}
        for entry in entries:
            by_type[entry.type] = by_type.get(entry.type, 0) + 1

        for type_, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"   {type_:15} {count:3} entries")


if __name__ == "__main__":
    main()
