# Phase 1 MVP: Static site deployment
# This file exists only to satisfy Vercel's Python runtime detection
# All serving is done via static files in ./web/

from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Not found. Please visit the static site.')
        return
