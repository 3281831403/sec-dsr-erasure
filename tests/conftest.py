import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

NOW = 1_700_000_000
DAY = 86_400


@pytest.fixture
def policy():
    return {
        "deadline_seconds": 30 * DAY,
        "targets": ["primary", "cache", "search"],
        "tombstone": True,
        "cascade": True,
        "residual_check": True,
        "backup_retention_seconds": 90 * DAY,
    }


@pytest.fixture
def store_factory():
    def build(user):
        return {
            "primary": {user: {"email": f"{user}@example.test"}},
            "cache": {user: {"last_seen": NOW}},
            "search": {user: {"index": "people"}},
        }

    return build


@pytest.fixture
def store(store_factory):
    return store_factory("alice")