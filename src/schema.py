#!/usr/bin/env python3
"""
schema.py — The data contract.

===============================================================================
WHY A SCHEMA FILE EXISTS IN AN EVAL PROJECT
===============================================================================
Because the most common cause of a silently wrong eval number is that two
components disagreed about what a field meant. The annotator wrote `3`, the
aggregator read it as a *string* "3", the sort put it first, and the report
showed the best score as the worst. Nobody noticed for a month.

So: one loader, one set of dataclasses, one validator that refuses to score a
trajectory it does not understand. `validate_trajectory` raises rather than
coercing, because coercion is how bad data becomes a plausible number.

===============================================================================
HOW TO KNOW IT WORKS
===============================================================================
    python src/schema.py        # validates the two bundled example records
Exits 0 and prints the record counts. Exits 1 with a specific complaint if a
required field is missing or a score is outside 0-4.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Iterable

from rubric import SCALE_MAX, DIMENSIONS

HERE = os.path.dirname(os.path.abspath(__file__))
TRACK_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(TRACK_DIR, "data")

# The fields without which a trajectory is not scoreable. Note `acceptance_criteria`
# and `hidden_tests` are required: a task with no stated acceptance criteria cannot
# fairly score `problem_framing`, and a task whose hidden tests you can see is not
# a measurement of engineering judgment — it is a measurement of test-guessing.
REQUIRED_TRAJECTORY_FIELDS = ("id", "title", "repo", "language", "task",
                              "acceptance_criteria", "constraints", "hidden_tests",
                              "steps", "final_diff", "tests", "budget")

STEP_KINDS = {"think", "tool", "edit", "test", "final"}


class SchemaError(ValueError):
    """Raised instead of coercing. A wrong field is a bug, not a formatting issue."""


@dataclass
class Step:
    n: int
    kind: str
    thought: str = ""
    tool: str = ""
    input: str = ""
    observation: str = ""
    target: str = ""
    diff: str = ""
    summary: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int) -> "Step":
        kind = raw.get("kind")
        if kind not in STEP_KINDS:
            raise SchemaError(f"step {index}: kind {kind!r} not in {sorted(STEP_KINDS)}")
        return cls(
            n=int(raw.get("n", index + 1)),
            kind=kind,
            thought=raw.get("thought", ""),
            tool=raw.get("tool", ""),
            input=raw.get("input", ""),
            observation=raw.get("observation", ""),
            target=raw.get("target", ""),
            diff=raw.get("diff", ""),
            summary=raw.get("summary", ""),
        )

    def render(self) -> str:
        head = f"  [{self.n:>2}] {self.kind.upper():<6}"
        if self.thought:
            head += f" think: {self.thought}"
        if self.tool:
            head += f"\n         $ {self.tool} {self.input}".rstrip()
        if self.observation:
            head += f"\n         -> {self.observation}"
        if self.target:
            head += f"\n         edit {self.target}\n{self._indent(self.diff)}"
        if self.summary:
            head += f"\n         SUMMARY: {self.summary}"
        return head

    @staticmethod
    def _indent(text: str, pad: str = "           ") -> str:
        return "\n".join(pad + line for line in text.splitlines())


@dataclass
class Trajectory:
    id: str
    title: str
    repo: str
    language: str
    task: str
    acceptance_criteria: list[str]
    constraints: list[str]
    hidden_tests: list[str]
    steps: list[Step]
    final_diff: str
    tests: dict[str, str]
    budget: dict[str, Any]
    # `planted` and `strengths` ARE the ground truth. They are authored, not
    # inferred, and `dataset.py` maps them through the rubric anchors to produce
    # gold scores. They are kept on the record so the mapping is auditable.
    planted: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Trajectory":
        validate_trajectory_dict(raw)
        return cls(
            id=raw["id"],
            title=raw["title"],
            repo=raw["repo"],
            language=raw["language"],
            task=raw["task"],
            acceptance_criteria=list(raw["acceptance_criteria"]),
            constraints=list(raw["constraints"]),
            hidden_tests=list(raw["hidden_tests"]),
            steps=[Step.from_dict(s, i) for i, s in enumerate(raw["steps"])],
            final_diff=raw["final_diff"],
            tests=dict(raw["tests"]),
            budget=dict(raw["budget"]),
            planted=list(raw.get("planted", [])),
            strengths=list(raw.get("strengths", [])),
            notes=raw.get("notes", ""),
        )

    def transcript(self, include_hidden: bool = False) -> str:
        """The blob an annotator (human or LLM judge) actually reads.

        ⚠️ HIDDEN TEST RESULTS ARE EXCLUDED BY DEFAULT, AND THAT IS THE WHOLE
        DESIGN. If the annotator can see which hidden tests failed, they are not
        evaluating engineering judgement — they are transcribing an outcome.
        traj-004 is the case that proves it: its visible suite is green and its
        hidden suite is not, and the only way to get `verification=0` without
        the hidden results is to notice that the agent duplicated the last row
        to satisfy a count assertion.

        Set `include_hidden=True` only to produce the *answer key* for scoring
        the annotator, never as annotator input.
        """
        lines = [
            f"# {self.id} — {self.title}",
            f"repo: {self.repo}   language: {self.language}",
            "",
            "## TASK",
            self.task,
            "",
            "## ACCEPTANCE CRITERIA (visible to the agent)",
        ]
        lines += [f"  - {c}" for c in self.acceptance_criteria]
        lines += ["", "## CONSTRAINTS"]
        lines += [f"  - {c}" for c in self.constraints]
        lines += ["", "## TRAJECTORY"]
        lines += [s.render() for s in self.steps]
        lines += [
            "",
            "## FINAL DIFF",
            self.final_diff,
            "",
            "## TEST RESULTS REPORTED BY THE AGENT",
        ]
        keys = ["visible"] + (["hidden"] if include_hidden else [])
        lines += [f"  {k}: {v}" for k, v in self.tests.items() if k in keys]
        if not include_hidden:
            lines += ["  (hidden acceptance tests: not available to the annotator)"]
        lines += [
            "",
            "## BUDGET",
            f"  tool_calls={self.budget.get('tool_calls')}  "
            f"wall_clock_min={self.budget.get('wall_clock_min')}  "
            f"tokens={self.budget.get('tokens')}",
        ]
        return "\n".join(lines)

    def hidden_outcome(self) -> str:
        """The answer key. Used to score the annotator, never shown to them."""
        return str(self.tests.get("hidden", ""))


def validate_trajectory_dict(raw: dict[str, Any]) -> None:
    """Fail loudly. Every check here corresponds to a way a benchmark has lied."""
    for f in REQUIRED_TRAJECTORY_FIELDS:
        if f not in raw:
            raise SchemaError(f"{raw.get('id', '<no id>')}: missing required field {f!r}")
    if not raw["steps"]:
        raise SchemaError(f"{raw['id']}: no steps — nothing to score")
    if raw["steps"][-1].get("kind") != "final":
        raise SchemaError(f"{raw['id']}: last step must be kind='final'")
    if len(raw["acceptance_criteria"]) < 2:
        raise SchemaError(
            f"{raw['id']}: needs >=2 acceptance criteria. With fewer, 'did it meet "
            "the criteria' collapses into 'did it pass the visible test'."
        )
    if not raw["hidden_tests"]:
        raise SchemaError(f"{raw['id']}: needs hidden_tests (the agent must not see them)")
    for k in ("tool_calls", "wall_clock_min"):
        if k not in raw["budget"]:
            raise SchemaError(f"{raw['id']}: budget missing {k!r}")


def validate_annotation(ann: dict[str, Any]) -> None:
    """An annotation that breaks these rules is discarded, not repaired."""
    if "trajectory_id" not in ann or "scores" not in ann:
        raise SchemaError("annotation needs trajectory_id and scores")
    scores = ann["scores"]
    missing = [d for d in DIMENSIONS if d not in scores]
    if missing:
        raise SchemaError(f"{ann['trajectory_id']}: unscored dimensions {missing}")
    for dim, value in scores.items():
        if dim not in DIMENSIONS:
            raise SchemaError(f"{ann['trajectory_id']}: unknown dimension {dim!r}")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise SchemaError(f"{ann['trajectory_id']}.{dim}: {value!r} is not a number")
        if not 0 <= value <= SCALE_MAX:
            raise SchemaError(
                f"{ann['trajectory_id']}.{dim}: {value} outside 0-{SCALE_MAX}. "
                "Clamp deliberately in the annotator, never here."
            )


def load_jsonl(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run `python src/dataset.py` first to build it."
        )
    out = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SchemaError(f"{os.path.basename(path)}:{lineno}: {exc}") from exc
    return out


def load_trajectories(path: str | None = None) -> list[Trajectory]:
    path = path or os.path.join(DATA_DIR, "trajectories.jsonl")
    return [Trajectory.from_dict(r) for r in load_jsonl(path)]


def load_annotations(path: str) -> list[dict[str, Any]]:
    anns = load_jsonl(path)
    for a in anns:
        validate_annotation(a)
    return anns


def write_jsonl(path: str, rows: Iterable[dict[str, Any]]) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def annotation(trajectory_id: str, annotator: str, scores: dict[str, float],
               **extra: Any) -> dict[str, Any]:
    """Build a validated annotation. The single constructor used by everything."""
    ann = {"trajectory_id": trajectory_id, "annotator": annotator,
           "scores": {k: float(v) for k, v in scores.items()}}
    ann.update(extra)
    validate_annotation(ann)
    return ann


if __name__ == "__main__":
    print("SCHEMA — self-check")
    sample = {
        "id": "demo-001", "title": "demo", "repo": "acme/api", "language": "python",
        "task": "Fix it.", "acceptance_criteria": ["a", "b"], "constraints": ["c"],
        "hidden_tests": ["t"], "final_diff": "diff", "tests": {"visible": "ok"},
        "budget": {"tool_calls": 1, "wall_clock_min": 1},
        "steps": [{"kind": "final", "summary": "done"}],
    }
    t = Trajectory.from_dict(sample)
    print(f"  trajectory ok: {t.id} ({len(t.steps)} step)")
    try:
        validate_annotation({"trajectory_id": "demo-001",
                             "scores": {d: 5 for d in DIMENSIONS}})
    except SchemaError as exc:
        print(f"  out-of-range score rejected correctly: {str(exc)[:60]}...")
    else:
        raise SystemExit("FAIL: an out-of-range score was accepted")
    print("  OK")
