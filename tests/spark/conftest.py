"""Local Spark 3.5 test fixtures. External network access remains blocked."""

import socket
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "spotify"


@pytest.fixture(scope="session")
def spark():
    session = (
        SparkSession.builder.master("local[2]")
        .appName("spotify-data-platform-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.host", "127.0.0.1")
        .getOrCreate()
    )
    yield session
    session.stop()


@pytest.fixture
def block_external_network(monkeypatch):
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    def guarded_connect(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError(f"External network disabled in Spark tests: {host}")
        return original_connect(sock, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError(f"External DNS disabled in Spark tests: {host}")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
