from dataclasses import dataclass
from requests import PreparedRequest
from requests.exceptions import ConnectionError
from socket import AddressFamily
from typing import Optional

from ..cgi_adapter import CGIAdapter
from .protocol import *
from .connection import *

__all__ = ('FastCGIAdapter','Connection','ExternalConnection','SubprocessConnection')

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

    def __init__(self, connection:Connection, override_env: Optional[dict] = None):
        self.connection = connection
        self.requests = [None] # Keep track of in-flight requests
        self.working_dir = None
        self.override_env = override_env
    
    def close(self):
        self.connection.close()
    
    def _cgi_env_helper(self, request):
        env = {}
        if isinstance(self.connection, ExternalConnection) and self.connection.address_family == AddressFamily.AF_INET:
            # Address of server
            ip, port = self.address
            env['SERVER_ADDR'] = ip
            env['SERVER_PORT'] = port
            # Address of client
            ip, port = self.connection.socket.getsockname() 
            env['REMOTE_ADDR'] = ip
            env['REMOTE_PORT'] = port
        return env
    
    def execute_send(self, request: PreparedRequest, env: dict, stdin: Optional[bytes], timeout: Optional[float]):
        self.connection.open()
        self.connection.socket.settimeout(timeout)
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
        self.connection.socket.send(packet)
        self.requests[req_id] = ActiveRequest(req_id, State.send, bytearray())
        response = self.await_response(req_id)
        if response.state == State.success:
            return self.build_response(request, response.content)
        else:
            # TODO capture and display stderr
            raise ConnectionError('Invalid response', request=request)
    
    def await_response(self, req_id)->ActiveRequest:
        while True:
            record = Record.read_from_stream(self.connection)
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

    @classmethod
    def connect(cls, address, address_family:AddressFamily=AddressFamily.AF_UNIX, **kwargs):
        return cls(ExternalConnection(address, address_family), **kwargs)
    
    @classmethod
    def launch(cls, command, working_dir = None, **kwargs):
        return cls(SubprocessConnection(command, working_dir), **kwargs)