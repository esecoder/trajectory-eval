#!/usr/bin/env python3
"""
inspect_eval.py — The same evaluation, expressed as an Inspect AI task.

===============================================================================
WHY REBUILD THE SAME EVAL IN A STANDARD FRAMEWORK
===============================================================================
Two reasons, and the second is the one that matters.

1. IT IS THE HONEST WAY TO CLAIM THE FRAMEWORK. "Familiar with Inspect AI" is a claim;
   this file is the evidence. A tool name on a CV that cannot be discussed is worse than
   no tool name at all.

2. IT MEASURES WHAT THE FRAMEWORK CANNOT DO. Inspect AI is the UK AI Safety Institute's
   evaluation framework — about as authoritative as this field gets — and it ships
   **no inter-rater reliability estimator at all**: no Cohen's κ, no Fleiss' κ, no
   Krippendorff's α, no ICC. Its documented guidance is to build an external annotation
   pipeline and import the labels back.

   That is not a criticism of Inspect. It is a statement about the shape of the problem:
   **the reliability layer is not a solved problem you install.** Every lab running human
   annotation on agent trajectories builds it themselves. This file makes that concrete
   by running the eval in Inspect and then reporting, in the same output, the statistics
   Inspect does not produce.

===============================================================================
HOW IT MAPS — Task / Solver / Scorer
===============================================================================
Inspect's data model, and the mapping to this project:

  Dataset  — one sample per trajectory. `input` is the transcript, `target` is the
             gold score vector, `metadata` carries the hidden outcome.
  Solver   — `replay_solver`, because the agent has ALREADY RUN. There is nothing to
             generate: the trajectory is the artefact under evaluation. ⚠️ This is the
             key conceptual difference from a normal Inspect eval, where the solver
             calls a model. Here the "model under test" is a log.
  Scorer   — a human-rubric scorer. In the offline default it applies the same
             rule-based proxy used elsewhere in this project, so the file runs with no
             API key. Pass `--judge llm` and it calls a real model instead.
  Metric   — Inspect aggregates a single score per sample, so the nine dimensions are
             collapsed to a weighted composite. ⚠️ That collapse is exactly the
             "aggregate hides a failing sub-population" problem this project keeps
             flagging, and it is a real limitation of using the framework's metric API
             for a multi-dimensional rubric.

===============================================================================
USAGE
===============================================================================
    python src/frameworks/inspect_eval.py                 # offline, no key
    python src/frameworks/inspect_eval.py --judge llm      # real model judge
    python src/frameworks/inspect_eval.py --write-log      # also emit an .eval log

===============================================================================
HOW TO KNOW IT WORKS
===============================================================================
It prints Inspect's own task/metric output AND this project's four reliability figures,
so the gap between them is visible in one screen. If Inspect reports a mean composite
and no agreement statistic, that is the finding, not a failure.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
TRACK = os.path.dirname(SRC)
for p in (SRC, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import rubric  # noqa: E402
from agreement import (adjacent_agreement, mae, mean_signed_error,  # noqa: E402
                       weighted_kappa)
from rubric import DIMENSIONS  # noqa: E402
from schema import DATA_DIR, load_jsonl, load_trajectories  # noqa: E402

from inspect_ai import Task, eval as inspect_eval  # noqa: E402
from inspect_ai.dataset import MemoryDataset, Sample  # noqa: E402
from inspect_ai.scorer import Score, Scorer, Target, metric, scorer  # noqa: E402
from inspect_ai.solver import Generate, Solver, TaskState, solver  # noqa: E402


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def build_dataset():
    """One Inspect Sample per trajectory.

    `target` is the gold score vector as JSON — Inspect targets are typically strings,
    so the nine-dimension vector is serialised. Encoded as an explicit dict in metadata
    as well, because a scorer that has to parse its own target is a scorer that can
    silently mis-parse it.
    """
    import json

    trajectories = load_trajectories()
    gold_rows = load_jsonl(os.path.join(DATA_DIR, "gold.jsonl"))
    gold = {r["trajectory_id"]: r["scores"] for r in gold_rows}
    verdict = {r["trajectory_id"]: r["verdict"] for r in gold_rows}

    samples = []
    for t in trajectories:
        samples.append(Sample(
            id=t.id,
            input=t.transcript(),          # ⚠️ hidden results excluded by design
            target=json.dumps(gold[t.id], sort_keys=True),
            metadata={
                "title": t.title,
                "language": t.language,
                "gold": gold[t.id],
                "gold_verdict": verdict[t.id],
                "budget": t.budget,
            },
        ))
    return MemoryDataset(samples=samples, name="coding-agent-trajectories")


# ---------------------------------------------------------------------------
# Solver — there is nothing to generate
# ---------------------------------------------------------------------------

@solver
def replay_solver() -> Solver:
    """A no-op solver: the trajectory is already in `input`.

    ⚠️ THIS IS THE CONCEPTUAL DIFFERENCE FROM A NORMAL INSPECT EVAL, AND IT IS WORTH
    STATING IN AN INTERVIEW. In a standard Inspect task the solver generates: it prompts
    a model and the model produces an output to be scored. Here the model has already
    run and the transcript is the artefact. The system under test is a *log*, not an
    endpoint — which is what evaluation of production agents actually looks like, and
    which is why the framework's model-facing API needs bending to fit.
    """
    async def solve(state: TaskState, generate: Generate) -> TaskState:
        return state

    return solve


# ---------------------------------------------------------------------------
# Scorer — a rubric scorer over nine dimensions
# ---------------------------------------------------------------------------

def _composite(scores: dict[str, float]) -> float:
    return rubric.composite(scores) / rubric.SCALE_MAX      # normalise to 0..1


@scorer(metrics=[])
def rubric_scorer(judge_kind: str = "offline"):
    """Score nine anchored dimensions and report the veto-aware composite.

    The returned Score's `value` is the normalised composite, because Inspect's metric
    API expects one number per sample. The nine per-dimension scores ride along in
    `metadata`, and `explanation` carries the verdict — including FAIL_SAFETY, which is
    the case a plain float would erase.
    """
    from judge import RuleBasedJudge

    if judge_kind == "llm":
        from judge import LLMJudge
        judge = LLMJudge()
        if not judge.available:
            raise RuntimeError("--judge llm requires OPENAI_API_KEY (or .env)")
    else:
        judge = RuleBasedJudge(min_score=2)

    async def score(state: TaskState, target: Target) -> Score:
        transcript = state.input_text
        if judge_kind == "llm":
            scores = judge.score(transcript)
        else:
            scores = judge.score(transcript)

        result = rubric.evaluate_composite(scores)
        return Score(
            value=_composite(scores),
            answer=str(scores),
            explanation=(f"verdict={result['verdict']} "
                         f"composite={result['composite']:.2f}/4 "
                         f"vetoed={result['vetoed']}"),
            metadata={
                "scores": scores,
                "verdict": result["verdict"],
                "vetoed": result["vetoed"],
                "composite_raw": result["composite"],
            },
        )

    return score


@metric
def veto_rate():
    """Fraction of samples the rubric vetoed.

    ⚠️ Added because Inspect's default metrics (accuracy, mean) cannot express it. A mean
    composite of 0.61 tells you nothing about whether the judge failed the trajectory
    that force-pushed to main — and that is the only question that decides whether the
    judge is safe. This is the same point as the whole project's veto sensitivity, and
    it needed a custom metric to survive inside the framework.
    """
    def compute(scores) -> float:
        if not scores:
            return float("nan")
        return sum(1 for s in scores if s.metadata and s.metadata.get("vetoed")) / len(scores)
    return compute


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

def build_task(judge_kind: str = "offline", with_log: bool = False) -> Task:
    return Task(
        dataset=build_dataset(),
        solver=replay_solver(),
        scorer=rubric_scorer(judge_kind=judge_kind),
        name="coding_agent_trajectory_eval",
        metadata={"judge": judge_kind, "rubric_version": "1.0"},
    )


# ---------------------------------------------------------------------------
# Cross-check: what Inspect does NOT give you
# ---------------------------------------------------------------------------

def report_against_gold(scores_by_id: dict[str, dict[str, float]]) -> None:
    """Compute the four figures Inspect has no estimator for, and say so."""
    gold_rows = load_jsonl(os.path.join(DATA_DIR, "gold.jsonl"))
    gold = {r["trajectory_id"]: r["scores"] for r in gold_rows}
    veto_ids = [r["trajectory_id"] for r in gold_rows if r["verdict"].startswith("FAIL_")]

    order = [i for i in scores_by_id if i in gold]
    if not order:
        print("  (no overlapping items to compare)")
        return
    g = [gold[i][d] for i in order for d in DIMENSIONS]
    p = [scores_by_id[i][d] for i in order for d in DIMENSIONS]

    caught = [i for i in veto_ids
              if scores_by_id.get(i, {}).get("safety_autonomy", 9) <= 0]

    print("\n  ── WHAT INSPECT DOES NOT COMPUTE, AND THIS PROJECT DOES ──────────")
    print(f"  weighted kappa vs gold   : {weighted_kappa(g, p):.4f}")
    print(f"  adjacent agreement       : {adjacent_agreement(g, p):.3f}")
    print(f"  bias (+ = lenient)       : {mean_signed_error(g, p):+.3f}")
    print(f"  mean absolute error      : {mae(g, p):.3f}")
    print(f"  veto sensitivity         : "
          f"{(len(caught) / len(veto_ids)) if veto_ids else float('nan'):.2f} "
          f"({caught} of {veto_ids})")
    print()
    print("  ⚠️ Inspect AI ships no Cohen's kappa, no Fleiss' kappa, no Krippendorff's")
    print("     alpha and no ICC — by design. Its documented guidance is to run")
    print("     annotation externally and import the labels. So the reliability layer")
    print("     above is not a missing feature you install; it is work every team")
    print("     running human annotation has to do, and it is the layer this project")
    print("     was built to demonstrate.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the trajectory eval as an Inspect AI task.")
    ap.add_argument("--judge", choices=["offline", "llm"], default="offline")
    ap.add_argument("--write-log", action="store_true", help="emit an .eval log file")
    args = ap.parse_args()

    # Inspect reads OPENAI_* for its own model access; the .env holds the base URL and
    # model used by this project's judge, so load it the same way run.sh does.
    sys.path.insert(0, SRC)
    from llm_judge_run import load_env
    load_env()

    print("inspect_eval.py — the same eval, as an Inspect AI task")
    print(f"  judge: {args.judge}")
    task = build_task(args.judge)

    # ⚠️ log_dir IS ALWAYS SET. Inspect writes an .eval log whether or not you ask it to;
    # leaving it at the default scattered `logs/` directories through the repository root.
    # Pinning it means the artefact lands with the other track output (and out/ is the one
    # directory .gitignore re-includes for this track).
    log_dir = os.path.join(TRACK, "out", "inspect_logs")
    logs = inspect_eval(
        task,
        model=None,                      # no generation: the solver replays a log
        log_dir=log_dir,
        display="plain",
    )

    scores_by_id: dict[str, dict[str, float]] = {}
    for log in logs:
        for s in (log.samples or []):
            md = s.metadata or {}
            sc = None
            if s.scores:
                first = next(iter(s.scores.values()))
                sc = first.metadata if first and first.metadata else None
            if sc and "scores" in sc:
                scores_by_id[str(s.id)] = sc["scores"]

    if not scores_by_id:
        print("\n  ⚠️ no per-sample scores recovered from the Inspect log — the metric")
        print("     API returns aggregates, and per-sample metadata is only available")
        print("     when a log is written. Re-run with --write-log.")
        return 0

    report_against_gold(scores_by_id)
    if args.write_log:
        print(f"\n  .eval logs written under {os.path.join(TRACK, 'out', 'inspect_logs')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
