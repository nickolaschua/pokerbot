"""Local browser practice table. Run with python -m app.web."""
import argparse
from contextlib import ExitStack
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import signal
import sys
from threading import Lock
from uuid import uuid4

from app import coach
from app.replay import Library
from app.encounter import OPPONENTS, WATCH_MODES, new_encounter, record_action, select_opponent
from app.comparison import compare, recommend
from app.practice import practice_session


ASSETS = Path(__file__).parent / "table"
FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/table.css": ("table.css", "text/css; charset=utf-8"),
    "/encounter.js": ("encounter.js", "text/javascript; charset=utf-8"),
    "/replay.js": ("replay.js", "text/javascript; charset=utf-8"),
    "/coach.js": ("coach.js", "text/javascript; charset=utf-8"),
    "/table.js": ("table.js", "text/javascript; charset=utf-8"),
}
DECISION_FIELDS = ("id", "hand", "position", "street", "hole", "board", "pot",
                   "stack", "opponent_stack", "my_pip", "opponent_pip", "call_cost",
                   "legal", "bounds")


class RequestError(Exception):
    def __init__(self, message, status=HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


class Table:
    """One local table. A lock serializes transactions across tabs and retries."""

    def __init__(self, seed=None):
        self.library = Library()
        self.seed = seed
        self.lock = Lock()
        self.resources = ExitStack()
        self._reset()

    def _reset(self):
        self.pipe = None
        self.state = {"phase": "idle", "session_id": None, "decision": None, "receipt": None,
                      "history": [], "settlement": None, "showdown": None, "hands": 0,
                      "comparison_mode": "deferred", "encounter": None}
        self.private_opponent = None
        self.journal = []
        self.reviews = {}

    def close(self):
        with self.lock:
            self.resources.close()
            self._reset()

    def _event(self):
        if not self.pipe.poll(30):
            raise RuntimeError("practice worker timed out")
        event = self.pipe.recv()
        if event["type"] == "error":
            raise RuntimeError("practice worker failed")
        return event

    def _advance(self):
        while True:
            event = self._event()
            kind = event["type"]
            if kind == "blinds":
                self.state.update(receipt=None, settlement=None, showdown=None,
                                  history=[f'{event["button"]} posts 1 · {event["bb"]} posts 2'])
            elif kind == "played":
                self.state["history"].append(event["text"])
                if event["opponent"]:
                    record_action(self.state["encounter"]["observed"], event)
            elif kind == "unplayed":
                self.state["decision"] = {k: event[k] for k in DECISION_FIELDS}
            elif kind == "decision":
                self.state.update(phase="decision", decision={k: event[k] for k in DECISION_FIELDS},
                                  receipt=None)
                return
            elif kind == "runout":
                # Keep the id of the last actual decision for settlement and retry.
                self.state["decision"].update(board=event["board"], street=event["street"], pot=event["pot"],
                                              stack=0, opponent_stack=0, my_pip=0, opponent_pip=0,
                                              legal=[], bounds=None, call_cost=0)
            elif kind == "showdown":
                self.state["showdown"] = event["opponent"]
            elif kind == "settled":
                self.state.update(phase="settled",
                                  settlement={k: event[k] for k in ("hand", "human_delta", "human_total", "starter_total")})
                return
            elif kind == "complete":
                self.state["phase"] = "complete"
                self.resources.close()
                self.pipe = None
                return
            elif kind not in ("ready", "ack"):
                raise RuntimeError("unexpected referee event")

    def _commit(self, body):
        decision_id = body.get("id")
        command, reason = body.get("command"), body.get("reason")
        if type(decision_id) is not int or not isinstance(command, str) or not isinstance(reason, str):
            raise RequestError("A decision ID, action and reason are required.")
        if len(command) > 64 or len(reason) > 2000:
            raise RequestError("Action or reason is too long.")
        receipt = {"id": decision_id, "command": command, "reason": reason}
        prior = self.reviews.get(decision_id)
        if prior is not None:
            if receipt != prior["receipt"]:
                raise RequestError("This decision already has a different commitment.", 409)
            return prior
        if self.state["phase"] != "decision" or decision_id != self.state["decision"]["id"]:
            raise RequestError("This decision is no longer pending.", 409)
        self.pipe.send((decision_id, command))
        reply = self._event()
        if reply["type"] == "rejected":
            raise RequestError(reply["reason"], 422)
        if reply["type"] != "committed" or reply["id"] != decision_id:
            raise RuntimeError("unexpected action receipt")
        if self.state["comparison_mode"] != "off":
            row = compare(self.state["decision"], receipt)
            row["history"] = self.state["history"].copy()
            row["seat_mode"] = self.state["encounter"]["seat_mode"]
            self.journal.append(row)
        self.state.update(phase="review", receipt=receipt)
        # The worker may already have emitted the opponent's reply. Read it
        # only after Continue so refresh and exact retries show the locked spot.
        self.reviews[decision_id] = deepcopy(self.state)
        return self.state

    def request(self, operation, body=None):
        with self.lock:
            try:
                snapshot = self._request(operation, body or {})
                visible = []
                if snapshot["phase"] == "complete":
                    visible = self.journal
                elif snapshot["comparison_mode"] == "immediate" and snapshot["decision"]:
                    # A replayed receipt exposes only decisions committed at that point.
                    last_id = snapshot["decision"]["id"]
                    visible = [row for row in self.journal if row["receipt"]["id"] <= last_id]
                return deepcopy({**snapshot, "journal": visible})
            except (EOFError, OSError, RuntimeError):
                self.resources.close()
                self._reset()
                raise RequestError("The practice session stopped. Start a new session.", 503)

    def visible_row(self, body):
        snapshot = self.request("state")
        if not snapshot["session_id"] or body.get("session_id") != snapshot["session_id"]:
            raise RequestError("Session has changed.", 409)
        row = next((r for r in snapshot["journal"] if type(body.get("id")) is int
                    and r["decision"]["id"] == body["id"]), None)
        if row is None:
            raise RequestError("This decision is unavailable for review.", 409)
        return row

    def coaching(self, operation, body):
        if body.get("fixture") == "river":
            command = body.get("prediction")
            if command not in ("call", "fold"):
                raise RequestError("Commit a prediction first.")
            decision, receipt = coach.RIVER_EXERCISE, {"command": command, "reason": ""}
        else:
            row = self.visible_row(body)
            decision, receipt = row["decision"], row["receipt"]
        try:
            analysis = coach.analyze(decision, body.get("model", "uniform"))
        except ValueError as exc:
            raise RequestError(str(exc)) from exc
        if operation == "analysis":
            return analysis
        return coach.explain(analysis, decision, receipt)

    def _request(self, operation, body):
        phase = self.state["phase"]
        if operation == "state":
            return self.state
        if operation == "start":
            hands, position = body.get("hands"), body.get("position")
            if type(hands) is not int or not 1 <= hands <= 1000 or position not in ("button", "bb"):
                raise RequestError("Choose 1–1000 hands and a starting seat.")
            mode = body.get("comparison_mode", "deferred")
            if mode not in ("deferred", "immediate", "off"):
                raise RequestError("Choose a valid comparison mode.")
            if phase not in ("idle", "complete"):
                raise RequestError("There is already an active session.", 409)
            selection = body.get("opponent", "starter")
            seat, watch = body.get("seat_mode", "human"), body.get("watch_mode", "step")
            if (not isinstance(selection, str) or selection not in (*OPPONENTS, "mystery")
                    or seat not in ("human", "watch") or watch not in WATCH_MODES):
                raise RequestError("Choose an available seat, opponent and watch mode.")
            self._reset()
            self.private_opponent = select_opponent(selection)
            self.state["encounter"] = new_encounter(selection, seat, watch)
            self.pipe = self.resources.enter_context(practice_session(
                hands, position, self.seed, self.private_opponent, selection == "mystery", seat == "watch"))
            self.state.update(session_id=uuid4().hex, hands=hands, comparison_mode=mode)
            self._advance()
        else:
            if phase == "idle" or body.get("session_id") != self.state["session_id"]:
                raise RequestError("Session has changed. Refresh the table.", 409)
            encounter = self.state["encounter"]
            if operation == "step":
                decision_id = body.get("id")
                if encounter["seat_mode"] != "watch" or type(decision_id) is not int:
                    raise RequestError("Select a pending watch decision.", 409)
                prediction = body.get("prediction", "")
                if not isinstance(prediction, str) or len(prediction) > 1000:
                    raise RequestError("Use a prediction of up to 1000 characters.")
                prior = self.reviews.get(decision_id)
                if prior:
                    if prior["receipt"]["reason"] != prediction:
                        raise RequestError("This prediction has already been recorded.", 409)
                    return prior
                if phase != "decision" or decision_id != self.state["decision"]["id"]:
                    raise RequestError("This watch decision has already advanced.", 409)
                chosen = recommend(self.state["decision"])
                return self._commit({**body, "command":chosen["command"], "reason":prediction})
            if operation == "watch-mode":
                pace = body.get("watch_mode")
                if encounter["seat_mode"] != "watch" or pace not in WATCH_MODES or phase == "complete":
                    raise RequestError("Choose an available watch mode.")
                encounter["watch_mode"] = pace
                return self.state
            if operation == "read":
                note, confidence = body.get("note"), body.get("confidence")
                if not isinstance(note, str) or len(note) > 1000 or confidence not in ("unsure","medium","high"):
                    raise RequestError("Enter a read of up to 1000 characters and a confidence level.")
                encounter.update(note=note, confidence=confidence)
                return self.state
            if operation == "reveal":
                if phase != "complete" or encounter["opponent"] != "mystery":
                    raise RequestError("Finish the mystery encounter before revealing your opponent.", 409)
                encounter.update(revealed=True, label=OPPONENTS[self.private_opponent])
                return self.state
            if operation == "commit":
                if encounter["seat_mode"] == "watch":
                    raise RequestError("Use the watch controls for the bot seat.", 409)
                return self._commit(body)
            if operation == "continue":
                expected = body.get("phase", "review")
                if (phase not in ("review", "settled") or expected != phase or
                        type(body.get("id")) is not int or self.state["decision"]["id"] != body["id"]):
                    raise RequestError("This table has already advanced.", 409)
                self._advance()
            elif operation == "end":
                self.resources.close()
                self._reset()
            else:
                raise RequestError("Unknown operation.", 404)
        return self.state


def finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("non-finite JSON value")
    return number


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status, content, content_type="application/json; charset=utf-8"):
        payload = content if isinstance(content, bytes) else json.dumps(content, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _handle(self, post):
        try:
            port = self.server.server_port
            hosts = {f"localhost:{port}", f"127.0.0.1:{port}"}
            if port == 80:
                hosts |= {"localhost", "127.0.0.1"}
            host = self.headers.get("Host")
            if host not in hosts or self.headers.get("Origin", f"http://{host}") != f"http://{host}":
                raise RequestError("Local origin required.", 403)
            if post:
                if self.path not in ("/api/start", "/api/end", "/api/commit", "/api/continue", "/api/analysis", "/api/explain",
                                     "/api/bookmark", "/api/replay", "/api/retain", "/api/step", "/api/watch-mode", "/api/read", "/api/reveal"):
                    raise RequestError("Unknown endpoint.", 404)
                if self.headers.get_content_type() != "application/json":
                    raise RequestError("JSON required.", 415)
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    raise RequestError("Invalid content length.")
                if not 0 < length <= 16384:
                    raise RequestError("Request body missing or too large.", 413)
                try:
                    body = json.loads(self.rfile.read(length).decode(), parse_constant=finite_float, parse_float=finite_float)
                except (ValueError, RecursionError):
                    raise RequestError("Invalid JSON.")
                if not isinstance(body, dict):
                    raise RequestError("Expected a JSON object.")
                operation = self.path[5:]
                if operation == "bookmark":
                    row = self.server.table.visible_row(body)
                    self._reply(200, self.server.table.library.save(body["session_id"], row))
                elif operation in ("replay", "retain"):
                    try:
                        result = self.server.table.library.experiment(operation, body)
                    except ValueError as exc:
                        raise RequestError(str(exc))
                    self._reply(200, result)
                elif operation in ("analysis", "explain"):
                    self._reply(200, self.server.table.coaching(operation, body))
                else:
                    self._reply(200, self.server.table.request(operation, body))
            elif self.path == "/api/bookmarks":
                self._reply(200, self.server.table.library.list())
            elif self.path == "/api/state":
                self._reply(200, self.server.table.request("state"))
            elif self.path in FILES:
                filename, mime = FILES[self.path]
                self._reply(200, (ASSETS / filename).read_bytes(), mime)
            else:
                raise RequestError("Unknown endpoint.", 404)
        except RequestError as exc:
            self._reply(exc.status, {"error": str(exc)})

    def do_GET(self):
        self._handle(False)

    def do_POST(self):
        self._handle(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--seed", type=int, help="use repeatable practice deals")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
        server.table = Table(args.seed)
        print(f"Practice table: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.table.close()


if __name__ == "__main__":
    main()
