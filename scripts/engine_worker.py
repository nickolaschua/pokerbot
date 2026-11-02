"""Execute unchanged MIT engine with a seeded training deck and run settings."""
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".engine"))
import engine
import eval7


def main():
    settings = json.loads(Path("match.json").read_text())
    rng = random.Random(settings["seed"])

    class SeededDeck(eval7.Deck):
        def shuffle(self):
            rng.shuffle(self.cards)

    # Override only this engine module's evaluator reference. Rules stay upstream.
    engine.eval7 = SimpleNamespace(Deck=SeededDeck, evaluate=eval7.evaluate)
    engine.NUM_ROUNDS = settings["hands"]
    engine.PLAYER_1_NAME, engine.PLAYER_2_NAME = "A", "B"
    engine.PLAYER_1_PATH, engine.PLAYER_2_PATH = "A", "B"
    engine.GAME_LOG_FILENAME = "gamelog"
    engine.STARTING_GAME_CLOCK = settings["clock"]
    engine.ENFORCE_GAME_CLOCK = True
    engine.Game().run()


if __name__ == "__main__":
    main()
