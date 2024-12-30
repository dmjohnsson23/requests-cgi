from os import PathLike
from typing import Optional, Sequence
from urllib.parse import urlparse, ParseResult as UrlParseResult

from .cgi_adapter import CGIAdapter

__all__ = ('PHPAdapter',)
# See https://www.php.net/manual/en/install.unix.commandline.php for PHP CGI usage
class PHPAdapter(CGIAdapter):
    """
    Adapter that allows running PHP scripts
    """
    php_script: Optional[str | bytes | PathLike[str] | PathLike[bytes]]

    def __init__(self, 
        php_script: str | bytes | PathLike[str] | PathLike[bytes] = None,
        working_dir: Optional[str | bytes | PathLike[str] | PathLike[bytes]] = None,
        override_env: Optional[dict] = None,
        *,
        command: str | bytes | PathLike[str] | PathLike[bytes] | Sequence[str | bytes | PathLike[str] | PathLike[bytes]] = 'php-cgi', 
        ):
        """
        :param php_script: If provided, the PHP script to execute. If None, the application will 
            attempt to route the request based on the URL.
        :param working_dir: The directory to execute the script from. This will also be considered
            the document root by the router.
        :param command: The command to execute for the php-cgi binary.
        """
        super().__init__(command, working_dir, override_env)
        self.php_script = php_script
    
    def _cgi_env_helper(self, request):
        url = urlparse(request.url)
        env = {
            'REDIRECT_STATUS': '200', # Required, PHP will refuse to run if this does not have a value
            'SCRIPT_NAME': url.path,
            'REQUEST_URI': request.path_url,
        }
        if self.working_dir is not None:
            env['DOCUMENT_ROOT'] = self.working_dir
            env['CONTEXT_DOCUMENT_ROOT'] = self.working_dir
        if self.php_script is None:
            env['SCRIPT_FILENAME'] = self.url_to_filename(url)
        else:
            env['SCRIPT_FILENAME'] = self.php_script
        return env
    
    def url_to_filename(self, url:UrlParseResult):
        """
        Route a URL to a PHP script
        """
        # TODO this is pretty rudimentary
        path = url.path
        if path.endswith('/'):
            path += 'index.php'
        return path.lstrip('/')