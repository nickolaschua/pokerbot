# Architecture and milestones

## Foundation implemented

The unchanged MIT engine runs in a separate process and communicates with two
bot subprocesses through its socket protocol. Our adapter translates MIT state
into an `Observation`; the strategy returns an action; the adapter translates it
back. Strategies do not receive hidden cards, engine seeds, or engine logs.
The benchmark controller alone knows the deal seed.

Each run has a new results directory containing:

- `manifest.json`: settings, source revision/dirty status, evaluator/Python version.
- `opponent/seed-N-seat-S/gamelog.txt`: full engine history for offline review.
- `A/decisions.jsonl` and `B/decisions.jsonl`: observed cards, decisions, and timing.
- `A.txt`, `B.txt`, `engine.txt`: subprocess diagnostic output.
- `summary.json`: written only after the entire benchmark succeeds.

Engine constants stay synchronized with the upstream Python skeleton: 400-chip
stacks and blinds 1/2. Only the number of hands and clock budget are configurable.
The bot does not use the skeleton's fixed NUM_ROUNDS constant. If we change game
rules later, both engine and client assumptions must be checked together.

## Next milestones

| Milestone | Deliverable | Acceptance criterion |
| --- | --- | --- |
| 1. Explain the baseline | Annotated review of ten hands | Account for chips; explain every returned action |
| 2. Freeze experiment versions | Versioned policies/configs and comparison tool | Candidate and baseline run on identical held-out deals without manual code swapping |
| 3. Starting-hand policy | Position-aware preflop tables/rules | Legal actions at different stack sizes; measurable held-out comparison |
| 4. Ranges | Weighted opponent combinations updated by observed actions | Card removal and normalization tested; no hidden-information access |
| 5. Betting | Small menu of sizes and deliberate bluff candidates | Improvements assessed by opponent and street, with adequate independent seeds |
| 6. Adaptation | Smoothed opponent statistics | No overreaction to a few hands; tested against changing styles |
| 7. Small-game solver | Kuhn CFR experiment | Known equilibrium/exploitability checks before scaling |
| 8. Larger training | Abstracted Hold'em/self-play experiments | Defined compute budget, baseline comparison, checkpoints, reproducible evaluation |

Avoid implementing all strategic layers simultaneously. Each must earn its
complexity in measurements and become understandable before adding another.

## Scaling

Start with more diverse opponents and independent seed batches. Next profile
equity sampling, strategy work, and process overhead separately. Parallelize
independent matches only with isolated output folders and CPU budgets; excess
concurrency can cause clock failures and confound timing comparisons.

Precompute stable quantities and cache repeatable work where correctness permits.
Use the language decision's criteria before porting hot code. Full Hold'em CFR
requires abstractions and careful validation, not just a larger loop count.
Self-play alone can produce policies that only beat their training opponents;
preserve external opponents and held-out evaluations.

## Not yet implemented

GUI/human-play interface, persistent opponent learning, weighted ranges, full
action-history features in `Observation`, paired candidate-minus-baseline
confidence intervals, native kernels, and solver training. MIT's state carries
history, but the current adapter intentionally exposes only the current snapshot.

The current runner is a local development harness, not a secure sandbox for
untrusted submitted bots or a public tournament server.
