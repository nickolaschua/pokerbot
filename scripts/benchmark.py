"""Paired local matches; fail closed on fallback actions, crashes, or timeouts."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time
from importlib.metadata import version

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.bootstrap_engine import verify_engine
from pokerbot.strategy import POLICIES


def parse_result(log, stdout, bot_logs, hands):
    errors = ("attempted illegal", "response misformatted", "ran out of time", "disconnected")
    if any(error in log for error in errors):
        raise RuntimeError("Engine used fallback actions; inspect gamelog.txt")
    if any(f"{seat} connected successfully" not in stdout for seat in ("A", "B")):
        raise RuntimeError("Both bots must connect; inspect engine.txt")
    if "Traceback" in bot_logs:
        raise RuntimeError("Bot crashed; inspect A.txt/B.txt")
    deltas = [int(x) for x in re.findall(r"^A awarded (-?\d+)$", log, re.M)]
    final = re.search(r"^Final(.*)$", log, re.M)
    if len(deltas) != hands or not final:
        raise RuntimeError("Incomplete match")
    totals = dict((name, int(value)) for name, value in re.findall(r", ([AB]) \((-?\d+)\)", final[1]))
    if set(totals) != {"A", "B"} or sum(totals.values()) != 0 or sum(deltas) != totals["A"]:
        raise RuntimeError("Inconsistent zero-sum result")
    return totals


def run_match(folder, hero, opponent, seed, hands, samples, clock, swap):
    folder.mkdir(parents=True)
    hero_seat = "B" if swap else "A"
    for seat in ("A", "B"):
        bot_dir = folder / seat
        bot_dir.mkdir()
        policy = hero if seat == hero_seat else opponent
        settings = {"policy": policy, "seed": seed * 2 + (seat != hero_seat), "samples": samples}
        (bot_dir / "settings.json").write_text(json.dumps(settings))
        (bot_dir / "commands.json").write_text(json.dumps({
            "build": [], "run": [sys.executable, str(ROOT / "scripts" / "play_bot.py")],
        }))
    (folder / "match.json").write_text(json.dumps({"seed": seed, "hands": hands, "clock": clock}))
    start = time.perf_counter()
    with (folder / "engine.txt").open("w") as output:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "engine_worker.py")],
                       cwd=folder, stdout=output, stderr=subprocess.STDOUT, check=True)
    stdout = (folder / "engine.txt").read_text()
    bot_logs = "\n".join((folder / (seat + ".txt")).read_text() for seat in ("A", "B"))
    totals = parse_result((folder / "gamelog.txt").read_text(), stdout, bot_logs, hands)
    traces = [json.loads(line) for line in (folder / hero_seat / "decisions.jsonl").read_text().splitlines()]
    if not traces:
        raise RuntimeError("Missing hero decision trace")
    return {"seed": seed, "swap": swap, "hero_seat": hero_seat, "hands": hands,
            "net_chips": totals[hero_seat], "bb_per_100": totals[hero_seat] / 2 / hands * 100,
            "seconds": time.perf_counter() - start,
            "mean_decision_ms": statistics.mean(t["decision_ms"] for t in traces),
            "max_decision_ms": max(t["decision_ms"] for t in traces)}


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hero", choices=POLICIES, default="equity")
    parser.add_argument("--opponents", nargs="+", choices=POLICIES, default=["check_call", "check_fold", "random"])
    parser.add_argument("--hands", type=positive_int, default=200, help="hands per seat per seed")
    parser.add_argument("--seeds", nargs="+", type=int, default=[11, 22, 33])
    parser.add_argument("--samples", type=positive_int, default=200)
    parser.add_argument("--clock", type=positive_int, default=60, help="seconds per bot per match")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds) or len(set(args.opponents)) != len(args.opponents):
        parser.error("seeds and opponents must be unique")
    revision = verify_engine()
    output = args.output or ROOT / "results" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    def git(*arguments):
        result = subprocess.run(["git", *arguments], cwd=ROOT, text=True, capture_output=True)
        return result.stdout.strip() if result.returncode == 0 else "uncommitted"
    report = {"hero": args.hero, "engine_revision": revision,
              "code_revision": git("rev-parse", "HEAD"), "working_tree": git("status", "--porcelain"),
              "python": platform.python_version(), "eval7": version("eval7"),
              "settings": {**vars(args), "output": str(output)}, "opponents": {}}
    (output / "manifest.json").write_text(json.dumps(report, indent=2))
    for opponent in args.opponents:
        matches, pairs = [], []
        for seed in args.seeds:
            pair = []
            for swap in (False, True):
                folder = output / opponent / f"seed-{seed}-seat-{int(swap)}"
                result = run_match(folder, args.hero, opponent, seed, args.hands, args.samples, args.clock, swap)
                matches.append(result)
                pair.append(result["bb_per_100"])
            pairs.append(statistics.mean(pair))
        report["opponents"][opponent] = {
            "hands": len(matches) * args.hands,
            "bb_per_100": statistics.mean(pairs),
            "paired_seed_standard_error": statistics.stdev(pairs) / len(pairs)**0.5 if len(pairs) > 1 else None,
            "matches": matches,
        }
        print(f"{args.hero} vs {opponent}: {statistics.mean(pairs):+.2f} bb/100 ({len(matches) * args.hands} hands)")
    report["interpretation"] = "Smoke/benchmark only; weak opponents do not establish competitive strength. Small seed counts give unstable uncertainty estimates."
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", output / "summary.json")


if __name__ == "__main__":
    main()
