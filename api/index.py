"""Vercel serverless function — Flask app handler."""

import sys
from pathlib import Path

# Ensure reports module can be imported
sys.path.insert(0, str(Path(__file__).parent))

from reports import app

# Export WSGI app for Vercel
__all__ = ['app']
