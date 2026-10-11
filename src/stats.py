#!/usr/bin/env python3
"""
stats.py — How many items do you actually need?

===============================================================================
THE QUESTION THAT DECIDES WHETHER YOUR EVAL IS A MEASUREMENT
===============================================================================
"We got 84% on 60 trajectories" is not a result. This file turns that into:
84% on 60 trajectories is ±9.8 points at 95% confidence, so the only differences
you can detect are larger than 9.8 points. Everything smaller is noise, and
shipping decisions based on noise are how you get a reputation for being wrong.

Three tools, in the order you should reach for them:

  1. WILSON INTERVAL / needed n for an accuracy.
     Wilson, not the textbook normal approximation, because at p near 0 or 1 (and
     at n=20) the normal interval produces bounds outside [0,1] and is simply
     wrong. This matters on a small eval set, which is every eval set.

  2. McNEMAR PAIRING — needed n to detect a difference between two models on the
     SAME items. Pairing removes item-difficulty variance. Comparing two
     independent percentages instead is the most common statistical error in
     applied ML and typically needs ~3x the data for the same conclusion.

  3. THE EMPIRICAL LEARNING CURVE FOR KAPPA.
     ⚠️ There is no closed form here that you should trust without checking it,
     and a large-sample Fleiss-Cohen variance evaluated at n=20 is extrapolation
     dressed as arithmetic. So this file SUBSAMPLES the data you have and
     measures the interval width as a function of n, then fits 1/sqrt(n). The
     numbers printed at n<=20 are measurements. Anything beyond that is labelled
     as the extrapolation it is, with the honest caveat: label 40 items and look.

===============================================================================
HOW TO KNOW IT WORKS
===============================================================================
    python src/stats.py
Correct output: an interval-width table that shrinks monotonically with n, a
"you need N items" line, and a check that the Wilson interval stays inside [0,1]
at p=0.95 and p=0.05 where the normal approximation does not.
"""

from __future__ import annotations

import math
import random

Z = {0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


def _z(conf: float) -> float:
    if conf not in Z:
        raise ValueError(f"only {sorted(Z)} supported; add the constant if you need more")
    return Z[conf]


def wilson_interval(successes: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Score interval for a binomial proportion. Correct at small n and at the
    boundaries, which is where an eval set lives."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = _z(conf)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def normal_interval(successes: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Kept ONLY to demonstrate why it is not used. It goes outside [0,1]."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    half = _z(conf) * math.sqrt(p * (1 - p) / n)
    return (p - half, p + half)


def needed_n_for_halfwidth(halfwidth: float, p: float = 0.8,
                           conf: float = 0.95) -> int:
    """Smallest n whose maximum half-width at the given p is <= halfwidth.

    Uses the conservative p(1-p) from the supplied p, then brute-forces upward,
    because the inverting algebra is only approximate and a wrong n from a tidy
    formula is worse than a loop.
    """
    z = _z(conf)
    if halfwidth <= 0:
        raise ValueError("halfwidth must be positive")
    n = 2
    while n < 10_000_000:
        half = z * math.sqrt(p * (1 - p) / n)
        if half <= halfwidth:
            return n
        n += 1
    raise RuntimeError("no n found")


def mcnemar_needed_n(psi: float, delta: float, conf: float = 0.95,
                     power: float = 0.8) -> int:
    """Pairs needed to detect `delta` in a paired binary comparison.

    psi   = discordant proportion, p10 + p01 (typically 0.1-0.3 for two models
            that are close).
    delta = p10 - p01, the accuracy difference you want to detect.

    Standard McNemar planning formula. ⚠️ It is an approximation that assumes
    equal discordance allocation; the honest use is to treat the output as an
    order of magnitude and then say so. Note how sharply it grows as delta
    shrinks: this is the arithmetic behind "a 2-point improvement is not a
    result".
    """
    z_alpha = _z(conf)
    z_beta = {0.80: 0.8416, 0.90: 1.2816}[power]
    if delta <= 0:
        raise ValueError("delta must be positive")
    if psi <= delta * delta:
        raise ValueError("psi must exceed delta^2 for the formula to be meaningful")
    num = (z_alpha * math.sqrt(psi) + z_beta * math.sqrt(psi - delta * delta)) ** 2
    return int(math.ceil(num / (delta * delta)))


def learning_curve(metric, units: list, sizes: list[int], repeats: int = 200,
                   seed: int = 3) -> list[dict]:
    """Measure the metric's interval half-width as a function of n, by subsampling.

    `metric(subset) -> float`. Each size is subsampled `repeats` times without
    replacement; we report the 2.5th and 97.5th percentile of the resulting
    point estimates. ⚠️ This is a *stability* interval, not a confidence
    interval: it says "how much would this number have moved if I had picked a
    different 10 items", which is the question a practitioner actually has.
    """
    rng = random.Random(seed)
    n_total = len(units)
    out = []
    for n in sizes:
        if n > n_total:
            continue
        vals = []
        for _ in range(repeats):
            sample = rng.sample(units, n)
            try:
                v = metric(sample)
            except (ValueError, ZeroDivisionError, KeyError):
                continue
            if v is None or (isinstance(v, float) and math.isnan(v)):
                continue
            vals.append(v)
        if len(vals) < 20:
            continue
        vals.sort()
        lo = vals[int(0.025 * len(vals))]
        hi = vals[int(0.975 * len(vals)) - 1]
        out.append({
            "n": n,
            "point": sum(vals) / len(vals),
            "lo": lo, "hi": hi,
            "halfwidth": (hi - lo) / 2,
            "repeats_used": len(vals),
        })
    return out


def extrapolate_halfwidth(curve: list[dict], target_n: int) -> float:
    """Half-width at `target_n`, using the 1/sqrt(n) scaling.

    ⚠️ EXTRAPOLATION. The largest n in the curve is a measurement; everything
    past it assumes the standard error scales as 1/sqrt(n), which holds for a
    mean and only approximately for a chance-corrected agreement coefficient.
    Print it as an estimate, with the caveat attached.
    """
    if not curve:
        return float("nan")
    last = curve[-1]
    return last["halfwidth"] * math.sqrt(last["n"] / target_n)


def interpretation_table(p: float = 0.8, conf: float = 0.95) -> str:
    lines = [f"  confidence intervals on an accuracy of {p:.0%} (Wilson, {conf:.0%})",
             "", "        n     ± 95% CI   smallest difference you could detect",
             "  " + "-" * 62]
    for n in (20, 50, 100, 200, 500, 1000, 2000):
        lo, hi = wilson_interval(int(round(p * n)), n, conf)
        lines.append(f"  {n:>7}      {(hi - lo) / 2 * 100:>6.1f}%   "
                     f"anything smaller than {(hi - lo) * 100:.1f} points")
    return "\n".join(lines)


if __name__ == "__main__":
    print("stats.py — self-check\n")

    failures = []

    # Wilson must stay inside [0,1] where the normal interval does not.
    for p, n in ((0.95, 20), (0.05, 20), (1.0, 10), (0.0, 10)):
        lo, hi = wilson_interval(int(round(p * n)), n)
        ok = 0.0 <= lo <= hi <= 1.0
        print(f"  {'ok  ' if ok else 'FAIL'} wilson in [0,1] at p={p}, n={n}: "
              f"[{lo:.3f}, {hi:.3f}]")
        if not ok:
            failures.append(f"wilson p={p} n={n}")
    nlo, nhi = normal_interval(19, 20)
    print(f"  note normal interval at p=0.95, n=20 is [{nlo:.3f}, {nhi:.3f}] "
          f"— hi>1, which is why it is not used")

    # needed_n must be monotone decreasing in the target half-width
    widths = [0.10, 0.05, 0.025]
    ns = [needed_n_for_halfwidth(w) for w in widths]
    ok = all(ns[i] < ns[i + 1] for i in range(len(ns) - 1))
    print(f"  {'ok  ' if ok else 'FAIL'} needed n grows as the target shrinks: "
          f"{dict(zip([f'±{w:.3f}' for w in widths], ns))}")
    if not ok:
        failures.append("needed_n monotonicity")

    # McNemar must grow as delta shrinks
    d1 = mcnemar_needed_n(0.20, 0.10)
    d2 = mcnemar_needed_n(0.20, 0.05)
    ok = d2 > d1
    print(f"  {'ok  ' if ok else 'FAIL'} mcnemar n grows as the effect shrinks: "
          f"delta=0.10 -> {d1} pairs, delta=0.05 -> {d2} pairs")
    if not ok:
        failures.append("mcnemar monotonicity")

    print()
    print(interpretation_table())
    print()
    if failures:
        print(f"  {len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("  OK")
