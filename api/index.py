"""WSGI entry point for Vercel — routes to Flask app."""

from reports import app

# Vercel expects a `app` variable for WSGI
__all__ = ['app']
