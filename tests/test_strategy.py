import random
from pokerbot.strategy import Observation, POLICIES, decide


def test_all_in_call_and_free_check():
    # Royal flush on board guarantees a split: calling the last 10 into 790 is profitable.
    obs = Observation(("2c", "3d"), ("As", "Ks", "Qs", "Js", "Ts"), 790, 10, 0, frozenset({"fold", "call"}))
    assert decide(obs, "equity", random.Random(1), 20)[0] == "call"
    obs = Observation(("2c", "3d"), (), 4, 0, 2, frozenset({"check"}))
    for policy in POLICIES:
        assert decide(obs, policy, random.Random(1), 20)[0] == "check"


def test_raise_to_bounds_on_short_stack():
    obs = Observation(("As", "Ks"), ("Qs", "Js", "Ts"), 700, 30, 50,
                      frozenset({"fold", "call", "raise"}), (90, 100))
    action, amount, _ = decide(obs, "equity", random.Random(1), 20)
    assert action == "raise" and amount == 100
