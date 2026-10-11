#!/usr/bin/env python3
"""
dataset.py — Build the eval data, and derive the ground truth from planted defects.

===============================================================================
THE GOLD-LABEL DERIVATION IS THE HEALTHIEST PART OF THIS DESIGN
===============================================================================
Gold is not typed in by hand. It is:

    baseline 3.0  (all dimensions)
        + Σ delta(strength)      for each strength the trajectory demonstrates
        - Σ delta(defect)        for each defective behaviour it exhibits
        -> clamped to [0, 4]

Every delta lives in `scenarios.DEFECTS` / `scenarios.STRENGTHS` next to the
rubric anchor that justifies it. So the ground truth is *auditable*: you can
disagree with a label, follow it to a one-line delta, follow that to an anchor,
and change the anchor.

That is the difference between a labelled set and a labelled set you would put
in front of a client.

===============================================================================
WHAT THIS WRITES
===============================================================================
    data/trajectories.jsonl   the 20 transcripts (the thing a human reads)
    data/gold.jsonl           one annotation per trajectory, annotator="gold"
    data/splits.json          a stable 12/4/4 calibration/holdout/adjudication
                              split, seeded — so "we tuned on the calibration
                              set" is a claim you can actually make

===============================================================================
HOW TO KNOW IT WORKS
===============================================================================
    python src/dataset.py
Correct output: "20 trajectories, 20 gold annotations, 9 dimensions, veto on 1
trajectory" and the three files listed above. Re-running produces byte-identical
gold (there is no randomness in the derivation; the split seed is fixed).
"""

from __future__ import annotations

import json
import os
import random

import rubric
import scenarios
from rubric import DIMENSIONS, SCALE_MAX
from schema import DATA_DIR, annotation, write_jsonl

BASELINE = 3.0
SPLIT_SEED = 20261003

# A stable split. Calibration is where an annotator is trained and corrected;
# holdout is never seen during calibration; adjudication is where the cases with
# genuine rubric ambiguity live and where disagreement is *allowed*.
SPLIT_SIZES = {"calibration": 12, "holdout": 4, "adjudication": 4}


def gold_labels(scenario: dict) -> dict[str, float]:
    """Derive the ground-truth score vector for one scenario.

    Raises on an unknown defect/strength code rather than ignoring it — a typo in
    a code name would otherwise silently remove a penalty and quietly make the
    eval easier.
    """
    scores = {d: BASELINE for d in DIMENSIONS}
    for code in scenario.get("planted", []):
        if code not in scenarios.DEFECTS:
            raise KeyError(f"{scenario['id']}: unknown defect {code!r}")
        for dim, delta in scenarios.DEFECTS[code]["delta"].items():
            scores[dim] += delta
    for code in scenario.get("strengths", []):
        if code not in scenarios.STRENGTHS:
            raise KeyError(f"{scenario['id']}: unknown strength {code!r}")
        for dim, delta in scenarios.STRENGTHS[code]["delta"].items():
            scores[dim] += delta
    return {d: float(max(0, min(SCALE_MAX, v))) for d, v in scores.items()}


def gold_evidence(scenario: dict) -> dict[str, str]:
    """For every non-baseline dimension, the single sentence that justifies it.

    An annotator who cannot cite evidence for a score is guessing. Requiring the
    evidence in the record makes that visible instead of hiding it in a number.
    """
    out: dict[str, str] = {}
    for code in scenario.get("planted", []):
        d = scenarios.DEFECTS[code]
        for dim in d["delta"]:
            out[dim] = f"DEFECT {code}: {d['desc']} | {d['anchor']}"
    for code in scenario.get("strengths", []):
        s = scenarios.STRENGTHS[code]
        for dim in s["delta"]:
            # A dimension can carry both; the strength is the less severe signal,
            # so it is recorded alongside rather than overwriting.
            prev = out.get(dim, "")
            out[dim] = (prev + " ; " if prev else "") + f"STRENGTH {code}: {s['desc']}"
    return out


def make_split(ids: list[str]) -> dict[str, list[str]]:
    """Deterministic split, and a *fixed* one — a moving eval set makes every
    result incomparable. The seed is written into the file so a rerun is
    reproducible and a change to the seed is visible in the diff."""
    ordered = sorted(ids)
    rng = random.Random(SPLIT_SEED)
    rng.shuffle(ordered)
    split: dict[str, list[str]] = {}
    cursor = 0
    for name, size in SPLIT_SIZES.items():
        split[name] = sorted(ordered[cursor:cursor + size])
        cursor += size
    return split


def build(verbose: bool = True) -> dict:
    traj_rows = []
    gold_rows = []
    veto_ids = []

    for sc in scenarios.SCENARIOS:
        traj_rows.append({k: v for k, v in sc.items()})
        labels = gold_labels(sc)
        ev = gold_evidence(sc)
        result = rubric.evaluate_composite(labels)
        if result["vetoed"]:
            veto_ids.append(sc["id"])
        gold_rows.append(annotation(
            sc["id"], "gold", labels,
            evidence=ev,
            composite=result["composite"],
            verdict=result["verdict"],
            source="derived from planted defects via rubric anchors",
        ))

    split = make_split([r["id"] for r in traj_rows])

    traj_path = os.path.join(DATA_DIR, "trajectories.jsonl")
    gold_path = os.path.join(DATA_DIR, "gold.jsonl")
    split_path = os.path.join(DATA_DIR, "splits.json")

    n_traj = write_jsonl(traj_path, traj_rows)
    n_gold = write_jsonl(gold_path, gold_rows)
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(split_path, "w", encoding="utf-8") as fh:
        json.dump({"seed": SPLIT_SEED, "sizes": SPLIT_SIZES, "split": split},
                  fh, indent=2)

    summary = {
        "trajectories": n_traj,
        "gold_annotations": n_gold,
        "dimensions": len(DIMENSIONS),
        "veto_ids": veto_ids,
        "files": [traj_path, gold_path, split_path],
        "baseline": BASELINE,
        "split_seed": SPLIT_SEED,
    }
    if verbose:
        print(f"dataset.py — built {n_traj} trajectories, {n_gold} gold annotations")
        print(f"  dimensions      : {len(DIMENSIONS)}")
        print(f"  veto fired on   : {veto_ids} (expected exactly ['traj-006'])")
        print(f"  split seed      : {SPLIT_SEED}")
        for name, ids in split.items():
            print(f"  {name:<14}: {len(ids):>2}  {', '.join(ids)}")
        for p in summary["files"]:
            print(f"  wrote {p}")
    return summary


if __name__ == "__main__":
    build()
