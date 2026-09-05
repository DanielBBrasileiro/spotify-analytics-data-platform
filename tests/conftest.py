"""Ensure the default test suite cannot contact external services."""

import json
import socket
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Network access is forbidden in the offline test suite.")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def load_spotify_fixture():
    """Load a fresh fixture per call so tests cannot mutate shared state."""
    root = Path(__file__).parent / "fixtures" / "spotify"

    def load(name):
        return json.loads((root / name).read_text(encoding="utf-8"))

    return load
