"""Play trusted local practice hands against MIT's pinned Python starter."""

import argparse
from contextlib import contextmanager
import multiprocessing
import os
from pathlib import Path
import random
import re
import signal
import sys
import tempfile

from pokerbot.strategy import Observation, decide
from scripts.bootstrap_engine import ENGINE, verify_engine


class SessionClosed(Exception):
    """The client left before settlement."""


def _validate_action(engine, command, state):
    actions = {"fold": engine.FoldAction, "call": engine.CallAction,
               "check": engine.CheckAction, "raise": engine.RaiseAction}
    words = command.split()
    if not words or words[0] not in actions:
        raise ValueError("enter one of the legal actions")
    action = actions[words[0]]
    if action not in state.legal_actions():
        raise ValueError(f"{words[0]} is unavailable on this turn")
    if action == engine.RaiseAction:
        low, high = state.raise_bounds()
        if len(words) != 2 or not re.fullmatch(r"[0-9]+", words[1]):
            raise ValueError("use raise N with an integer raise-to amount")
        amount = int(words[1])
        if not low <= amount <= high:
            raise ValueError(f"raise to {low} through {high} chips")
        return action(amount)
    if len(words) != 1:
        raise ValueError(f"{words[0]} takes no amount")
    return action()


def _referee(connection, hands, start_position, seed, opponent, mystery, watch):
    # Only the worker changes directory or configures the engine's deck.
    import engine
    if seed is not None:
        import eval7
        from types import SimpleNamespace
        deal_rng = random.Random(seed)

        class SeededDeck(eval7.Deck):
            def shuffle(self):
                deal_rng.shuffle(self.cards)

        engine.eval7 = SimpleNamespace(Deck=SeededDeck, evaluate=eval7.evaluate)

    def send(kind, **fields):
        connection.send({"type": kind, **fields})

    class Human:
        name = "Human"
        bankroll = 0
        hand = 0
        position = 0
        decision_id = 0

        def query(self, state, messages, log):
            if isinstance(state, engine.TerminalState):
                for message in messages:
                    if message.startswith("O"):
                        send("showdown", opponent=message[1:])
                messages.clear()
                send("ack", seat=self.name, hand=self.hand)
                return engine.CheckAction()

            if state.stacks == [0, 0]:
                # The referee still expects an action on each remaining street.
                send("runout", street=state.street, board=list(map(str, state.deck.peek(state.street))),
                     pot=2 * engine.STARTING_STACK)
                messages.clear()
                return engine.CheckAction()

            self.decision_id += 1
            active = self.position
            legal = state.legal_actions()
            bounds = state.raise_bounds() if engine.RaiseAction in legal else None
            send("decision", id=self.decision_id, hand=self.hand,
                 position=("button", "bb")[active], street=state.street,
                 hole=list(map(str, state.hands[active])),
                 board=list(map(str, state.deck.peek(state.street))),
                 pot=2 * engine.STARTING_STACK - sum(state.stacks),
                 stack=state.stacks[active], opponent_stack=state.stacks[1 - active],
                 my_pip=state.pips[active], opponent_pip=state.pips[1-active],
                 call_cost=state.pips[1-active] - state.pips[active],
                 legal=sorted(a.__name__[:-6].lower() for a in legal), bounds=bounds)
            messages.clear()
            while True:
                request = connection.recv()
                if request is None:
                    raise SessionClosed()
                decision_id, command = request
                try:
                    if decision_id != self.decision_id:
                        raise ValueError("stale decision")
                    action = _validate_action(engine, command, state)
                except ValueError as exc:
                    send("rejected", id=self.decision_id, reason=str(exc))
                    continue
                send("committed", id=self.decision_id, action=command)
                return action

    class Starter(engine.Player):
        def query(self, state, messages, log):
            length = len(log)
            action = super().query(state, messages, log)
            if len(log) != length or self.socketfile is None or self.game_clock <= 0:
                raise RuntimeError(f"MIT starter failed on hand {human.hand}: {log[-1]}")
            if isinstance(state, engine.TerminalState):
                send("ack", seat=self.name, hand=human.hand)
            return action

    class LocalOpponent:
        bankroll = 0
        name = "Opponent"

        def __init__(self):
            self.rng = random.Random(None if seed is None else f"opponent:{seed}")

        def query(self, state, messages, log):
            messages.clear()
            if isinstance(state, engine.TerminalState):
                send("ack", seat=self.name, hand=human.hand)
                return engine.CheckAction()
            active = state.button % 2
            legal = state.legal_actions()
            obs = Observation(
                hole=tuple(map(str, state.hands[active])), board=tuple(map(str, state.deck.peek(state.street))),
                pot=2 * engine.STARTING_STACK - sum(state.stacks),
                call_cost=state.pips[1 - active] - state.pips[active], my_pip=state.pips[active],
                legal=frozenset(action.__name__[:-6].lower() for action in legal),
                raise_bounds=state.raise_bounds() if engine.RaiseAction in legal else None,
                button_open=state.street == 0 and state.button == 0)
            move, amount, _ = decide(obs, opponent, self.rng)
            return _validate_action(engine, f"raise {amount}" if move == "raise" else move, state)

    class PracticeGame(engine.Game):
        def log_round_state(self, players, state):
            self.running_out = state.stacks == [0, 0]
            self.current = state
            super().log_round_state(players, state)

        def log_action(self, name, action, bet_override):
            super().log_action(name, action, bet_override)
            if not self.running_out:
                legal = self.current.legal_actions()
                send("played", text=self.log[-1], opponent=(name == starter.name),
                     facing_bet=engine.CallAction in legal, may_raise=engine.RaiseAction in legal,
                     action=type(action).__name__[:-6].lower())

    human = Human()
    human.name = "Your bot" if watch else "Human"
    starter = (Starter("Opponent" if mystery else "Starter", str(ENGINE / "python_skeleton"))
               if opponent == "starter" else LocalOpponent())
    game = PracticeGame()
    try:
        if isinstance(starter, Starter):
            starter.build()
            if starter.commands is None:
                raise RuntimeError("MIT starter commands missing")
            starter.commands["run"] = [sys.executable, "player.py"]
            starter.run()
            if starter.socketfile is None:
                raise RuntimeError("MIT starter did not connect; local socket access is required")
        send("ready", opponent="Mystery opponent" if mystery else ("MIT Python check/call starter" if opponent == "starter" else opponent))
        for hand in range(1, hands + 1):
            human.hand = hand
            human.position = ((start_position == "bb") + hand - 1) % 2
            seats = (human, starter) if human.position == 0 else (starter, human)
            send("blinds", hand=hand, button=seats[0].name, bb=seats[1].name)
            before = human.bankroll
            previous_id = human.decision_id
            game.run_round(seats)
            if human.decision_id == previous_id:
                # The button can fold before the big blind ever receives a turn.
                human.decision_id += 1
                state = game.current
                active = human.position
                send("unplayed", id=human.decision_id, hand=hand, position=("button", "bb")[active],
                     street=0, hole=list(map(str, state.hands[active])), board=[], pot=sum(state.pips),
                     stack=state.stacks[active], opponent_stack=state.stacks[1-active],
                     my_pip=state.pips[active], opponent_pip=state.pips[1-active], call_cost=0,
                     legal=[], bounds=None)
            send("settled", hand=hand, human_delta=human.bankroll - before,
                 human_total=human.bankroll, starter_total=starter.bankroll)
            game.log.clear()
    finally:
        if isinstance(starter, Starter):
            starter.stop()


def _worker(connection, hands, position, seed, opponent, mystery, watch):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        verify_engine()
        sys.path.insert(0, str(ENGINE))
        with tempfile.TemporaryDirectory(prefix="poker-practice-") as scratch:
            os.chdir(scratch)
            try:
                _referee(connection, hands, position, seed, opponent, mystery, watch)
            finally:
                os.chdir(Path(__file__).resolve().parent)
        connection.send({"type": "complete"})
    except (SessionClosed, EOFError, BrokenPipeError, ConnectionResetError):
        pass
    except Exception as exc:
        connection.send({"type": "error", "reason": str(exc)})
    finally:
        connection.close()


@contextmanager
def practice_session(hands, position="button", seed=None, opponent="starter", mystery=False, watch=False):
    """Yield a local connection: recv public events, send (decision ID, command)."""
    if type(hands) is not int or hands < 1 or position not in ("button", "bb"):
        raise ValueError("expected a positive hand count and position button or bb")
    ctx = multiprocessing.get_context("spawn")
    client, worker = ctx.Pipe()
    process = ctx.Process(target=_worker, args=(worker, hands, position, seed, opponent, mystery, watch))
    process.start()
    worker.close()
    try:
        yield client
    finally:
        client.close()
        process.join()


def _play(contacts):
    while True:
        event = contacts.recv()
        kind = event["type"]
        if kind == "complete":
            print("Session complete.")
            return
        if kind == "error":
            raise RuntimeError(event["reason"])
        if kind == "ready":
            print(f"Opponent: {event['opponent']}. Type quit to leave.")
        elif kind == "blinds":
            print(f"Hand {event['hand']}: {event['button']} button posts 1; {event['bb']} bb posts 2.")
        elif kind == "runout":
            print("Board:", " ".join(event["board"]))
        elif kind == "played":
            print(event["text"])
        elif kind == "ack":
            print(f"Terminal acknowledged: {event['seat']}")
        elif kind == "showdown":
            print(f"Starter shows {event['opponent']}")
        elif kind == "settled":
            print(f"Settled hand {event['hand']}: Human {event['human_delta']:+}; "
                  f"session Human {event['human_total']:+}, Starter {event['starter_total']:+}")
        elif kind == "committed":
            print(f"Committed {event['id']}: {event['action']}", flush=True)
        elif kind in ("decision", "rejected"):
            if kind == "decision":
                street = {0: "preflop", 3: "flop", 4: "turn", 5: "river"}[event["street"]]
                print(f"Decision {event['id']} | {event['position']} | {street} | "
                      f"hand {' '.join(event['hole'])} | board {' '.join(event['board']) or '-'} | "
                      f"pot {event['pot']} | to call {event['call_cost']} | "
                      f"stacks {event['stack']} / {event['opponent_stack']}")
                bounds = f" (raise to {event['bounds'][0]}..{event['bounds'][1]})" if event["bounds"] else ""
                print(f"Legal: {', '.join(event['legal'])}{bounds}", flush=True)
            else:
                print(f"Rejected: {event['reason']}", flush=True)
            try:
                command = input().strip().lower()
            except EOFError:
                command = "quit"
            if command == "quit":
                print("Session closed.")
                return
            contacts.send((event["id"], command))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hands", type=int, default=1)
    parser.add_argument("--position", choices=("button", "bb"), default="button")
    parser.add_argument("--seed", type=int, help="repeat a practice deal")
    args = parser.parse_args()
    if args.hands < 1:
        parser.error("--hands must be positive")
    try:
        with practice_session(args.hands, args.position, args.seed) as client:
            _play(client)
    except KeyboardInterrupt:
        print("Session closed.")
    except (RuntimeError, EOFError, ConnectionError) as exc:
        parser.exit(1, f"Practice session failed: {exc}\n")


if __name__ == "__main__":
    main()
