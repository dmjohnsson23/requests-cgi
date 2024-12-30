from dataclasses import dataclass
from enum import IntEnum
from requests import PreparedRequest
from requests.exceptions import ConnectionError, ReadTimeout
from socket import socket, error as SocketError, AddressFamily, SOL_SOCKET, SO_REUSEADDR
from struct import Struct
from typing import Optional
import random

from .cgi_adapter import CGIAdapter

__all__ = ('FastCGIAdapter',)

FASTCGI_VERSION = 1

class FastCGIRole(IntEnum):
    responder = 1
    authorizer = 2
    filter = 3


class FastCGIType(IntEnum):
    begin = 1
    abort = 2
    end = 3
    params = 4
    stdin = 5
    stdout = 6
    stderr = 7
    data = 8
    getvalues = 9
    getvalues_result = 10
    unkowntype = 11


class FastCGIState(IntEnum):
    send = 1
    error = 2
    success = 3


_HEADER_STRUCT = Struct(">BBHHBx")
_UNSIGNED_LONG_STRUCT = Struct(">L")
@dataclass
class FastCGIHeader:
    version: int
    type: FastCGIType
    request_id: int
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
class FastCGIRecord:
    header: FastCGIHeader
    content: bytes

    @classmethod
    def create(cls, fcgi_type: FastCGIType, content: bytes, req_id: int):
        header = FastCGIHeader(
            FASTCGI_VERSION,
            fcgi_type,
            req_id,
            len(content),
            0,
        )
        return cls(header, content)
    
    @classmethod
    def read_from_stream(cls, stream):
        header = stream.read(_HEADER_STRUCT.size)
        if not header:
            return None
        header = FastCGIHeader.decode(header)

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

    def encode(self):
        return self.header.encode() + self.content

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
        request_record = bytearray()
        record_content = bytearray()
        record_content.append(0)
        record_content.append(FastCGIRole.responder)
        record_content.append(0) # keepalive
        record_content += bytes(5)
        request_record += self._encode_record(FastCGIType.begin, record_content, req_id)
        
        params = bytearray()
        if env:
            for name, value in env.items():
                params += self._encode_param(name.encode('ascii'), value.encode('ascii'))

        if len(params) > 0:
            request_record += self._encode_record(FastCGIType.params, params, req_id)
        request_record += self._encode_record(FastCGIType.params, bytearray(), req_id)

        if stdin:
            request_record += self._encode_record(FastCGIType.stdin, stdin, req_id)
        request_record += self._encode_record(FastCGIType.stdin, bytearray(), req_id)
        # Send request
        self.socket.send(request_record)
        self.requests[req_id]['state'] = FastCGIState.send
        self.requests[req_id]['response'] = bytearray()
        return self.build_response(request, self.await_response(req_id))
    
    def await_response(self, req_id):
        while True:
            record = FastCGIRecord.read_from_stream(self)
            if not record:
                break

            # FIXME The header ID returned is always 1 for some reason?
            # if req_id != header.request_id:
            #     continue
            if record.header.type == FastCGIType.stdout:
                self.requests[req_id]['response'] += record.content
            if record.header.type == FastCGIType.stderr:
                self.requests[req_id]['state'] = FastCGIState.error
                if req_id == record.header.request_id:
                    self.requests[req_id]['response'] += record.content
            if record.header.type == FastCGIType.end:
                if self.requests[req_id]['state'] != FastCGIState.error:
                    self.requests[req_id]['state'] = FastCGIState.success
        
        self.close()
        response = self.requests[req_id]['response']
        del self.requests[req_id]

        return response
    
    def _encode_record(self, fcgi_type: FastCGIType, content: bytes, req_id: int):
        return FastCGIRecord.create(fcgi_type, content, req_id).encode()

    def _encode_param(self, name: bytes, value: bytes):
        len_name = len(name)
        len_value = len(value)
        record = bytearray()
        if len_name < 128:
            record.append(len_name)
        else:
            record.extend(_UNSIGNED_LONG_STRUCT.pack(len_name | 0x80_00_00_00))
        if len_value < 128:
            record.append(len_value)
        else:
            record.extend(_UNSIGNED_LONG_STRUCT.pack(len_value | 0x80_00_00_00))
        return record + name + value