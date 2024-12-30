from .fcgi_adapter import FastCGIAdapter
from .php_adapter import PHPAdapter

__all__ = ('PHPFPMAdapter',)

class PHPFPMAdapter(FastCGIAdapter, PHPAdapter):
    """
    A FastCGIAdapter specially tailored to work with PHP-FPM
    """
    pass