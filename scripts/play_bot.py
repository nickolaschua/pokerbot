"""MIT socket adapter; policies only see their own cards and the public board."""
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / ".engine" / "python_skeleton"))

from skeleton.actions import CallAction, CheckAction, FoldAction, RaiseAction
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot
from skeleton.states import STARTING_STACK
from pokerbot.strategy import Observation, decide

ACTIONS = {"call": CallAction, "check": CheckAction, "fold": FoldAction, "raise": RaiseAction}


class Player(Bot):
    def __init__(self, settings):
        self.settings = settings
        self.rng = random.Random(settings["seed"])
        self.trace = open("decisions.jsonl", "w")

    def handle_new_round(self, game_state, round_state, active):
        pass

    def handle_round_over(self, game_state, terminal_state, active):
        pass

    def get_action(self, game_state, round_state, active):
        start = time.perf_counter()
        legal = round_state.legal_actions()
        obs = Observation(
            hole=tuple(round_state.hands[active]),
            board=tuple(round_state.deck[:round_state.street]),
            pot=2 * STARTING_STACK - sum(round_state.stacks),
            call_cost=round_state.pips[1-active] - round_state.pips[active],
            my_pip=round_state.pips[active],
            legal=frozenset(name for name, action in ACTIONS.items() if action in legal),
            raise_bounds=round_state.raise_bounds() if RaiseAction in legal else None,
        )
        action, amount, detail = decide(obs, self.settings["policy"], self.rng, self.settings["samples"])
        self.trace.write(json.dumps({
            "round": game_state.round_num, "street": round_state.street,
            "hole": obs.hole, "board": obs.board, "pot": obs.pot,
            "call_cost": obs.call_cost, "action": action, "raise_to": amount,
            "decision_ms": (time.perf_counter() - start) * 1000, **detail,
        }) + "\n")
        return ACTIONS[action](amount) if action == "raise" else ACTIONS[action]()


if __name__ == "__main__":
    player = Player(json.loads(Path("settings.json").read_text()))
    try:
        run_bot(player, parse_args())
    finally:
        player.trace.close()
