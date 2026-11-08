"""Policies return (action name, raise-to amount, diagnostics).

Only the adapter imports MIT's types. This is intentionally a weak teaching
baseline: uniform opponent ranges, no search, no deliberate bluffing.
"""
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from pokerbot.equity import estimate_equity, required_equity

POLICIES = ("equity", "check_call", "check_fold", "random", "king_chart")


with (Path(__file__).parent / "charts" / "button_open_2_5bb.csv").open(newline="") as chart:
    BUTTON_OPEN = {row["high_card"]: row for row in csv.DictReader(chart)}


@dataclass(frozen=True)
class Observation:
    hole: tuple
    board: tuple
    pot: int
    call_cost: int
    my_pip: int
    legal: frozenset
    raise_bounds: Optional[Tuple[int, int]] = None
    button_open: bool = False


def decide(obs, policy, rng, samples=200, *, explain=False):
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

    if policy == "king_chart" and obs.button_open:
        ranks = "23456789TJQKA"
        low, high = sorted(obs.hole, key=lambda card: ranks.index(card[0]))
        if high[0] in BUTTON_OPEN and low[0] != high[0]:
            suited = low[1] == high[1]
            column = "suited_min_kicker" if suited else "offsuit_min_kicker"
            cutoff = BUTTON_OPEN[high[0]][column]
            hand = high[0] + low[0] + ("s" if suited else "o")
            opens = ranks.index(low[0]) >= ranks.index(cutoff)
            detail = {"rule": "button_king_chart", "hand": hand}
            return ("raise", 5, detail) if opens else ("fold", None, detail)

    equity = estimate_equity(obs.hole, obs.board, samples, rng)
    threshold = required_equity(obs.pot, obs.call_cost)
    detail = {"equity": equity, "pot_odds": threshold, "samples": samples}
    value_threshold = 0.65
    if equity >= value_threshold and "raise" in obs.legal:
        low, high = obs.raise_bounds
        # MIT expects total contribution THIS STREET, not additional chips.
        target = obs.my_pip + obs.call_cost + max(2, (obs.pot + obs.call_cost) // 2)
        amount = min(high, max(low, target))
        if explain:
            detail["decision_rule"] = (
                f"Equity reached the {value_threshold:.0%} value threshold. "
                f"The half-pot sizing rule targeted {target} chips total and the legal size is {amount}."
            )
        return "raise", amount, detail
    if "check" in obs.legal:
        if explain:
            detail["decision_rule"] = "The value-bet rule did not trigger and checking costs no chips."
        return "check", None, detail
    call_threshold = threshold + 0.05
    action = "call" if equity >= call_threshold else "fold"
    if explain:
        comparison = "reached" if action == "call" else "fell below"
        detail["decision_rule"] = (
            f"Equity {comparison} the {call_threshold:.1%} call threshold "
            "(pot odds plus five percentage points)."
        )
    return action, None, detail
