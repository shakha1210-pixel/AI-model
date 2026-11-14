import socket

import pytest
from cryptography.fernet import Fernet

from workspace.credentials.encryption import (
    CredentialEncryptionError,
    decrypt_api_key,
    encrypt_api_key,
)
from workspace.credentials.endpoint import (
    ProviderEndpointError,
    validate_public_https_base_url,
)


def test_credential_round_trip_uses_authenticated_encryption(monkeypatch):
    monkeypatch.setenv(
        "PROVIDER_CREDENTIALS_ENCRYPTION_KEY",
        Fernet.generate_key().decode("ascii"),
    )

    ciphertext = encrypt_api_key("sk-provider-secret")

    assert ciphertext != "sk-provider-secret"
    assert decrypt_api_key(ciphertext) == "sk-provider-secret"


def test_missing_or_invalid_encryption_key_fails_closed(monkeypatch):
    monkeypatch.delenv("PROVIDER_CREDENTIALS_ENCRYPTION_KEY", raising=False)
    with pytest.raises(CredentialEncryptionError, match="not configured"):
        encrypt_api_key("secret")

    monkeypatch.setenv("PROVIDER_CREDENTIALS_ENCRYPTION_KEY", "not-a-fernet-key")
    with pytest.raises(CredentialEncryptionError, match="invalid"):
        encrypt_api_key("secret")


def test_wrong_encryption_key_cannot_decrypt_ciphertext(monkeypatch):
    monkeypatch.setenv(
        "PROVIDER_CREDENTIALS_ENCRYPTION_KEY",
        Fernet.generate_key().decode("ascii"),
    )
    ciphertext = encrypt_api_key("secret")
    monkeypatch.setenv(
        "PROVIDER_CREDENTIALS_ENCRYPTION_KEY",
        Fernet.generate_key().decode("ascii"),
    )

    with pytest.raises(CredentialEncryptionError, match="could not be decrypted"):
        decrypt_api_key(ciphertext)


def test_custom_endpoint_requires_public_https(monkeypatch):
    def public_dns(host, port, type):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", port))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", public_dns)
    assert (
        validate_public_https_base_url("https://api.example.net/v1/")
        == "https://api.example.net/v1"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.net/v1",
        "https://localhost/v1",
        "https://127.0.0.1/v1",
        "https://169.254.169.254/latest",
        "https://user:pass@api.example.net/v1",
        "https://api.example.net/v1?token=leak",
        "https://api.example.net/v1#fragment",
    ],
)
def test_custom_endpoint_rejects_unsafe_url_shapes(url):
    with pytest.raises(ProviderEndpointError):
        validate_public_https_base_url(url)


def test_custom_endpoint_rejects_private_dns_results(monkeypatch):
    def private_dns(host, port, type):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", port))
        ]

    monkeypatch.setattr(socket, "getaddrinfo", private_dns)
    with pytest.raises(ProviderEndpointError, match="public IP"):
        validate_public_https_base_url("https://attacker.example.net/v1")
