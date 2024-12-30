# CGI Adapter for Requests

This library allows using the popular [Requests](https://docs.python-requests.org/en/latest/index.html) library to directly make requests to CGI application, bypassing the need for an actual web server such as Apache or Nginx. This can result in simplicity and better performance with inter-application communications. There is also another adapter specially tuned for running PHP scripts as an HTTP request.

# Purpose

This application can be useful in the following sorts of situations:

1. For inter-application communication between a Python web app and a CGI or PHP application on the same server
2. To expose the existing HTTP API of a CGI of PHP application to a command-line tool, such as an application management tool
3. To use Python as a "middleware" to proxy another application (e.g. as part of a legacy application conversion, to put additional barriers in front of an insecure application, to embed the other application, and/or for data sharing)
4. For testing CGI or PHP applications without needing a server

## Usage

To use the adapter, all that is needed is to mount it to your Requests session object. Beyond this, no other changes are needed compared with vanilla Requests. All requests to the mounted domains will be wired directly to the CGI or PHP application.

```python
import requests
import requests_cgi

# Create a normal requests session object
sess = requests.Session()

# Mount the adapter(s). 
# The domains your mount to can be anything you like, and do not need to exist.
# If they do exist, mounting the adapter will prevent access to the real site.
sess.mount(
    'https://example.com/', # Requests to this domain will use the CGI adapter...
    requests_cgi.CGIAdapter(['sh', 'myscript.sh']) # ...and the adapter will use this CGI script for all paths
)
sess.mount(
    'https://php.net/', # Requests to this domain will use the PHP adapter...
    requests_cgi.PHPAdapter('router.php') # ...and the adapter will use this PHP script for all paths
)
sess.mount(
    'https://php.org/', # Requests to this domain will use the PHP adapter...
    requests_cgi.PHPAdapter() # ...and the adapter will choose the PHP script based on the URL path in each request
)
sess.mount(
    'https://example.net/', # Requests to this domain will use the FastCGI adapter...
    requests_cgi.FastCGIAdapter('fcgi.sock') # ...and the adapter will relay traffic to this unix socket via FastCGI
)
from socket import AddressFamily
sess.mount(
    'https://example.org/', # Requests to this domain will use the FastCGI adapter...
    requests_cgi.FastCGIAdapter(('127.0.0.1', 1234), AddressFamily.AF_INET) # ...and the adapter will relay traffic to this IP and Port via FastCGI
)
```

## Roadmap

For sure happening:

* Add more tests
* Fix bugs

Maybe happening:

* Additional special-purpose adapters for other common languages or frameworks (e.g. Perl?) like the current PHP adapter (I'm not sure what features would be actually helpful to implement for other languages/frameworks though.)

Probably not happening:

* Support WSGI (Since both applications would be Python-based, I don't see a point. There are better ways to accomplish all use cases I can think of.)

## People I stole code from

Credit given where credit is due:

* [Requests](https://docs.python-requests.org/en/latest/_modules/requests/adapters/#HTTPAdapter) -- HTTP-related code based on `HTTPAdapter`
* [CPython Standard Library](https://github.com/python/cpython/blob/main/Lib/http/client.py) -- More HTTP-related code based on `http.client.HTTPResponse`
* [FCGI-Client](https://github.com/darkpills/fcgi-client) -- FastCGI code based on this library