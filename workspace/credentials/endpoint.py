"""Validation for user-supplied OpenAI-compatible provider endpoints.

This blocks common SSRF targets before a custom endpoint is persisted or used.
Production deployments must additionally enforce outbound network policy; DNS
can change between validation and connection time (DNS rebinding).
"""
from __future__ import annotations

import socket
from ipaddress import ip_address
from urllib.parse import urlsplit


class ProviderEndpointError(ValueError):
    """Raised when a custom provider endpoint is unsafe or malformed."""


_BLOCKED_HOSTS = {
    "localhost",
    "metadata.google.internal",
    "metadata",
}


def validate_public_https_base_url(value: str) -> str:
    """Require HTTPS and reject private, loopback, link-local, or reserved IPs."""
    if not isinstance(value, str) or not value.strip():
        raise ProviderEndpointError("A custom provider base URL is required")

    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port or 443
    except ValueError:
        raise ProviderEndpointError("The custom provider base URL is invalid") from None

    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ProviderEndpointError(
            "Custom provider endpoints must be public HTTPS URLs without credentials, query, or fragment"
        )

    host = hostname.rstrip(".").lower()
    if (
        host in _BLOCKED_HOSTS
        or host.endswith(".localhost")
        or host.endswith(".local")
        or host.endswith(".internal")
    ):
        raise ProviderEndpointError("Private or local provider endpoints are not allowed")

    try:
        literal = ip_address(host)
        addresses = {literal}
    except ValueError:
        try:
            resolved = socket.getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
        except OSError:
            raise ProviderEndpointError(
                "Custom provider hostname could not be resolved"
            ) from None
        addresses = set()
        for result in resolved:
            address_text = result[4][0].split("%", 1)[0]
            try:
                addresses.add(ip_address(address_text))
            except ValueError:
                continue

    if not addresses or any(not address.is_global for address in addresses):
        raise ProviderEndpointError(
            "Custom provider endpoints must resolve only to public IP addresses"
        )

    return raw.rstrip("/")
