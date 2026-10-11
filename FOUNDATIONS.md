# FOUNDATIONS — AI evaluation, in plain English, for a software engineer

**Read this first. Not the PLAYBOOK. Not the JD-ANALYSIS. This.**

You have 11 years of software engineering and no exposure to evaluation. That is a
perfectly good starting position — it is the *target* profile for this contract — but you
cannot bluff your way through the calibration round, and you should not try.

This file teaches the whole discipline using only things you already know. No maths you
have not seen, no ML, no statistics beyond "a small sample is a weak sample".

---

## The one sentence

> **AI evaluation is code review, applied to an AI's work instead of a human's — with the
> difference that you have to prove your review is consistent and that two competent
> reviewers would agree.**

That is the whole job. Everything below is detail on that sentence.

---

## Why your background is the qualification, not a gap

Read what the job description actually asks for and translate each line into what it
means day to day:

| JD says | In plain English |
|---|---|
| "assess engineering judgment" | Was this a sensible decision, or did it just happen to work? |
| "analyse debugging approaches" | Did it find the actual cause, or patch the symptom? |
| "identify misleading, weak, incomplete or low-signal outputs" | Did it tell the truth about what it did? |
| "distinguish subtle differences in response quality" | Which of these two is better, and why |
| "provide structured, high-quality written feedback" | **Write the code review, in a fixed format** |
| "operated at Staff/Principal/Tech Lead level" | You have. That is the requirement. |
| "strong debugging instincts" | You have. |
| "can quickly recognise weak engineering reasoning" | You have. This is code review. |

There is no ML, no training, no models, no maths in what they are actually buying.
**They are buying a senior engineer's judgement, written down carefully and
consistently.**

---

## Is there anything like this in software engineering?

Yes. Six things, and you have probably done all of them. Here they are in order of how
close they are.

### 1. Code review — the closest analogy by far

You read someone's change. You decide: merge, request changes, or reject. You write a
comment explaining why, with evidence (a line number, a failing case). You care about
whether the *reasoning* was sound, not only whether the tests passed.

**That is 70% of the job.** The differences are only these:

- The author is an AI, so you cannot ask it a follow-up question — you get a transcript
  and nothing else.
- Instead of merge/reject you place it on a 0–4 scale across nine aspects.
- You write it so that **another reviewer reading your review would have reached the same
  score.** That last point is the new part.

### 2. QA and test engineering — especially mutation testing

You know that "the tests pass" is a claim about the tests, not about the code. You know a
test that can never fail is worthless. You know the scary case is the code path your
suite never exercises.

**Every one of those instincts is load-bearing here.** In evaluation:

- A "green" eval that never exercises the broken path is exactly a coverage gap.
- Validating that your evaluation setup actually *can* fail is exactly mutation testing.
- The AI's claim "all tests pass" is exactly a developer's claim "it works on my machine".

### 3. Incident postmortems

You read a timeline — what the engineer tried, in order — and judge the decisions, not
just the outcome. You know a wrong hypothesis tested and discarded is *good* work, and the
same hypothesis acted on without checking is bad work. You know the difference between
the fix and the root cause.

**This is exactly what "trajectory evaluation" means**, which we will define below. A
trajectory review *is* a postmortem.

### 4. Static analysis with severity levels

A linter emits errors and warnings. An error blocks the build; a warning does not. Some
rules are "critical, always fix"; most are "style, fix when convenient".

**A rubric is a linter for engineering judgement**, with the same structure: rules,
severities, and a few that block everything. That "blocks everything" rule is called a
**veto** here, and it is the single most important thing in the work sample.

### 5. Load testing and benchmarking

You know a load test with 5 requests tells you nothing. You know a benchmark that reports
one number with no variance is hiding something. You know a 2% improvement on a noisy
benchmark is not an improvement.

**That is the statistics half of this job.** Same instinct, different numbers.

### 6. Usability / accessibility heuristic evaluation

If you have ever done an accessibility audit: you applied a fixed list of heuristics, gave
each a severity, and wrote findings. Nielsen's heuristics are literally a rubric. And if
two auditors reviewed the same page, you would want to know whether they found the same
problems.

**That is this job, with a codebase instead of a page.**

### What is genuinely NEW — the 20% that SE does not prepare you for

Be clear about this, because it is where you must actually study:

1. **Agreement statistics.** Software engineering has no standard practice of measuring
   "do two reviewers agree, beyond what you'd expect by luck". Code review has no κ. You
   will learn one estimator (κ) properly and recognise three others.
2. **The thing being judged is reasoning, not code.** Code is right or wrong and a
   compiler adjudicates. Reasoning is arguable, so the criteria must be written down very
   carefully, and the disagreement is *the interesting data* rather than a problem to
   resolve and move on from.
3. **Validating the judge as a formal step.** In a code review you trust the reviewers. In
   evaluation, "an automated reviewer" (an LLM judge) is a device, and a device must be
   calibrated before you trust its readings — same as you would not trust a load-test
   harness you had never sanity-checked.
4. **Treating a judgement as a measurement with an error bar.** "This trajectory is a 3"
   becomes "this trajectory is a 3, and my scoring of items like it varies by ±0.4".

If you learn those four things, you are no longer bluffing. You are qualified.

---

## Part 2 — The thirteen ideas, in plain English

Each one in the same shape: the plain version, the comparison to something you know, why
it matters, and the sentence to say.

---

### 1. Task, environment, hidden tests

**Plain English.** The AI is given a job: fix this bug in this codebase. It gets some tests
it can run itself, and there are other tests it cannot see that decide whether it actually
succeeded.

**The comparison.** A work trial. The candidate gets a repo and the visible test suite; you
the reviewer have an acceptance test they never saw. **The reason you hide it is the same
reason you do not hand a candidate the marking scheme**: otherwise they optimise for the
marking scheme instead of the problem.

**Why it matters.** Without hidden tests, you are measuring "can it guess the tests"
instead of "can it engineer". This is the same reason a take-home with visible tests is
weaker evidence than a take-home with hidden ones.

**What you'd say.** *"The visible suite is what the agent optimises against, so it can't be
the measure. The hidden tests are the measure — and the agent never sees them."*

---

### 2. Outcome vs trajectory

**Plain English.** The **outcome** is the final diff — the code that came out. The
**trajectory** is the whole story: every command it ran, everything it read, everything it
tried, in order.

**The comparison.** A postmortem vs the merged PR. The PR shows what shipped. The postmortem
timeline shows whether the *engineering* was sound: did they reproduce it, did they find the
cause, did they verify, how many wrong turns.

**Why it matters.** This is THE idea the whole job rests on. An agent can get the right
answer by a bad route — hardcoding the test's expected value, getting lucky, reading a file
it should not have. If you only score the outcome, **you give that a perfect mark.** The
job says it directly:

> *"The focus is not simply 'is the code technically valid?' The focus is whether the model
> behaves like a strong engineer."*

**What you'd say.** *"Scoring the outcome rewards the agent that hardcodes the failing
assertion. In my own sample set, a rater who scores only the visible test result lands at
κ = 0.13 against the gold labels — they look reasonable and they are wrong in a specific,
dangerous direction."*

---

### 3. Rubric and behavioural anchors

**Plain English.** A rubric is the marking scheme. Instead of saying "score code quality
1–5", you write out, for each number, **the observable behaviour that earns it**.

**The comparison.** Acceptance criteria, but written as a ladder. Compare:

- ❌ *"3 = good debugging"* — meaningless. Two people will place the same work at 2 and 4.
- ✅ *"3 = reproduced the failure first, isolated the cause, fixed it, and confirmed the
  reproduction now passes"* — checkable. Two people read this and land in the same place.

**Why it matters.** A rubric that cannot be applied consistently produces numbers that look
like measurements and are actually opinions. Writing anchors *is* the hard part of the job,
and it is the same skill as writing testable acceptance criteria.

**What you'd say.** *"An anchor describes behaviour you can point at. 'Good debugging' is
not an anchor; 'reproduced the failure before editing' is. If two reviewers applying my
anchors disagree, the anchor is ambiguous and I fix the wording — not the reviewer."*

**The nine things my rubric scores** — read these as categories of code review comment:

| Aspect | Plain question |
|---|---|
| problem_framing | Did it understand what it was asked? |
| localization | Did it find the right file? |
| planning | Did it have a plan, and did it adapt? |
| debugging | Root cause, or symptom? |
| verification | Did it prove the change works? |
| engineering_judgment | Were the trade-offs sensible? (Heaviest weight) |
| tool_use | Did it read its own output? |
| communication | Did it tell the truth about what it did? |
| safety_autonomy | Did it respect boundaries, and ask when it should? |

---

### 4. The scale, the weights, and the composite

**Plain English.** Each aspect gets 0–4. Then you squash the nine numbers into one overall
score. The aspects are not equally important, so each has a **weight**.

**The comparison.** A build-health score. Test pass rate matters more than lint warnings, so
you weight it higher. The weighted average is the "overall health" number.

**Why it matters — and this is the important bit.** A weighted average has a specific
failure mode you must understand: **good marks can pay for a bad one.** Fix your tests,
and a security hole gets averaged away.

**What you'd say.** *"Weights sum to 1.0, judgment is heaviest at 0.18 because the JD says
process matters most. But it's not a plain average — see the veto."*

---

### 5. The veto (also called a blocking issue)

**Plain English.** A few failures are so serious that **nothing else counts.** If the agent
force-pushes to a shared branch and destroys other people's commits, it does not matter that
its tests passed.

**The comparison.** **A linter error vs a warning.** A warning lowers your score. An error
fails the build regardless of everything else. Also: a security vulnerability in a code
review — you do not say "yes but the naming is lovely, so approve".

**Why it matters.** This is the single best thing in your work sample and the best thing to
talk about in the interview, because it is a *judgement* rather than a technique, and most
candidates get it wrong by treating everything as a weighted average.

**What you'd say.** *"A weighted mean is the wrong tool for a one-way door. With safety at
weight 0.08, an otherwise-perfect trajectory scores 3.68 and passes — I know, because my own
harness printed that before I added the veto. So the veto is checked first, and for a vetoed
trajectory I don't print the composite at all, because '3.68' invites someone to read it as
borderline."*

---

### 6. Gold labels (also: ground truth, the answer key)

**Plain English.** For each item, what the correct scores are. Without them you can only
give opinions; with them you can measure whether you are scoring accurately.

**The comparison.** **The expected values in a test suite.** You cannot assert without them,
and you cannot score a rater without them.

**Why it matters.** Here is the subtle part, and it is why your project does something
clever: **if the answer key is just someone's opinion, then "agreement with the answer key"
is a measure of how much you agree with that person, not of how good you are.** So in the
sample set, the gold labels are *derived mechanically* from defects that were deliberately
planted in the trajectories. A trajectory with a force-push always scores 0 on safety — not
because someone decided it, but because it is a fact about the trajectory.

**What you'd say.** *"Gold isn't hand-typed. Each planted defect maps to a rubric anchor
through a one-line rule, and the test suite re-derives the labels and fails if they drift.
So a disagreement about ground truth is a one-line diff, not an argument."*

---

### 7. Annotator / rater

**Plain English.** A person doing the scoring. In software terms: **the reviewer.**
(You are one. That is the job title, more or less.)

---

### 8. Inter-rater reliability — the genuinely new thing

This deserves its own section. It follows below, in Part 3, because it is the idea that
takes longest to click and it is the one they will test.

---

### 9. Negative control

**Plain English.** Deliberately include something you *know* the answer to, so you can check
your measuring instrument is not broken before you trust any other reading.

**The comparison.** **Mutation testing.** You deliberately inject a bug and confirm your
tests catch it. If your tests pass on the injected bug, your tests are the problem — not the
code. Exactly the same reasoning, applied to a scoring setup instead of a test suite.

**Why it matters.** Your project's control is: *a rater who always says "3" must score
exactly 0.000 agreement.* If that rater scored 0.9, the harness would be broken and every
other number in the report would be worthless. And the honest detail: **the first version of
the control was broken** — it used a set where every item had the same answer, and a rater
who always gives that answer scores 100%. A control that cannot fail controls nothing.

**What you'd say.** *"A constant rater must score exactly zero. It does. And the first
version of that control was broken — the items all shared one answer, so a constant rater
aced it. That's why the set is mixed now."*

---

### 10. LLM-as-judge, and validating it

**Plain English.** Instead of paying humans to score thousands of items, you have an AI do
the scoring. Cheaper, faster, and **it must be checked before you believe it.**

**The comparison.** **An automated linter.** You would never adopt a linter because it
*looks* reasonable. You measure: does it catch what your reviewers catch? Does it produce
false positives? Is it consistent between runs? A judge is a linter that rates engineering
quality, and it needs exactly the same scrutiny.

**Why it matters, and this is your best story.** The obvious thing to measure is "how often
does the judge agree with the humans". That number can look great while the judge is
useless, because of a failure mode you already understand from test suites:

> A test suite with 90% coverage that does not cover the one function that matters is worse
> than useless — it creates confidence.

Your judge had **0.90 adjacent agreement** (it looked fine) and **0.00 sensitivity to the one
trajectory that must hard-fail.** It could not fail the agent that force-pushed to main. The
reason was concrete: the judge had a rule "never score below 2", so it *structurally could
not* express the veto. Removing that floor took sensitivity 0.00 → 1.00 and agreement went
*up*.

**What you'd say.** *"Average agreement is the number everyone reports and it is the one that
hides the problem. The number that matters is sensitivity to the cases that must fail. Mine
was zero."*

---

### 11. Bias vs noise

**Plain English.** Two different reasons a rater is wrong.

- **Noise** — random wobble. Scores a 3 as a 4 today and a 2 tomorrow. Unpredictable.
- **Bias** — a consistent lean. Always a bit generous, or always a bit harsh. Predictable.

**The comparison.** A mis-calibrated instrument vs a shaky hand. **A scale that reads 1kg
heavy every time is biased** (you can correct for it, and it is a different problem from a
scale that wobbles ±0.5kg). And there is a name for it in your world: a **systematically
failing flaky test** versus a **test that fails randomly**.

**Why it matters.** They need different fixes: bias is retraining or re-anchoring; noise is
a clearer rubric. And they produce different numbers — you measure noise with agreement, and
bias with the *average signed error* (is the rater consistently above or below the key?).

**What you'd say.** *"Low agreement with no bias means the anchor is ambiguous — fix the
wording. Low agreement with a consistent lean means the rater is mis-calibrated — retrain
them. Same symptom, different fix, and my report separates them."*

---

### 12. Confidence intervals and sample size

**Plain English.** A number from 20 items is not a number. It is a number plus "how much it
might have wobbled if I had picked 20 different items".

**The comparison.** **A benchmark with n=5.** Or a load test with 5 requests. You already
distrust it. Same instinct, applied to a score.

**Why it matters.** This is how you avoid saying something confidently wrong. With 20
trajectories, a 3-point difference between two models is noise — and a small sample produces
an interval so wide that the honest conclusion is "not distinguishable yet".

**Concrete numbers from your own project:** ±5% on an 80% score needs **246 items**. To
detect a 5-point difference between two models on the same items needs **626 pairs**.

**What you'd say.** *"I report the interval before the point estimate, and I'd rather say
'not distinguishable yet' than ship a decision on noise. A 2-point improvement isn't a
result at any sample size I could realistically label."*

---

### 13. Calibration (two meanings — do not confuse them)

**Plain English, meaning one.** Aligning a person to the team's standard. The process: you
both score the same 20 items, compare, argue about the differences, agree on how the
anchors apply. **This is called a calibration round.**

**The comparison.** What you do with a new reviewer: pair them with a senior reviewer on
their first few PRs, compare notes, align.

**Plain English, meaning two.** A number is "calibrated" if you chose its value by measuring,
not by guessing. *"A calibrated threshold of 0.45"* means 0.45 was derived from data, not
picked because it looked nice.

**Why it matters.** The first meaning is *literally the interview*. The JD says the
evaluation "is intentionally designed to mirror the actual work". Your calibration round
**is** a calibration exercise: they will give you tasks and compare your judgement to theirs
and to other raters. **Consistency and evidence are what they score, not being right.**

---

### 14. Failure taxonomy (and "abstention")

**Plain English — taxonomy.** Instead of "it failed", you sort failures into named
categories, because **different categories have different fixes.**

**The comparison.** Error codes, or bug categories in a defect tracker. "The build is broken"
is not actionable; "dependency resolution failed" is. Your track 12 failure taxonomy makes
exactly that point: a loop means the *error messages* were unhelpful; a tool error means the
*tool* is broken; neither is fixed by touching the model.

**Plain English — abstention.** Saying "I don't know" instead of guessing. When the
retrieved content does not support an answer, the system returns nothing rather than
inventing something.

**The comparison.** **Returning `null` instead of a plausible wrong value.** You know this
one in your bones: a function that returns garbage is worse than one that throws, because
garbage propagates.

**What you'd say.** *"For high-stakes content, a confident wrong answer is worse than an
honest miss, because you stop looking. So the retrieval returns 'cannot answer' as a
first-class result rather than a failure."*

---

## Part 3 — Agreement, taught properly

This is the one thing with no real equivalent in software engineering, so it gets its own
section. Read it twice. It is the idea they will test, and it is the idea that makes you
sound like you belong in this field.

### 3.1 The problem

Two senior engineers review the same PR. One approves it, one requests changes. Both are
competent. Both can justify their view.

In normal engineering, you resolve that by escalation and move on. **In evaluation, that
disagreement is the most important thing you can measure**, because:

- If two competent reviewers disagree, you cannot trust a number produced by one reviewer.
- If the disagreement is caused by vague criteria, you can fix the criteria.
- If it is caused by a biased reviewer, you can fix the reviewer.
- If you cannot tell which, you have no idea whether your data means anything.

**So the job includes measuring how much your reviewers agree.** That is what
"inter-rater reliability" means: *reliability between raters* — the raters are you and your
colleagues.

### 3.2 Why "we agreed 80% of the time" is not good enough

Here is the concrete example, using real numbers from your own project. Take 20 items. Two
raters decide "would a staff engineer approve this change?"

**Setup:** Rater A approves everything — all 20. Rater B approves 15 and rejects 5.

They agreed on 15 of 20 items. **That is 75% agreement. That sounds decent.**

It is worthless. **Rater A has told you nothing.** Rater A's answer was "yes" for every
single item, so it contains zero information about which items are good. You could have got
that 75% agreement by throwing a dart at the base rate, without reading anything.

**An agreement percentage rewards raters who say the same thing a lot.** Saying "approve"
20 times is the highest-agreement strategy that exists, and it is the lowest-information
strategy that exists.

**The comparison you already know:** a test suite that passes everything. "All tests pass"
is technically true and therefore worthless. You need to know whether the tests *could* have
failed. This is the same failure of a metric.

### 3.3 What κ (kappa) does about it — one idea, no maths

**κ corrects for the agreement you would get by luck.**

It asks one question:

> **How much better did you agree than you would have by accident, given how often each of
> you said each thing?**

Then it puts that on a scale where:

| κ | Meaning |
|---|---|
| **1.0** | Perfect agreement |
| **0.8** | Strong agreement (this is the target for important dimensions) |
| **0.6** | Moderate — usable, needs attention |
| **0.0** | **No better than luck.** The raters carry no shared information |
| **negative** | Worse than luck — they systematically contradict each other |

So in the example above: 75% raw agreement, but **κ = 0.0**, because A's answers were
useless. And that is exactly what your project reports for the "constant" rater:

```
constant rater:  adjacent agreement 0.889   κ = 0.000
```

**89% agreement and zero information.** That single line is the best thing you can say in
this interview, because it shows you understand why the chance-corrected number exists.

**The comparison:** you already do this reasoning with flaky tests. "The suite passed" is
not evidence; "the suite passed *and it fails when I break the code*" is evidence. κ is the
"and it fails when I break the code" of agreement.

### 3.4 The other four numbers, and when each applies

You do not need the maths. You need to know **which one to reach for and why.**

| Name | Plain English | Reach for it when |
|---|---|---|
| **Raw agreement** | "We agreed 80% of the time" | Never alone. It is meaningless without the correction. Use it only next to κ, because it is the number a non-technical person understands. |
| **κ (kappa)** | Agreement, corrected for luck. For yes/no decisions. | Two raters, yes/no answer. ⚠️ Treats "3 vs 4" as identical to "4 vs 0" — so it is the *wrong* tool for a 0–4 scale. |
| **Weighted κ** | Same, but for a 0–4 scale: a near miss counts as a partial agreement. | **This is the right default for a 0–4 rubric.** "3 vs 4" is a small disagreement; "4 vs 0" is a big one. |
| **Krippendorff's α (alpha)** | Same idea as κ, but works with **more than two raters** and tolerates **missing entries**. | Three or more raters, or people who did not all do all the items. This is what a real annotation team uses. |
| **ICC** | A different question: *"if I picked one rater at random, how close is their number to the truth?"* | You want to know whether **a single rater can be trusted**, not whether two raters agree. |
| **Bias (mean signed error)** | The average lean: is the rater consistently above or below? | To tell "ambiguous criteria" apart from "generous reviewer". |

⚠️ **One trap to avoid.** κ and α are *not* comparable across different sets of items. A κ
of 0.7 on one dataset and 0.7 on another are not the same claim, because the chance
correction depends on how common each answer was. So always say what set the number is on.

### 3.5 The honest part: your numbers and their limits

Your project reports, for a competent rater against the gold labels:

- **weighted κ = 0.89** with an interval of 0.84–0.94
- and a weakest dimension at **0.71** — `planning`

Two things to say about that, both of which make you sound senior:

1. **Why the interval matters.** 20 items is a small sample. The interval says "if I'd
   labelled 20 different items, the number would have been somewhere in here". A κ with no
   interval is a claim you cannot defend.
2. **What the weak dimension means.** `planning` at 0.71 with **no bias** means the
   *wording* is ambiguous — specifically the line between "followed a rigid plan" and
   "revised the plan when evidence arrived". **The fix is to rewrite the anchor, not to
   retrain the rater.** Getting that diagnosis right is exactly the skill being hired.

### 3.6 The five sentences to memorise

1. *"κ corrects for the agreement you'd get by luck. Raw agreement is meaningless alone —
   my constant rater agreed 89% of the time and carried zero information (κ = 0.000)."*
2. *"For a 0–4 scale I use weighted κ or Krippendorff's α, not plain κ, because plain κ
   treats a 3-vs-4 as the same disagreement as a 4-vs-0."*
3. *"Low agreement with no bias means an ambiguous anchor — fix the wording. Low agreement
   with a consistent lean means a mis-calibrated rater — fix the rater."*
4. *"Inter-rater reliability is not a nice-to-have. If two competent reviewers disagree, a
   single reviewer's number is not a measurement."*
5. *"I report the interval with the number, because 20 items is small and the width of the
   interval is a finding in itself."*

---

## Part 4 — The words they will use

Learn to recognise these. You do not need to use all of them; you need to not be lost when
they do. **The middle column is what it really means.**

| They say | What it means | Your engineer's version |
|---|---|---|
| **Eval / evaluation** | A test suite for AI behaviour | A test suite |
| **Benchmark** | A standardised eval so everyone measures the same thing | A published test suite |
| **Harness** | The code that runs the eval | The test runner |
| **Rubric** | The marking scheme | The acceptance criteria |
| **Anchor** | The description of what earns a specific score | A concrete example in the acceptance criteria |
| **Gold / ground truth** | The correct answers | Expected values |
| **Annotator / rater / judge** | A person scoring items | The reviewer |
| **Trajectory** | The full record of what the agent did | A postmortem timeline |
| **Outcome** | The final code / answer | The merged diff |
| **Rollout** | One attempt at a task by the model | One test run |
| **Scaffold / agent** | The program driving the model | The runner |
| **Task suite** | A set of tasks being evaluated | The test cases |
| **Held-out set** | Items never used for development | The test set (vs training set) |
| **Contamination** | The model has already seen the eval items | Overfitting to the test set |
| **Rubric / guideline** | The long document defining the rules | The style guide + spec |
| **Inter-rater reliability (IRR)** | Do two raters agree, beyond luck | — (no equivalent) |
| **κ / alpha / ICC** | Three ways to measure that | — (no equivalent) |
| **Calibration** | Aligning raters to the standard; also: a measured threshold | Onboarding a new reviewer |
| **Drift** | A rater's standard changing over time | Inconsistent review standards |
| **Bias** | A consistent lean (generous/harsh) | A systematically wrong test |
| **Noise** | Random wobble in scores | A flaky test |
| **LLM-as-judge** | An AI doing the scoring | An automated linter |
| **Judge validation** | Checking the AI judge against humans | Validating the linter |
| **Negative control** | An item you know the answer to, to catch a broken harness | Mutation testing |
| **Abstention** | Saying "cannot answer" instead of guessing | Returning `null`, not garbage |
| **Failure taxonomy** | Named categories of failure | Error codes / bug categories |
| **Severity** | How bad a finding is | Lint error vs warning |
| **Veto / critical failure** | A failure that overrides everything | A failing build |
| **Adjudication** | Resolving a disagreement between raters | Escalation |
| **Per-category breakdown** | Scores split by sub-group | Per-directory coverage |
| **Confidence interval** | How much the number might have wobbled | Error bars on a benchmark |
| **Sample size / power** | How many items you need to detect a difference | Enough load-test requests |
| **Paired comparison** | Comparing two models on the *same* items | Same input, two builds |
| **Regression** | Old capability got worse | A regression |
| **Structured output** | Making the model return valid JSON to a schema | A typed API response |
| **Tool calling** | The model invoking functions | An RPC / plugin call |
| **Grounding** | Answers must come from provided sources | No invented data |
| **Faithfulness** | Every claim in the answer is supported by the sources | No unsupported assertions |
| **RAG** | Look things up, then answer using what you found | A cache lookup before compute |
| **Vector search** | Finding things by meaning rather than exact text | Fuzzy match, but on meaning |
| **Hallucination** | Confidently stating something untrue | — |
| **Drift (model)** | Model behaviour changing between versions | Behaviour change across releases |
| **Red-teaming** | Deliberately attacking the system to find failures | Adversarial/fuzz testing |
| **Online vs offline eval** | Live traffic vs a fixed test set | Production monitoring vs CI |

### The four names that are not in the list above, and matter

These are the standard *tools* in this field. You have **not** used them. Do not claim them
— but know what they are, so you can answer the one question that will come.

| Tool | What it does | Closest thing you have used |
|---|---|---|
| **LangSmith** | Tracing, datasets, experiments, human annotation queues | A tracing/APM tool plus a test-case database |
| **DeepEval** | Pytest-style AI tests and metrics | Pytest with AI-specific assertions |
| **Promptfoo** | Comparing prompts/models, and red-teaming | A config-driven benchmark harness |
| **Inspect AI** | The UK AI Safety Institute's eval framework | A test runner for AI tasks — **and it does not do inter-rater reliability at all** |

**The sentence to have ready:**

> "I know the stack — LangSmith for traces and annotation queues, DeepEval for pytest-style
> metrics, Promptfoo for sweeps and red-teaming. I built this layer by hand for two reasons:
> the reliability maths isn't in any of them, including Inspect AI, and when you're asked
> 'how is the ordinal metric defined', a library call isn't an answer. I'd happily port the
> same eval into DeepEval and show you the three things it won't tell you."

---

## Part 5 — What to do when you don't know something

You will be asked things you cannot answer. How you handle it is scored, because the whole
role is about the trustworthiness of reports.

**The three-part answer. Use it every time:**

1. **Name it as a gap, plainly.** *"I haven't built adaptive learning systems."*
2. **Say what you *do* have that is adjacent.** *"I have built ranking and calibrated
   thresholds, which is the layer underneath."*
3. **Name what you would need to learn.** *"Item response theory and spaced-repetition
   scheduling."*

**Why this beats bluffing, in a measurable way:** the whole job is deciding whether a report
can be trusted. A candidate who admits a gap is *demonstrating the skill under test*. A
candidate who bluffs is demonstrating the failure the job exists to catch. **In this
interview, "I don't know" is a correct answer when followed by the two other parts.**

**And the one sentence that buys you time without looking lost:**

> "Let me make sure I understand what you mean by X — I want to answer the question you're
> actually asking."

---

## Part 6 — Your study plan

**Do not read the PLAYBOOK or the JD-ANALYSIS yet.** They assume this file. Order:

### Hour 0–2: read this file twice

Once to see the shape, once slowly with a pen. Write down the five sentences in §3.6 by
hand. That is not busywork — you need them to come out of your mouth without assembling
them.

### Hour 2–4: read three real critiques

Open `out/REPORT.md` and read §7 (the worked critique). Then open
`data/trajectories.jsonl`, pick three trajectories, and read them. **Read the trajectory and
decide what you think before you look at the gold scores.** You will be wrong sometimes.
That is the exercise.

### Hour 4–6: write two critiques yourself

Use the format in `RUBRIC.md`: **Issue → Evidence → Impact → Fix**, with the anchor quoted
for each score. Rules: cite a step number, quote a line, and end with what you could not
determine. Do not read the gold scores until you have finished both.

### Hour 6–8: run the tool and read the report out loud

```bash
./run.sh g2i        # regenerates the whole report
./run.sh g2i-test   # 34 invariants + 152 tests
```

Then read the numbers out loud until you can say them without reading:
κ 0.89 · constant rater κ 0.000 with 89% agreement · judge 0.90 agreement and 0.00 veto
sensitivity · 246 items for ±5%.

### Hour 8–10: the drill bank

`PLAYBOOK.md` §10 has 60 questions. Do not answer them — **read them and check you
recognise every term.** Then read PLAYBOOK §6 (the calibration protocol) properly, because
that is the part that decides the contract.

### Then, before the interview: three of five

The `POSITIONING.md` Tier 1 items are the ones that change how you are seen. The one that
matters most is getting **one real second reviewer** to score 20 items independently. That
converts "I built a harness" into "I ran an annotation process", which is the job itself.

---

## The whole file in five lines

1. **The job is code review of an AI's work**, written down in a fixed format.
2. **Score the process, not just the outcome** — a correct answer from bad work is not a
   success.
3. **Write anchors as observable behaviour**, because vague criteria produce numbers that
   look like measurements and are opinions.
4. **Prove your review is reliable** — κ corrects for luck, and your constant rater proves
   why that correction exists.
5. **Say what you could not determine.** In a role about trustworthiness, admitting the
   limit is the qualification.

---

## Part 7 — "Can't AI just do the evaluation itself?"

⚠️ **This is the question you will be asked**, in some form, by someone who wants to know
whether your role is necessary. It is also the most interesting question in the field. It
has a real answer, and the answer is measured in your own project rather than asserted.

### 7.1 The short answer

**AI can do most of the volume, and it cannot do the part that matters most — and those
are different items, not the same items done worse.**

The honest formulation: **automation moves the human up one level. It does not remove the
need for human judgement; it changes what the human spends their time on.**

You already know this shape from engineering:

| You automated... | and the human's job became... |
|---|---|
| The compiler checks syntax | Reviewing design |
| Unit tests catch regressions | Deciding what "correct" means |
| Static analysis flags smells | Judging whether the architecture holds |
| CI blocks the bad build | Deciding what to build |

**You cannot unit-test a specification.** That sentence is the whole answer. Automation
verifies an implementation *against* a spec. Something has to write the spec. In
evaluation, **the rubric is the spec** — and no judge can write it, because the judge would
be defining "good" as "what I tend to produce".

### 7.2 What a real model judge did in this project

Not theory. This project ran a real model as the judge (`src/llm_judge_run.py`) against the
same 20 trajectories, and here is what happened:

| Judge | agreement with gold (weighted κ) | bias | **veto sensitivity** |
|---|---|---|---|
| A rater who only checks the visible test result | 0.13 | ~0 | 0.00 |
| **A real model (DeepSeek), full rubric, anchors, JSON output** | **0.15** | **−1.13 (harsh)** | **1.00** |
| The rule-based proxy with a leniency floor | 0.20 | +0.19 (lenient) | **0.00** |
| The rule-based proxy without the floor | 0.27 | +0.11 | 1.00 |

**Three things to notice, and they are all usable in the interview.**

**First: the real model judge scored no better than a rater who ignored the process
entirely.** κ 0.15 versus 0.13. That is a striking result: a competent model, given the
full rubric and the full anchors, agreed with the gold labels essentially as well as a
rater who only looked at whether the visible tests passed.

Be careful with this claim. The honest caveats:
- **n = 20**, so the interval is wide (0.08–0.21).
- The model is a **cheap, fast** one, not a frontier model. A frontier model would likely
  do better.
- **The gold labels are mechanically derived from planted defects.** So they are
  *cleaner* than reality, which means a judge doing genuine nuance can disagree for
  reasons the derivation cannot represent. The κ is a lower bound on *usefulness*, not an
  estimate of *capability*.

**Second: the direction of the bias was a surprise, and it is the useful kind.** The
prevailing assumption in the field is that model judges are **lenient** — they say nice
things. This one was **harsh by 1.13 points on a 0–5 scale**. If you had assumed leniency
and set a threshold accordingly, every number you produced would have been wrong in a
specific direction. **The lesson is not "judges are harsh" — it is "the direction of the
error is not knowable without measuring it, and you cannot assume it".**

**Third, and this is the important one: agreement and tail-sensitivity came apart, and
they came apart in opposite directions.**

- The **lenient** judge: better average agreement (0.20), **completely blind** to the
  must-fail case (0.00).
- The **real model** judge: worse average agreement (0.15), **perfect** on the must-fail
  case (1.00).

**There is no single "best" judge in that table.** They fail differently. A team that
reported only the average would ship the lenient one — the one that cannot say
"unacceptable". **This is the single strongest argument for why this job exists**, and you
now have measured evidence for it rather than an opinion.

### 7.3 What AI genuinely does well — say all of this, it is true

Do not be the candidate who is defensive about automation. Automation is how the field
scales, and you should be able to describe its strengths precisely:

1. **Volume.** Ten thousand items at negligible cost. Humans cannot.
2. **Mechanical consistency.** Same prompt, temperature 0, same answer. A human's standard
   drifts across an afternoon; a judge's does not.
3. **Applying a written rubric literally.** Models are genuinely good at following explicit
   criteria. Given a precise anchor, they apply it more uniformly than a tired human.
4. **Pre-labelling.** A judge's first pass turns 3 hours of human annotation into 40
   minutes of human *review*. This is the biggest practical win and the least discussed.
5. **Triage.** Route the clearly-fine and clearly-broken to automation; escalate the
   ambiguous middle to humans. **The middle is where the disagreement is.**
6. **Pairwise comparison.** "Which of these two is better" is more reliable than "score
   this 0–4", largely because it sidesteps the judge's private idea of what a 3 means.
7. **Finding what you told it to find.** It is very good at *checking*. It is much weaker
   at *noticing*.

### 7.4 What AI cannot do — seven things, each with the reason

**1. It cannot define the standard.** ← *the deepest one*
A judge applies a rubric. It cannot write one, because writing it means deciding what
counts as good — and a model's answer to that is "what looks good to me", which is
circular. **Every anchor in your rubric was a human decision. That is the irreducible
human contribution, and it is what the JD means by "help define what great looks like".**

**2. It shares the blind spots of the thing it is judging.**
If the judge and the agent come from the same model family, they were trained on similar
data and make similar mistakes. The judge will systematically fail to notice the failures
its own family produces. **This is correlated error** — the same reason you do not let the
author's own test suite be the only gate on their change. A human from a different
background does not share that blind spot.

**3. It is worst exactly where the stakes are highest.**
Scores cluster in the middle. The interesting cases — the brilliant trajectory and the
catastrophic one — are the tails, and the tails are where a judge compresses hardest. Your
own lenient judge scored 0.00 on the single most important item in the set.

**4. Its rationale can be invented.**
A judge's explanation is generated text. It can be plausible, confident, and not grounded
in the transcript. So **you cannot audit a judge's reasoning the way you audit a
colleague's** — you can only check its outputs against a key. When a colleague says "I
scored this 2 because it edited before reproducing", you can go and look. When a judge says
it, the sentence may be decoration on a number it produced for other reasons.

**5. It cannot detect genuinely novel failure modes.**
A judge recognises what is in its training distribution. **The failure classes a lab cares
most about are, by definition, the new ones.** A concrete example from your own work: an
index that reported 859,569 rows while returning zero results. No judge trained on normal
code flags that, because the check *looked* like a check. **Someone has to notice the
category is missing — and noticing is not a scoring task.**

**6. It cannot be accountable.**
"The model scored it 0.6" is not an answer you can give a regulator, a customer, or an
engineer whose work was rejected. A frontier lab ships a safety decision with a **named
person** behind it. Accountability requires someone who can be asked "why", and can be
wrong.

**7. It cannot tell you when the eval itself is broken.**
This is the one that surprises people. Your project's best findings are all of this kind:
the negative control that did not control anything; the learning curve that returned an
interval of exactly zero; the judge whose agreement looked fine and whose sensitivity was
zero. **Each was a defect in the measurement, found by a human looking at the measurement
rather than at the thing being measured.** A judge cannot audit its own instrument.

### 7.5 The one-line version, and the analogy to end on

> **A model judge can tell you how well the work matches your definition of good. It
> cannot tell you whether your definition is right, it is blindest on the cases that matter
> most, and it cannot be held responsible. Those three things are the job.**

And the analogy that lands it cleanly, if you need one in the room:

> "It's the difference between a linter and a design review. Static analysis catches the
> mechanical 80% and I'd use it for that. But the reason you still have a senior engineer
> reading the diff is that a linter can only check rules someone already wrote down — and
> the interesting question is always whether the rules are right.
>
> The same split shows up in my own numbers. My automated judge was 90% agreeable and it
> could not fail the one trajectory that force-pushed to main. Average agreement would have
> shipped it. The tail said no."

### 7.6 So why does this *contract* need a human?

The economics, plainly. The JD says quality matters more than speed and budgets about
**5 hours per task**. Five hours is not a rate a human uses to grind through a thousand
items — it is a rate for **expert judgement on hard trajectories**, which is precisely the
work that is hardest to automate and most consequential if you get wrong.

So the job is not "rate items faster than a model". It is:

1. **Write the standard** — the anchors, the veto rules, the failure taxonomy.
2. **Audit the machine that rates** — measure agreement, bias, and the tail.
3. **Handle the tail** — the hard trajectories, the disagreements, the novel failures.
4. **Be accountable** — a named person who can defend a decision.
5. **Notice when the eval is wrong.**

**Every one of those five is a human job, and the first, second and fifth cannot be
delegated to the thing being measured.**
