"""Secrets Manager and local credential-provider security contracts."""

import sys
import types
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from spotify_data_platform.auth import SpotifyAuthClient
from spotify_data_platform.lambda_runtime import credentials as credentials_module
from spotify_data_platform.lambda_runtime.credentials import (
    CredentialProviderError,
    SecretsManagerCredentialProvider,
    SpotifyCredentials,
)

SECRET_ID = "spotify/api/credentials"
VALID_SECRET = (
    '{"client_id":"synthetic-id","client_secret":"synthetic-secret",'
    '"refresh_token":"synthetic-refresh"}'
)


@pytest.fixture(autouse=True)
def reset_runtime_cache():
    credentials_module.invalidate_runtime_caches()
    yield
    credentials_module.invalidate_runtime_caches()


def test_spotify_credentials_are_validated_trimmed_frozen_and_redacted():
    credentials = SpotifyCredentials(
        client_id=" synthetic-id ",
        client_secret=" synthetic-secret ",
        refresh_token=" synthetic-refresh ",
    )
    assert credentials.client_id == "synthetic-id"
    assert credentials.client_secret == "synthetic-secret"
    assert credentials.refresh_token == "synthetic-refresh"
    assert "synthetic" not in repr(credentials)
    with pytest.raises(ValidationError):
        credentials.client_id = "changed"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"client_id": "", "client_secret": "secret", "refresh_token": "refresh"},
        {"client_id": "id", "client_secret": "   ", "refresh_token": "refresh"},
        {"client_id": "id", "client_secret": "secret", "refresh_token": ""},
        {
            "client_id": "id",
            "client_secret": "secret",
            "refresh_token": "refresh",
            "extra": "forbidden",
        },
    ],
)
def test_invalid_credential_values_are_rejected_without_leaking_input(payload):
    marker = "do-not-leak-this-secret"
    payload = {**payload, "leak_marker": marker}
    with pytest.raises(CredentialProviderError) as exc_info:
        credentials_module._validated_credentials(payload, "test")
    assert marker not in str(exc_info.value)


def test_non_mapping_payload_is_rejected():
    with pytest.raises(CredentialProviderError, match="JSON object"):
        credentials_module._validated_credentials(["not", "mapping"], "test")


def test_local_environment_provider_uses_env_without_aws(monkeypatch):
    env = {
        "ENVIRONMENT": " LOCAL ",
        "SPOTIFY_CLIENT_ID": "synthetic-id",
        "SPOTIFY_CLIENT_SECRET": "synthetic-secret",
        "SPOTIFY_REFRESH_TOKEN": "synthetic-refresh",
    }
    with patch.object(credentials_module, "_default_secrets_client") as client_factory:
        credentials = credentials_module._load_credentials(env)
    client_factory.assert_not_called()
    assert credentials.client_id == "synthetic-id"


def test_local_environment_missing_secret_field_is_sanitized():
    env = {
        "ENVIRONMENT": "local",
        "SPOTIFY_CLIENT_ID": "synthetic-id",
        "SPOTIFY_CLIENT_SECRET": "very-secret-value",
    }
    with pytest.raises(CredentialProviderError, match="environment") as exc_info:
        credentials_module._load_credentials(env)
    assert "very-secret-value" not in str(exc_info.value)


def test_cloud_provider_reads_expected_secret_and_caches_result():
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": VALID_SECRET}
    provider = SecretsManagerCredentialProvider(client, SECRET_ID)

    first = provider.get_credentials()
    second = provider.get_credentials()

    assert first is second
    assert first.refresh_token == "synthetic-refresh"
    client.get_secret_value.assert_called_once_with(SecretId=SECRET_ID)


def test_concurrent_calls_share_one_secrets_manager_read():
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": VALID_SECRET}
    provider = SecretsManagerCredentialProvider(client, SECRET_ID)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: provider.get_credentials(), range(20)))
    assert all(result is results[0] for result in results)
    client.get_secret_value.assert_called_once_with(SecretId=SECRET_ID)


@pytest.mark.parametrize("secret_id", ["", "   ", None, 123])
def test_secret_id_must_be_nonblank_string(secret_id):
    with pytest.raises(CredentialProviderError, match="secret id"):
        SecretsManagerCredentialProvider(Mock(), secret_id)


def test_secrets_manager_api_failure_is_sanitized():
    client = Mock()
    client.get_secret_value.side_effect = RuntimeError("upstream secret details")
    with pytest.raises(CredentialProviderError, match="Could not retrieve") as exc_info:
        SecretsManagerCredentialProvider(client, SECRET_ID).get_credentials()
    assert "upstream secret details" not in str(exc_info.value)


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"SecretString": ""},
        {"SecretString": "   "},
        {"SecretString": b"binary"},
        [],
    ],
)
def test_missing_or_non_string_secret_value_is_rejected(response):
    client = Mock()
    client.get_secret_value.return_value = response
    with pytest.raises(CredentialProviderError, match="SecretString"):
        SecretsManagerCredentialProvider(client, SECRET_ID).get_credentials()


def test_invalid_secret_json_is_sanitized():
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": "{super-secret-invalid-json"}
    with pytest.raises(CredentialProviderError, match="not valid JSON") as exc_info:
        SecretsManagerCredentialProvider(client, SECRET_ID).get_credentials()
    assert "super-secret" not in str(exc_info.value)


def test_invalid_secret_schema_is_sanitized():
    client = Mock()
    client.get_secret_value.return_value = {
        "SecretString": '{"client_id":"id","client_secret":"do-not-leak"}'
    }
    with pytest.raises(CredentialProviderError, match="invalid required fields") as exc_info:
        SecretsManagerCredentialProvider(client, SECRET_ID).get_credentials()
    assert "do-not-leak" not in str(exc_info.value)


def test_non_local_environment_uses_secrets_manager_default_id():
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": VALID_SECRET}
    with patch.object(credentials_module, "_default_secrets_client", return_value=client):
        credentials = credentials_module._load_credentials({"ENVIRONMENT": "prod"})
    assert credentials.client_id == "synthetic-id"
    client.get_secret_value.assert_called_once_with(SecretId=SECRET_ID)


def test_custom_secret_id_is_used_in_cloud_environment():
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": VALID_SECRET}
    with patch.object(credentials_module, "_default_secrets_client", return_value=client):
        credentials_module._load_credentials(
            {"ENVIRONMENT": "dev", "AWS_SECRETS_MANAGER_SECRET_NAME": "custom/spotify"}
        )
    client.get_secret_value.assert_called_once_with(SecretId="custom/spotify")


def test_default_credentials_cache_survives_warm_invocations(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    client = Mock()
    client.get_secret_value.return_value = {"SecretString": VALID_SECRET}
    with patch.object(credentials_module, "_default_secrets_client", return_value=client):
        first = credentials_module.get_default_credentials()
        second = credentials_module.get_default_credentials()
    assert first is second
    client.get_secret_value.assert_called_once()


def test_default_auth_client_is_cached_for_token_state(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "local")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "synthetic-id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "synthetic-secret")
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "synthetic-refresh")
    first = credentials_module.get_default_auth_client()
    second = credentials_module.get_default_auth_client()
    assert first is second
    assert isinstance(first, SpotifyAuthClient)
    assert "synthetic-secret" not in repr(first)


def test_default_auth_client_uses_cached_credentials(monkeypatch):
    credentials = SpotifyCredentials(
        client_id="id", client_secret="secret", refresh_token="refresh"
    )
    with (
        patch.object(
            credentials_module, "get_default_credentials", return_value=credentials
        ) as loader,
        patch.object(credentials_module, "SpotifyAuthClient", autospec=True) as auth_factory,
    ):
        first = credentials_module.get_default_auth_client()
        second = credentials_module.get_default_auth_client()
    assert first is second
    loader.assert_called_once_with()
    auth_factory.assert_called_once_with("id", "secret", "refresh")


def test_default_secrets_client_uses_boto3_runtime_module(monkeypatch):
    client = object()
    boto3 = types.SimpleNamespace(client=Mock(return_value=client))
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    assert credentials_module._default_secrets_client() is client
    boto3.client.assert_called_once_with("secretsmanager")


def test_default_secrets_client_reports_missing_sdk(monkeypatch):
    real_import = credentials_module.importlib.import_module

    def fake_import(name):
        if name == "boto3":
            raise ImportError
        return real_import(name)

    monkeypatch.setattr(credentials_module.importlib, "import_module", fake_import)
    with pytest.raises(CredentialProviderError, match="boto3 is unavailable"):
        credentials_module._default_secrets_client()
