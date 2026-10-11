#!/usr/bin/env python3
"""
agreement.py — Inter-rater reliability, implemented from scratch.

===============================================================================
WHY THIS FILE IS THE POINT OF THE WHOLE PROJECT
===============================================================================
An eval team's product is *judgements*, and a judgement is only a measurement if
you know how much two competent people agree about it. Every frontier lab that
runs human annotation publishes or internally tracks reliability; almost no
portfolio project computes it. This is the file that separates "I can rate model
outputs" from "I can build a rating process".

Nothing here uses scikit-learn. That is deliberate: `cohen_kappa_score` is one
line away, and using it would make the artefact unreviewable at exactly the
moment a staff interviewer asks "how is the ordinal metric defined?".

===============================================================================
FIVE ESTIMATORS, AND WHEN EACH IS THE WRONG ONE
===============================================================================
  cohen_kappa            2 raters, NOMINAL, chance-corrected.
                         ⚠️ Treats a 3-vs-4 disagreement as identical to a 1-vs-4.
                            On a 0-4 ordinal scale that is simply false, and it is
                            the single most common misuse of kappa.

  weighted_kappa         Ordinal, with linear or quadratic weights. THIS is the
  (linear/quadratic)     estimator to lead with on a 0-4 rubric. The quadratic
                         form punishes large disagreements much harder, which
                         matches how a rubric is actually used: 3-vs-4 is noise,
                         3-vs-0 is a real disagreement.

  krippendorff_alpha     N raters, missing data allowed, any metric. The right
  (ordinal)              tool for a real annotation team, because raters miss
                         items and you should not have to throw the item away.

  icc_2_1                Continuous/ordinal, absolute agreement, two-way random
                         effects. Answers "can a single rater's score be trusted
                         as the score?" — which is the operationally important
                         question and NOT the same as kappa's question.

  adjacent_agreement     The plain-English number for a stakeholder: what
                         fraction of decisions are within one point. Unglamorous,
                         assumption-free, and impossible to misread.

⚠️ REPORTING RULE OBSERVED THROUGHOUT: every estimate is a point value with a
bootstrap interval, resampled over ITEMS, not over scores. Scores within one
trajectory are correlated (an annotator who is generous is generous about all
nine dimensions), so resampling individual scores understates the uncertainty.
That mistake is common enough to be worth naming out loud.

===============================================================================
HOW TO KNOW IT WORKS
===============================================================================
    python src/agreement.py
Correct output: a table of self-tests, each with the analytic answer it must
match, and a final "OK". The two hand-computable cases are a kappa of exactly
0.4 on a 2x2 table and an alpha of exactly -0.5 on the maximally-disagreeing
binary case; if those two are right, the bookkeeping is right.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Sequence

# ---------------------------------------------------------------------------
# Confusion / coincidence machinery
# ---------------------------------------------------------------------------

def confusion(a: Sequence[float], b: Sequence[float],
              lo: int = 0, hi: int = 4) -> list[list[int]]:
    if len(a) != len(b):
        raise ValueError(f"rater vectors differ in length: {len(a)} vs {len(b)}")
    m = [[0] * (hi - lo + 1) for _ in range(hi - lo + 1)]
    for x, y in zip(a, b):
        xi, yi = int(x) - lo, int(y) - lo
        if not (0 <= xi < len(m) and 0 <= yi < len(m[0])):
            raise ValueError(f"value out of range [{lo},{hi}]: {x}, {y}")
        m[xi][yi] += 1
    return m


def _marginals(m: list[list[int]]) -> tuple[list[int], list[int], int]:
    n = sum(sum(row) for row in m)
    rows = [sum(row) for row in m]
    cols = [sum(m[i][j] for i in range(len(m))) for j in range(len(m[0]))]
    return rows, cols, n


def cohen_kappa(a: Sequence[float], b: Sequence[float],
                lo: int = 0, hi: int = 4) -> float:
    """Nominal chance-corrected agreement for exactly two raters.

    Returns float('nan') when pe == 1, i.e. when both raters used a single
    identical category throughout. NaN is the honest answer there — the quantity
    is undefined — and a caller that prints 0.0 instead is inventing a number.
    """
    m = confusion(a, b, lo, hi)
    rows, cols, n = _marginals(m)
    if n == 0:
        return float("nan")
    po = sum(m[i][i] for i in range(len(m))) / n
    pe = sum(rows[i] * cols[i] for i in range(len(m))) / (n * n)
    if abs(1.0 - pe) < 1e-12:
        return float("nan")
    return (po - pe) / (1.0 - pe)


def ordinal_weight(i: int, j: int, kind: str = "linear",
                   lo: int = 0, hi: int = 4) -> float:
    """The weight function for weighted kappa: w = 1 - (|i-j| / span)^p.

    Extracted as its own function so it can be TESTED directly. It was inline
    inside `weighted_kappa` until a test of its shape was written, and the shape
    is the part that is easy to get subtly wrong and impossible to see from a
    single kappa value. See `tests/test_trajectory_eval.py`.

    ⚠️ THE TWO FORMS ARE NOT "LINEAR IS STRICTER THAN QUADRATIC". They differ only
    at intermediate distances, and quadratic is the more GENEROUS of the two:

        distance (0-4 scale)   1      2      3      4
        linear weight        0.75   0.50   0.25   0.00
        quadratic weight     0.94   0.75   0.44   0.00
        linear penalty       0.25   0.50   0.75   1.00
        quadratic penalty    0.06   0.25   0.56   1.00

    What quadratic does differently is make the PENALTY grow super-linearly:
    penalty(k·d) / penalty(d) = k², so a 4-point miss is punished 16× a 1-point
    miss whereas linear punishes it only 4×. That is the property people mean by
    "quadratic punishes large disagreements disproportionately", and it is the
    right shape for a rubric where 3-vs-4 is noise and 3-vs-0 is a real
    disagreement.

    Because quadratic also makes small misses nearly free (0.06 vs 0.25), it
    inflates kappa on data that mostly agrees — which is why **linear is the
    default here**: it is the conservative choice, and a reliability figure should
    be the conservative one.
    """
    if kind not in ("linear", "quadratic"):
        raise ValueError("kind must be 'linear' or 'quadratic'")
    span = float(hi - lo)
    if span == 0:
        raise ValueError("span must be non-zero")
    d = abs(i - j) / span
    return 1.0 - (d if kind == "linear" else d * d)


def weighted_kappa(a: Sequence[float], b: Sequence[float], kind: str = "linear",
                   lo: int = 0, hi: int = 4) -> float:
    """Ordinal (weighted) kappa. The estimator to lead with on a 0-4 rubric.

    Uses `ordinal_weight`; see its docstring for why linear is the default and
    for the exact sense in which quadratic is harsher.
    """
    if kind not in ("linear", "quadratic"):
        raise ValueError("kind must be 'linear' or 'quadratic'")
    if float(hi - lo) == 0:
        return float("nan")

    def w(i: int, j: int) -> float:
        return ordinal_weight(i, j, kind, lo, hi)

    m = confusion(a, b, lo, hi)
    rows, cols, n = _marginals(m)
    if n == 0:
        return float("nan")
    po = sum(w(i, j) * m[i][j] for i in range(len(m)) for j in range(len(m))) / n
    pe = sum(w(i, j) * rows[i] * cols[j]
             for i in range(len(m)) for j in range(len(m))) / (n * n)
    if abs(1.0 - pe) < 1e-12:
        return float("nan")
    return (po - pe) / (1.0 - pe)


def adjacent_agreement(a: Sequence[float], b: Sequence[float], tol: int = 1) -> float:
    """Fraction of decisions within `tol` points. Say this to stakeholders."""
    if not len(a):
        return float("nan")
    return sum(1 for x, y in zip(a, b) if abs(x - y) <= tol) / len(a)


def mean_signed_error(reference: Sequence[float], predicted: Sequence[float]) -> float:
    """Positive = the predictor is LENIENT. The judge-bias headline number."""
    if not len(reference):
        return float("nan")
    return sum(p - r for r, p in zip(reference, predicted)) / len(reference)


def mae(reference: Sequence[float], predicted: Sequence[float]) -> float:
    if not len(reference):
        return float("nan")
    return sum(abs(p - r) for r, p in zip(reference, predicted)) / len(reference)


# ---------------------------------------------------------------------------
# Krippendorff's alpha, ordinal metric.
#
# Two independent implementations. The fast one builds the coincidence matrix;
# the slow one evaluates the formula over ordered pairs inside each unit. They
# must agree to floating-point tolerance on random data, and `selftest.py`
# asserts that they do. If a future refactor breaks the coincidence
# bookkeeping, the test fails instead of the number silently drifting.
# ---------------------------------------------------------------------------

def _delta2_ordinal(c: int, k: int, n_g: dict[int, int]) -> float:
    """Squared ordinal difference for values c, k.

    delta^2_ck = ( sum_{g=c..k} n_g  -  (n_c + n_k)/2 )^2      for c < k
    The sum-of-marginals term is what makes intermediate categories matter: two
    ratings of 1 and 3 disagree *through* category 2, so the amount of data in
    category 2 changes the distance. A nominal metric cannot express that.
    """
    if c == k:
        return 0.0
    a, b = (c, k) if c < k else (k, c)
    inner = sum(n_g.get(g, 0) for g in range(a, b + 1)) - (n_g.get(a, 0) + n_g.get(b, 0)) / 2.0
    return inner * inner


def _marginal_counts(units: list[list[int]]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for u in units:
        for v in u:
            counts[v] = counts.get(v, 0) + 1
    return counts


def _pairable(units: list[list[int]]) -> list[list[int]]:
    """Krippendorff discards units with fewer than two ratings: they carry no
    disagreement information but would still move the marginals."""
    return [u for u in units if len(u) >= 2]


def krippendorff_alpha_ordinal(units: list[list[int]]) -> float:
    """Coincidence-matrix implementation. O(N * m^2) in ratings per unit."""
    units = _pairable(units)
    if not units:
        return float("nan")
    n_g = _marginal_counts(units)
    n = sum(n_g.values())

    # Coincidence matrix: for each unit with m ratings, every ordered pair of
    # distinct ratings contributes 1/(m-1).
    coin: dict[tuple[int, int], float] = {}
    for u in units:
        m = len(u)
        contrib = 1.0 / (m - 1)
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                key = (u[i], u[j])
                coin[key] = coin.get(key, 0.0) + contrib

    do_num = sum(v * _delta2_ordinal(c, k, n_g) for (c, k), v in coin.items())
    do = do_num / n
    de_num = sum(n_g[c] * n_g[k] * _delta2_ordinal(c, k, n_g)
                 for c in n_g for k in n_g)
    de = de_num / (n * (n - 1)) if n > 1 else float("nan")
    if de == 0 or math.isnan(de):
        return float("nan")
    return 1.0 - do / de


def krippendorff_alpha_ordinal_bruteforce(units: list[list[int]]) -> float:
    """Direct implementation of the definition. Slow, obviously-correct, used
    only to cross-check the fast one."""
    units = _pairable(units)
    if not units:
        return float("nan")
    n_g = _marginal_counts(units)
    n = sum(n_g.values())

    do_num = 0.0
    for u in units:
        m = len(u)
        acc = 0.0
        for i in range(m):
            for j in range(m):
                if i != j:
                    acc += _delta2_ordinal(u[i], u[j], n_g)
        do_num += acc / (m - 1)
    do = do_num / n
    de_num = sum(n_g[c] * n_g[k] * _delta2_ordinal(c, k, n_g)
                 for c in n_g for k in n_g)
    de = de_num / (n * (n - 1)) if n > 1 else float("nan")
    if de == 0 or math.isnan(de):
        return float("nan")
    return 1.0 - do / de


# ---------------------------------------------------------------------------
# ICC
# ---------------------------------------------------------------------------

def icc_2_1(matrix: list[list[float]]) -> float:
    """ICC(2,1): two-way random effects, absolute agreement, single rater.

    matrix: n_subjects x k_raters, complete (no missing values).

    This answers the question an ops manager actually asks: "if I pick ONE rater
    at random, how close is their score to the truth?" Kappa answers a different
    question ("do raters agree beyond chance?") and can be high while ICC is
    low when raters are consistently offset from each other.
    """
    n = len(matrix)
    if n < 2:
        return float("nan")
    k = len(matrix[0])
    if k < 2:
        return float("nan")
    if any(len(row) != k for row in matrix):
        raise ValueError("icc_2_1 requires a complete, rectangular matrix")

    grand = sum(sum(r) for r in matrix) / (n * k)
    row_means = [sum(r) / k for r in matrix]
    col_means = [sum(matrix[i][j] for i in range(n)) / n for j in range(k)]

    ss_total_rows = k * sum((rm - grand) ** 2 for rm in row_means)
    ss_total_cols = n * sum((cm - grand) ** 2 for cm in col_means)
    ss_err = sum((matrix[i][j] - row_means[i] - col_means[j] + grand) ** 2
                 for i in range(n) for j in range(k))

    ms_rows = ss_total_rows / (n - 1)          # between subjects
    ms_cols = ss_total_cols / (k - 1)          # between raters
    ms_err = ss_err / ((n - 1) * (k - 1))
    denom = ms_rows + (k - 1) * ms_err + k * (ms_cols - ms_err) / n
    if abs(denom) < 1e-12:
        return float("nan")
    return (ms_rows - ms_err) / denom


# ---------------------------------------------------------------------------
# Bootstrap intervals
# ---------------------------------------------------------------------------

def bootstrap_ci(metric: Callable[..., float], units: list, n_boot: int = 2000,
                 seed: int = 0, alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap over ITEMS.

    `units` is the list of items; `metric` is called with a resampled list. Note
    the resampling unit is the trajectory, because the nine dimension scores
    inside one trajectory come from one judgement and are not independent. With
    n=20 items the interval is wide, and that width is the finding — a kappa
    quoted without it is a number pretending to be a measurement.
    """
    if not units:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(units)
    vals = []
    for _ in range(n_boot):
        sample = [units[rng.randrange(n)] for _ in range(n)]
        try:
            v = metric(sample)
        except (ValueError, ZeroDivisionError, KeyError):
            continue
        if v is None or math.isnan(v):
            continue
        vals.append(v)
    if len(vals) < 20:
        return (float("nan"), float("nan"))
    vals.sort()
    lo = vals[int((alpha / 2) * len(vals))]
    hi = vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]
    return (lo, hi)


# ---------------------------------------------------------------------------
# Pooling across dimensions — and the caveat that goes with it
# ---------------------------------------------------------------------------

def flatten(records: list[dict], annotator: str, dimensions: Sequence[str],
            ) -> dict[str, list[float]]:
    """{dimension: [score per item]} for one annotator, in item order.

    Item order is preserved deliberately: `reliability_report` rebuilds
    (item, dimension) pairs to bootstrap over, and a reordering here would
    silently pair one item's gold with another item's prediction.
    """
    out = {d: [] for d in dimensions}
    for rec in records:
        for d in dimensions:
            out[d].append(float(rec[annotator][d]))
    return out


def reliability_report(gold_dims: dict[str, list[float]],
                       pred_dims: dict[str, list[float]],
                       rank: str = "ordinal") -> dict:
    """The full reliability picture for one annotator against gold.

    Returns per-dimension estimates, the pooled headline, and the bias profile.
    A single kappa number is not a reliability report; this is.
    """
    dims = list(gold_dims)
    per_dim = {}
    for d in dims:
        g, p = gold_dims[d], pred_dims[d]
        key = weighted_kappa if rank == "ordinal" else cohen_kappa
        per_dim[d] = {
            "kappa": (key(g, p) if rank == "ordinal" else key(g, p)),
            "kappa_nominal": cohen_kappa(g, p),
            "adjacent": adjacent_agreement(g, p),
            "mae": mae(g, p),
            "bias": mean_signed_error(g, p),
            "n_distinct_gold": len(set(g)),
        }

    flat_g = [x for d in dims for x in gold_dims[d]]
    flat_p = [x for d in dims for x in pred_dims[d]]
    key = weighted_kappa if rank == "ordinal" else cohen_kappa

    # Bootstrap resamples ITEMS: rebuild (item, dim) pairs together.
    n_items = len(next(iter(gold_dims.values())))
    pairs = [(d, i) for i in range(n_items) for d in dims]

    def metric_from_pairs(subset) -> float:
        g = [gold_dims[d][i] for d, i in subset]
        p = [pred_dims[d][i] for d, i in subset]
        return key(g, p)

    lo, hi = bootstrap_ci(metric_from_pairs, pairs, seed=7)

    return {
        "per_dimension": per_dim,
        "pooled": {
            "estimator": "linear weighted kappa" if rank == "ordinal" else "cohen kappa",
            "kappa": key(flat_g, flat_p),
            "kappa_nominal": cohen_kappa(flat_g, flat_p),
            "pooled_ci95": (lo, hi),
            "n_decisions": len(flat_g),
            "n_items": n_items,
            "adjacent": adjacent_agreement(flat_g, flat_p),
            "mae": mae(flat_g, flat_p),
            "bias": mean_signed_error(flat_g, flat_p),
            # ICC treats the two annotators as the two "raters" and each
            # (item, dimension) decision as a subject. That is the right shape:
            # the question is "can I trust one rater's score absolutely", so the
            # raters must be raters.
            "icc_2_1": icc_2_1([[g, p] for g, p in zip(flat_g, flat_p)]),
        },
        "caveat": (
            "Pooled kappa mixes nine dimensions with different marginal "
            "distributions, so it is not comparable to a single-dimension kappa "
            "and it is sensitive to which dimensions happen to have spread. Read "
            "it as a headline with the per-dimension table beside it, never alone."
        ),
    }


def landis_koch(kappa: float) -> str:
    """The conventional verbal bands. Quote them, and quote their origin, rather
    than inventing adjectives. NOTE they were written for nominal kappa and are
    routinely over-applied to weighted kappa, where values run lower."""
    if math.isnan(kappa):
        return "undefined (no variance to correct for)"
    for cut, label in ((0.81, "almost perfect"), (0.61, "substantial"),
                       (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")):
        if kappa >= cut:
            return label
    return "poor (worse than chance)"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _selftest() -> int:
    failures = []

    def check(name: str, got: float, want: float, tol: float = 1e-9) -> None:
        ok = (math.isnan(got) and math.isnan(want)) or abs(got - want) < tol
        print(f"  {'ok  ' if ok else 'FAIL'} {name:<52} got={got!r:>10} want={want!r}")
        if not ok:
            failures.append(name)

    # Hand-computable kappa: 2x2 table [[20,5],[10,15]] -> po=.70, pe=.50, k=.40
    a = [0] * 20 + [0] * 5 + [1] * 10 + [1] * 15
    b = [0] * 20 + [1] * 5 + [0] * 10 + [1] * 15
    check("cohen_kappa hand-computed 2x2", cohen_kappa(a, b), 0.4)

    # Perfect agreement
    check("cohen_kappa perfect agreement", cohen_kappa(a, a), 1.0)
    check("weighted_kappa perfect agreement", weighted_kappa(a, a), 1.0)

    # Maximally disagreeing binary case: alpha must be exactly -0.5
    units = [[0, 1], [1, 0]]
    check("krippendorff ordinal alpha = -0.5",
          krippendorff_alpha_ordinal(units), -0.5)
    check("krippendorff ordinal alpha perfect", krippendorff_alpha_ordinal(
        [[3, 3], [1, 1], [4, 4]]), 1.0)

    # The two alpha implementations must agree on random data.
    rng = random.Random(11)
    max_diff = 0.0
    for _ in range(40):
        nu = rng.randint(3, 12)
        units = [[rng.randint(0, 4) for _ in range(rng.randint(2, 5))]
                 for _ in range(nu)]
        f = krippendorff_alpha_ordinal(units)
        s = krippendorff_alpha_ordinal_bruteforce(units)
        if math.isnan(f) and math.isnan(s):
            continue
        max_diff = max(max_diff, abs(f - s))
    check("alpha: coincidence == bruteforce (max diff over 40 draws)",
          max_diff, 0.0, tol=1e-9)

    # ICC: perfect agreement -> 1; identical raters -> 1 even if all wrong
    check("icc_2_1 perfect agreement", icc_2_1([[1, 1], [3, 3], [4, 4]]), 1.0)
    check("icc_2_1 identical raters (consistency)",
          icc_2_1([[1, 1], [3, 3]]), 1.0)

    # The negative control: a constant rater must score kappa 0, not 0.9
    gold = [1, 2, 3, 4, 3, 2, 1, 0, 4, 3]
    const = [3] * 10
    k = cohen_kappa(gold, const)
    check("negative control: constant rater kappa == 0", k, 0.0, tol=1e-12)

    # Adjacency and bias
    check("adjacent_agreement tol=1", adjacent_agreement([1, 2, 3], [2, 3, 4]), 1.0)
    check("mean_signed_error is leniency-positive",
          mean_signed_error([1, 2], [2, 4]), 1.5)

    print()
    if failures:
        print(f"  {len(failures)} FAILURE(S): {failures}")
        return 1
    print("  OK — all agreement estimators match their analytic answers.")
    return 0


if __name__ == "__main__":
    print("agreement.py — self-test")
    raise SystemExit(_selftest())
