"""The silent policy sees the learner's decision and never takes their seat."""
import json
import random

import pytest

from app.comparison import compare
from app.web import Table, RequestError


def opening(kicker="5"):
    return {"id": 1, "hand": 1, "position": "button", "street": 0, "hole": ["Ks", kicker+"h"],
            "board": [], "pot": 3, "stack": 399, "opponent_stack": 398, "my_pip": 1,
            "opponent_pip": 2, "call_cost": 1, "legal": ["call", "fold", "raise"], "bounds": [4, 400]}


@pytest.mark.parametrize("kicker,raise_to,expected,disagrees", [
    ("5", 5, "fold", True), ("7", 4, "raise 5", False), ("7", 7, "raise 5", True),
])
def test_chart_and_substantive_size(kicker, raise_to, expected, disagrees):
    row = compare(opening(kicker), {"id": 1, "command": f"raise {raise_to}", "reason": ""})
    recommendation = row["recommendation"]
    assert recommendation["command"] == expected and row["disagrees"] == disagrees
    assert recommendation["diagnostics"] == {"rule": "button_king_chart", "hand": "K"+kicker+"o", "min_kicker": "7"}
    assert recommendation["chart_version"]


def test_evaluation_is_reproducible_and_independent_of_human_choice_and_global_rng():
    spot = {**opening(), "hole": ["3d", "9s"]}
    rng_state = random.getstate()
    first = compare(spot, {"command": "fold"})
    second = compare(spot, {"command": "raise 5"})
    assert first["recommendation"] == second["recommendation"]
    assert random.getstate() == rng_state
    diagnostics = first["recommendation"]["diagnostics"]
    assert diagnostics["pot_odds"] == .25 and diagnostics["samples"] == 200
    assert 0 <= diagnostics["equity"] <= 1
    assert "30.0% call threshold" in diagnostics["decision_rule"]


@pytest.mark.parametrize("mode", ["immediate", "deferred", "off"])
def test_called_shove_freezes_public_snapshot_and_obeys_reveal_mode(mode):
    table = Table(seed=22)
    try:
        start = table.request("start", {"hands": 1, "position": "button", "comparison_mode": mode})
        token = {"id": start["decision"]["id"], "session_id": start["session_id"]}
        bet = {**token, "command": "raise 400", "reason": "Expect a call"}
        assert "recommendation" not in json.dumps(start)
        with pytest.raises(RequestError) as error:
            table.request("commit", {**bet, "command": "raise 500"})
        assert error.value.status == 422 and table.request("state") == start
        review = table.request("commit", bet)
        assert bool(review["journal"]) == (mode == "immediate")
        assert table.request("commit", bet) == review
        settled = table.request("continue", {**token, "phase": "review"})
        assert len(settled["decision"]["board"]) == 5
        assert settled["settlement"]["human_delta"] == 400
        assert bool(settled["journal"]) == (mode == "immediate")
        end = table.request("continue", {**token, "phase": "settled"})
        assert end == table.request("state")
        assert table.request("commit", bet) == review
        assert len(end["journal"]) == (0 if mode == "off" else 1)
        if mode != "off":
            row, = end["journal"]
            assert row["decision"] == start["decision"] and row["history"] == start["history"]
            assert row["receipt"] == review["receipt"] and row["disagrees"]
    finally:
        table.close()
