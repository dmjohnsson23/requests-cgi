import pytest
import requests
import requests_cgi
import os
from urllib.parse import unquote

def php_session(script=None, url='https://example.com/'):
    sess = requests.session()
    sess.mount(url, requests_cgi.PHPAdapter(
        os.path.join(os.path.dirname(__file__), f'cgi_scripts/{script}.php') if script else None,
        os.path.join(os.path.dirname(__file__), 'cgi_scripts')
    ))
    return sess

def test_get():
    sess = php_session('get')
    response = sess.get('https://example.com/')
    assert response.status_code == 200
    assert response.text == "You got me!"

def test_query_string():
    sess = php_session('echo')
    response = sess.get('https://example.com/?one=1&two=2')
    assert response.status_code == 200
    json = response.json()
    assert json['$_SERVER']['REQUEST_METHOD'] == 'GET'
    assert json['$_GET']['one'] == '1'
    assert json['$_GET']['two'] == '2'

def test_post():
    sess = php_session('echo')
    response = sess.post('https://example.com/', "ECHO!")
    assert response.status_code == 200
    json = response.json()
    assert json['$_SERVER']['REQUEST_METHOD'] == 'POST'
    assert json['stdin'] == 'ECHO!'

def test_post_form_data():
    sess = php_session('echo')
    response = sess.post('https://example.com/', data={'one':'1', 'two':'2'})
    assert response.status_code == 200
    json = response.json()
    assert json['$_SERVER']['REQUEST_METHOD'] == 'POST'
    assert json['$_POST']['one'] == '1'
    assert json['$_POST']['two'] == '2'

def test_status():
    sess = php_session('status_500')
    response = sess.get('https://example.com/')
    assert response.status_code == 500
    assert response.text == "Nope, this page don't work at all"

def test_send_cookie():
    sess = php_session('echo')
    response = sess.get('https://example.com/', cookies={'my_cookie':'yum!'})
    assert response.status_code == 200
    json = response.json()
    assert json['$_COOKIE']['my_cookie'] == 'yum!'

def test_receive_cookie():
    sess = php_session('cookie')
    response = sess.get('https://example.com/')
    assert response.status_code == 200
    assert unquote(response.cookies['gingersnap']) == 'chocolate chip'

def test_router_named():
    sess = php_session()
    response = sess.get('https://example.com/get.php')
    assert response.status_code == 200
    assert response.text == "You got me!"

def test_router_index():
    sess = php_session()
    response = sess.get('https://example.com/')
    assert response.status_code == 200
    assert response.text == "This is the index"

def test_router_non_existent():
    sess = php_session()
    response = sess.get('https://example.com/not_real')
    assert response.status_code == 404