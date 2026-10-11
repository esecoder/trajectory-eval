#!/usr/bin/env python3
"""
selftest.py — Prove the harness still measures what it claims.

===============================================================================
WHY THIS FILE EXISTS AND WHAT IT IS NOT
===============================================================================
This is not a unit test of "does the code run". It is a check of the properties
that make the *numbers* meaningful. Each one corresponds to a way this project
could quietly start lying:

  * the rubric weights no longer sum to 1, so the composite silently rescales
  * a dimension loses its spread, so its kappa is 0 by construction and looks
    like a real finding
  * the veto stops firing, so an unsafe trajectory is reported as BORDERLINE
  * the transcript starts leaking hidden test results, so the annotator task
    becomes transcription and the difficulty is fake
  * gold stops being derivable from the planted defects, so the "auditable
    ground truth" claim becomes false
  * the negative control stops scoring 0, which invalidates every other number
    in the repo in one stroke

A harness without this file is a harness you cannot re-run in three months.

===============================================================================
HOW TO RUN IT
===============================================================================
    python src/selftest.py
Exit 0 and a ✅ per check. Any ❌ is a real defect: the number it protects is
no longer trustworthy, and the correct response is to fix the harness before
quoting any figure from it.
"""

from __future__ import annotations

import json
import math
import os
import sys

import annotators as ann_mod
import dataset as dataset_mod
import judge as judge_mod
import rubric
import stats
from agreement import (cohen_kappa, icc_2_1,
                       krippendorff_alpha_ordinal,
                       krippendorff_alpha_ordinal_bruteforce, weighted_kappa)
from rubric import DIMENSIONS, SCALE_MAX
from schema import (DATA_DIR, SchemaError, load_jsonl, load_trajectories,
                    validate_annotation, validate_trajectory_dict)

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    tag = "ok  " if condition else "FAIL"
    line = f"  {tag} {name}"
    if detail:
        line += f"   [{detail}]"
    print(line)
    (PASSED if condition else FAILED).append(name)


def try_raises(name: str, exc, fn, *a, **kw) -> None:
    try:
        fn(*a, **kw)
    except exc:
        check(name, True)
    except Exception as other:  # noqa: BLE001 - deliberate: report the wrong exception
        check(name, False, f"raised {type(other).__name__}, expected {exc.__name__}")
    else:
        check(name, False, "did not raise")


def main() -> int:
    print("selftest.py — invariants that make the numbers meaningful\n")

    # ---------------------------------------------------------------- rubric
    print("RUBRIC")
    total_w = sum(d["weight"] for d in DIMENSIONS.values())
    check("weights sum to 1.00", abs(total_w - 1.0) < 1e-9, f"sum={total_w:.6f}")
    check("every dimension has 5 anchors (scale 0-4)",
          all(len(d["anchors"]) == SCALE_MAX + 1 for d in DIMENSIONS.values()))
    check("engineering_judgment is the heaviest dimension",
          max(DIMENSIONS, key=lambda d: DIMENSIONS[d]["weight"]) == "engineering_judgment",
          f"w={DIMENSIONS['engineering_judgment']['weight']:.2f}")
    check("safety_autonomy is a veto dimension",
          any(r["dimension"] == "safety_autonomy" for r in rubric.VETO_RULES))

    # composite monotonicity: raising any dimension must not lower the composite
    base = {d: 2.0 for d in DIMENSIONS}
    mono = all(rubric.composite({**base, d: 3.0}) > rubric.composite(base)
               for d in DIMENSIONS)
    check("composite is strictly increasing in every dimension", mono)

    veto_scores = {d: 4.0 for d in DIMENSIONS}
    veto_scores["safety_autonomy"] = 0.0
    res = rubric.evaluate_composite(veto_scores)
    check("an otherwise-perfect trajectory with safety=0 is vetoed, not averaged",
          res["vetoed"] and res["verdict"] == "FAIL_SAFETY",
          f"composite={res['composite']} verdict={res['verdict']}")

    # ---------------------------------------------------------------- schema
    print("\nSCHEMA")
    good = {
        "id": "t", "title": "t", "repo": "r", "language": "python", "task": "t",
        "acceptance_criteria": ["a", "b"], "constraints": ["c"], "hidden_tests": ["h"],
        "final_diff": "d", "tests": {"visible": "ok"},
        "budget": {"tool_calls": 1, "wall_clock_min": 1},
        "steps": [{"kind": "final", "summary": "s"}],
    }
    validate_trajectory_dict(good)
    check("a well-formed trajectory validates", True)

    try_raises("missing required field raises",
               SchemaError, validate_trajectory_dict, {k: v for k, v in good.items()
                                                       if k != "hidden_tests"})
    try_raises("one acceptance criterion raises (criteria collapse into 'did the test pass')",
               SchemaError, validate_trajectory_dict,
               {**good, "acceptance_criteria": ["only one"]})
    try_raises("a last step that is not 'final' raises",
               SchemaError, validate_trajectory_dict,
               {**good, "steps": [{"kind": "think"}]})
    try_raises("an out-of-range score raises rather than clamping",
               SchemaError, validate_annotation,
               {"trajectory_id": "t", "scores": {d: 9 for d in DIMENSIONS}})
    try_raises("an unscored dimension raises",
               SchemaError, validate_annotation,
               {"trajectory_id": "t", "scores": {d: 3 for d in list(DIMENSIONS)[:-1]}})

    # ---------------------------------------------------------------- dataset
    print("\nDATASET")
    traj = load_trajectories()
    gold_rows = load_jsonl(os.path.join(DATA_DIR, "gold.jsonl"))
    gold_by_id = {r["trajectory_id"]: r["scores"] for r in gold_rows}

    check("trajectories and gold are the same population",
          sorted(t.id for t in traj) == sorted(gold_by_id), 
          f"{len(traj)} trajectories, {len(gold_rows)} gold rows")
    check("every gold row scores all 9 dimensions",
          all(len(v) == len(DIMENSIONS) for v in gold_by_id.values()))
    check("every gold score is inside 0-4",
          all(0 <= s <= SCALE_MAX for v in gold_by_id.values() for s in v.values()))

    # gold is DERIVED: recompute and compare. This is the auditability claim.
    import scenarios as scenarios_mod
    recomputed = {sc["id"]: dataset_mod.gold_labels(sc)
                  for sc in scenarios_mod.SCENARIOS}
    drift = [i for i in recomputed
             if any(abs(recomputed[i][d] - gold_by_id[i][d]) > 1e-9 for d in DIMENSIONS)]
    check("gold on disk equals gold re-derived from the planted defects",
          not drift, f"drift={drift}")

    veto_ids = [r["trajectory_id"] for r in gold_rows if r["verdict"].startswith("FAIL_")]
    check("the veto fires on exactly traj-006 (the force-push)", veto_ids == ["traj-006"],
          str(veto_ids))

    degenerate = []
    for d in DIMENSIONS:
        if len({gold_by_id[i][d] for i in gold_by_id}) < 3:
            degenerate.append(d)
    check("every dimension has >=3 distinct gold scores, so kappa is meaningful",
          not degenerate, f"degenerate={degenerate}")

    # The leak check. This is the one that protects the whole annotator task.
    sample = traj[0]
    check("the annotator transcript does NOT contain hidden test results",
          "hidden" not in sample.transcript().lower()
          or "not available" in sample.transcript().lower())
    check("the answer key IS available separately for scoring",
          bool(sample.hidden_outcome()))

    # ---------------------------------------------------------------- agreement
    print("\nAGREEMENT")
    check("cohen_kappa matches its hand-computed value (0.4)",
          abs(cohen_kappa([0] * 25 + [1] * 25,
                          [0] * 20 + [1] * 5 + [0] * 10 + [1] * 15) - 0.4) < 1e-9)
    check("krippendorff ordinal alpha matches its analytic value (-0.5)",
          abs(krippendorff_alpha_ordinal([[0, 1], [1, 0]]) + 0.5) < 1e-9)

    import random
    rng = random.Random(99)
    worst = 0.0
    for _ in range(25):
        units = [[rng.randint(0, 4) for _ in range(rng.randint(2, 5))]
                 for _ in range(rng.randint(3, 10))]
        f = krippendorff_alpha_ordinal(units)
        s = krippendorff_alpha_ordinal_bruteforce(units)
        if math.isnan(f) and math.isnan(s):
            continue
        worst = max(worst, abs(f - s))
    check("the two independent alpha implementations agree on random data",
          worst < 1e-9, f"max diff={worst:.2e}")

    check("icc_2_1 returns 1.0 for identical raters",
          abs(icc_2_1([[1, 1], [3, 3], [4, 4]]) - 1.0) < 1e-9)

    # ---------------------------------------------------------------- control
    print("\nTHE NEGATIVE CONTROL")
    ann = ann_mod.generate(traj, gold_by_id, verbose=False)
    order = sorted(gold_by_id)
    gold_flat = [gold_by_id[i][d] for i in order for d in DIMENSIONS]

    def flat(rows):
        by = {r["trajectory_id"]: r for r in rows}
        return [by[i]["scores"][d] for i in order for d in DIMENSIONS]

    k_const = weighted_kappa(gold_flat, flat(ann["constant"]))
    check("a constant annotator scores kappa 0.000 (else the harness is broken)",
          abs(k_const) < 1e-9, f"kappa={k_const:.6f}")
    k_gold = weighted_kappa(gold_flat, flat(ann["gold"]))
    check("the gold annotator reproduces gold exactly (kappa 1.000)",
          abs(k_gold - 1.0) < 1e-9, f"kappa={k_gold:.6f}")
    k_out = weighted_kappa(gold_flat, flat(ann["outcome-only"]))
    check("scoring by outcome alone lands far from gold (the point of a process rubric)",
          k_out < 0.4, f"kappa={k_out:.4f}")

    # ---------------------------------------------------------------- judge
    print("\nJUDGE")
    jf = judge_mod.validate(judge_mod.RuleBasedJudge(min_score=2), traj,
                            gold_by_id, veto_ids, label="floored")
    ju = judge_mod.validate(judge_mod.RuleBasedJudge(min_score=0), traj,
                            gold_by_id, veto_ids, label="unfloored")
    check("the lenient judge cannot express the veto (sensitivity 0)",
          jf["veto_sensitivity"] == 0.0, f"sensitivity={jf['veto_sensitivity']:.2f}")
    check("removing the leniency floor restores veto sensitivity to 1.0",
          ju["veto_sensitivity"] == 1.0, f"sensitivity={ju['veto_sensitivity']:.2f}")
    check("the judge is validated against gold, not assumed (kappa is reported)",
          isinstance(jf["pooled_weighted_kappa"], float))

    # ---------------------------------------------------------------- stats
    print("\nSTATS")
    check("a ±5% interval on 80% accuracy needs a plausible n",
          200 <= stats.needed_n_for_halfwidth(0.05) <= 300,
          f"n={stats.needed_n_for_halfwidth(0.05)}")
    check("McNemar n grows as the effect shrinks",
          stats.mcnemar_needed_n(0.20, 0.05) > stats.mcnemar_needed_n(0.20, 0.10))

    # ---------------------------------------------------------------- determinism
    print("\nDETERMINISM")
    v1 = ann_mod.generate(traj, gold_by_id, verbose=False)
    v2 = ann_mod.generate(traj, gold_by_id, verbose=False)
    check("annotator generation is seeded and reproducible",
          json.dumps(v1, sort_keys=True, default=str)
          == json.dumps(v2, sort_keys=True, default=str))
    s1 = dataset_mod.make_split([t.id for t in traj])
    s2 = dataset_mod.make_split([t.id for t in traj])
    check("the train/holdout split is stable across runs", s1 == s2)

    # ---------------------------------------------------------------- summary
    print()
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("\n  ❌ FAILURES:")
        for f in FAILED:
            print(f"     - {f}")
        print("\n  Do not quote any number from this project until these are fixed.")
        return 1
    print("\n  ✅ The harness still measures what it claims.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
