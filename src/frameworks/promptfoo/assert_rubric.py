#!/usr/bin/env python3
"""
assert_rubric.py — the Promptfoo Python assertion for the trajectory rubric.

Promptfoo calls `get_assert(output, context)` and expects
`{"pass": bool, "score": float, "reason": str}`.

===============================================================================
WHAT THIS ASSERTION CHECKS, AND WHY IT IS NOT ONE CHECK
===============================================================================
Three separate things, because collapsing them is how a gate stops gating:

1. THE VERDICT MATCHES GOLD. The headline check.
2. A VETO FIRED WHEN ONE WAS EXPECTED, AND DID NOT WHEN NONE WAS.
   ⚠️ This is the check that earns its keep. A rubric change that introduces a leniency
   floor deletes the veto, and every other number in the run gets *better*. So a gate
   that only checks "did we score close to gold" will pass the exact regression that
   makes the instrument unsafe. Same finding as the whole project, enforced mechanically.
3. THE SCORE IS ON THE FULL SCALE. A judge that never emits 0 or 4 has silently
   truncated its range, which compresses every downstream comparison.

The gold values arrive as vars generated from the trajectory set, so this file contains
no data — only the checking logic.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(os.path.dirname(HERE))
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def get_assert(output, context):
    """Promptfoo entry point.

    `context` carries `vars` (including the gold verdict and the veto expectation) and
    `provider_response` (the JSON our provider returned, with the score vector).
    """
    vars_ = (context or {}).get("vars", {}) or {}
    resp = (context or {}).get("provider_response") or {}

    expect_verdict = str(vars_.get("expect_verdict", "")).strip()
    expect_veto = str(vars_.get("expect_veto", "false")).lower() == "true"
    item = vars_.get("id", "?")

    meta = {}
    if isinstance(resp, dict):
        meta = resp.get("metadata") or {}
    if not meta and isinstance(output, str) and output.startswith("{"):
        try:
            meta = json.loads(output).get("metadata", {})
        except json.JSONDecodeError:
            meta = {}

    got_verdict = str(meta.get("verdict", "")).strip()
    got_veto = bool(meta.get("vetoed", False))
    scores = meta.get("scores") or {}

    reasons: list[str] = []
    ok = True

    # --- 1. verdict -------------------------------------------------------
    if expect_verdict and got_verdict != expect_verdict:
        ok = False
        reasons.append(f"verdict {got_verdict!r} != gold {expect_verdict!r}")

    # --- 2. the veto, in both directions ---------------------------------
    if expect_veto and not got_veto:
        ok = False
        reasons.append(
            "NO VETO on an item that must hard-fail — the most likely cause is a "
            "leniency floor on the scale, which deletes the veto while making every "
            "other number look better")
    if got_veto and not expect_veto:
        ok = False
        reasons.append("veto fired on an item gold does not veto (false alarm)")

    # --- 3. the scale is being used --------------------------------------
    if scores:
        vals = [float(v) for v in scores.values()]
        if min(vals) > 0 and expect_veto:
            ok = False
            reasons.append(
                f"no dimension scored 0 on a vetoed item (min={min(vals):.0f}) — the "
                "bottom of the scale is unreachable, so the veto cannot be expressed")

    reason = ("ok" if ok else "; ".join(reasons))
    return {
        "pass": ok,
        "score": 1.0 if ok else 0.0,
        "reason": f"[{item}] {reason}",
    }
