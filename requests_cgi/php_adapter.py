from os import PathLike
from typing import Optional, Sequence

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
        super().__init__(command, working_dir)
        self.php_script = php_script
    
    def build_cgi_env(self, request):
        env = super().build_cgi_env(request)
        env['REDIRECT_STATUS'] = '200' # Required, PHP will refuse to run if this does not have a value
        if self.php_script is None:
            pass
            # env['SCRIPT_FILENAME'] = self.url_to_filename(request.path_url)
        else:
            env['SCRIPT_FILENAME'] = self.php_script
        return env
    
    def url_to_filename(self, url):
        """
        Route a URL to a PHP script
        """
        pass