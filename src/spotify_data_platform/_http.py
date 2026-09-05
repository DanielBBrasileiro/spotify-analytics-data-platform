"""Small standard-library transport; never follow credential-bearing redirects."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class TransportError(Exception):
    """An HTTP exchange failed before a usable response was received."""


@dataclass(frozen=True)
class Response:
    """HTTP response whose potentially sensitive contents are excluded from repr."""

    status: int
    body: bytes = field(repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(request: Request, timeout: float) -> Response:
    """Send once with TLS verification, a finite timeout, and no redirects."""
    try:
        try:
            response = build_opener(_NoRedirect()).open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            return Response(response.status, response.read(), dict(response.headers))
    except (URLError, OSError, ValueError, HTTPException):
        raise TransportError("HTTP transport failed.") from None
