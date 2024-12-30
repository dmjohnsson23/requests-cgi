from http.client import HTTPException
from io import BytesIO
from os import PathLike
from requests import PreparedRequest, Response
from requests.adapters import BaseAdapter
from requests.cookies import MockRequest
from requests.exceptions import ConnectionError, ReadTimeout
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers
from subprocess import run, CalledProcessError, TimeoutExpired
from typing import Optional, Sequence, Union
from urllib.parse import urlparse


from .cgi_response import CGIResponse

__all__ = ('CGIAdapter',)

class CGIAdapter(BaseAdapter):
    """
    Generic adapter for psuedo-HTTP communication with CGI applications.

    Many CGI application will have vendor-specific extensions. Subclass this to take advantage of 
    those. These extensions are normally controlled by environment variables, which you can change
    by extending the `build_cgi_env` method.
    """
    command: str | bytes | PathLike[str] | PathLike[bytes] | Sequence[str | bytes | PathLike[str] | PathLike[bytes]]
    working_dir: Optional[str | bytes | PathLike[str] | PathLike[bytes]]

    def __init__(self, 
        command: str | bytes | PathLike[str] | PathLike[bytes] | Sequence[str | bytes | PathLike[str] | PathLike[bytes]], 
        working_dir: Optional[str | bytes | PathLike[str] | PathLike[bytes]] = None,
        override_env: Optional[dict] = None,
        ):
        """
        :param command: The command to execute for the CGI application.
        :param working_dir: The directory to execute the script from.
        """
        super().__init__()
        self.command = command
        self.working_dir = working_dir
        self.override_env = override_env
    
    def send(self, request: PreparedRequest, stream:bool = False, timeout:Optional[Union[float,tuple]] = None, verify = True, cert = None, proxies = None):
        env = self.build_cgi_env(request)
        stdin = self.build_cgi_stdin(request)
        if stdin is None:
            # Send an empty body
            stdin = b''
        else:
            # Set content length and type if there is a body
            env['CONTENT_LENGTH'] = str(len(stdin))
            env['CONTENT_TYPE'] = request.headers.get('Content-Type', 'text/plain')
        # If we have separate connect/read timeouts, use the read timeout
        # Connection timeout is ignored; it doesn't make sense in this context
        if isinstance(timeout, tuple):
            timeout = timeout[1]
        return self.execute_send(request, env, stdin, timeout)
    
    def execute_send(self, request: PreparedRequest, env: dict, stdin: Optional[bytes], timeout: Optional[float]):
        try:
            result = run(self.command, capture_output=True, cwd=self.working_dir, env=env, input=stdin, check=True, timeout=timeout)
        except CalledProcessError as e:
            if e.stdout:
                try:
                    # Process may still have returned a valid response
                    # e.g. an error 404
                    return self.build_response(request, e.stdout)
                except Exception:
                    pass # raise error below
            raise ConnectionError(e.stderr, e.stdout, request=request) from e
        except TimeoutExpired as e:
            raise ReadTimeout(request=request) from e
        return self.build_response(request, result.stdout)
    
    def close(self):
        return None
    
    def build_cgi_env(self, request: PreparedRequest)->dict:
        """
        Build a dictionary of environment variables to use when executing the CGI application.

        It is recommended to overwrite ``_cgi_env_helper`` instead of this method
        """
        env = {}
        for cls in reversed(self.__class__.__mro__):
            if '_cgi_env_helper' in cls.__dict__.keys():
                env.update(cls._cgi_env_helper(self, request))
        if self.override_env is not None:
            env.update(self.override_env)
        return env
    
    def _cgi_env_helper(self, request: PreparedRequest)->dict:
        """
        This method will be called for *each* class in the inheritance hierarchy, and the resulting
        dicts will all be merged together.
        """
        url = urlparse(request.url)
        # Standard environment variables
        env = {
            'HTTP_HOST': url.hostname,
            'PATH_INFO': request.path_url,
            'QUERY_STRING': url.query,
            'REMOTE_ADDR': '127.0.0.1',
            'REMOTE_HOST': url.hostname,
            'REQUEST_METHOD': request.method,
            'SCRIPT_NAME': '/', # TODO is this right?
            'SERVER_NAME': url.hostname,
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'GATEWAY_INTERFACE': 'CGI/1.1',
            # CONTENT_TYPE
            # AUTH_TYPE
            # PATH_TRANSLATED
            # REMOTE_IDENT
            # REMOTE_USER
            # SERVER_PORT
            # SERVER_SOFTWARE 
        }
        # HTTP headers as environment variables
        for key, value in request.headers.items():
            env[f"HTTP_{key.upper().replace('-', '_')}"] = value
        return env
    
    def build_cgi_stdin(self, request: PreparedRequest)->Optional[bytes]:
        """
        Build the body of the CGI request (stdin)
        """
        if request.body:
            return request.body if isinstance(request.body, bytes) else request.body.encode()
        return None
    
    def build_response(self, request: PreparedRequest, raw_response: bytes)->Response:
        """
        Parse the CGI response into a Requests Response object
        """
        is_parsed_mode = not raw_response.startswith(b'HTTP/') # See http://graphcomp.com/info/specs/cgi11.html "Data output from the CGI script"
        if is_parsed_mode:
            # Pretend it's a normal response for now
            raw_response = b'HTTP/1.1 200\n'+raw_response
        raw_response = BytesIO(raw_response)
        http_response = CGIResponse(raw_response)
        try:
            # Parse the HTTP response
            http_response.begin()
        except HTTPException as e:
            raise ConnectionError(request=request) from e

        # See https://docs.python-requests.org/en/latest/_modules/requests/adapters/#HTTPAdapter.build_response
        response = Response()

        # Make headers case-insensitive.
        response.headers = CaseInsensitiveDict(getattr(http_response, "headers", {}))

        if is_parsed_mode:
            # The status is in the headers instead of the normal place
            status = response.headers.get('status')
            if status:
                try:
                    response.status_code = int(status[:3])
                except ValueError:
                    raise ConnectionError(f"Could not parse status header: {status}", request=request)
                response.reason = status[4:]
            else:
                response.status_code = None
        else:
            # Fallback to None if there's no status_code, for whatever reason.
            response.status_code = getattr(http_response, "status", None)
            response.reason = http_response.reason
        if response.status_code is None:
            # CGI applications may not send a status code, so we have to infer it
            # TODO look for location header and use redirect status code if found
            response.status_code = 200
            response.reason = 'Okay'

        # Set encoding.
        response.encoding = get_encoding_from_headers(response.headers)
        response.raw = http_response

        if isinstance(request.url, bytes):
            response.url = request.url.decode("utf-8")
        else:
            response.url = request.url

        # Add new cookies from the server.
        response.cookies.extract_cookies(http_response, MockRequest(request))

        # Give the Response some context.
        response.request = request
        response.connection = self

        return response