"""Showdown equity against a uniformly random legal opponent hand."""
import random

import eval7


def estimate_equity(hole, board, samples=200, rng=None):
    if len(hole) != 2 or len(board) not in (0, 3, 4, 5):
        raise ValueError("Expected two hole cards and 0, 3, 4, or 5 board cards")
    if samples < 1:
        raise ValueError("samples must be positive")
    known = [eval7.Card(card) for card in list(hole) + list(board)]
    if len(set(known)) != len(known):
        raise ValueError("Duplicate cards")
    deck = [card for card in eval7.Deck().cards if card not in known]
    rng = rng if rng is not None else random.Random()
    points = 0.0
    for _ in range(samples):
        draw = rng.sample(deck, 2 + 5 - len(board))
        community = known[2:] + draw[2:]
        hero = eval7.evaluate(known[:2] + community)
        villain = eval7.evaluate(draw[:2] + community)
        points += 1.0 if hero > villain else 0.5 if hero == villain else 0.0
    return points / samples


def required_equity(pot, call_cost):
    """Pot includes opponent's bet, but excludes our prospective call."""
    if pot < 0 or call_cost < 0:
        raise ValueError("Pot and call cost cannot be negative")
    return call_cost / (pot + call_cost) if call_cost else 0.0
