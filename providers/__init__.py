"""Browser provider implementations for remote browser control."""

from .base import BrowserProvider
from .anchorbrowser import AnchorBrowserProvider
from .browserbase import BrowserBaseProvider
from .steel import SteelProvider
from .hyperbrowser import HyperBrowserProvider

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
