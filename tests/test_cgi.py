import pytest
import requests
import requests_cgi
import os

@pytest.fixture
def sh_session(script_name, bind_url):
    sh_session = requests.session()
    sh_session.mount(bind_url, requests_cgi.CGIAdapter(['sh', os.path.join(os.path.dirname(__file__), f'cgi_scripts/{script_name}.sh')]))
    return sh_session

@pytest.mark.script_name('get')
def test_get(sh_session, bind_url):
    response = sh_session.get(bind_url)
    assert response.status_code == 200
    assert response.text == "You got me!"

@pytest.mark.script_name('echo')
def test_post(sh_session, bind_url):
    response = sh_session.post(bind_url, "ECHO!")
    assert response.status_code == 200
    assert response.text == "ECHO!"

@pytest.mark.script_name('status_404_unparsed')
def test_status_unparsed(sh_session, bind_url):
    response = sh_session.get(bind_url)
    assert response.status_code == 404

@pytest.mark.script_name('status_404_parsed')
def test_status_parsed(sh_session, bind_url):
    response = sh_session.get(bind_url)
    assert response.status_code == 404

@pytest.mark.script_name('echo')
def test_http_header(sh_session, bind_url):
    response = sh_session.get(bind_url, headers={'Accept':'application/fish-tacos'})
    assert response.headers['ENV_HTTP_ACCEPT'] == '"application/fish-tacos"'

@pytest.mark.script_name('timeout')
def test_timeout(sh_session, bind_url):
    with pytest.raises(requests.exceptions.Timeout):
        sh_session.get(bind_url, timeout=.1)

@pytest.mark.script_name('not_real')
def test_non_existent(sh_session, bind_url):
    with pytest.raises(requests.exceptions.ConnectionError):
        sh_session.get(bind_url)

@pytest.mark.script_name('malformed')
def test_malformed(sh_session, bind_url):
    with pytest.raises(requests.exceptions.ConnectionError):
        sh_session.get(bind_url)