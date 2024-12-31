from dataclasses import dataclass
from enum import IntEnum, IntFlag
from requests import PreparedRequest
from requests.exceptions import ConnectionError, ReadTimeout
from socket import socket, error as SocketError, AddressFamily, SOL_SOCKET, SO_REUSEADDR
from struct import Struct
from typing import Optional

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
        # The spec recommends padding to make the full record length a multiple of 8 bytes. This 
        # is supposedly a performance thing. However, in practice I actually got worse performance 
        # when I tried it. Anyway, performance seems perfectly fine with or without padding. And I 
        # also doubt this library will ever reach the level of optimization where tweaks like that 
        # would be impactful.
        header = RecordHeader(
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
        header = RecordHeader.decode(header)

        content = bytearray()
        bytes_read = 0
        while bytes_read < header.content_length:
            buffer = stream.read(header.content_length - bytes_read)
            if not buffer:
                break
            bytes_read += len(buffer)
            content += buffer
        # TODO not sure why we need all that above to fully capture the regular content, but not the padding...
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
    keep_connection = 0b00000001


# Specs: https://fastcgi-archives.github.io/_Specification.html#S5.1
_BEGIN_REQUEST_STRUCT = Struct(">HBxxxxx")
@dataclass
class BeginRequestBody:
    role: Role
    flags: BeginRequestOptions = BeginRequestOptions(0)

    def encode(self):
        return _BEGIN_REQUEST_STRUCT.pack(self.role, self.flags)


@dataclass
class ActiveRequest:
    id: int
    state: State
    content: bytearray


class FastCGIAdapter(CGIAdapter):
    """
    Reads and interprets an HTTP response from a FastCGI application.

    This is largely based on https://github.com/darkpills/fcgi-client/blob/master/src/fcgi_client/FastCGIClient.py
    """

    def __init__(self, address, address_family:AddressFamily=AddressFamily.AF_UNIX, override_env: Optional[dict] = None):
        self.socket = None
        self.requests = [None] # Keep track of in-flight requests
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
        # Get the lowest available request ID (See https://fastcgi-archives.github.io/FastCGI_Specification.html#S3.3 "Managing request IDs")
        try:
            req_id = self.requests.index(None, 1)
        except ValueError:
            req_id = len(self.requests)
            self.requests.append(None)
        # Assemble the packet
        # First the begin request record
        packet = bytearray()
        packet += Record.create(RecordType.begin, BeginRequestBody(Role.responder).encode(), req_id).encode()
        # Then the params (pseudo environment variables)
        params = bytearray()
        if env:
            for name, value in env.items():
                params += NameValue(name.encode('ascii'), value.encode('ascii')).encode()
        if len(params) > 0:
            packet += Record.create(RecordType.params, params, req_id).encode()
        packet += Record.create(RecordType.params, bytearray(), req_id).encode()
        # Then the main request body (pseudo sdtin)
        if stdin:
            packet += Record.create(RecordType.stdin, stdin, req_id).encode()
        # Stream ends with an empty record (see https://fastcgi-archives.github.io/FastCGI_Specification.html#S3.3 "Types of record types")
        packet += Record.create(RecordType.stdin, bytearray(), req_id).encode()
        # Send request
        self.socket.send(packet)
        self.requests[req_id] = ActiveRequest(req_id, State.send, bytearray())
        response = self.await_response(req_id)
        if response.state == State.success:
            return self.build_response(request, response.content)
        else:
            # TODO capture and display stderr
            raise ConnectionError('Invalid response', request=request)
    
    def await_response(self, req_id)->ActiveRequest:
        while True:
            record = Record.read_from_stream(self)
            if not record:
                break

            # FIXME The request ID returned from the FastCGI script is always 1 for some reason, 
            # even if we send a larger value. Not a problem now, because we aren't sending 
            # concurrent requests and always use the lowest available ID anyway, but possibly an 
            # issue in the future. I also suspect this is an issue with the FastCGI script, not 
            # this code.
            if req_id != record.header.request_id:
                # TODO there could be records we shouldn't just ignore
                continue
            if record.header.type == RecordType.stdout:
                self.requests[req_id].content += record.content
            if record.header.type == RecordType.stderr:
                self.requests[req_id].state = State.error
                if req_id == record.header.request_id:
                    self.requests[req_id].content += record.content
            if record.header.type == RecordType.end:
                 # TODO an END packet may not always be a graceful end; see https://fastcgi-archives.github.io/FastCGI_Specification.html#S5.5
                if self.requests[req_id].state != State.error:
                    self.requests[req_id].state = State.success
        
        self.close()
        response = self.requests[req_id]
        self.requests[req_id] = None

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