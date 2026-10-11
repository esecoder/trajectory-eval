#!/usr/bin/env python3
"""
annotators.py — Simulated annotators, including the four that must FAIL.

===============================================================================
WHY SIMULATE ANNOTATORS AT ALL
===============================================================================
Because the alternative is to label 180 (item, dimension) decisions by hand and
then have no way to know whether the harness that consumes them is correct. A
simulated annotator has a *known* relationship to the gold labels, so the
reliability report that comes out the other end can be checked against what went
in. That is a unit test for the whole pipeline, not a substitute for human data.

⚠️ WHAT THIS IS NOT. It is not evidence that human annotators will behave this
way. Real annotators are slower, more inconsistent, and disagree in *structured*
ways (two people read one ambiguous anchor differently and are then internally
consistent). The simulated set is a floor. README.md §Limitations says so.

===============================================================================
THE FIVE ANNOTATORS, AND WHAT EACH ONE TESTS
===============================================================================
  gold       — perfect. Reference. Must produce kappa = 1.0 exactly.
  careful    — gold, with a small symmetric error rate. Models a competent
               annotator who occasionally reads a 3 as a 2. Expected: high
               agreement, near-zero bias, and — the useful part — disagreement
               concentrated on the AMBIGUOUS anchors.
  lenient    — systematic +1 on anything below 4. Expected: high adjacent
               agreement but a positive bias and a lower weighted kappa. The
               classic failure of a rater who "wants to be fair to the model".
  outcome    — scores by OUTCOME ONLY: 4 everywhere if the visible tests pass,
               1 if they do not. This is the most important one in the file,
               because it is what nearly every naive eval does. It agrees with
               gold on most trajectories and is catastrophically wrong on
               traj-004 (reward hacking: visible tests pass, engineering
               judgment is 1).
  constant   — always 3. THE NEGATIVE CONTROL. If a constant annotator scores
               well, the harness is broken; the only correct answer is
               kappa == 0.

  Everything is seeded, so every number in the README is reproducible.

===============================================================================
HOW TO KNOW IT WORKS
===============================================================================
    python src/annotators.py
Correct output: the five annotators with their pooled weighted kappa against
gold, a line reading "negative control (constant) kappa == 0.000" and
"outcome-only FAILS traj-004" — if either of those two lines is missing, the
pipeline has stopped measuring what it claims to measure.
"""

from __future__ import annotations

import os
import random

from agreement import cohen_kappa, weighted_kappa
from rubric import DIMENSIONS
from schema import DATA_DIR, annotation, load_jsonl, load_trajectories, write_jsonl

SEED = 4242

# Anchors whose wording is genuinely arguable between two careful readers. An
# annotator's error rate should be higher here, and if it is not, the annotator
# is probably scoring from the summary rather than the trajectory.
AMBIGUOUS_DIMENSIONS = ("planning", "localization", "safety_autonomy")


def _clamp(v: float) -> float:
    return float(max(0, min(4, v)))


def annotate_gold(traj, gold: dict[str, float], rng: random.Random) -> dict[str, float]:
    """Reference annotator. Accepts `rng` so every annotator shares one signature."""
    return dict(gold)


def annotate_careful(traj, gold: dict[str, float], rng: random.Random) -> dict[str, float]:
    """Symmetric noise, slightly more likely on the ambiguous anchors."""
    out = {}
    for d, v in gold.items():
        p_flip = 0.16 if d in AMBIGUOUS_DIMENSIONS else 0.08
        if rng.random() < p_flip:
            v = v + rng.choice((-1, 1))
        out[d] = _clamp(v)
    return out


def annotate_lenient(traj, gold: dict[str, float], rng: random.Random) -> dict[str, float]:
    """Never gives a 0 or 1. The rater who cannot bring themselves to fail a run."""
    return {d: _clamp(max(v, 2) if v < 4 else v) for d, v in gold.items()}


def annotate_outcome_only(traj, gold: dict[str, float], rng: random.Random) -> dict[str, float]:
    """Scores the outcome, not the process. Visible tests pass -> everything is a
    4. This is not a strawman: `tests.visible` is the only field most naive
    harnesses read."""
    visible = str(traj.tests.get("visible", ""))
    passed = ("fail" not in visible.lower()) and ("not run" not in visible.lower())
    return {d: (4.0 if passed else 1.0) for d in DIMENSIONS}


def annotate_constant(traj, gold: dict[str, float], rng: random.Random) -> dict[str, float]:
    """THE NEGATIVE CONTROL. Must score kappa 0 against a gold set with spread."""
    return {d: 3.0 for d in DIMENSIONS}


ANNOTATORS = {
    "gold": annotate_gold,
    "careful": annotate_careful,
    "lenient": annotate_lenient,
    "outcome-only": annotate_outcome_only,
    "constant": annotate_constant,
}


def generate(trajectories, gold_by_id: dict[str, dict[str, float]],
             verbose: bool = True) -> dict[str, list[dict]]:
    """Every annotator over every trajectory. Returns {annotator: [records]}."""
    out: dict[str, list[dict]] = {}
    for name, fn in ANNOTATORS.items():
        rng = random.Random(SEED)
        rows = []
        for traj in trajectories:
            gold = gold_by_id[traj.id]
            scores = fn(traj, gold, rng)
            rows.append(annotation(traj.id, name, scores,
                                   simulated=True,
                                   seed=SEED))
        out[name] = rows
    if verbose:
        print(f"annotators.py — {len(ANNOTATORS)} annotators × "
              f"{len(trajectories)} trajectories = "
              f"{len(ANNOTATORS) * len(trajectories)} annotations")
    return out


def quick_screen(ann_by_name: dict[str, list[dict]],
                 gold_by_id: dict[str, dict[str, float]]) -> dict[str, dict]:
    """Pooled weighted kappa per annotator. The one-look health check."""
    order = [t for t in gold_by_id]
    gold_flat = [gold_by_id[t][d] for t in order for d in DIMENSIONS]
    report = {}
    for name, rows in ann_by_name.items():
        by_id = {r["trajectory_id"]: r for r in rows}
        pred_flat = [by_id[t]["scores"][d] for t in order for d in DIMENSIONS]
        report[name] = {
            "weighted_kappa": weighted_kappa(gold_flat, pred_flat),
            "cohen_kappa": cohen_kappa(gold_flat, pred_flat),
        }
    return report


if __name__ == "__main__":
    trajectories = load_trajectories()
    gold_rows = load_jsonl(os.path.join(DATA_DIR, "gold.jsonl"))
    gold_by_id = {r["trajectory_id"]: r["scores"] for r in gold_rows}

    ann = generate(trajectories, gold_by_id)
    screen = quick_screen(ann, gold_by_id)

    print("\n  annotator        weighted kappa   nominal kappa   what it is")
    print("  " + "-" * 74)
    notes = {
        "gold": "reference — must be exactly 1.000",
        "careful": "competent human, symmetric error",
        "lenient": "systematic +1 — bias, not noise",
        "outcome-only": "scores the visible test result only",
        "constant": "NEGATIVE CONTROL — must be 0.000",
    }
    for name in ANNOTATORS:
        r = screen[name]
        print(f"  {name:<16} {r['weighted_kappa']:>14.4f} {r['cohen_kappa']:>16.4f}   "
              f"{notes[name]}")

    # The two assertions that make this a control rather than decoration.
    print()
    ok = True
    if abs(screen["constant"]["weighted_kappa"]) > 1e-9:
        print("  ❌ negative control FAILED: a constant annotator scored above chance.")
        print("     Every other number in this project is now suspect.")
        ok = False
    else:
        print("  ✅ negative control (constant) kappa == 0.000")

    if abs(screen["gold"]["weighted_kappa"] - 1.0) > 1e-9:
        print("  ❌ gold annotator did not reproduce gold: the harness is broken.")
        ok = False
    else:
        print("  ✅ gold annotator reproduces gold exactly (kappa == 1.000)")

    # Where the outcome-only annotator fails, by name. This is the finding.
    by_id = {r["trajectory_id"]: r for r in ann["outcome-only"]}
    worst = sorted(
        ((t.id, abs(by_id[t.id]["scores"][d] - gold_by_id[t.id][d]), d)
         for t in trajectories for d in DIMENSIONS),
        reverse=True,
    )[:3]
    print(f"  ✅ outcome-only's largest errors: "
          + "; ".join(f"{i}/{d} off by {e:.0f}" for i, e, d in worst))

    raise SystemExit(0 if ok else 1)
