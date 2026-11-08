"""Compare a committed move with the owner's chart and equity policy."""
from copy import deepcopy
import hashlib
import json
import random

from pokerbot.strategy import BUTTON_OPEN, Observation, decide


def chart_version(chart):
    return hashlib.sha256(json.dumps(chart, sort_keys=True).encode()).hexdigest()[:12]


CHART_VERSION = chart_version(BUTTON_OPEN)
SIZE_THRESHOLD = 2  # One big blind in the pinned game.


def recommend(decision, chart=None):
    chart = BUTTON_OPEN if chart is None else chart
    bounds = decision["bounds"]
    obs = Observation(
        hole=tuple(decision["hole"]), board=tuple(decision["board"]), pot=decision["pot"],
        call_cost=decision["call_cost"], my_pip=decision["my_pip"],
        legal=frozenset(decision["legal"]), raise_bounds=tuple(bounds) if bounds else None,
        button_open=(decision["position"] == "button" and decision["street"] == 0
                     and (decision["my_pip"], decision["opponent_pip"]) == (1, 2)),
    )
    # A public decision can be sampled again without the referee's deck seed.
    rng = random.Random(json.dumps(decision, sort_keys=True))
    action, amount, detail = decide(obs, "king_chart", rng, explain=True, button_chart=chart)
    if detail.get("rule") == "button_king_chart":
        hand = detail["hand"]
        column = "suited_min_kicker" if hand.endswith("s") else "offsuit_min_kicker"
        detail["min_kicker"] = chart[hand[0]][column]
    else:
        detail["opponent_range"] = "uniform"
    command = f"raise {amount}" if action == "raise" else action
    return {"command": command, "diagnostics": detail, "chart_version": chart_version(chart)}


def compare(decision, receipt):
    recommendation = recommend(decision)
    parts = recommendation["command"].split()
    action = parts[0]
    words = receipt["command"].split()
    disagrees = (words[0] != action or
                 (action == "raise" and abs(int(words[1]) - int(parts[1])) >= SIZE_THRESHOLD))
    return {"decision": deepcopy(decision), "receipt": receipt.copy(),
            "recommendation": recommendation,
            "disagrees": disagrees}
