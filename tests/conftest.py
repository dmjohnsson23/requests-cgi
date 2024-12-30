import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "script_name(name): The session will use the script with this name")
    config.addinivalue_line("markers", "bind_url(url): The session will bind to this URL")


@pytest.fixture
def script_name(request):
    marker = request.node.get_closest_marker("script_name")
    if marker is None:
        return None
    else:
        return marker.args[0]


@pytest.fixture
def bind_url(request):
    marker = request.node.get_closest_marker("bind_url")
    if marker is None:
        return 'https://example.com/'
    else:
        return marker.args[0]