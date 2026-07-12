"""Load reference data (R1-R5) into ref schema."""

import json
from pathlib import Path
from ..core import HolosDB, Config

def load_sample_centerlines(db: HolosDB):
    """Load sample Chicago centerlines into ref.centerlines."""
    # Phase 1B: stub with sample data (real implementation fetches from Socrata)
    sample_centerlines = [
        {
            "street_name": "MICHIGAN",
            "predir": "N",
            "suffix": "AVE",
            "from_house_num_l": 1,
            "to_house_num_l": 199,
            "from_house_num_r": 2,
            "to_house_num_r": 200,
            "geom": "LINESTRING(-87.6244 41.8841, -87.6244 41.8851)",
            "source_id": "chicago_centerlines"
        },
        {
            "street_name": "CLARK",
            "predir": None,
            "suffix": "ST",
            "from_house_num_l": 1,
            "to_house_num_l": 9999,
            "from_house_num_r": 2,
            "to_house_num_r": 10000,
            "geom": "LINESTRING(-87.6298 41.9082, -87.6298 41.9182)",
            "source_id": "chicago_centerlines"
        },
    ]
    
    for cl in sample_centerlines:
        db.execute(f"""
            INSERT INTO ref.centerlines 
            (street_name, predir, suffix, from_house_num_l, to_house_num_l, 
             from_house_num_r, to_house_num_r, geom, source_id)
            VALUES (
                '{cl['street_name']}',
                {f"'{cl['predir']}'" if cl['predir'] else 'NULL'},
                '{cl['suffix']}',
                {cl['from_house_num_l']}, {cl['to_house_num_l']},
                {cl['from_house_num_r']}, {cl['to_house_num_r']},
                ST_GeomFromText('{cl['geom']}', 4326),
                '{cl['source_id']}'
            )
        """)
    
    print(f"✓ Loaded {len(sample_centerlines)} centerlines")

def load_sample_wards(db: HolosDB):
    """Load sample Chicago wards."""
    sample_wards = [
        {"ward_number": 4, "vintage": "2023", "geom": "POLYGON((-87.7 41.8, -87.6 41.8, -87.6 41.9, -87.7 41.9, -87.7 41.8))"},
        {"ward_number": 11, "vintage": "2023", "geom": "POLYGON((-87.65 41.95, -87.62 41.95, -87.62 42.0, -87.65 42.0, -87.65 41.95))"},
        {"ward_number": 20, "vintage": "2023", "geom": "POLYGON((-87.72 41.75, -87.68 41.75, -87.68 41.82, -87.72 41.82, -87.72 41.75))"},
        {"ward_number": 25, "vintage": "2023", "geom": "POLYGON((-87.71 41.95, -87.68 41.95, -87.68 42.02, -87.71 42.02, -87.71 41.95))"},
        {"ward_number": 32, "vintage": "2023", "geom": "POLYGON((-87.63 41.88, -87.60 41.88, -87.60 41.92, -87.63 41.92, -87.63 41.88))"},
    ]
    
    for ward in sample_wards:
        db.execute(f"""
            INSERT INTO ref.wards (ward_number, geom, vintage, source_id)
            VALUES ({ward['ward_number']}, ST_GeomFromText('{ward['geom']}', 4326), '{ward['vintage']}', 'chicago_wards')
        """)
    
    print(f"✓ Loaded {len(sample_wards)} ward boundaries")

def load_sample_address_points(db: HolosDB):
    """Load sample address points."""
    sample_points = [
        {"address_number": 123, "street_name": "MICHIGAN", "city": "Chicago", "state": "IL", "zip": "60601", "geom": "POINT(-87.6244 41.8841)"},
        {"address_number": 456, "street_name": "CLARK", "city": "Chicago", "state": "IL", "zip": "60654", "geom": "POINT(-87.6298 41.9082)"},
    ]
    
    for pt in sample_points:
        db.execute(f"""
            INSERT INTO ref.address_points 
            (address_number, street_name, city, state, zip, geom, source_id)
            VALUES ({pt['address_number']}, '{pt['street_name']}', '{pt['city']}', '{pt['state']}', '{pt['zip']}', 
                    ST_GeomFromText('{pt['geom']}', 4326), 'chicago_address_points')
        """)
    
    print(f"✓ Loaded {len(sample_points)} address points")

def load_sample_gazetteer(db: HolosDB):
    """Load sample gazetteer entries."""
    sample_places = [
        {"name": "MILLENNIUM PARK", "geom": "POINT(-87.6217 41.8829)"},
        {"name": "GRANT PARK", "geom": "POINT(-87.6197 41.8759)"},
    ]
    
    for place in sample_places:
        db.execute(f"""
            INSERT INTO ref.gazetteer (name, geom, source_id)
            VALUES ('{place['name']}', ST_GeomFromText('{place['geom']}', 4326), 'chicago_gazetteer')
        """)
    
    print(f"✓ Loaded {len(sample_places)} gazetteer places")

def main():
    """Load all reference data."""
    config = Config()
    db = HolosDB(config.db_url)
    
    print("Loading reference data (R1–R5)...")
    print()
    
    try:
        load_sample_centerlines(db)
        load_sample_wards(db)
        load_sample_address_points(db)
        load_sample_gazetteer(db)
        print()
        print("✓ Reference data loaded successfully")
        print("  Next: holos geocode cascade (golden test)")
    except Exception as e:
        print(f"✗ Failed to load reference data: {e}")
        raise

if __name__ == "__main__":
    main()
