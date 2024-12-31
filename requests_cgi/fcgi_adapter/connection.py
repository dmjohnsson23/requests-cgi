import os, sys
from requests.exceptions import ConnectionError, ReadTimeout
from socket import socket, socketpair, error as SocketError, AddressFamily, SOL_SOCKET, SO_REUSEADDR
from subprocess import Popen

__all__ = ('Connection','ExternalConnection','SubprocessConnection')


class Connection:
    def open(self):
        raise NotImplementedError()
    
    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def read(self, size)->bytes:
        try:
            return self.socket.recv(size)
        except TimeoutError as e:
            self.close()
            raise ReadTimeout() from e
        except SocketError as e:
            self.close()
            raise ConnectionError(f"Unexpected socket error") from e


class ExternalConnection(Connection):
    """
    FastCGI connection to an external process via an existing socket
    """
    def __init__(self, address, address_family:AddressFamily=AddressFamily.AF_UNIX):
        self.socket = None
        # Convenience conversion for address
        if address_family == AddressFamily.AF_INET and not isinstance(address, tuple):
            # Split a host:port string
            address = str(address).split(':', 1)
            if len(address) == 1:
                # Default port
                address.append(9000)
            else:
                address[1] = int(address[1])
            address = tuple(address)
        if address_family == AddressFamily.AF_UNIX:
            address = str(address)
            if address.lower().startswith('unix://'):
                address = address[7:]
        self.address = address
        self.address_family = address_family
    
    def open(self):
        if self.socket is not None:
            return
        sock = socket(self.address_family)
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        # Actually connect
        try:
            sock.connect(self.address)
        except SocketError as e:
            sock.close()
            raise ConnectionError(f"Could not connect to {self.address}") from e
        self.socket = sock


class SubprocessConnection(Connection):
    """
    FastCGI connection to a subprocess which will be launched with the given command.

    This is a work in progress and not yet working properly.
    """

    def __init__(self, command, working_dir = None):
        self.command = command
        self.working_dir = working_dir
        self.socket = None
        self.process = None
    
    def open(self):
        if self.socket is not None:
            return
        print("Warning: the `launch` method is a work in progress and may not work correctly\n", file=sys.stderr)
        # FIXME the created adapter will only be good for a single request, because it doesn't 
        # have a real socket address to reconnect to. I probably either need a subclass, or a 
        # special `FastCGIConnection` object that would be contained in the main class.
        s1, s2 = socketpair()
        s1.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        s2.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        os.set_inheritable(s1.fileno(), True)
        self.socket = s2
        self.process = Popen(self.command, 
            env={'FCGI_LISTENSOCK_FILENO': str(s1.fileno())}, 
            pass_fds=[s1.fileno()],
            cwd=self.working_dir,
        )
        s1.close()
    
    def close(self):
        self.process.terminate()
        self.process = None
        return super().close()