import json
import random

PHRASES_PATH = "phrases.json"
_CACHE: dict | None = None


def _load_phrases() -> dict:
    global _CACHE
    if _CACHE is None:
        with open(PHRASES_PATH, "r", encoding="utf-8") as handle:
            _CACHE = json.load(handle)
    return _CACHE


def pick_phrase(kind: str) -> str:
    data = _load_phrases()
    options = data.get(kind, [])
    if not options:
        return ""
    return random.choice(options)