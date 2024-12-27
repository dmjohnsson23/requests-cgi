from http.client import HTTPResponse, _UNKNOWN

class CGIResponse(HTTPResponse):
    """
    Reads and interprets an HTTP response from a CGI application.
    """
    def __init__(self, raw_response, debuglevel = 0, method = None, url = None):
        # See https://github.com/python/cpython/blob/4f59f1d0d31522483fd881af5de3dadc0121401b/Lib/http/client.py#L261-L289
        self.fp = raw_response
        self.debuglevel = debuglevel
        self._method = method

        # The HTTPResponse object is returned via urllib.  The clients
        # of http and urllib expect different attributes for the
        # headers.  headers is used here and supports urllib.  msg is
        # provided as a backwards compatibility layer for http
        # clients.

        self.headers = self.msg = None

        # from the Status-Line of the response
        self.version = _UNKNOWN # HTTP-Version
        self.status = _UNKNOWN  # Status-Code
        self.reason = _UNKNOWN  # Reason-Phrase

        self.chunked = _UNKNOWN         # is "chunked" being used?
        self.chunk_left = _UNKNOWN      # bytes left to read in current chunk
        self.length = _UNKNOWN          # number of bytes left in response
        self.will_close = _UNKNOWN      # conn will close at end of response