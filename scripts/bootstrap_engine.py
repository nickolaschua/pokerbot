"""Fetch a fixed upstream revision without vendoring third-party source."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / ".engine"
ENGINE_COMMIT = "569415deb85853ebd058d42ee2b6151e4bffc3fa"
ENGINE_URL = "https://github.com/mitpokerbots/engine.git"


def verify_engine():
    if not (ENGINE / "engine.py").exists():
        raise RuntimeError("Run python scripts/bootstrap_engine.py first")
    revision = subprocess.check_output(["git", "-C", str(ENGINE), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(ENGINE), "status", "--porcelain", "--untracked-files=no"], text=True)
    if revision != ENGINE_COMMIT or dirty:
        raise RuntimeError("Engine differs from the pinned revision; use a clean engine checkout")
    return revision


def main():
    if not ENGINE.exists():
        subprocess.run(["git", "clone", ENGINE_URL, str(ENGINE)], check=True)
        subprocess.run(["git", "-C", str(ENGINE), "checkout", "--detach", ENGINE_COMMIT], check=True)
    print("MIT engine ready:", verify_engine())


if __name__ == "__main__":
    main()
