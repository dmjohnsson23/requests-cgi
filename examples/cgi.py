import requests_cgi
import requests

# Create a normal requests session object
sess = requests.Session()

# Mount the adapter
sess.mount(
    'https://example.com/', # Requests to this domain will use the adapter...
    requests_cgi.CGIAdapter(['sh', 'tests/echo.sh']) # ...and the adapter will use this CGI script
)

# Now we have the full feature set of Requests available for interaction with the CGI script
response = sess.post('https://example.com/test?oh=yeah', "This is the request body and will be echoed back")
if response.status_code == 200:
    for header in response.headers.items():
        print("Header:", header)
    for cookie in response.cookies.items():
        print("Cookie:", header)

    print("Body:", response.text)