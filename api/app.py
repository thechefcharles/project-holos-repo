"""Vercel serverless Flask app — serves unified dashboard (app.html).

This is a lightweight Flask app for Vercel that serves static HTML files.
It does NOT connect to the database (that's only needed locally).
"""

from flask import Flask, send_from_directory
import os

app = Flask(__name__)

# Vercel deploys the repo root to /var/task
WEB_DIR = os.path.join(os.path.dirname(__file__), '../web')

@app.route('/')
def root():
    """Serve the unified dashboard (app.html)."""
    try:
        with open(os.path.join(WEB_DIR, 'app.html'), 'r') as f:
            return f.read(), 200, {'Content-Type': 'text/html'}
    except FileNotFoundError:
        # Fallback to index.html if app.html not found
        try:
            with open(os.path.join(WEB_DIR, 'index.html'), 'r') as f:
                return f.read(), 200, {'Content-Type': 'text/html'}
        except FileNotFoundError:
            return "App not found", 404

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (GeoJSON, CSS, JS, etc.)."""
    # Only serve safe file types
    safe_extensions = ['.geojson', '.json', '.html', '.css', '.js', '.png', '.jpg', '.svg']
    if any(filename.endswith(ext) for ext in safe_extensions):
        try:
            return send_from_directory(WEB_DIR, filename)
        except FileNotFoundError:
            return "File not found", 404
    return "Forbidden", 403

if __name__ == '__main__':
    app.run(debug=True)
