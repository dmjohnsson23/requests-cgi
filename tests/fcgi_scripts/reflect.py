#!/usr/bin/env python
from fastcgi import *
from pathlib import Path
from socketserver import UnixStreamServer
from json import dumps

class TestHandler(FcgiHandler):
    def handle(self):
        self.print('Content-type: application/json')
        self.print()
        self.print(dumps({
            'env': self.environ,
            'content': self.content(),
        }))

socket_path = Path('fcgi.sock')
if socket_path.exists():
    socket_path.unlink()

with UnixStreamServer(str(socket_path), TestHandler) as server:
    server.serve_forever()