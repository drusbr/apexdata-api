from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parents[2] / "cache"
CACHE_DIR.mkdir(exist_ok=True)
