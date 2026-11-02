# Pokerbot lab

A solo learning project: build an explainable poker bot, test it against MIT's
standard heads-up Texas Hold'em engine, and improve it through measured experiments.

## Start here

- [Learning plan](docs/learning-plan.md): poker, math, and Python taught together through exercises.
- [Language decision](docs/language.md): Python first; when C++ or Rust makes sense.
- [Architecture and roadmap](docs/roadmap.md): what exists and what to build next.
- [Experiment guide](docs/experiments.md): what to change, how to compare, and how to interpret results.

## Local setup

Use Python 3.11 for a new installation. The foundation also runs on the existing
macOS Python 3.9 installation; CI targets 3.11. A compiler may be needed to build
eval7 on platforms without a wheel (on macOS: Xcode Command Line Tools).

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-build.txt
python -m pip install --no-build-isolation -r requirements.txt
python scripts/bootstrap_engine.py
python -m pytest -q
python scripts/benchmark.py --hands 100 --seeds 11 22 33 --samples 100
```

The build prerequisites are installed first because eval7's source build imports
Cython. Dependencies go into the virtual environment, not system Python.
Setup needs internet; matches then run locally. The engine uses local TCP sockets,
so a restricted execution sandbox must allow them.

## What you get

- A Monte Carlo equity bot with pot-odds calling and simple value raises.
- Check/call, check/fold, and random/minimum-raise reference opponents.
- Paired matches with the same deals and reversed starting seats.
- JSON results, engine hand histories, and per-decision traces.
- Validation that rejects failed connections, illegal actions, timeouts, malformed
  responses, incomplete matches, and detected bot crashes.
- Unit tests and a GitHub Actions smoke match.

This is a deliberately simple learning baseline, not a competitive solver.
The equity bot assumes uniformly random opponent hands, ignores future betting
when comparing equity to pot odds, and has no deliberate bluffing or adaptation.
Its 65% raising threshold and 5 percentage point calling margin are arbitrary
starting parameters, not established optimal values.

## Your first experiment

```sh
python scripts/benchmark.py --hero check_call --opponents check_fold random --hands 100 --seeds 11 22 33
python scripts/benchmark.py --hero equity --opponents check_fold random --hands 100 --seeds 11 22 33
```

Read the printed `summary.json` paths. Open one match's `gamelog.txt` and the hero
seat's `decisions.jsonl`. Find a decision you understand, then one you disagree
with. Write a hypothesis before changing `pokerbot/strategy.py`.

`--hands` is per match: 100 hands × 3 seeds × 2 seat assignments × 3 opponents =
1,800 hands. This checks integration, not statistical proof of strength.
`--clock` is the per-bot budget in seconds for an entire match, not per action.
Outputs go into ignored `results/` folders; an explicit `--output` must be new.

## Files

| File | Purpose |
| --- | --- |
| `pokerbot/equity.py` | Equity sampling and pot odds |
| `pokerbot/strategy.py` | Observable state and policy decisions |
| `scripts/play_bot.py` | Adapter to MIT's socket protocol and decision logs |
| `scripts/engine_worker.py` | Run upstream engine with a seeded deck |
| `scripts/benchmark.py` | Paired matches, validation, and metrics |
| `scripts/bootstrap_engine.py` | Download and verify pinned MIT revision |

## Upstream engine

The [MIT Pokerbots base engine](https://github.com/mitpokerbots/engine) is fetched
into ignored `.engine/`, pinned to `569415deb85853ebd058d42ee2b6151e4bffc3fa`.
Upstream source is not copied into this repository. The engine's checkout is left
unchanged. Our worker injects a deterministic deck shuffle and training settings
at runtime; all game transitions and payouts remain MIT's implementation.

This setup uses two players, blinds 1/2, and 400-chip stacks (200 big blinds),
reset every hand. It is not an elimination tournament, an annual MIT variant,
or a reproduction of Sequoia's event rules. The bot receives only its own cards
and the public state during decisions. Engine logs contain both hands for offline
review; never feed them to a playing policy.

MIT learning resources: [2026 course](https://github.com/mitpokerbots/class-resources-2026),
[lecture slides](https://github.com/mitpokerbots/class-resources-2026/tree/main/Lectures),
[poker theory videos](https://ocw.mit.edu/courses/15-s50-poker-theory-and-analytics-january-iap-2015/resources/lecture-videos/).
