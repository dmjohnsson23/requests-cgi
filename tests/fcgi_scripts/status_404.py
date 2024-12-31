#!/usr/bin/env python
from fastcgi import *
from pathlib import Path
from socketserver import UnixStreamServer

class TestHandler(FcgiHandler):
    def handle(self):
        self.print('Status: 404 Not Found')
        self.print()

socket_path = Path('fcgi.sock')
if socket_path.exists():
    socket_path.unlink()

with UnixStreamServer(str(socket_path), TestHandler) as server:
    server.serve_forever()