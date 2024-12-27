import pytest
import requests
import requests_cgi
import os

def sh_session(script, url='https://example.com/'):
    sess = requests.session()
    sess.mount(url, requests_cgi.CGIAdapter(['sh', os.path.join(os.path.dirname(__file__), f'cgi_scripts/{script}.sh')]))
    return sess

def test_get():
    sess = sh_session('get')
    response = sess.get('https://example.com/')
    assert response.status_code == 200
    assert response.text == "You got me!"

def test_post():
    sess = sh_session('echo')
    response = sess.post('https://example.com/', "ECHO!")
    assert response.status_code == 200
    assert response.text == "ECHO!"

def test_status_unparsed():
    sess = sh_session('status_404_unparsed')
    response = sess.get('https://example.com/')
    assert response.status_code == 404

def test_status_parsed():
    sess = sh_session('status_404_parsed')
    response = sess.get('https://example.com/')
    assert response.status_code == 404

def test_http_header():
    sess = sh_session('echo')
    response = sess.get('https://example.com/', headers={'Accept':'application/fish-tacos'})
    assert response.headers['ENV_HTTP_ACCEPT'] == '"application/fish-tacos"'

def test_timeout():
    sess = sh_session('timeout')
    with pytest.raises(requests.exceptions.Timeout):
        sess.get('https://example.com/', timeout=.1)

def test_non_existent():
    sess = sh_session('not_real')
    with pytest.raises(requests.exceptions.ConnectionError):
        sess.get('https://example.com/')

@pytest.mark.skip('Not yet passing')
def test_malformed():
    sess = sh_session('malformed')
    with pytest.raises(requests.exceptions.ConnectionError):
        sess.get('https://example.com/').headers