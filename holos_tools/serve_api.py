"""Flask API to serve centerlines from PostGIS."""

import hmac
import json
import logging
import os
from typing import Optional

from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from holos_tools.core import Config, HolosDB

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)
config = Config()
_db = None


def get_db() -> HolosDB:
    """Lazy database connection (connects on first use)."""
    global _db
    if _db is None:
        db_url = config.db_url
        # Log connection host (not password)
        host = db_url.split('@')[-1].split('/')[0] if '@' in db_url else 'unknown'
        logger.info(f"Connecting to PostGIS database at {host}...")
        _db = HolosDB(db_url)
        logger.info("✓ Connected to PostGIS")
    return _db


@app.route('/', methods=['GET'])
def index():
    """Serve the interactive map."""
    with open('/app/docs/2017_map.html', 'r') as f:
        return f.read()


@app.route('/<path:filename>', methods=['GET'])
def serve_static(filename):
    """Serve static GeoJSON files from docs directory."""
    if not filename.endswith('.geojson'):
        abort(404)
    docs_dir = os.path.realpath('/app/docs')
    requested = os.path.realpath(os.path.join(docs_dir, filename))
    if not requested.startswith(docs_dir + os.sep):
        abort(404)
    return send_from_directory(docs_dir, filename, mimetype='application/geo+json')


@app.route('/api/streets.geojson', methods=['GET'])
def get_streets():
    """Serve street centerlines as GeoJSON."""
    bbox = request.args.get('bbox')

    if bbox:
        # Parse bbox: minLon,minLat,maxLon,maxLat
        try:
            min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(','))
            sql = f"""
                SELECT ST_AsGeoJSON(geometry) as geometry, properties
                FROM (
                    SELECT geometry,
                           jsonb_build_object(
                               'street_name', street_nam,
                               'street_type', street_typ,
                               'class', class
                           ) as properties
                    FROM public.street_centerlines
                    WHERE ST_Intersects(geometry, ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326))
                ) t
            """
        except ValueError:
            return jsonify({'error': 'Invalid bbox format'}), 400
    else:
        sql = """
            SELECT ST_AsGeoJSON(geometry) as geometry, properties
            FROM (
                SELECT geometry,
                       jsonb_build_object(
                           'street_name', street_nam,
                           'street_type', street_typ,
                           'class', class
                       ) as properties
                FROM public.street_centerlines
            ) t
        """

    try:
        results = get_db().execute(sql)
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
                SELECT ST_AsGeoJSON(geometry) as geometry
                FROM public.curb_centerlines
                WHERE ST_Intersects(geometry, ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326))
            """
        except ValueError:
            return jsonify({'error': 'Invalid bbox format'}), 400
    else:
        sql = """
            SELECT ST_AsGeoJSON(geometry) as geometry
            FROM public.curb_centerlines
        """

    try:
        results = get_db().execute(sql)
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


@app.route('/api/tiger-roads.geojson', methods=['GET'])
def get_tiger_roads():
    """Serve TIGER roads clipped to Chicago boundary."""
    bbox = request.args.get('bbox')

    if bbox:
        try:
            min_lon, min_lat, max_lon, max_lat = map(float, bbox.split(','))
            sql = f"""
                SELECT ST_AsGeoJSON(geometry) as geometry
                FROM public.tiger_roads
                WHERE ST_Intersects(geometry, ST_MakeEnvelope({min_lon}, {min_lat}, {max_lon}, {max_lat}, 4326))
                AND ST_Contains((SELECT geom FROM public.chicago_boundary LIMIT 1), geometry)
                LIMIT 50000
            """
        except ValueError:
            return jsonify({'error': 'Invalid bbox format'}), 400
    else:
        return jsonify({'error': 'bbox parameter required'}), 400

    try:
        results = get_db().execute(sql)
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
        logger.error(f"Error fetching TIGER roads: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check."""
    return jsonify({'status': 'ok'})


@app.route('/admin/load-data', methods=['POST'])
def load_data():
    """Load centerline data (one-time, requires admin password in header)."""
    admin_pw = os.getenv('ADMIN_PASSWORD', '')
    provided_pw = request.headers.get('X-Admin-Password', '')

    if not admin_pw or not hmac.compare_digest(provided_pw, admin_pw):
        return jsonify({'error': 'unauthorized'}), 401

    try:
        from holos_tools.load_all_reference_data import load_all_data

        logger.info("Loading reference datasets...")
        load_all_data()
        return jsonify({'status': 'Data loaded successfully'})
    except Exception as e:
        logger.error(f"Load failed: {e}", exc_info=True)
        return jsonify({'error': 'Load failed'}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
