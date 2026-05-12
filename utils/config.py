import json

CONFIG_PATH = "config.json"


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
