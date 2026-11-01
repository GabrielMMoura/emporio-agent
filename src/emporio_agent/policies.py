"""Store policy manual, one entry per section (built by scripts/build_policies.py)."""

import json
from functools import lru_cache

from emporio_agent.config import POLICIES_PATH


@lru_cache(maxsize=1)
def load_policies() -> dict[str, dict]:
    return json.loads(POLICIES_PATH.read_text(encoding="utf-8"))


def policy_topics() -> list[str]:
    return list(load_policies())


def get_policy(topic: str) -> dict:
    policies = load_policies()
    if topic not in policies:
        return {"error": f"Unknown topic '{topic}'.", "available_topics": list(policies)}
    return {"topic": topic, **policies[topic]}
