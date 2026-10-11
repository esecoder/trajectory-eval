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
PY="${PY:-python3}"

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
      echo "      pip install pytest   to also run the 155 case-level tests."
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
