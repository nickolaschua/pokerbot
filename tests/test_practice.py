"""Protect the action boundary that human input crosses before MIT's referee."""
from pathlib import Path
import socket

import pytest

from app.practice import _validate_action, practice_session


@pytest.fixture
def referee(monkeypatch):
    root = Path(__file__).resolve().parents[1] / ".engine"
    if not (root / "engine.py").is_file():
        pytest.skip("bootstrap the pinned MIT engine")
    monkeypatch.syspath_prepend(str(root))
    import engine
    return engine


def test_human_raise_to_is_legal_before_referee_advances(referee):
    state = referee.RoundState(0, 0, [1, 2], [399, 398], [], None, None)
    for command in ("check", "raise", "raise 3", "raise 401", "raise 5.5", "call 2"):
        with pytest.raises(ValueError):
            _validate_action(referee, command, state)
    move = _validate_action(referee, "raise 5", state)
    assert move == referee.RaiseAction(5)
    after = state.proceed(move)
    assert after.pips == [5, 2]
    assert after.stacks == [395, 398]


def test_short_all_in_raise_uses_referees_reduced_minimum(referee):
    # Both players entered this street with 8 chips. One bets 6; only 8 total
    # is available to the responder, below a normal full raise to 12.
    state = referee.RoundState(2, 4, [0, 6], [8, 2], [], None, None)
    assert state.raise_bounds() == (8, 8)
    for illegal in ("raise 7", "raise 12"):
        with pytest.raises(ValueError):
            _validate_action(referee, illegal, state)
    after = state.proceed(_validate_action(referee, "raise 8", state))
    assert after.pips == [8, 6]
    assert after.stacks == [0, 2]


def test_complete_hand_through_starter_socket_after_rejected_raise():
    # Some local sandboxes disallow even loopback listeners. All other
    # connection and protocol errors should fail this integration test.
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", 0))
        except PermissionError:
            pytest.skip("loopback binding is restricted in this environment")

    events = []
    with practice_session(1, "button", 42) as client:
        while True:
            assert client.poll(15), "practice worker timed out"
            event = client.recv()
            events.append(event)
            kind = event["type"]
            assert kind != "error", event
            if kind == "decision":
                client.send((event["id"], "raise 3" if event["street"] == 0 else "check"))
            elif kind == "rejected":
                client.send((event["id"], "raise 5"))
            elif kind == "complete":
                break

    opening, flop = [event for event in events if event["type"] == "decision"][:2]
    assert opening["bounds"] == (4, 400)
    assert flop["street"] == 3 and flop["pot"] == 10
    action_events = [event["type"] for event in events if event.get("id") == opening["id"]]
    assert action_events == ["decision", "rejected", "committed"]
    assert any(e.get("text") == "Starter calls" for e in events)
    assert [e["seat"] for e in events if e["type"] == "ack"] == ["Human", "Starter"]
    settlement = next(e for e in events if e["type"] == "settled")
    assert (settlement["human_total"], settlement["starter_total"]) == (5, -5)
