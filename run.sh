#!/usr/bin/env bash
# trajectory-eval — one entry point.
#
#   ./run.sh            build the data, run everything, write out/REPORT.md
#   ./run.sh test       34 invariants + 155 pytest cases
#   ./run.sh report     regenerate out/REPORT.md and out/report.json
#   ./run.sh rubric     print the rubric with its behavioural anchors
#
# ⚠️ NO DEPENDENCIES REQUIRED. The measurement itself needs nothing beyond the
# standard library, so every number here is verifiable on a fresh clone before
# anything is installed. pytest is optional and used only by `test`.
set -euo pipefail
cd "$(dirname "$0")"
# ⚠️ PICK THE INTERPRETER THAT CAN RUN THIS, AND ECHO WHICH ONE.
# The first version hardcoded python3. It appeared to work here only because the core
# needs nothing beyond the standard library -- so the failure was INVISIBLE. It would
# not work for pytest: a reviewer without it silently got 34 invariants instead of the
# 155 the README advertises, and could reasonably conclude the claim was inflated.
# Prefer a venv, then PATH, and always say which was chosen.
PY=""
for cand in "./.venv/bin/python" "$(command -v python3 || true)"; do
  [ -n "$cand" ] && [ -x "$cand" ] && { PY="$cand"; break; }
done
[ -n "$PY" ] || { echo "  no python3 found on PATH" >&2; exit 1; }
echo "  python: $PY"

case "${1:-report}" in
  report|"")
    "$PY" src/evaluate.py "${@:2}"
    ;;
  test)
    "$PY" src/selftest.py
    if "$PY" -c "import pytest" 2>/dev/null; then
      "$PY" -m pytest tests -q
    else
      echo
      echo "  ⚠️  pytest not installed — the 34 invariants above are the full check."
      echo "      One line to get all 155 case-level tests:"
      echo "        python3 -m venv .venv && .venv/bin/pip install pytest"
    fi
    ;;
  rubric)
    # ⚠️ The rubric is data, not a function of any one score — printing it needs no
    # candidate. `format_table` takes scores, so the dimensions are read directly.
    "$PY" - <<'PYEOF'
import sys; sys.path.insert(0, "src")
from rubric import DIMENSIONS, DIMENSION_ORDER, THRESHOLDS, VETO_RULES, SCALE_MAX
print(f"\n  Scale 0-{SCALE_MAX}. PASS >= {THRESHOLDS['PASS']}, "
      f"BORDERLINE >= {THRESHOLDS['BORDERLINE']}.\n")
for name in DIMENSION_ORDER:
    d = DIMENSIONS[name]
    print(f"  {name}  (weight {d['weight']:.2f})")
    for level in range(SCALE_MAX + 1):
        print(f"      {level}  {d['anchors'][level]}")
    print()
print("  VETO RULES — evaluated BEFORE any threshold, so no weighted average can")
print("  buy back a violation:")
for rule in VETO_RULES:
    print(f"      {rule}")
print()
PYEOF
    ;;
  *)
    sed -n '2,9p' "$0"
    exit 1
    ;;
esac
