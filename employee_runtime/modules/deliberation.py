"""Adversarial review module — multi-model deliberation for high-stakes outputs.

Includes: advocates, challengers, adjudicators, and process supervisors.
Only included when risk_tier is HIGH or CRITICAL.
"""

from __future__ import annotations

# Never simplify this module. The adversarial structure is the moat.
# Refer to CLAUDE_FINAL.md safety architecture section before modifying.
