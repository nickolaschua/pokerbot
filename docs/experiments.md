# Improve a hypothesis, not a scoreboard

## Repeatable loop

1. Save a baseline commit and its complete run settings.
2. Review losses and ordinary hands, not just the most dramatic bad beat.
3. Write a mechanism: what is wrong, why, and against which opponents?
4. Change one component, keeping the compute budget comparable.
5. Run both versions against the same opponents, seeds, and seat pairings.
6. Review decision traces as well as aggregate scores.
7. Use held-out seeds/opponents to assess the chosen change; keep or revert.

Use development seeds 11/22/33 for initial debugging. Reserve separate seeds for
evaluation (for example 1001 onward), and do not repeatedly optimize against that
same held-out set. A future candidate comparison tool will automate versioned
policy evaluation. Today, keep separate clean commits and result directories.

## What to iterate on

| Suspected weakness | Candidate experiment | What to inspect |
| --- | --- | --- |
| Calls big bets too lightly | Replace uniform ranges with tighter action-conditioned ranges | Call decisions by street/bet size |
| Folds profitable draws | Revisit call margin and future betting assumptions | Equity estimates, costs, and future actions |
| Strong hands earn little | Compare value bet sizes | Which worse hands call; total chips gained |
| Easy to fold against | Add selected bluff candidates | Fold frequency and cost when called |
| Slow decisions | Profile and cache/optimize the hot function | Mean/max time, clock failures, unchanged behavior |
| Beats only one style | Broaden opponent suite | Results broken down by opponent |

## Read the metrics correctly

`bb_per_100 = net_chips / big_blind / hands * 100`. This engine's big blind is 2.
Counting pots won rewards the wrong behavior. Win rate measures chip outcomes,
not decision quality in an individual hand.

For each seed, the runner averages two seat-swapped match rates. It reports the
mean and standard error across these paired seed averages. Seeds, not individual
hands or the two dependent seat runs, are the statistical replicates here.
One seed has no estimated standard error; three gives a very unstable estimate.
There is no confidence interval or superiority test in this first runner.

Each round starts with a fresh full deck and consumes a fixed deal independently
of betting. The same seed therefore reproduces deals across policies. Starting
seats are swapped in the second match, and MIT also alternates positions each hand.
Bot policy RNGs are separate from the deal RNG. Runtime and clock pressure can
still break reproducibility, so invalid runs must never become accepted results.

Begin with small smoke runs to catch bugs. Use progressively larger independent
batches for strategy comparisons, and judge the uncertainty relative to the
improvement you care about. There is no universal sufficient hand count.
Choose evaluation sample sizes before checking outcomes to avoid stopping only
when a noisy result looks good.

Check/call, check/fold, and random/minimum-raise are plumbing and elementary
strategy references. Beating them does not establish strong play or low
exploitability. Add frozen prior versions, different deliberate strategies, and
eventually stronger independent opponents.

## Failure handling

The engine can silently substitute check/fold when a bot fails. This harness
rejects runs showing failed connections, malformed/illegal actions, clock expiry,
disconnects, Python tracebacks, missing decisions, or inconsistent payouts.
Inspect `engine.txt`, `A.txt`, `B.txt`, and `gamelog.txt` in the failed directory.
No complete `summary.json` is written for a failed suite. Do not compare it as a
valid strategic result. Increase `--clock` only as a documented experiment setting.

## Experiment note template

```text
Baseline commit:
Candidate commit:
Hypothesis and mechanism:
Single change:
Opponents / seeds / hands / samples / clock:
Expected affected situations:
Results by opponent and uncertainty:
Reviewed hand paths and observations:
Held-out assessment:
Decision: keep / revert / inconclusive
Next question:
```
