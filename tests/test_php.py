import pytest
import requests
import requests_cgi
import os

def php_session(script, url='https://example.com/'):
    sess = requests.session()
    sess.mount(url, requests_cgi.PHPAdapter(os.path.join(os.path.dirname(__file__), f'cgi_scripts/{script}.php')))
    return sess

def test_get():
    sess = php_session('get')
    response = sess.get('https://example.com/')
    assert response.status_code == 200
    assert response.text == "You got me!"

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