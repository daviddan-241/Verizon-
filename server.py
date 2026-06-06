"""
Lightweight HTTP server to keep Render free web service alive.
Render free tier requires a web service listening on a port.
"""
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import logging

logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "10000"))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # suppress logs


def start_health_server():
    """Start HTTP server in background thread for Render."""
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health server running on port {PORT}")
