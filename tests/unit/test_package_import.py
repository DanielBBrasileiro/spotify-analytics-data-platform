"""Unit tests verifying package importability and baseline metadata."""

import re

import spotify_data_platform


def test_package_import() -> None:
    """Verify that the spotify_data_platform package can be imported."""
    assert spotify_data_platform is not None


def test_package_version_format() -> None:
    """Verify that __version__ is defined and complies with semantic versioning."""
    version = spotify_data_platform.__version__
    assert isinstance(version, str)
    assert re.match(r"^\d+\.\d+\.\d+$", version), f"Invalid semver: {version}"


def test_package_has_docstring() -> None:
    """Verify that the root package includes a descriptive docstring."""
    assert spotify_data_platform.__doc__ is not None
    assert "Spotify Analytics Data Platform" in spotify_data_platform.__doc__
