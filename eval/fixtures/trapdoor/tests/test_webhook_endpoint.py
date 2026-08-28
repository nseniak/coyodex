"""Which endpoints this product will call, and which it refuses."""
from __future__ import annotations

import pytest

from src.notify.webhook_sender import ALLOWED_SCHEME, EndpointRejected, check_endpoint


def make_endpoint(host: str = "example.com", scheme: str = ALLOWED_SCHEME) -> str:
    """Builder, so a test names the endpoint shape it means."""
    return f"{scheme}://{host}/hooks/tickets"


def test_plain_http_is_refused():
    with pytest.raises(EndpointRejected):
        check_endpoint(make_endpoint(scheme="http"))


def test_loopback_is_refused():
    with pytest.raises(EndpointRejected):
        check_endpoint(make_endpoint("127.0.0.1"))


def test_a_private_address_is_refused():
    with pytest.raises(EndpointRejected):
        check_endpoint(make_endpoint("10.0.0.5"))


def test_the_cloud_metadata_address_is_refused():
    with pytest.raises(EndpointRejected):
        check_endpoint(make_endpoint("169.254.169.254"))


def test_an_endpoint_with_no_host_is_refused():
    with pytest.raises(EndpointRejected):
        check_endpoint("https:///hooks")
