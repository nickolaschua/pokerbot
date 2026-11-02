# Learning plan: learn one idea, build it, explain the result

This is a suggested six-stage plan, not a deadline. Each stage can span several
sessions. Skip introductory exercises you can already explain confidently.
Keep your own notes and predictions before running code.

## 1. Read a hand and read a program

**Poker:** ranks, suits, hand rankings, hole/community cards, blinds, button,
preflop/flop/turn/river, check/call/fold/bet/raise, stack and pot.
In heads-up play the button posts the small blind and acts first preflop;
the big blind acts first postflop. MIT resets the stack every hand.

**Python:** run a script, activate a virtual environment, variables, functions,
lists, dictionaries, loops, imports, and reading a traceback.

**Exercise:** run check/call against check/fold. Choose one hand history and
account for every chip. Explain which actions were legal at every turn.
Read `Observation` and describe each field in ordinary language.

**Done when:** you can manually reproduce the final chip gain/loss for that hand
and locate the code returning an action. Chips already committed are sunk costs;
folding has zero *additional* cost, but the hand may still show a net loss.

## 2. Turn a betting decision into arithmetic

**Math:** probabilities, averages, expected value, combinations, conditional
probability, and ties. Equity is the expected fraction of the pot at showdown;
heads-up wins count as 1 and ties as 0.5.

**Poker:** pot odds, outs, draws, and why a profitable call can lose most often.
With pot P including the opponent's bet, and call cost C, terminal call EV is
`equity * (P + C) - C`. Break-even equity is `C / (P + C)`.
This simple calculation assumes no further betting, no rake, and equal eligibility
for the pot. Future betting changes the problem on earlier streets.

**Python:** pure functions, assertions, exceptions, tests, and floating-point values.

**Exercise:** compute thresholds for (P,C) = (100,20), (100,50), and (100,100).
Expected answers: 1/6, 1/3, 1/2. Explain why the denominator includes your call.
Predict whether a call with 25% equity is profitable in each case.

**Done when:** you can explain the pot-odds test and distinguish a good decision
from a lucky outcome. Read MIT lectures 2 and 3.

## 3. Estimate what you cannot see

**Math:** sampling without replacement, Monte Carlo estimation, sampling error,
and random seeds. More samples improve precision, not the correctness of the
assumed opponent distribution.

**Python:** objects, dataclasses, local random generators, and separating modules.

**Exercise:** read `estimate_equity`. Explain why known cards are excluded and
why two cards are sampled for the opponent before completing the board.
Compare 50, 200, and 1,000 samples across multiple seeds for the same hand.
Test an unbeatable royal flush and a royal flush shared by everyone on the board.

**Done when:** you can explain both the uncertainty in an estimate and its
uniform-random-opponent assumption. Never pass actual hidden opponent cards
from the engine to the policy.

## 4. Build a strategy and challenge its assumptions

**Poker:** ranges, position, value betting, bluffing, board texture, and effective
stack size. An opponent's action is evidence about possible hands.

**Python:** small policy functions, configuration, JSON logs, and Git commits.

**Exercise:** explain the current 65% raise threshold, 5-point call margin,
and half-pot sizing rule. These are heuristics, not solver output. Identify one
spot where random-hand equity is misleading after strong opponent action.
Propose one change and predict which opponents it should help against.

**Done when:** one experiment has a hypothesis, before/after results, and reviewed
hands. Read MIT lecture 5 on game theory; use OCW basic strategy and preflop
analysis as supporting material.

## 5. Learn to distrust a small winning sample

**Math:** variance, sample means, standard errors, paired comparisons, overfitting,
and multiple testing. Repeatedly choosing the best of many noisy trials creates bias.

**Python:** command-line arguments, subprocesses, result parsing, and profiling.

**Exercise:** run the same version twice with the same seeds. Scores and hand
histories should match if neither run hits a time limit; timings need not match.
Change seeds and explain why scores vary. Inspect results separately for each
opponent rather than hiding weaknesses inside one average.

**Done when:** you can explain why beating check/fold proves little, why paired
deals help, and why three seeds are not a strong statistical study. Follow the
[experiment guide](experiments.md).

## 6. Explore a solver on a small game

**Math:** mixed strategies, information sets, regret matching, self-play, and
approximate equilibrium. Study Kuhn poker before expanding to Hold'em.

**Implementation:** build a separate tiny-game trainer with reproducible updates;
validate against known small-game results. The average strategy matters in CFR.
Convergence guarantees depend on game structure and algorithm assumptions;
do not assume they transfer unchanged to multiplayer poker.

**Done when:** the small-game solver can be validated independently. Then explore
action abstractions, hand buckets, and search. Read MIT lecture 9 (CFR), then
8/12 for broader solver context and 10/11 for profiling. Lectures 4/6/7 introduce
ML/RL/neural nets; those are optional paths after the baseline.

## Sources

- [MIT 2026 syllabus](https://github.com/mitpokerbots/class-resources-2026/blob/main/syllabus.pdf)
- [MIT 2026 lectures](https://github.com/mitpokerbots/class-resources-2026/tree/main/Lectures)
- [MIT OCW Poker Theory and Analytics](https://ocw.mit.edu/courses/15-s50-poker-theory-and-analytics-january-iap-2015/resources/lecture-videos/)

The exercises and milestones above are this project's teaching plan, not MIT assignments.
