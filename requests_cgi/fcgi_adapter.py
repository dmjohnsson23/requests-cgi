from dataclasses import dataclass
from enum import IntEnum, IntFlag
from requests import PreparedRequest
from requests.exceptions import ConnectionError, ReadTimeout
from socket import socket, error as SocketError, AddressFamily, SOL_SOCKET, SO_REUSEADDR
from struct import Struct
from typing import Optional
import random

from .cgi_adapter import CGIAdapter

__all__ = ('FastCGIAdapter','launch_fcgi')

# See https://fastcgi-archives.github.io/FastCGI_Specification.html

FASTCGI_VERSION = 1

class Role(IntEnum):
    responder = 1
    authorizer = 2
    filter = 3


class RecordType(IntEnum):
    begin = 1
    abort = 2
    end = 3
    params = 4
    stdin = 5
    stdout = 6
    stderr = 7
    data = 8
    get_values = 9
    get_values_result = 10
    unknown_type = 11


class State(IntEnum):
    send = 1
    error = 2
    success = 3


# Specs: https://fastcgi-archives.github.io/FastCGI_Specification.html#S3.3
_HEADER_STRUCT = Struct(">BBHHBx")
@dataclass
class RecordHeader:
    version: int
    type: RecordType
    request_id: int # value 0 reserved for management records; values 1-0xffff allowed
    content_length: int
    padding_length: int

    @classmethod
    def decode(cls, data: bytes):
        return cls(*_HEADER_STRUCT.unpack(data))
    
    def encode(self)->bytes:
        return _HEADER_STRUCT.pack(
            self.version, 
            self.type, 
            self.request_id, 
            self.content_length, 
            self.padding_length, 
        )


@dataclass
class Record:
    header: RecordHeader
    content: bytes

    @classmethod
    def create(cls, fcgi_type: RecordType, content: bytes, req_id: int):
        header = RecordHeader(
            FASTCGI_VERSION,
            fcgi_type,
            req_id,
            len(content),
            0, # TODO padding is recommended to make the full record length a multiple of 8 bytes
        )
        return cls(header, content)
    
    @classmethod
    def read_from_stream(cls, stream):
        header = stream.read(_HEADER_STRUCT.size)
        if not header:
            return None
        header = RecordHeader.decode(header)

        content = bytearray()
        bytes_read = 0
        while bytes_read < header.content_length:
            buffer = stream.read(header.content_length - bytes_read)
            bytes_read += len(buffer)
            if buffer:
                content += buffer
            if len(buffer) == 0:
                break
        stream.read(header.padding_length)
        return cls(header, content)

    def encode(self)->bytes:
        return b''.join((self.header.encode(), self.content, bytes(self.header.padding_length)))


# Specs: https://fastcgi-archives.github.io/FastCGI_Specification.html#S3.4
_UNSIGNED_LONG_STRUCT = Struct(">L")
@dataclass
class NameValue:
    name: bytes
    value: bytes

    def encode(self):
        len_name = len(self.name)
        len_value = len(self.value)
        lengths = bytearray()
        if len_name < 128:
            lengths.append(len_name)
        else:
            lengths.extend(_UNSIGNED_LONG_STRUCT.pack(len_name | 0x80_00_00_00))
        if len_value < 128:
            lengths.append(len_value)
        else:
            lengths.extend(_UNSIGNED_LONG_STRUCT.pack(len_value | 0x80_00_00_00))
        return lengths + self.name + self.value


class BeginRequestOptions(IntFlag):
    keep_connection = 1


# Specs: https://fastcgi-archives.github.io/_Specification.html#S5.1
_BEGIN_REQUEST_STRUCT = Struct(">HBxxxxx")
@dataclass
class BeginRequestBody:
    role: Role
    flags: BeginRequestOptions = BeginRequestOptions(0)

    def encode(self):
        return _BEGIN_REQUEST_STRUCT.pack(self.role, self.flags)


class FastCGIAdapter(CGIAdapter):
    """
    Reads and interprets an HTTP response from a FastCGI application.

    This is largely based on https://github.com/darkpills/fcgi-client/blob/master/src/fcgi_client/FastCGIClient.py
    """

    def __init__(self, address, address_family:AddressFamily=AddressFamily.AF_UNIX, override_env: Optional[dict] = None):
        self.socket = None
        self.requests = {} # Keep track of in-flight requests
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
        self.override_env = override_env
    
    def connect(self):
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
    
    def close(self):
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def read(self, size)->bytes:
        try:
            return self.socket.recv(size)
        except socket.error as e:
            self.close()
            raise ConnectionError(f"Unexpected socket error") from e
    
    def _cgi_env_helper(self, request):
        env = {}
        if self.address_family == AddressFamily.AF_INET:
            # Address of server
            ip, port = self.address
            env['SERVER_ADDR'] = ip
            env['SERVER_PORT'] = port
            # Address of client
            ip, port = self.socket.getsockname() 
            env['REMOTE_ADDR'] = ip
            env['REMOTE_PORT'] = port
        return env
    
    def execute_send(self, request: PreparedRequest, env: dict, stdin: Optional[bytes], timeout: Optional[float]):
        self.connect()
        self.socket.settimeout(timeout)
        # Generate a unique request ID
        req_id = random.randint(0x1, 0xffff)
        while req_id in self.requests:
            req_id = random.randint(0x1, 0xffff)
        self.requests[req_id] = {}
        packet = bytearray()
        packet += Record.create(RecordType.begin, BeginRequestBody(Role.responder).encode(), req_id).encode()
        
        params = bytearray()
        if env:
            for name, value in env.items():
                params += NameValue(name.encode('ascii'), value.encode('ascii')).encode()

        if len(params) > 0:
            packet += Record.create(RecordType.params, params, req_id).encode()
        packet += Record.create(RecordType.params, bytearray(), req_id).encode()

        if stdin:
            packet += Record.create(RecordType.stdin, stdin, req_id).encode()
        packet += Record.create(RecordType.stdin, bytearray(), req_id).encode()
        # Send request
        self.socket.send(packet)
        self.requests[req_id]['state'] = State.send
        self.requests[req_id]['response'] = bytearray()
        return self.build_response(request, self.await_response(req_id))
    
    def await_response(self, req_id):
        while True:
            record = Record.read_from_stream(self)
            if not record:
                break

            # FIXME The header ID returned is always 1 for some reason?
            # if req_id != header.request_id:
            #     continue
            if record.header.type == RecordType.stdout:
                self.requests[req_id]['response'] += record.content
            if record.header.type == RecordType.stderr:
                self.requests[req_id]['state'] = State.error
                if req_id == record.header.request_id:
                    self.requests[req_id]['response'] += record.content
            if record.header.type == RecordType.end:
                 # TODO an END packet may not always be a graceful end; see https://fastcgi-archives.github.io/FastCGI_Specification.html#S5.5
                if self.requests[req_id]['state'] != State.error:
                    self.requests[req_id]['state'] = State.success
        
        self.close()
        response = self.requests[req_id]['response']
        del self.requests[req_id]

        return response


    def launch(self, command):
        """
        Launch a FastCGI process as if we are a web server.
        """
        # TODO: I'm trying to wrap my head around this. The specs claim that we should provide a socket
        # handle via the FCGI_LISTENSOCK_FILENO environment variable. However, the socket doesn't exist
        # yet. I'm fairly certain the FastCGI application is considered the server in this context,
        # and this code is considered the client, so the server should be the one to create the socket, 
        # right? I'm not a socket guru, so I guess I'm just confused.
        raise NotImplementedError()