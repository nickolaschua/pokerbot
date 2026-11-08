"""Verify browser retries, disclosure timing and the practice referee over loopback."""
from concurrent.futures import ThreadPoolExecutor
import http.client
from http.server import ThreadingHTTPServer
import json
from threading import Thread

import pytest

from app.web import Handler, Table


@pytest.fixture
def post_get():
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("loopback binding is restricted")
    server.table = Table(seed=42)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(path="state", body=None, raw=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=20)
        try:
            post = raw is not None or body is not None
            payload = raw if raw is not None else json.dumps(body).encode() if post else None
            conn.request("POST" if post else "GET", "/api/" + path, body=payload,
                         headers={"Content-Type": "application/json", **(headers or {})})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    try:
        yield request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        server.table.close()


def test_local_request_boundary(post_get):
    assert post_get(headers={"Host": "evil.test"})[0] == 403
    assert post_get("start", {}, headers={"Origin": "https://other.test"})[0] == 403
    for payload in (b"{", b"[]", b'{"hands":NaN}', b'{"unused":1e999}'):
        assert post_get("start", raw=payload)[0] == 400
    assert post_get("start", {"hands": True, "position": "button"})[0] == 400
    assert post_get("start", {}, headers={"Content-Type": "text/plain"})[0] == 415
    assert post_get()[1]["phase"] == "idle"


def test_one_commit_per_decision_and_disclosure_after_continue(post_get):
    status, start = post_get("start", {"hands": 2, "position": "button"})
    assert status == 200 and start["phase"] == "decision"
    decision = start["decision"]
    assert decision["pot"] == 3 and decision["bounds"] == [4, 400]
    assert set(decision) == {"id", "hand", "position", "street", "hole", "board", "pot",
                             "stack", "opponent_stack", "my_pip", "opponent_pip", "call_cost",
                             "legal", "bounds"}
    token = {"session_id": start["session_id"], "id": decision["id"]}
    bet = {**token, "command": "raise 5", "reason": "Test a small open"}
    assert post_get("commit", {**bet, "session_id": "obsolete"})[0] == 409
    assert post_get("commit", {**bet, "id": 222})[0] == 409
    assert post_get("commit", {**bet, "command": "raise 3"})[0] == 422
    assert post_get()[1] == start
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: post_get("commit", bet), range(2)))
    assert responses[0] == responses[1]
    status, review = responses[0]
    assert status == 200 and review["phase"] == "review"
    assert review["decision"] == decision and review["history"] == start["history"]
    assert review["receipt"] == {key: bet[key] for key in ("id", "command", "reason")}
    assert post_get()[1] == review
    assert post_get("commit", {**bet, "reason": "changed my mind"})[0] == 409
    _, flop = post_get("continue", token)
    assert flop["decision"]["pot"] == 10 and len(flop["decision"]["board"]) == 3
    assert flop["history"].count("Human raises to 5") == 1 and "Starter calls" in flop["history"]
    assert post_get("continue", token)[0] == 409
    assert post_get("commit", bet) == (200, review)
    assert post_get()[1] == flop
    state = flop
    while state["phase"] == "decision":
        assert state["showdown"] is None
        token["id"] = state["decision"]["id"]
        assert post_get("commit", {**token, "command": "check", "reason": ""})[0] == 200
        _, state = post_get("continue", token)
    assert state["phase"] == "settled" and state["settlement"]["human_total"] == 5
    assert len(state["showdown"].split(",")) == 2
    assert post_get("continue", token)[0] == 409
    assert post_get()[1] == state
    _, next_hand = post_get("continue", {**token, "phase": "settled"})
    assert next_hand["decision"]["hand"] == 2 and next_hand["decision"]["position"] == "bb"
    assert next_hand["showdown"] is None and next_hand["settlement"] is None
    assert post_get("end", token)[1]["phase"] == "idle"


@pytest.mark.parametrize("opening", ["raise 400", "raise 399"])
def test_called_all_in_runs_out_without_another_human_decision(post_get, opening):
    _, start = post_get("start", {"hands": 2, "position": "button"})
    token = {"session_id": start["session_id"], "id": start["decision"]["id"]}

    def play(command):
        status, review = post_get("commit", {**token, "command": command, "reason": ""})
        assert status == 200 and review["phase"] == "review"
        status, state = post_get("continue", {**token, "phase": "review"})
        assert status == 200
        return state

    result = play(opening)
    if opening == "raise 399":
        assert result["phase"] == "decision" and result["decision"]["bounds"] == [1, 1]
        token["id"] = result["decision"]["id"]
        result = play("raise 1")
    assert result["phase"] == "settled"
    assert len(result["decision"]["board"]) == 5
    assert result["decision"]["pot"] == 800
    assert result["settlement"]["human_delta"] == 400
    assert "Human checks" not in result["history"]
    assert post_get()[1] == result
    status, next_hand = post_get("continue", {**token, "phase": "settled"})
    assert status == 200 and next_hand["decision"]["hand"] == 2
