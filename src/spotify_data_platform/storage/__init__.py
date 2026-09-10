"""Storage naming contracts shared by local and cloud persistence adapters."""

from .s3 import (
    S3PathValidationError,
    build_bronze_playlist_key,
    build_bronze_playlist_uri,
)

__all__ = [
    "S3PathValidationError",
    "build_bronze_playlist_key",
    "build_bronze_playlist_uri",
]
