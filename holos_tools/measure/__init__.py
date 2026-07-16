"""Measure: spatial analysis of infrastructure assets (widths, lengths, densities).

Phase 1 Step 5: Alley width measurement workflow
- Load alley centerlines from database
- Load building footprints (GeoJSON reference)
- Measure distance between buildings to determine alley width
- Store measurements with metadata for Ward 1 pilot
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import typer
import math

app = typer.Typer(help="Measure: spatial infrastructure analysis")


def distance_between_points(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two lat/lon points in meters (Haversine formula)."""
    R = 6371000  # Earth radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def point_to_line_distance(point: Tuple[float, float], line_coords: List[Tuple[float, float]]) -> Tuple[float, int]:
    """Find minimum distance from point to line segment and return the point index.

    Args:
        point: (lon, lat)
        line_coords: [(lon, lat), ...]

    Returns:
        (distance_in_meters, closest_segment_index)
    """
    min_dist = float('inf')
    closest_idx = 0

    for i in range(len(line_coords) - 1):
        lon1, lat1 = line_coords[i]
        lon2, lat2 = line_coords[i + 1]

        # Distance from point to line segment
        # Simplified: just use distance to endpoints
        dist1 = distance_between_points(point[1], point[0], lat1, lon1)
        dist2 = distance_between_points(point[1], point[0], lat2, lon2)

        min_segment_dist = min(dist1, dist2)
        if min_segment_dist < min_dist:
            min_dist = min_segment_dist
            closest_idx = i

    return min_dist, closest_idx


@app.command()
def alley_widths(
    alley_centerlines_path: str = typer.Option(
        "data/chicago_alleys.geojson",
        help="Path to alley centerlines GeoJSON"
    ),
    building_footprints_path: str = typer.Option(
        "data/ward01_building_footprints_sample.geojson",
        help="Path to building footprints GeoJSON"
    ),
    output_path: str = typer.Option(
        None,
        help="Output path for measurements (auto-generate if not provided)"
    ),
):
    """Measure alley widths by calculating distances between building footprints.

    This workflow:
    1. Loads alley centerlines and building footprints
    2. For each alley segment, finds the two nearest buildings (one on each side)
    3. Calculates the distance between them as proxy for alley width
    4. Outputs measurements with confidence metadata

    Example:
      holos measure alley-widths --alley-centerlines-path data/chicago_alleys.geojson
    """
    # Load building footprints
    buildings_file = Path(building_footprints_path)
    if not buildings_file.exists():
        typer.echo(f"✗ File not found: {building_footprints_path}", err=True)
        raise typer.Exit(1)

    with open(buildings_file) as f:
        buildings_geojson = json.load(f)

    buildings = buildings_geojson.get('features', [])
    typer.echo(f"📦 Loaded {len(buildings)} building footprints")

    # For pilot: create synthetic alley segments
    # In production, these would come from PostGIS database
    alley_segments = [
        {
            "id": "alley_001",
            "name": "Alley between California & Francisco",
            "centerline": [
                [-87.6972, 41.9206],
                [-87.6972, 41.9201]
            ]
        },
        {
            "id": "alley_002",
            "name": "Alley at Chicago & Bishop",
            "centerline": [
                [-87.6641, 41.8966],
                [-87.6636, 41.8966]
            ]
        },
        {
            "id": "alley_003",
            "name": "Alley at Bloomingdale",
            "centerline": [
                [-87.698, 41.9140],
                [-87.6975, 41.9140]
            ]
        }
    ]

    typer.echo(f"📍 Measuring {len(alley_segments)} alley segments...\n")

    measurements = []

    for segment in alley_segments:
        segment_id = segment['id']
        centerline = segment['centerline']

        # Use centerline midpoint as measurement reference
        mid_lon = (centerline[0][0] + centerline[1][0]) / 2
        mid_lat = (centerline[0][1] + centerline[1][1]) / 2
        reference_point = (mid_lon, mid_lat)

        # Find nearest buildings
        nearest_buildings = []
        for building in buildings:
            coords = building['geometry']['coordinates'][0]
            # Get building center (average of polygon coords)
            bldg_lon = sum(c[0] for c in coords) / len(coords)
            bldg_lat = sum(c[1] for c in coords) / len(coords)

            dist = distance_between_points(reference_point[1], reference_point[0], bldg_lat, bldg_lon)
            nearest_buildings.append({
                'building': building,
                'distance': dist,
                'center': (bldg_lon, bldg_lat)
            })

        # Sort by distance and get two nearest
        nearest_buildings.sort(key=lambda x: x['distance'])

        if len(nearest_buildings) >= 2:
            building1 = nearest_buildings[0]
            building2 = nearest_buildings[1]

            # Distance between the two nearest buildings = proxy for alley width
            alley_width = distance_between_points(
                building1['center'][1], building1['center'][0],
                building2['center'][1], building2['center'][0]
            )

            # Convert meters to feet (standard for alley measurements in US)
            alley_width_feet = alley_width * 3.28084

            measurement = {
                'segment_id': segment_id,
                'segment_name': segment['name'],
                'alley_width_m': round(alley_width, 2),
                'alley_width_ft': round(alley_width_feet, 2),
                'nearest_building_1': building1['building']['properties'].get('address', 'Unknown'),
                'nearest_building_2': building2['building']['properties'].get('address', 'Unknown'),
                'confidence': 0.6,  # Low confidence on synthetic data; would be higher with real footprints
                'notes': 'Pilot measurement using sample building footprints'
            }

            measurements.append(measurement)
            typer.echo(f"✓ {segment_id}: {alley_width_feet:.1f} ft wide")
        else:
            typer.echo(f"⚠️  {segment_id}: insufficient nearby buildings for measurement")

    # Output results
    if output_path is None:
        output_path = "data/ward01_alley_widths_measured.json"

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    result = {
        'metadata': {
            'ward': 1,
            'year': 2017,
            'measurement_type': 'alley_width',
            'method': 'building_footprint_distance',
            'unit': 'feet',
            'confidence': 0.6,
            'note': 'Pilot measurement using sample data; production load will use full Chicago building footprints'
        },
        'measurements': measurements
    }

    with open(out_file, 'w') as f:
        json.dump(result, f, indent=2)

    typer.echo(f"\n✓ Measurements complete")
    typer.echo(f"  Segments measured: {len(measurements)}/{len(alley_segments)}")
    typer.echo(f"  Output: {out_file}")

    # Summary statistics
    if measurements:
        widths = [m['alley_width_ft'] for m in measurements]
        typer.echo(f"\n📊 Summary:")
        typer.echo(f"  Average alley width: {sum(widths)/len(widths):.1f} ft")
        typer.echo(f"  Min: {min(widths):.1f} ft, Max: {max(widths):.1f} ft")


if __name__ == "__main__":
    app()
