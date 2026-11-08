"""Persistent public decision bookmarks and isolated model-based experiments."""
from contextlib import closing
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import random
import sqlite3
from statistics import mean, stdev

import eval7

from app.comparison import recommend
from pokerbot.strategy import BUTTON_OPEN


POLICY = "king_chart/1"
RNG = "python-random/sorted-decision-json/1"
RANKS = "23456789TJQ"
BATCH_SEED = 781
BATCH_SIZE = 512


def library_path():
    default = Path(__file__).resolve().parents[1] / "results" / "practice-bookmarks.sqlite3"
    return Path(os.environ.get("POKER_BOOKMARK_DB", default)).expanduser()


def costs(decision, command):
    """Return additional hero and opponent contributions if the opponent calls."""
    if not isinstance(command, str) or len(command) > 64:
        raise ValueError("Select a legal action.")
    words = command.split()
    if not words or words[0] not in decision["legal"]:
        raise ValueError("That action was unavailable at the saved decision.")
    action = words[0]
    if action == "raise":
        if len(words) != 2 or not words[1].isascii() or not words[1].isdigit():
            raise ValueError("Enter a whole-chip raise total.")
        total = int(words[1])
        low, high = decision["bounds"]
        if not low <= total <= high:
            raise ValueError(f"Raise to {low}–{high} chips.")
        return total - decision["my_pip"], total - decision["opponent_pip"]
    if len(words) != 1:
        raise ValueError("This move takes no amount.")
    return (decision["call_cost"] if action == "call" else 0), 0


def paired(decision, original, alternate):
    lines = []
    for cmd in [original, alternate]:
        hero, opponent = costs(decision, cmd)
        lines.append((0, 0) if cmd.strip() == "fold" else (decision["pot"] + hero + opponent, hero))
    known = [eval7.Card(c) for c in decision["hole"] + decision["board"]]
    unseen = [c for c in eval7.Deck() if c not in known]
    rng = random.Random(BATCH_SEED)
    differences = []
    for _ in range(BATCH_SIZE):
        draw = rng.sample(unseen, 7 - len(decision["board"]))
        board = known[2:] + draw[2:]
        hero = eval7.evaluate(known[:2] + board)
        villain = eval7.evaluate(draw[:2] + board)
        share = 1 if hero > villain else .5 if hero == villain else 0
        a, b = [share * pot - investment for pot, investment in lines]
        differences.append(b - a)
    return {"original": original, "alternate": alternate, "deals": BATCH_SIZE, "seed": BATCH_SEED,
            "mean_difference": mean(differences), "standard_error": stdev(differences) / BATCH_SIZE**.5}


def replay(record, kicker, alternate):
    if record.get("schema") != 1 or record.get("policy") != POLICY or record.get("rng") != RNG or not record.get("chart"):
        return {"status": "Saved policy or chart version unavailable. The original record remains readable."}
    row = record["row"]
    decision = row["decision"]
    original = recommend(decision, record["chart"])
    if original != row["recommendation"]:
        return {"status": "The installed evaluator no longer reproduces this saved version."}
    chart = deepcopy(record["chart"])
    if not isinstance(kicker, str) or kicker not in list(RANKS):
        raise ValueError("Select a valid offsuit king cutoff.")
    chart["K"]["offsuit_min_kicker"] = kicker
    revised = recommend(decision, chart)
    difference = paired(decision, row["receipt"]["command"], alternate or revised["command"])
    return {"status": "Reproduced", "original": original, "revised": revised, "batch": difference}


class Library:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else library_path()

    def _open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        db.execute("CREATE TABLE IF NOT EXISTS spots (id TEXT PRIMARY KEY, record TEXT NOT NULL, candidate TEXT)")
        return db

    def save(self, session, row):
        key = hashlib.sha256(f"{session}/{row['decision']['id']}".encode()).hexdigest()
        record = {"schema": 1, "policy": POLICY, "rng": RNG, "row": row, "chart": BUTTON_OPEN}
        with closing(self._open()) as db, db:
            db.execute("INSERT OR IGNORE INTO spots(id, record) VALUES (?, ?)", (key, json.dumps(record)))
        return {"key": key}

    def get_row(self, key):
        if not isinstance(key, str):
            return None
        with closing(self._open()) as db:
            saved = db.execute("SELECT record FROM spots WHERE id = ?", (key,)).fetchone()
        return json.loads(saved[0])["row"] if saved else None

    def list(self):
        with closing(self._open()) as db:
            rows = db.execute("SELECT id, record, candidate FROM spots ORDER BY rowid DESC")
            return [{"key": k, "record": json.loads(r), "candidate": c} for k, r, c in rows]

    def experiment(self, op, body):
        key = body.get("key")
        if not isinstance(key, str):
            raise ValueError("Choose a saved decision.")
        with closing(self._open()) as db, db:
            saved = db.execute("SELECT record FROM spots WHERE id = ?", (key,)).fetchone()
            if saved is None:
                raise ValueError("Saved decision unavailable.")
            cutoff = body.get("cutoff")
            if op == "retain" and cutoff is None:
                db.execute("UPDATE spots SET candidate=NULL WHERE id=?", (key,))
                return {"candidate": None}
            result = replay(json.loads(saved[0]), cutoff, body.get("alternate"))
            if op == "retain":
                if result["status"] != "Reproduced":
                    raise ValueError(result["status"])
                db.execute("UPDATE spots SET candidate=? WHERE id=?", (cutoff, key))
            return result
