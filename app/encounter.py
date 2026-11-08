"""Public opponent choices and observed betting frequencies."""
import secrets


OPPONENTS = {"starter":"MIT starter", "equity":"Equity bot", "random":"Random bot",
             "check_fold":"Check/fold bot"}
WATCH_MODES = ("step", "continuous", "river_raise")


def select_opponent(selection):
    return secrets.choice(tuple(OPPONENTS)) if selection == "mystery" else selection


def new_encounter(selection, seat, watch):
    return {"opponent": selection, "label": OPPONENTS.get(selection, "Mystery opponent"),
            "seat_mode": seat, "watch_mode": watch, "note": "", "confidence": "unsure",
            "revealed": False, "observed": {"facing_bet": 0, "folded": 0,
                                            "may_raise": 0, "raised": 0}}


def record_action(stats, event):
    if event["facing_bet"]:
        stats["facing_bet"] += 1
        stats["folded"] += event["action"] == "fold"
    if event["may_raise"]:
        stats["may_raise"] += 1
        stats["raised"] += event["action"] == "raise"
