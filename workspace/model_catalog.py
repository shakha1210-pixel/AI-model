"""Provider model discovery with normalized, credential-safe results."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from workspace.providers import get_provider


class ModelCatalogError(RuntimeError):
    """A safe provider-neutral model catalog error."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


class ModelCatalogUnsupported(RuntimeError):
    """Raised when a provider does not expose a model-list endpoint."""


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    owned_by: str | None = None

    def public_dict(self) -> dict[str, str | None]:
        return {"id": self.id, "name": self.name, "owned_by": self.owned_by}


def _endpoint(provider_id: str, base_url: str | None) -> tuple[str, str]:
    provider = get_provider(provider_id)
    root = (base_url or provider.default_base_url or "").strip()
    parsed = urlsplit(root)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ModelCatalogError(
            "The provider base URL is invalid",
            provider=provider_id,
        )
    return provider.api_style, root.rstrip("/") + "/models"


def _headers(provider_id: str, api_key: str) -> dict[str, str]:
    if not api_key or not api_key.strip():
        raise ModelCatalogError("An API key is required", provider=provider_id)
    provider = get_provider(provider_id)
    if provider.api_style == "anthropic":
        return {
            "x-api-key": api_key.strip(),
            "anthropic-version": "2023-06-01",
            "accept": "application/json",
        }
    if provider.api_style == "google":
        return {
            "x-goog-api-key": api_key.strip(),
            "accept": "application/json",
        }
    return {
        "authorization": f"Bearer {api_key.strip()}",
        "accept": "application/json",
    }


def _normalize(provider_id: str, data: dict[str, Any]) -> list[ModelInfo]:
    provider = get_provider(provider_id)
    models: list[ModelInfo] = []

    if provider.api_style == "google":
        raw_models = data.get("models", [])
        for item in raw_models if isinstance(raw_models, list) else []:
            if not isinstance(item, dict):
                continue
            methods = item.get("supportedGenerationMethods")
            if isinstance(methods, list) and "generateContent" not in methods:
                continue
            model_id = item.get("name")
            if isinstance(model_id, str):
                model_id = model_id.removeprefix("models/")
            display_name = item.get("displayName") or model_id
            if isinstance(model_id, str) and model_id:
                models.append(ModelInfo(model_id, str(display_name), "Google"))
    else:
        raw_models = data.get("data")
        if not isinstance(raw_models, list):
            raw_models = data.get("models", [])
        for item in raw_models if isinstance(raw_models, list) else []:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id") or item.get("name")
            if not isinstance(model_id, str) or not model_id:
                continue
            display_name = (
                item.get("display_name")
                or item.get("displayName")
                or item.get("name")
                or model_id
            )
            owner = item.get("owned_by") or item.get("provider")
            models.append(ModelInfo(model_id, str(display_name), owner if isinstance(owner, str) else None))

    unique = {model.id: model for model in models}
    return sorted(unique.values(), key=lambda item: (item.name.lower(), item.id))


async def list_provider_models(
    provider_id: str,
    *,
    api_key: str,
    base_url: str | None = None,
    timeout: float = 20.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[ModelInfo]:
    """Fetch and normalize model IDs without exposing credentials or raw bodies."""
    provider = get_provider(provider_id)
    # Perplexity documents manual model selection; it does not provide a
    # general /models catalog endpoint.
    if provider_id == "perplexity":
        raise ModelCatalogUnsupported(
            "This provider does not expose a model catalog; enter a model ID manually."
        )

    style, url = _endpoint(provider_id, base_url)
    headers = _headers(provider_id, api_key)
    if style == "google":
        url += "?pageSize=100"

    try:
        async with httpx.AsyncClient(
            timeout=timeout, transport=transport
        ) as client:
            response = await client.get(url, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                raise ModelCatalogUnsupported(
                    "This provider does not expose a model catalog; enter a model ID manually."
                ) from None
            raise ModelCatalogError(
                f"Provider model request failed (HTTP {status})",
                provider=provider_id,
                status_code=status,
                retryable=status in {408, 409, 425, 429} or status >= 500,
            ) from None
        try:
            data = response.json()
        except ValueError:
            raise ModelCatalogError(
                "Provider returned an invalid model catalog",
                provider=provider_id,
            ) from None
        if not isinstance(data, dict):
            raise ModelCatalogError(
                "Provider returned an invalid model catalog",
                provider=provider_id,
            )
        return _normalize(provider_id, data)
    except (ModelCatalogError, ModelCatalogUnsupported):
        raise
    except httpx.TimeoutException:
        raise ModelCatalogError(
            "Provider model request timed out",
            provider=provider_id,
            retryable=True,
        ) from None
    except httpx.RequestError:
        raise ModelCatalogError(
            "Could not connect to provider model catalog",
            provider=provider_id,
            retryable=True,
        ) from None
