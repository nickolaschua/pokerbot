import random
import pytest
from pokerbot.equity import estimate_equity, required_equity


def test_pot_odds_include_call_once():
    assert required_equity(100, 20) == pytest.approx(1 / 6)
    assert required_equity(0, 0) == 0
    with pytest.raises(ValueError):
        required_equity(10, -1)


def test_unbeatable_hand_and_board_tie():
    assert estimate_equity(["As", "Ks"], ["Qs", "Js", "Ts", "2d", "3c"], 30, random.Random(1)) == 1
    assert estimate_equity(["2c", "3d"], ["As", "Ks", "Qs", "Js", "Ts"], 30, random.Random(1)) == 0.5


def test_seed_reproducibility_and_input_validation():
    args = (["Ah", "Ad"], [])
    assert estimate_equity(*args, rng=random.Random(9)) == estimate_equity(*args, rng=random.Random(9))
    with pytest.raises(ValueError):
        estimate_equity(["As", "As"], [])
    with pytest.raises(ValueError):
        estimate_equity(*args, samples=0)
