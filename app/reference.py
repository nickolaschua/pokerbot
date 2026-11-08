"""Compatibility and exact equilibrium for one published river betting game."""
from fractions import Fraction
import json
from pathlib import Path

from app.coach import analyze


REFERENCE = Path(__file__).with_name("river_reference.json")
RANGE = "equal_polar"
HISTORY = ["button raises to 200", "bb calls", "bb checks", "button checks",
           "bb checks", "button checks", "bb bets 200"]


def exercise(variant):
    pot, cost, stack, behind = 600, 200, 200, 0
    history = HISTORY.copy()
    if variant == "size":
        cost, pot, behind = 150, 550, 50
        history[-1] = "bb bets 150"
    elif variant == "stack":
        stack, behind = 300, 100
    elif variant == "history":
        history[:4] = ["button raises to 4", "bb calls", "bb bets 196", "button calls"]
    elif variant != "covered":
        raise ValueError("Choose an available reference exercise.")
    decision = {"position":"button", "street":5, "board":["5h","Jh","5d","Qh","3h"],
                "hole":["Kc","5s"], "pot":pot, "call_cost":cost, "stack":stack,
                "opponent_stack":behind, "my_pip":0, "opponent_pip":cost,
                "legal":["call","fold","raise"] if behind else ["call","fold"],
                "bounds":[stack,stack] if behind else None}
    return {"decision":decision, "history":["button posts 1 · bb posts 2", *history]}


def action_history(lines):
    if not lines or " posts 1 · " not in lines[0] or not lines[0].endswith(" posts 2"):
        return None
    button, bb = lines[0][:-8].split(" posts 1 · ", 1)
    aliases = {button:"button", bb:"bb"}
    normalized = []
    for line in lines[1:]:
        for actor, seat in aliases.items():
            if line.startswith(actor + " "):
                normalized.append(seat + line[len(actor):])
                break
        else:
            return None
    return normalized


def review(row, range_model, source_path=None):
    d = row["decision"]
    misses = []
    if range_model != RANGE:
        misses.append("Opponent range differs from the reference prior.")
    if d["street"] != 5 or d["position"] != "button":
        misses.append("Street or position differs from the river button decision.")
    if set(d["hole"]) != {"Kc","5s"} or d["board"] != ["5h","Jh","5d","Qh","3h"]:
        misses.append("Cards differ from the covered holding and board.")
    if d["stack"] != 200 or d["opponent_stack"] + d["opponent_pip"] != 200:
        misses.append("Effective stacks before the river bet differ from 200 chips.")
    if (d["pot"], d["call_cost"], d["my_pip"], d["opponent_pip"]) != (600,200,0,200):
        misses.append("Pot or bet size differs from the 200-chip jam into 400.")
    if set(d["legal"]) != {"call","fold"} or d["bounds"] is not None:
        misses.append("Available actions differ from call or fold.")
    if action_history(row["history"]) != HISTORY:
        misses.append("Blinds or betting history differ from the reference line.")
    try:
        with (source_path or REFERENCE).open() as source:
            reference = json.load(source)
        if reference.get("revision") != "half-street-river/1" or any(
                not isinstance(reference.get(k), str) for k in ("source","url","range","tree")):
            raise ValueError("unrecognized reference")
    except (OSError, ValueError, AttributeError):
        reference = None
        misses.append("The local reference is unavailable.")
    if misses:
        return {"covered":False, "reasons":misses, "math":analyze(d, "uniform"),
                "conditional_ev_available": range_model == "uniform", "reference":reference}
    bet = d["call_cost"]
    pot = d["pot"] - bet
    relative_bet = Fraction(bet, pot)
    call_rate = 1 / (1 + relative_bet)
    bluff_rate = relative_bet / (1 + relative_bet)
    bluff_share = bluff_rate / (1 + bluff_rate)
    call_ev = bluff_share * d["pot"] - (1 - bluff_share) * bet
    return {"covered":True, "reference":reference, "call_frequency":float(call_rate),
            "fold_frequency":float(1-call_rate), "bluff_frequency":float(bluff_rate),
            "conditional_equity":float(bluff_share), "call_ev_chips":float(call_ev),
            "fold_ev_chips":0, "ev_gap_bb":float(abs(call_ev)/2),
            "on_win_bb":d["pot"]/2, "on_loss_bb":-bet/2}
