"""Vercel serverless function — Flask app handler.

Routes to the full Project Holos map with all reference layers and API endpoints.
Requires database connection (PostGIS for centerlines, TIGER roads, alleys, etc.).
"""

import sys
from pathlib import Path

# Add parent to path so we can import holos_tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from holos_tools.serve_api import app

# Export WSGI app for Railway/Vercel
__all__ = ['app']
