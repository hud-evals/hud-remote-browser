"""Browser provider implementations for remote browser control."""

from .anchorbrowser import AnchorBrowserProvider
from .base import BrowserProvider
from .browserbase import BrowserBaseProvider
from .hyperbrowser import HyperBrowserProvider
from .steel import SteelProvider

__all__ = [
    "BrowserProvider",
    "AnchorBrowserProvider",
    "BrowserBaseProvider",
    "SteelProvider",
    "HyperBrowserProvider",
]

# Provider registry for easy lookup
PROVIDERS = {
    "anchorbrowser": AnchorBrowserProvider,
    "browserbase": BrowserBaseProvider,
    "steel": SteelProvider,
    "hyperbrowser": HyperBrowserProvider,
}


def get_provider(name: str) -> type[BrowserProvider]:
    """Get a provider class by name."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]
