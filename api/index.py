# Phase 1 MVP: Static site deployment via Vercel
# Serve index.html on root request to enable client-side routing
# All assets are in /web/ directory

from http.server import BaseHTTPRequestHandler
from pathlib import Path
import mimetypes

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Default to index.html for root
        path = self.path.lstrip('/')
        if not path or path == '/' or path.endswith('/'):
            path = 'index.html'

        # Serve static files from web/
        file_path = Path(__file__).parent.parent / 'web' / path

        try:
            if file_path.is_file() and file_path.exists():
                # Read and serve the file
                mime_type, _ = mimetypes.guess_type(str(file_path))
                mime_type = mime_type or 'text/plain'

                with open(file_path, 'rb') as f:
                    content = f.read()

                self.send_response(200)
                self.send_header('Content-type', mime_type)
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
            else:
                # File not found
                self.send_response(404)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<h1>404 - Not Found</h1>')
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Internal Server Error')
