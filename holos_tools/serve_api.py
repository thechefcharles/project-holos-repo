"""Flask API to serve centerlines from PostGIS."""

import json
import logging
from typing import Optional

from flask import Flask, request, jsonify
from holos_tools.core import Config, HolosDB

logger = logging.getLogger(__name__)

app = Flask(__name__)
config = Config()
db = HolosDB(config.db_url)


@app.route('/api/streets.geojson', methods=['GET'])
def get_streets():
    """Serve street centerlines as GeoJSON."""
    bbox = request.args.get('bbox')

    if bbox:
        # Parse bbox: minLon,minLat,maxLon,maxLat
        try:
            min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(','))
            sql = f"""
                SELECT ST_AsGeoJSON(geom) as geometry, properties
                FROM (
                    SELECT geom,
                           jsonb_build_object(
                               'street_name', street_nam,
                               'street_type', street_typ,
                               'class', class
                           ) as properties
                    FROM public.street_centerlines
                    WHERE ST_Intersects(geom, ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326))
                ) t
            """
        except ValueError:
            return jsonify({'error': 'Invalid bbox format'}), 400
    else:
        sql = """
            SELECT ST_AsGeoJSON(geom) as geometry, properties
            FROM (
                SELECT geom,
                       jsonb_build_object(
                           'street_name', street_nam,
                           'street_type', street_typ,
                           'class', class
                       ) as properties
                FROM public.street_centerlines
            ) t
        """

    try:
        results = db.execute(sql)
        features = []
        for row in results:
            features.append({
                'type': 'Feature',
                'geometry': json.loads(row['geometry']),
                'properties': row['properties']
            })

        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }
        return jsonify(geojson)
    except Exception as e:
        logger.error(f"Error fetching streets: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/curbs.geojson', methods=['GET'])
def get_curbs():
    """Serve curb centerlines as GeoJSON."""
    bbox = request.args.get('bbox')

    if bbox:
        try:
            min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(','))
            sql = f"""
                SELECT ST_AsGeoJSON(geom) as geometry
                FROM public.curb_centerlines
                WHERE ST_Intersects(geom, ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326))
            """
        except ValueError:
            return jsonify({'error': 'Invalid bbox format'}), 400
    else:
        sql = """
            SELECT ST_AsGeoJSON(geom) as geometry
            FROM public.curb_centerlines
        """

    try:
        results = db.execute(sql)
        features = []
        for row in results:
            features.append({
                'type': 'Feature',
                'geometry': json.loads(row['geometry']),
                'properties': {}
            })

        geojson = {
            'type': 'FeatureCollection',
            'features': features
        }
        return jsonify(geojson)
    except Exception as e:
        logger.error(f"Error fetching curbs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, port=5000)
