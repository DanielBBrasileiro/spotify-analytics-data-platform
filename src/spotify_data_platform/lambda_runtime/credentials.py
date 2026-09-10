"""Credential providers for local and AWS Lambda Spotify authentication."""

import importlib
import json
import os
from collections.abc import Mapping
from threading import RLock
from typing import Annotated, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from spotify_data_platform.auth import SpotifyAuthClient


class CredentialProviderError(RuntimeError):
    """Credentials could not be loaded without exposing secret values."""


class SecretsManagerClient(Protocol):
    """Minimal AWS Secrets Manager client surface used by the runtime."""

    def get_secret_value(self, **kwargs: Any) -> Mapping[str, Any]:
        """Return one Secrets Manager value."""
        ...


class SpotifyCredentials(BaseModel):
    """Validated confidential-client credentials with redacted representations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    client_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        repr=False
    )
    client_secret: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        repr=False
    )
    refresh_token: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] = Field(
        repr=False
    )

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "SpotifyCredentials":
        """Load local-only credentials from process environment values."""
        payload = {
            "client_id": environ.get("SPOTIFY_CLIENT_ID", ""),
            "client_secret": environ.get("SPOTIFY_CLIENT_SECRET", ""),
            "refresh_token": environ.get("SPOTIFY_REFRESH_TOKEN", ""),
        }
        return _validated_credentials(payload, "environment")


class SecretsManagerCredentialProvider:
    """Fetch and cache a JSON credential document for one Lambda container."""

    def __init__(self, client: SecretsManagerClient, secret_id: str) -> None:
        if not isinstance(secret_id, str) or not secret_id.strip():
            raise CredentialProviderError("Secrets Manager secret id is missing.")
        self._client = client
        self._secret_id = secret_id.strip()
        self._cached: SpotifyCredentials | None = None
        self._lock = RLock()

    def get_credentials(self) -> SpotifyCredentials:
        """Read the secret at most once per provider instance."""
        with self._lock:
            if self._cached is not None:
                return self._cached
            try:
                response = self._client.get_secret_value(SecretId=self._secret_id)
            except Exception:
                raise CredentialProviderError(
                    "Could not retrieve Spotify credentials from Secrets Manager."
                ) from None
            secret = response.get("SecretString") if isinstance(response, Mapping) else None
            if not isinstance(secret, str) or not secret.strip():
                raise CredentialProviderError(
                    "Secrets Manager response does not contain a valid SecretString."
                )
            try:
                payload = json.loads(secret)
            except (TypeError, ValueError):
                raise CredentialProviderError(
                    "Secrets Manager credential payload is not valid JSON."
                ) from None
            self._cached = _validated_credentials(payload, "Secrets Manager")
            return self._cached


_DEFAULT_LOCK = RLock()
_DEFAULT_CREDENTIALS: SpotifyCredentials | None = None
_DEFAULT_AUTH_CLIENT: SpotifyAuthClient | None = None


def get_default_credentials() -> SpotifyCredentials:
    """Resolve and cache credentials for the current process/runtime environment."""
    global _DEFAULT_CREDENTIALS
    with _DEFAULT_LOCK:
        if _DEFAULT_CREDENTIALS is not None:
            return _DEFAULT_CREDENTIALS
        _DEFAULT_CREDENTIALS = _load_credentials(os.environ)
        return _DEFAULT_CREDENTIALS


def get_default_auth_client() -> SpotifyAuthClient:
    """Reuse one auth client per warm container to retain token/rotation state in memory."""
    global _DEFAULT_AUTH_CLIENT
    with _DEFAULT_LOCK:
        if _DEFAULT_AUTH_CLIENT is not None:
            return _DEFAULT_AUTH_CLIENT
        credentials = get_default_credentials()
        _DEFAULT_AUTH_CLIENT = SpotifyAuthClient(
            credentials.client_id,
            credentials.client_secret,
            credentials.refresh_token,
        )
        return _DEFAULT_AUTH_CLIENT


def _load_credentials(environ: Mapping[str, str]) -> SpotifyCredentials:
    environment = environ.get("ENVIRONMENT", "").strip().lower()
    if environment == "local":
        return SpotifyCredentials.from_env(environ)
    secret_id = environ.get("AWS_SECRETS_MANAGER_SECRET_NAME", "spotify/api/credentials")
    provider = SecretsManagerCredentialProvider(_default_secrets_client(), secret_id)
    return provider.get_credentials()


def _validated_credentials(payload: Any, source: str) -> SpotifyCredentials:
    if not isinstance(payload, Mapping):
        raise CredentialProviderError(f"{source} credential payload must be a JSON object.")
    try:
        return SpotifyCredentials.model_validate(payload)
    except ValidationError:
        raise CredentialProviderError(
            f"{source} credential payload is missing or contains invalid required fields."
        ) from None


def _default_secrets_client() -> SecretsManagerClient:
    try:
        boto3 = importlib.import_module("boto3")
    except ImportError:
        raise CredentialProviderError(
            "boto3 is unavailable; use the AWS Lambda runtime or package the AWS SDK."
        ) from None
    return boto3.client("secretsmanager")


def invalidate_runtime_caches() -> None:
    """Discard cached credentials/auth state after invalid grant or explicit reset."""
    global _DEFAULT_AUTH_CLIENT, _DEFAULT_CREDENTIALS
    with _DEFAULT_LOCK:
        _DEFAULT_AUTH_CLIENT = None
        _DEFAULT_CREDENTIALS = None
