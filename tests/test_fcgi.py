import pytest
from subprocess import Popen
import requests
import requests_cgi
import os

@pytest.fixture
def fcgi_session(script_name, bind_url):
    # FIXME I have to launch the server manually for some reason; this doesn't work
    # server = Popen(['python3', os.path.join(os.path.dirname(__file__), f'fcgi_scripts/{script_name}.py')])
    sess = requests.session()
    sess.mount(bind_url, requests_cgi.FastCGIAdapter('fcgi.sock'))
    yield sess
    # server.terminate()

@pytest.mark.script_name('echo')
def test_post(fcgi_session, bind_url):
    response = fcgi_session.post(bind_url, "ECHO!")
    assert response.status_code == 200
    assert response.text.strip() == "ECHO!"
