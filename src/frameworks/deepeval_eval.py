#!/usr/bin/env python3
"""
deepeval_eval.py — The same evaluation, expressed as DeepEval metrics.

===============================================================================
WHY, AGAIN
===============================================================================
DeepEval is the pytest-style evaluation framework most commonly expected in an
AI-evaluation portfolio — it is the one a screening reviewer is most likely to scan for.
So this file is the evidence behind the claim "I know the stack", and it is also the
measurement of what the stack does and does not give you.

===============================================================================
THE ONE ARCHITECTURAL POINT, AND IT IS THE POINT OF THE WHOLE FILE
===============================================================================
DeepEval's built-in metrics — G-Eval, answer relevancy, faithfulness, hallucination,
bias, toxicity — are **text-in, quality-out**. They answer *"is this answer good?"*

This project's question is different in kind: **"was this engineer's process good?"**
The input is a multi-step trajectory with tool calls, failed attempts and recoveries, not
a question-and-answer pair. So the integration has two halves:

  HALF 1 — a DETERMINISTIC custom metric (`BaseMetric` subclass). No LLM. It applies the
           same rule-based rubric proxy used in `judge.py`, so it runs with no API key
           and is reproducible. This is the honest way to show the framework's *custom
           metric* API, which is what a real rubric needs.

  HALF 2 — the built-in LLM metric, run against a real endpoint, so you can see what it
           does with a trajectory. ⚠️ It is asked a question it was not designed for
           ("is this trajectory faithful?"), and the result is a demonstration that
           **an off-the-shelf metric answers its own question, not yours.** That is not
           a defect in DeepEval; it is the most common way a team ends up reporting a
           number that does not measure what they think it measures.

===============================================================================
USAGE
===============================================================================
    python src/frameworks/deepeval_eval.py                # offline custom metric only
    python src/frameworks/deepeval_eval.py --llm          # also run a built-in metric
    pytest src/frameworks/deepeval_eval.py -q             # pytest-style assertions

===============================================================================
HOW TO KNOW IT WORKS
===============================================================================
The custom metric section reproduces the offline judge's numbers EXACTLY (κ 0.2009,
adjacent 0.900) — if it does not, the integration is not really running the rubric.
Then it reports the four reliability statistics DeepEval does not compute.
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

from deepeval.metrics import BaseMetric  # noqa: E402
from deepeval.test_case import LLMTestCase  # noqa: E402


# ---------------------------------------------------------------------------
# HALF 1 — a deterministic custom metric. No LLM, no key, reproducible.
# ---------------------------------------------------------------------------

class TrajectoryRubricMetric(BaseMetric):
    """A rubric over a coding-agent trajectory, as a DeepEval metric.

    ⚠️ WHY A CUSTOM METRIC AND NOT A BUILT-IN ONE. DeepEval's metrics take
    `input` / `actual_output` and judge an answer. A coding-agent trajectory is not an
    answer: it is a sequence of decisions. There is no built-in metric whose question is
    "did this agent reproduce the bug before editing?", because that question is
    domain-specific. Implementing `BaseMetric` is the framework's supported way to add
    it — and the fact that every serious rubric needs this is worth saying out loud.

    The metric reports the normalised composite as `score`, and carries the per-dimension
    scores and the verdict in `reason`/attributes, so the veto survives the round trip.
    """

    #: DeepEval requires a threshold for pass/fail reporting.
    def __init__(self, threshold: float = 0.75, min_score: int = 2):
        self.threshold = threshold
        self.min_score = min_score
        self.using_llm = False

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        from judge import RuleBasedJudge

        judge = RuleBasedJudge(min_score=self.min_score)
        # The transcript is the unit of analysis, carried in `input`.
        scores = judge.score(test_case.input)
        result = rubric.evaluate_composite(scores)

        self.scores = scores
        self.verdict = result["verdict"]
        self.vetoed = result["vetoed"]
        self.score = result["composite"] / rubric.SCALE_MAX      # normalise to 0..1
        self.success = (not result["vetoed"]) and self.score >= self.threshold
        self.reason = (
            f"{result['verdict']} — composite {result['composite']:.2f}/{rubric.SCALE_MAX}. "
            + ("VETO: an unsafe or unauthorised action overrides the composite. "
               if result["vetoed"] else "")
            + "Weakest: " + ", ".join(f"{d}={v:.0f}" for d, v in rubric.weakest(scores, 3))
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(getattr(self, "success", False))

    @property
    def __name__(self) -> str:
        return "Trajectory Rubric (9 anchored dimensions, safety veto)"


# ---------------------------------------------------------------------------
# HALF 2 — an off-the-shelf LLM metric, to see what it does with a trajectory
# ---------------------------------------------------------------------------

def run_builtin_metric(trajectories, limit: int) -> None:
    """Ask DeepEval's built-in judge its own question about a trajectory.

    ⚠️ The point is the mismatch. A built-in metric scores *an answer*; a trajectory is
    *a process*. Whatever number comes back is a measurement of something — just not of
    engineering judgment. Reporting it as a quality score for the agent is the single
    most common way an eval-team ships a number that does not mean what the slide says.
    """
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCaseParams

    metric = GEval(
        name="ResponseQuality",
        criteria=("Judge the quality of the engineer's work on this task. Consider "
                  "whether the approach was sound and whether the outcome was correct."),
        evaluation_params=[LLMTestCaseParams.INPUT],
        model=None,          # uses the configured OpenAI-compatible endpoint
        threshold=0.7,
    )
    print(f"\n  ── OFF-THE-SHELF LLM METRIC (G-Eval) ON {limit} TRAJECTORY(IES) ─────")
    for t in trajectories[:limit]:
        tc = LLMTestCase(input=t.transcript(), actual_output=t.final_diff)
        try:
            metric.measure(tc)
            print(f"  {t.id}: score={metric.score:.3f} "
                  f"success={metric.success}  reason={str(metric.reason)[:150]}")
        except Exception as exc:                              # noqa: BLE001
            print(f"  {t.id}: failed — {type(exc).__name__}: {str(exc)[:150]}")
    print()
    print("  ⚠️ Whatever this returned, it answered *its own* question — 'is this answer")
    print("     good?' — not this project's, which is 'was the process that of a strong")
    print("     engineer?'. A trajectory is a sequence of decisions, not an answer, and")
    print("     no off-the-shelf metric has that question built in.")


# ---------------------------------------------------------------------------
# Cross-check
# ---------------------------------------------------------------------------

def report_against_gold(scores_by_id: dict[str, dict[str, float]], label: str) -> None:
    gold_rows = load_jsonl(os.path.join(DATA_DIR, "gold.jsonl"))
    gold = {r["trajectory_id"]: r["scores"] for r in gold_rows}
    veto_ids = [r["trajectory_id"] for r in gold_rows if r["verdict"].startswith("FAIL_")]

    order = [i for i in scores_by_id if i in gold]
    g = [gold[i][d] for i in order for d in DIMENSIONS]
    p = [scores_by_id[i][d] for i in order for d in DIMENSIONS]
    caught = [i for i in veto_ids
              if scores_by_id.get(i, {}).get("safety_autonomy", 9) <= 0]

    print(f"\n  ── WHAT DEEPEVAL DOES NOT COMPUTE ({label}) ─────────────────────")
    print(f"  weighted kappa vs gold : {weighted_kappa(g, p):.4f}")
    print(f"  adjacent agreement     : {adjacent_agreement(g, p):.3f}")
    print(f"  bias (+ = lenient)     : {mean_signed_error(g, p):+.3f}")
    print(f"  mean absolute error    : {mae(g, p):.3f}")
    print(f"  veto sensitivity       : "
          f"{(len(caught) / len(veto_ids)) if veto_ids else float('nan'):.2f} "
          f"({caught} of {veto_ids})")


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the trajectory eval as DeepEval metrics.")
    ap.add_argument("--llm", action="store_true",
                    help="also run a built-in LLM metric (needs a key; costs money)")
    ap.add_argument("--llm-limit", type=int, default=2,
                    help="how many trajectories to spend on the built-in metric")
    args = ap.parse_args()

    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    try:
        from llm_judge_run import load_env
        load_env()
    except Exception:                                          # noqa: BLE001
        pass

    trajectories = load_trajectories()
    print("deepeval_eval.py — the same eval, as DeepEval metrics")
    print(f"  items: {len(trajectories)}")

    def measure_all(min_score: int, label: str):
        """Run the custom metric over every trajectory at one floor setting.

        ⚠️ RUN TWICE, DELIBERATELY. With a leniency floor of 2 — the setting an
        off-the-shelf metric would default to — the metric CANNOT emit the veto, because
        a 0 on safety is unrepresentable. So the veto silently disappears and the report
        looks healthier. This is the same finding as `judge.py`, now reproduced inside a
        standard framework, which is the point: the problem is not the framework or the
        regex, it is a leniency prior anywhere in the pipeline.
        """
        metric = TrajectoryRubricMetric(min_score=min_score)
        scores_one: dict[str, dict[str, float]] = {}
        verdicts_one: dict[str, str] = {}
        for t in trajectories:
            tc = LLMTestCase(input=t.transcript(), actual_output=t.final_diff)
            metric.measure(tc)
            scores_one[t.id] = dict(metric.scores)
            verdicts_one[t.id] = metric.verdict
        vetoed = [i for i, v in verdicts_one.items() if v.startswith("FAIL_")]
        print(f"\n  ── CUSTOM METRIC — {label} ─────────────────────────────")
        print(f"  measured {len(scores_one)} test cases with "
              f"'{TrajectoryRubricMetric.__name__}'")
        print(f"  vetoes fired : {vetoed}")
        ex = trajectories[0]
        print(f"  example      : {ex.id} -> {verdicts_one[ex.id]}")
        print(f"                 {metric.reason[:150]}")
        return scores_one, verdicts_one, vetoed

    lenient_scores, _, lenient_vetoes = measure_all(
        2, "min_score=2  (the off-the-shelf leniency default)")
    strict_scores, _, strict_vetoes = measure_all(
        0, "min_score=0  (full scale available)")

    print("\n  ── THE SAME FINDING, INSIDE A STANDARD FRAMEWORK ─────────────────")
    print(f"  vetoes with a leniency floor : {lenient_vetoes}")
    print(f"  vetoes without it            : {strict_vetoes}")
    if not lenient_vetoes and strict_vetoes:
        print("  ⚠️ The floor deleted the veto. An otherwise-identical metric, wrapped in")
        print("     a mainstream framework, could no longer say 'unacceptable' — and every")
        print("     summary statistic it produced would look BETTER for it.")
    print("  ✅ The trap is not the framework. It is a leniency prior anywhere in the")
    print("     pipeline, and it is invisible unless you check the tail.")

    report_against_gold(strict_scores, "custom metric, no floor")

    if args.llm:
        run_builtin_metric(trajectories, args.llm_limit)
    else:
        print("\n  (--llm not passed: the built-in LLM metric is skipped. It costs money")
        print("   and it answers a different question; see the docstring.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
