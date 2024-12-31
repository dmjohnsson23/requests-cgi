#!/usr/bin/env python
from fastcgi import *
from socketserver import UnixStreamServer, BaseServer
from socket import socket
import os, sys

# None of the FastCGI implementations I can find actually seems to live by the part of the spec 
# that discusses the file descriptor socket. Here I do my best to implement a spec-compliant server
# to test the launch function. I'm not 100% confident this is correct, but I *think* it is.

class Server(UnixStreamServer):
    def __init__(self, socket, RequestHandlerClass, bind_and_activate=True):
        BaseServer.__init__(self, socket.getsockname() , RequestHandlerClass)
        self.socket = socket
        if bind_and_activate:
            try:
                self.server_bind()
                self.server_activate()
            except:
                self.server_close()
                raise


class TestHandler(FcgiHandler):
    def handle(self):
        query = self.environ["QUERY_STRING"]
        self.print(f"Content-type: text/plain")
        self.print()
        self.print(query)


sock = socket(fileno=int(os.environ['FCGI_LISTENSOCK_FILENO']))
with Server(sock, TestHandler) as server:
    server.serve_forever()

