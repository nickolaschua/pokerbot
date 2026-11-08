"""Review the incremental chip value of a call from the player's public cards."""
from http.client import HTTPException
from itertools import combinations
import json
import os
import random
from urllib.error import URLError
from urllib.request import Request, urlopen

import eval7

from pokerbot.equity import estimate_equity, required_equity


RIVER_EXERCISE = {"hole": ["Kc", "5s"], "board": ["5h", "Jh", "5d", "Qh", "3h"],
                  "pot": 480, "call_cost": 160, "street": 5}


def river_equity(hole, board, strongest):
    known = [eval7.Card(card) for card in [*hole, *board]]
    hero = eval7.evaluate(known)
    remaining = [card for card in eval7.Deck() if card not in known]
    wins = ties = total = 0
    for holding in combinations(remaining, 2):
        other = eval7.evaluate([*holding, *known[2:]])
        wins += hero > other
        ties += hero == other
        total += 1
    # The strongest of independent draws loses/ties only if each draw does.
    draws = 3 if strongest else 1
    win = (wins / total) ** draws
    non_loss = ((wins + ties) / total) ** draws
    return (win + non_loss) / 2


def analyze(decision, model):
    pot, cost = decision["pot"], decision["call_cost"]
    river = decision["street"] == 5
    if model not in ("uniform", "strong") or (model == "strong" and not river):
        raise ValueError("Choose an available opponent range.")
    if river:
        equity = river_equity(decision["hole"], decision["board"], model == "strong")
        assumption = ("Strongest made hand from three independent uniform holdings."
                      if model == "strong" else "Every legal opponent holding is equally likely.")
        assumption += " River equity is enumerated exactly, including half of tied pots."
    else:
        equity = estimate_equity(decision["hole"], decision["board"], 2000,
                                 random.Random("|".join(decision["hole"] + decision["board"])))
        assumption = ("2,000 simulated runouts against a uniform hand. Both players check through "
                      "all remaining streets after this decision. Future betting can change the result.")
    ev = equity * (pot + cost) - cost if cost else None
    return {"pot": pot, "cost": cost, "equity": equity, "break_even": required_equity(pot, cost),
            "call_ev": ev, "model": model, "terminal": river, "assumption": assumption}


def coach_facts(math):
    pot, cost, equity, ev = (math[k] for k in ("pot", "cost", "equity", "call_ev"))
    facts = {"range": math["assumption"], "equity": f"Your modeled share of the pot is {equity:.1%}."}
    if cost:
        unit = "chip" if cost == 1 else "chips"
        facts["price"] = f"Calling {cost} {unit} into {pot} requires {math['break_even']:.1%} equity."
        if abs(ev) < 1e-9:
            verdict = "Calling and folding break even against each other."
        else:
            verdict = ("Calling earns more than folding" if ev > 0 else "Folding earns more than calling") + " under this assumption."
        facts["value"] = f"The incremental call EV is {ev:+.1f} chips. {verdict}"
    else:
        facts["price"] = "Checking costs zero. A bet also needs a model of how the opponent responds."
    return facts


def explain(math, decision, receipt, *, opener=None):
    """The model selects verified facts, so generated numbers never reach the table."""
    facts = coach_facts(math)
    fallback = {"text": facts.get("value", facts["price"]), "source": "Computed locally"}
    endpoint, model = os.getenv("POKER_COACH_URL"), os.getenv("POKER_COACH_MODEL")
    if not endpoint or not model:
        return fallback
    public = {"hole": decision["hole"], "board": decision["board"], "action": receipt["command"],
              "reason": receipt["reason"], "facts": facts}
    payload = {"model": model, "messages": [
        {"role": "system", "content": 'Choose up to two relevant supplied fact IDs to explain the recorded decision. Respond only with a JSON array of IDs.'},
        {"role": "user", "content": json.dumps(public)}], "max_tokens": 80}
    headers = {"Content-Type": "application/json"}
    key = os.getenv("POKER_COACH_KEY")
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        req = Request(endpoint, data=json.dumps(payload).encode(), headers=headers)
        with (opener or urlopen)(req, timeout=2) as response:
            answer = json.loads(response.read(16_384))
        ids = json.loads(answer["choices"][0]["message"]["content"])
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 2
                or any(not isinstance(i, str) or i not in facts for i in ids)):
            return fallback
        return {"text": " ".join(facts[i] for i in dict.fromkeys(ids)), "source": "Coach-selected explanation"}
    except (OSError, HTTPException, URLError, ValueError, KeyError, IndexError, TypeError):
        return fallback
