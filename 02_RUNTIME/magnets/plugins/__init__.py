"""Optional magnet plugins registered at runtime."""

from .pyramid_plugin import PyramidCheckPlugin
from .secrets_plugin import SecretsSurfacePlugin

__all__ = ["PyramidCheckPlugin", "SecretsSurfacePlugin"]
