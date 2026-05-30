"""Control plane (B7): proportional quota controller + routing policy overlay.

Per TOKEN_ECONOMY_SPEC §7. The controller reads the Axis P quota signal
(``quota_state.json``) and the forecast (``forecast_latest.json``) and writes a
dynamic C->T threshold overlay that ``gate.py`` consumes advisory-only on the
next PreToolUse.
"""

from __future__ import annotations
