"""Privacy classifier and gate."""

from .contracts import PrivacyClass, RouteRequest, RouteResponse, RouteLogs
from .policy import PolicyLoader


class PrivacyGate:
    """Enforces privacy-class-based provider restrictions."""

    # Numeric ordering for comparison
    _ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}

    def __init__(self, loader: PolicyLoader | None = None):
        self.loader = loader or PolicyLoader()
        self.policy = self.loader.privacy()

    def _numeric(self, p: PrivacyClass | str) -> int:
        return self._ORDER.get(str(p), 4)

    def classify_text(self, text: str) -> PrivacyClass:
        """Simple heuristic classifier; override with real model if needed."""
        lowered = text.lower()
        # P3 indicators
        p3_indicators = [
            "api_key", "apikey", "secret", "password", "token",
            "private_key", "bearer", "auth_token", "access_token",
            "aws_secret", "ghp_", "sk-",
        ]
        if any(ind in lowered for ind in p3_indicators):
            return PrivacyClass.P3
        # P4 indicators
        p4_indicators = [
            "hipaa", "gdpr", "legal opinion", "medical", "compliance audit",
            "irrevocable", "contract signature", "binding",
        ]
        if any(ind in lowered for ind in p4_indicators):
            return PrivacyClass.P4
        return PrivacyClass.P1  # default conservative

    def check(self, req: RouteRequest) -> tuple[bool, RouteLogs]:
        """Returns (allowed, logs)."""
        logs = RouteLogs()
        pc = req.constraints.privacy_class
        cfg = self.policy.get(pc.value, {})

        if pc == PrivacyClass.P3:
            logs.errors.append("P3 data blocked: no LLM route allowed for secrets.")
            return False, logs

        if pc == PrivacyClass.P4:
            if req.audit.human_gate_required:
                logs.policy_checks.append("P4 passed with human gate.")
            else:
                logs.errors.append("P4 data blocked: human gate required.")
                return False, logs

        allowed = cfg.get("allowed_providers", [])
        if req.preferred_provider != "auto" and req.preferred_provider not in allowed:
            logs.warnings.append(
                f"Preferred provider {req.preferred_provider} not in privacy allowlist for {pc.value}."
            )

        logs.policy_checks.append(f"Privacy gate passed for {pc.value}.")
        return True, logs
