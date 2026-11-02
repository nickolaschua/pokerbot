"""Policies return (action name, raise-to amount, diagnostics).

Only the adapter imports MIT's types. This is intentionally a weak teaching
baseline: uniform opponent ranges, no search, no deliberate bluffing.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from pokerbot.equity import estimate_equity, required_equity

POLICIES = ("equity", "check_call", "check_fold", "random")


@dataclass(frozen=True)
class Observation:
    hole: tuple
    board: tuple
    pot: int
    call_cost: int
    my_pip: int
    legal: frozenset
    raise_bounds: Optional[Tuple[int, int]] = None


def decide(obs, policy, rng, samples=200):
    if policy not in POLICIES:
        raise ValueError("Unknown policy: " + policy)
    passive = "check" if "check" in obs.legal else "call"
    if policy == "check_call":
        return passive, None, {}
    if policy == "check_fold":
        return ("check" if "check" in obs.legal else "fold"), None, {}
    if policy == "random":
        # Stable ordering makes random seeds reproducible across processes.
        action = rng.choice(sorted(obs.legal))
        amount = obs.raise_bounds[0] if action == "raise" else None
        return action, amount, {}

    equity = estimate_equity(obs.hole, obs.board, samples, rng)
    threshold = required_equity(obs.pot, obs.call_cost)
    detail = {"equity": equity, "pot_odds": threshold, "samples": samples}
    if equity >= 0.65 and "raise" in obs.legal:
        low, high = obs.raise_bounds
        # MIT expects total contribution THIS STREET, not additional chips.
        target = obs.my_pip + obs.call_cost + max(2, (obs.pot + obs.call_cost) // 2)
        return "raise", min(high, max(low, target)), detail
    if "check" in obs.legal:
        return "check", None, detail
    if equity >= threshold + 0.05:
        return "call", None, detail
    return "fold", None, detail
