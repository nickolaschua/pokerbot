import json

import pytest

from app.web import RequestError, Table


def test_watch_steps_once_and_holds_river_prediction():
    table = Table(seed=457)
    try:
        state = table.request("start", {"hands":1, "position":"button", "seat_mode":"watch",
                                        "opponent":"equity", "watch_mode":"river_raise"})
        token = {"session_id":state["session_id"]}
        while state["phase"] == "decision":
            d = state["decision"]
            token["id"] = d["id"]
            pending_raise = d["street"] == 5 and d["my_pip"] and d["call_cost"]
            if pending_raise:
                assert (d["id"], d["call_cost"], d["pot"]) == (5, 8, 24)
                assert state["receipt"] is None and state["history"][-1] == "Opponent raises to 14"
                assert table.request("state") == state
                with pytest.raises(RequestError):
                    table.request("commit", {**token, "command":"fold","reason":""})
            step = {**token, "prediction":"Call" if pending_raise else ""}
            review = table.request("step", step)
            assert table.request("step", step) == review
            state = table.request("continue", {**token, "phase":"review"})
            if pending_raise:
                assert review["receipt"]["reason"] == "Call"
                break
        else:
            pytest.fail("watch hand settled before reaching a river raise")
    finally:
        table.close()


def test_mystery_selection_stable_read_note_and_explicit_reveal(monkeypatch):
    chosen = []
    def choose(policies):
        chosen.append(policies)
        return "check_fold"
    monkeypatch.setattr("app.encounter.secrets.choice", choose)
    table = Table(seed=22)
    try:
        state = table.request("start", {"hands":2, "position":"button", "opponent":"mystery"})
        token = {"session_id":state["session_id"]}
        table.request("read", {**token,"note":"Folds to opens","confidence":"medium"})
        with pytest.raises(RequestError):
            table.request("reveal", token)
        table.request("commit", {**token,"id":1,"command":"raise 5","reason":"Try a steal"})
        first = table.request("continue", {**token,"id":1,"phase":"review"})
        assert first["phase"] == "settled"
        stats = first["encounter"]["observed"]
        assert stats == {"facing_bet":1,"folded":1,"may_raise":1,"raised":0}
        second = table.request("continue", {**token,"id":1,"phase":"settled"})
        # Opponent folds its small blind before the big blind has acted.
        assert second["phase"] == "settled" and second["decision"]["hand"] == 2
        assert second["settlement"]["human_delta"] == 1
        final = table.request("continue", {**token,"id":2,"phase":"settled"})
        assert final == table.request("state")
        assert "check_fold" not in json.dumps(final) and "Check/fold bot" not in json.dumps(final)
        assert final["encounter"]["note"] == "Folds to opens"
        assert final["encounter"]["observed"]["facing_bet"] == 2
        reveal = table.request("reveal", token)
        assert reveal["encounter"]["label"] == "Check/fold bot" and reveal["encounter"]["revealed"]
        assert len(chosen) == 1
    finally:
        table.close()
