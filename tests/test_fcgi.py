import pytest
from subprocess import Popen
import requests
import requests_cgi
import os
from time import sleep, time

@pytest.fixture
def fcgi_session(script_name, bind_url, tmp_path):
    server = Popen(['python3', os.path.join(os.path.dirname(__file__), f'fcgi_scripts/{script_name}.py')], cwd=tmp_path)
    t = time()
    while not os.path.exists(tmp_path / 'fcgi.sock'):
        if time() - t > 5:
            raise Exception(f'Timeout waiting for FastCGI script to create socket: {script_name}')
        sleep(.1)
    sess = requests.session()
    sess.mount(bind_url, requests_cgi.FastCGIAdapter(tmp_path / 'fcgi.sock'))
    yield sess
    server.terminate()
    os.unlink(tmp_path / 'fcgi.sock')

@pytest.mark.script_name('echo')
def test_post(fcgi_session, bind_url):
    response = fcgi_session.post(bind_url, "ECHO!")
    assert response.status_code == 200
    assert response.text.strip() == "ECHO!"
