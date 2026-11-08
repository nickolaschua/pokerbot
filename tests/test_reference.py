from fractions import Fraction

import eval7
import pytest

from app.reference import RANGE, exercise, review


def test_reference_mix_makes_both_players_indifferent():
    result = review(exercise("covered"), RANGE)
    assert result["covered"]
    # Compute best responses directly in chips from the payoff matrix.
    call = Fraction(result["call_frequency"]).limit_denominator()
    bluff = Fraction(result["bluff_frequency"]).limit_denominator()
    bluff_bet_value = (1 - call) * 400 - call * 200
    assert bluff_bet_value == 0  # Checking a losing hand also earns zero.
    posterior_bluff = (bluff / 2) / (bluff / 2 + Fraction(1, 2))
    assert posterior_bluff * 600 - (1 - posterior_bluff) * 200 == 0
    assert result["call_ev_chips"] == result["fold_ev_chips"] == result["ev_gap_bb"] == 0
    assert result["on_win_bb"] == 300 and result["on_loss_bb"] == -100
    assert call == Fraction(2, 3) and bluff == Fraction(1, 3)


def test_concrete_hands_match_binary_types_and_real_engine_history():
    row = exercise("covered")
    board = [eval7.Card(c) for c in row["decision"]["board"]]
    def score(hand):
        return eval7.evaluate(board + [eval7.Card(c) for c in hand])
    assert score(["Ah","2h"]) > score(["Kc","5s"]) > score(["7s","2d"])
    row["history"] = [s.replace("button","Your bot").replace("bb","Opponent") for s in row["history"]]
    assert review(row, RANGE)["covered"]


@pytest.mark.parametrize("variant,reason", [("size","bet size"), ("stack","stacks"), ("history","betting history")])
def test_incompatible_fixtures_return_modeled_feedback(variant, reason):
    result = review(exercise(variant), RANGE)
    assert not result["covered"] and reason in " ".join(result["reasons"])
    assert not result["conditional_ev_available"]
    assert "call_frequency" not in result and result["math"]["model"] == "uniform"


@pytest.mark.parametrize("changes,reason", [
    ({"position":"bb"}, "position"), ({"board":["5h","Jh","5d"],"street":3}, "Street"),
    ({"hole":["Kd","5s"]}, "Cards"), ({"legal":["call","fold","raise"],"bounds":[300,300]}, "actions")
])
def test_public_inputs_must_match(changes, reason):
    row = exercise("covered")
    row["decision"].update(changes)
    result = review(row, RANGE)
    assert not result["covered"] and reason in " ".join(result["reasons"])


def test_missing_source_range_and_blinds_never_return_equilibrium(tmp_path):
    row = exercise("covered")
    result = review(row, "uniform", tmp_path / "missing.json")
    assert len(result["reasons"]) == 2 and result["math"]["terminal"]
    row["history"][0] = "button posts 5 · bb posts 10"
    assert not review(row, RANGE)["covered"]
