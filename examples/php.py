import requests_cgi
import requests

# Create a normal requests session object
sess = requests.Session()

# Mount the adapter
sess.mount(
    'https://example.com/', # Requests to this domain will use the adapter...
    requests_cgi.PHPAdapter() # ...and the adapter will use this PHP script
)

# Now we have the full feature set of Requests available for interaction with the CGI script
response = sess.post('https://example.com/tests/echo.php?oh=yeah', "This is the request body and will be echoed back")
if response.status_code == 200:
    for header in response.headers.items():
        print("Header:", header)
    for cookie in response.cookies.items():
        print("Cookie:", header)

    print("Body:", response.text)
else:
    response.raise_for_status()