import pytest
import requests
import requests_cgi
import os
from urllib.parse import unquote, urljoin

@pytest.fixture
def php_session(script_name, bind_url):
    sess = requests.session()
    sess.mount(bind_url, requests_cgi.PHPAdapter(
        os.path.join(os.path.dirname(__file__), f'cgi_scripts/{script_name}.php') if script_name else None,
        os.path.join(os.path.dirname(__file__), 'cgi_scripts')
    ))
    return sess

@pytest.mark.script_name('get')
def test_get(php_session, bind_url):
    response = php_session.get(bind_url)
    assert response.status_code == 200
    assert response.text == "You got me!"

@pytest.mark.script_name('echo')
def test_query_string(php_session, bind_url):
    response = php_session.get(urljoin(bind_url, '/?one=1&two=2'))
    assert response.status_code == 200
    json = response.json()
    assert json['$_SERVER']['REQUEST_METHOD'] == 'GET'
    assert json['$_GET']['one'] == '1'
    assert json['$_GET']['two'] == '2'

@pytest.mark.script_name('echo')
def test_post(php_session, bind_url):
    response = php_session.post(bind_url, "ECHO!")
    assert response.status_code == 200
    json = response.json()
    assert json['$_SERVER']['REQUEST_METHOD'] == 'POST'
    assert json['stdin'] == 'ECHO!'

@pytest.mark.script_name('echo')
def test_post_form_data(php_session, bind_url):
    response = php_session.post(bind_url, data={'one':'1', 'two':'2'})
    assert response.status_code == 200
    json = response.json()
    assert json['$_SERVER']['REQUEST_METHOD'] == 'POST'
    assert json['$_POST']['one'] == '1'
    assert json['$_POST']['two'] == '2'

@pytest.mark.script_name('status_500')
def test_status(php_session, bind_url):
    response = php_session.get(bind_url)
    assert response.status_code == 500
    assert response.text == "Nope, this page don't work at all"

@pytest.mark.script_name('echo')
def test_send_cookie(php_session, bind_url):
    response = php_session.get(bind_url, cookies={'my_cookie':'yum!'})
    assert response.status_code == 200
    json = response.json()
    assert json['$_COOKIE']['my_cookie'] == 'yum!'

@pytest.mark.script_name('cookie')
def test_receive_cookie(php_session, bind_url):
    response = php_session.get(bind_url)
    assert response.status_code == 200
    assert unquote(response.cookies['gingersnap']) == 'chocolate chip'

def test_router_named(php_session, bind_url):
    response = php_session.get(urljoin(bind_url, '/get.php'))
    assert response.status_code == 200
    assert response.text == "You got me!"

def test_router_index(php_session, bind_url):
    response = php_session.get(bind_url)
    assert response.status_code == 200
    assert response.text == "This is the index"

def test_router_non_existent(php_session, bind_url):
    response = php_session.get(urljoin(bind_url, '/not_real'))
    assert response.status_code == 404