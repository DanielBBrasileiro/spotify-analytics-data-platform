"""AWS Lambda runtime adapters for the Spotify Bronze ingestion path."""

from .credentials import (
    CredentialProviderError,
    SecretsManagerCredentialProvider,
    SpotifyCredentials,
    get_default_auth_client,
    get_default_credentials,
    invalidate_runtime_caches,
)
from .handler import (
    LambdaConfigurationError,
    LambdaExtractionRequest,
    LambdaExtractorService,
    lambda_handler,
)
from .s3_writer import S3BronzeWriteError, S3BronzeWriter

__all__ = [
    "CredentialProviderError",
    "LambdaConfigurationError",
    "LambdaExtractionRequest",
    "LambdaExtractorService",
    "S3BronzeWriteError",
    "S3BronzeWriter",
    "SecretsManagerCredentialProvider",
    "SpotifyCredentials",
    "get_default_auth_client",
    "get_default_credentials",
    "invalidate_runtime_caches",
    "lambda_handler",
]
