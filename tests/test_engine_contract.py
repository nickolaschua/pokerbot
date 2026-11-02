"""Walk actual upstream game trees to exercise legality at many stack sizes."""
from pathlib import Path
import random
import sys

import eval7
import pytest

ENGINE = Path(__file__).resolve().parents[1] / ".engine"
pytestmark = pytest.mark.skipif(not (ENGINE / "engine.py").exists(), reason="bootstrap MIT engine first")


def test_policies_obey_upstream_rules():
    sys.path.insert(0, str(ENGINE))
    import engine
    from pokerbot.strategy import Observation, POLICIES, decide

    actions = {"fold": engine.FoldAction, "call": engine.CallAction,
               "check": engine.CheckAction, "raise": engine.RaiseAction}
    rng = random.Random(2718)
    for policy in POLICIES:
        for _ in range(12):
            deck = eval7.Deck()
            rng.shuffle(deck.cards)
            state = engine.RoundState(0, 0, [1, 2], [399, 398],
                                      [deck.deal(2), deck.deal(2)], deck, None)
            while isinstance(state, engine.RoundState):
                active = state.button % 2
                legal = state.legal_actions()
                obs = Observation(
                    tuple(map(str, state.hands[active])),
                    tuple(map(str, state.deck.peek(state.street))),
                    800 - sum(state.stacks), state.pips[1-active] - state.pips[active],
                    state.pips[active], frozenset(k for k, v in actions.items() if v in legal),
                    state.raise_bounds() if engine.RaiseAction in legal else None,
                )
                name, amount, _ = decide(obs, policy if active == 0 else "random", rng, 20)
                assert actions[name] in legal
                if name == "raise":
                    low, high = state.raise_bounds()
                    assert low <= amount <= high
                    action = actions[name](amount)
                else:
                    action = actions[name]()
                state = state.proceed(action)
            assert sum(state.deltas) == 0
