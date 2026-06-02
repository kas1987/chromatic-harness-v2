"""Chromatic API Router — provider-neutral routing with governance gates."""

# Wrapped so gate.py can import router.pipeline.* in bare-script environments
# where adapter dependencies (openai, google-genai, etc.) are not installed.
try:
    from .router import ChromaticRouter, RouteRequest, RouteResponse
except Exception:
    pass  # adapter deps unavailable; pipeline subpackage still importable

__all__ = ["ChromaticRouter", "RouteRequest", "RouteResponse",
           "ContextDetector", "ComplexityClassifier", "ProviderSelector",
           "OllamaRemoteAdapter"]
