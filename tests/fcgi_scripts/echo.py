#!/usr/bin/env python
from fastcgi import *
from pathlib import Path
from socketserver import UnixStreamServer

class TestHandler(FcgiHandler):
    def handle(self):
        self.print(f'Content-type: text/html\n\n{self.content()}')

socket_path = Path('fcgi.sock')
if socket_path.exists():
    socket_path.unlink()

with UnixStreamServer(str(socket_path), TestHandler) as server:
    server.serve_forever()