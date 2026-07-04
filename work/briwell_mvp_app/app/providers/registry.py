"""Registry of all creator/video data providers.

Provides a single lookup point (``get_provider``) and a status roll-up
(``list_status``) so routers and pipeline code do not need to import each
provider adapter individually. Unknown provider names return a clear error
instead of crashing.
"""

from __future__ import annotations

from app.providers.apify_provider import ApifyProvider
from app.providers.base import CreatorDataProvider, ProviderStatus
from app.providers.creator_provided import CreatorProvidedProvider
from app.providers.licensed_vendor import LicensedVendorProvider
from app.providers.tiktok_official import TikTokOfficialProvider


class UnknownProviderError(KeyError):
    """Raised when a caller requests a provider name that is not registered."""


PROVIDERS: dict[str, CreatorDataProvider] = {
    "apify": ApifyProvider(),
    "creator_provided": CreatorProvidedProvider(),
    "tiktok_official": TikTokOfficialProvider(),
    "licensed_vendor": LicensedVendorProvider(),
}


def get_provider(name: str) -> CreatorDataProvider:
    """Look up a registered provider by name.

    Raises ``UnknownProviderError`` (a ``KeyError`` subclass) with a clear
    message when ``name`` is not registered, instead of crashing with a
    generic ``KeyError`` or ``AttributeError``.
    """

    provider = PROVIDERS.get(name)
    if provider is None:
        known = ", ".join(sorted(PROVIDERS)) or "none"
        raise UnknownProviderError(
            f"Unknown provider '{name}'. Known providers: {known}."
        )
    return provider


def list_status() -> list[ProviderStatus]:
    """Return the status of every registered provider."""

    return [provider.status() for provider in PROVIDERS.values()]
