"""Vercel serverless function — Flask app handler.

Lightweight app that serves the unified dashboard (app.html).
Does not require database connections (those are local-only).
"""

from app import app

# Export WSGI app for Vercel
__all__ = ['app']
