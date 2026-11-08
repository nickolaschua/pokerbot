from copy import deepcopy
import json
import sqlite3

import pytest

from app.comparison import compare
from app.replay import Library, costs, paired
from app.web import RequestError, Table


def spot():
    decision = dict(id=1, hand=1, position="button", street=0, hole=["5c","Kd"], board=[],
                    pot=3, stack=399, opponent_stack=398, my_pip=1, opponent_pip=2, call_cost=1,
                    legal=["fold","call","raise"], bounds=[4,400])
    row = compare(decision, {"command":"fold","reason":"Weak kicker","id":1})
    return {**row, "history":["Human posts 1 · Starter posts 2"]}


def test_persistent_chart_trial_is_separate_from_recorded_move(tmp_path):
    path = tmp_path / "bookmarks.sqlite3"
    row = spot()
    lib = Library(path)
    key = lib.save("session", row)["key"]
    assert lib.save("session", row)["key"] == key
    stored, = Library(path).list()
    assert stored["record"]["row"] == row
    body = {"key":key, "cutoff":"5"}
    result = lib.experiment("replay", body)
    assert result["original"] == row["recommendation"]
    assert result["revised"]["command"] == "raise 5"
    assert result["batch"] == lib.experiment("retain", body)["batch"]
    assert lib.list()[0] == {**stored, "candidate":"5"}
    lib.experiment("retain", {**body,"cutoff":None})
    assert lib.list() == [stored]
    with sqlite3.connect(path) as db:
        old = {**stored["record"], "policy":"unknown"}
        db.execute("UPDATE spots SET record=?", (json.dumps(old),))
    assert "version unavailable" in lib.experiment("replay",body)["status"]


def test_paired_incremental_chips_and_size_validation():
    d = spot()["decision"]
    river = {**d,"street":5,"board":["As","Ks","Qs","Js","Ts"], "pot":18,
             "call_cost":2,"my_pip":0,"opponent_pip":2,"bounds":[4,390]}
    assert costs(river,"raise 9") == (9,7)
    # Both players play the royal flush on every paired runout.
    result = paired(river,"fold","call")
    assert result["mean_difference"] == (18+2)/2-2
    assert result["deals"] == 512 and result["standard_error"] == 0
    assert paired(river,"call","raise 9")["mean_difference"] == 0
    with pytest.raises(ValueError): paired(d,"fold","raise 401")
    with pytest.raises(ValueError): paired(d,"fold","check")


def test_only_revealed_row_can_be_bookmarked_and_library_does_not_touch_game(tmp_path):
    table = Table(seed=72)
    table.library = Library(tmp_path / "saved.db")
    try:
        state = table.request("start", {"hands":1, "position":"button", "opponent":"mystery"})
        token = {"session_id":state["session_id"],"id":state["decision"]["id"]}
        with pytest.raises(RequestError): table.visible_row(token)
        table.request("commit", {**token,"command":"fold","reason":"weak kicker"})
        with pytest.raises(RequestError): table.visible_row(token)
        for phase in ("review","settled"):
            table.request("continue", {**token,"phase":phase})
        settled = deepcopy(table.request("state"))
        row = table.visible_row(token)
        key = table.library.save(token["session_id"], row)["key"]
        table.library.experiment("replay", {"key":key, "cutoff":"5"})
        record = table.library.list()[0]["record"]
        assert record["row"]["decision"] == json.loads(json.dumps(state["decision"]))
        assert record["row"]["history"] == state["history"]
        assert not {"encounter","seed","session_id","showdown","opponent"}.intersection(record)
        assert table.request("state") == settled
    finally:
        table.close()
