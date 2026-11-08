import io
import json

import pytest

from app import coach
from app.web import RequestError, Table


@pytest.mark.parametrize("model,expected", [("uniform", 233.0505), ("strong", -11.7521)])
def test_saved_river_incremental_ev(model, expected):
    math = coach.analyze(coach.RIVER_EXERCISE, model)
    assert math["break_even"] == .25 and math["terminal"]
    assert math["call_ev"] == pytest.approx(expected, abs=.001)


def test_royal_flush_on_board_ties_every_opponent():
    for strongest in [False, True]:
        assert coach.river_equity(["2c", "3d"], ["Ts", "Js", "Qs", "Ks", "As"], strongest) == .5


def test_free_check_has_no_call_ev_and_early_street_has_continuation_assumption():
    spot = {**coach.RIVER_EXERCISE, "board": ["5h", "Jh", "5d"], "street": 3, "call_cost": 0}
    math = coach.analyze(spot, "uniform")
    assert math["call_ev"] is None
    assert "check through" in math["assumption"] and not math["terminal"]
    with pytest.raises(ValueError):
        coach.analyze(spot, "strong")


def test_coach_respects_commit_visibility():
    table = Table(seed=72)
    try:
        started = table.request("start", {"hands": 1, "position": "button", "comparison_mode":"deferred"})
        token = {"session_id": started["session_id"], "id": started["decision"]["id"]}
        for op in ("analysis", "explain"):
            with pytest.raises(RequestError):
                table.coaching(op, token)
        table.request("commit", {**token, "command":"fold", "reason":"K5o below cutoff"})
        with pytest.raises(RequestError):
            table.coaching("analysis", token)
        table.request("continue", {**token, "phase":"review"})
        table.request("continue", {**token, "phase":"settled"})
        assert table.coaching("analysis", token)["pot"] == 3
        with pytest.raises(RequestError):
            table.coaching("analysis", {**token, "session_id":"another session"})
    finally:
        table.close()


@pytest.mark.parametrize("reply,expected", [('["value","price"]', "Coach-selected explanation"),
                                           ('["The EV is 5000 chips"]', "Computed locally"),
                                           (None, "Computed locally")])
def test_optional_provider_grounding_and_timeout(monkeypatch, reply, expected):
    monkeypatch.setenv("POKER_COACH_URL", "http://localhost/coach")
    monkeypatch.setenv("POKER_COACH_MODEL", "local")
    def provider(request, *, timeout):
        assert timeout == 2
        payload = json.loads(request.data)
        context = json.loads(payload["messages"][1]["content"])
        assert set(context) == {"hole", "board", "action", "reason", "facts"}
        assert context["reason"] == "I expect a flush"
        if reply is None:
            raise TimeoutError("provider timeout")
        return io.BytesIO(json.dumps({"choices":[{"message":{"content":reply}}]}).encode())
    math = coach.analyze(coach.RIVER_EXERCISE, "strong")
    result = coach.explain(math, coach.RIVER_EXERCISE, {"command":"fold","reason":"I expect a flush"}, opener=provider)
    assert result["source"] == expected
    assert "-11.8 chips" in result["text"]
