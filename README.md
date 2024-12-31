# CGI Adapter for Requests

This library allows using the popular [Requests](https://docs.python-requests.org/en/latest/index.html) library to directly make requests to CGI-based application, bypassing the need for an actual web server such as Apache or Nginx. This can result in simplicity and better performance with inter-application communications.

CGI is a ubiquitous, albeit somewhat outdated, technology. Numerous application support the CGI protocol, and this library simplifies usage of these applications without the need to go through an actual web server.

FastCGI, as the name suggests, is an evolution of the CGI protocol that is designed to be faster. It accomplishes this primarily by way of keeping a live active "server" process rather than creating a new process for each request. It is less widely used, but if available, it will likely be faster, particularly if you need to execute multiple requests to the application.

The PHP language supports both protocols, and this library also contains additional adapters specially tuned to PHP's implementations of the protocols. This allows Python to call into a PHP application as if it were making an HTTP request, with the simplicity and performance benefits of removing the "middle man".

# Purpose

This application can be useful in the following sorts of situations:

1. For inter-application communication between a Python web app and a CGI or PHP application on the same server
2. To expose the existing HTTP API of a CGI of PHP application to a command-line tool, such as an application management tool
3. To use Python as a "middleware" to proxy another application (e.g. as part of a legacy application conversion, to put additional barriers in front of an insecure application, to embed the other application, and/or for data sharing)
4. For testing CGI or PHP applications without needing a server
5. Creating a (probably not very performant, but educational) web server for CGI applications

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
    # Requests to this domain will use the CGI adapter...
    'https://example.com/', 
    # ...and the adapter will use this CGI script for all paths
    requests_cgi.CGIAdapter(['sh', 'myscript.sh']) 
)
sess.mount(
    # Requests to this domain will use the PHP adapter...
    'https://php.net/', 
    # ...and the adapter will use this 'router.php' for all paths
    requests_cgi.PHPAdapter('router.php') 
)
sess.mount(
    # Requests to this domain will use the PHP adapter...
    'https://php.org/', 
    # ...and the adapter will choose the PHP script based on the URL path in each request
    requests_cgi.PHPAdapter() 
)
sess.mount(
    # Requests to this domain will use the FastCGI adapter...
    'https://example.net/', 
    # ...and the adapter will relay traffic to this unix socket via FastCGI
    requests_cgi.FastCGIAdapter.connect('fcgi.sock') 
)
from socket import AddressFamily
sess.mount(
    # Requests to this domain will use the FastCGI adapter...
    'https://example.org/', 
    # ...and the adapter will relay traffic to this IP and Port via FastCGI
    requests_cgi.FastCGIAdapter.connect(('127.0.0.1', 1234), AddressFamily.AF_INET) 
)
# Note: if the FastCGI process is not already running on your machine, you will need to start it 
# before you can use the FastCGI adapter. The adapter will not attempt to launch the process; 
# merely connect to it.
```

## Roadmap

For sure happening:

* Add more tests
* Fix bugs
* Provide a way to launch the FastCGI process rather than relying on it already existing

Maybe happening:

* Additional special-purpose adapters for other common languages or frameworks (e.g. Perl?) like the current PHP adapter (I'm not sure what features would be actually helpful to implement for other languages/frameworks though.)

Probably not happening:

* Support WSGI (Since both applications would be Python-based, I don't see a point. There are better ways to accomplish all use cases I can think of.)

## People I stole code from

Credit given where credit is due:

* [Requests](https://docs.python-requests.org/en/latest/_modules/requests/adapters/#HTTPAdapter) -- HTTP-related code based on `HTTPAdapter`
* [CPython Standard Library](https://github.com/python/cpython/blob/main/Lib/http/client.py) -- More HTTP-related code based on `http.client.HTTPResponse`
* [FCGI-Client](https://github.com/darkpills/fcgi-client) -- FastCGI code based on this library