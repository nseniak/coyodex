"""Posts ticket events to a URL the TENANT owns.

This is the fixture's one genuine outbound surface: a real network call, to a far side we do
not define, whose shape someone else decides. Everything else that looked outbound in this
tree buffers in memory and never leaves.

The endpoint is attacker-influenced by construction — a tenant types it into a settings form —
so it is checked before anything is sent. That check is a real business rule, and a map of this
tree should find it.
"""
from __future__ import annotations

import ipaddress
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

#: Seconds to wait on the tenant's endpoint before giving up.
TIMEOUT_SECONDS = 5

#: How many times a failed delivery is retried before it is dropped.
MAX_ATTEMPTS = 3

#: The only scheme a tenant endpoint may use. Plain HTTP would put the secret on the wire.
ALLOWED_SCHEME = "https"


class DeliveryError(Exception):
    """Raised when the tenant's endpoint could not be reached after every attempt."""


class EndpointRejected(Exception):
    """Raised when the configured endpoint is not one this product will call."""


def check_endpoint(url: str) -> str:
    """Refuse any endpoint that is not a public HTTPS address. Returns the hostname.

    The enforcing raises below are the operative lines: a tenant may point us at any URL, so
    an unchecked endpoint would let a tenant read our own private network through us.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != ALLOWED_SCHEME:
        raise EndpointRejected(f"{url}: only {ALLOWED_SCHEME} endpoints are called")
    host = parts.hostname
    if not host:
        raise EndpointRejected(f"{url}: no host")
    try:
        resolved = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise EndpointRejected(f"{url}: host does not resolve ({exc})") from exc
    for entry in resolved:
        address = ipaddress.ip_address(entry[4][0])
        if (address.is_private or address.is_loopback or address.is_link_local
                or address.is_reserved or address.is_multicast or address.is_unspecified):
            raise EndpointRejected(f"{url}: resolves to the private address {address}")
    return host


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect is a second endpoint nobody checked, so it is refused rather than followed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201
        raise EndpointRejected(f"{newurl}: the endpoint redirected, which is not followed")


class WebhookSender:
    """Delivers one event to one tenant-configured endpoint."""

    def __init__(self, endpoint: str, secret: str) -> None:
        self._endpoint = endpoint
        self._secret = secret
        self._opener = urllib.request.build_opener(_NoRedirects)

    def deliver(self, event: str, payload: dict[str, Any]) -> int:
        """POST the event. Returns the status code the tenant's endpoint answered with.

        The endpoint is checked BEFORE the secret header is built, so a rejected endpoint never
        sees our credential. The `open` call below is where this product stops being the only
        thing running.
        """
        check_endpoint(self._endpoint)
        body = json.dumps({"event": event, "data": payload}).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={"Content-Type": "application/json", "X-Trapdoor-Secret": self._secret},
            method="POST",
        )
        last: Exception | None = None
        for _attempt in range(MAX_ATTEMPTS):
            try:
                with self._opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                    return int(response.status)
            except urllib.error.URLError as exc:
                last = exc
        raise DeliveryError(f"{self._endpoint} unreachable after {MAX_ATTEMPTS} attempts: {last}")
