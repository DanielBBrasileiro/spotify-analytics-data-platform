"""Ensure the default test suite cannot contact external services."""

import ipaddress
import json
import socket
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    original_connect = socket.socket.connect
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def is_loopback(host):
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def denied(*args, **kwargs):
        raise AssertionError("Network access is forbidden in the offline test suite.")

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if not is_loopback(host):
            return denied()
        return original_connect(sock, address)

    def guarded_create_connection(address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if not is_loopback(host):
            return denied()
        return original_create_connection(address, *args, **kwargs)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if not is_loopback(host):
            return denied()
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)


@pytest.fixture
def load_spotify_fixture():
    """Load a fresh fixture per call so tests cannot mutate shared state."""
    root = Path(__file__).parent / "fixtures" / "spotify"

    def load(name):
        return json.loads((root / name).read_text(encoding="utf-8"))

    return load
