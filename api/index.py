"""Vercel serverless function — Flask app handler.

Routes requests to the unified dashboard (app.html with map + analytics tabs).
Imports serve_api.py which is the primary Flask application.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import holos_tools
sys.path.insert(0, str(Path(__file__).parent.parent))

from holos_tools.serve_api import app

# Export WSGI app for Vercel
__all__ = ['app']
