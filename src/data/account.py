"""Local account parameter persistence."""

import json
from pathlib import Path

from src.compute import config

ACCOUNT_PATH = Path("data/account/account.json")

_DEFAULTS = {
    "total_assets": 0.0,
    "debt": 0.0,
    "cash": 0.0,
    "annual_rate": 0.035,
    "warning_line": config.RISK_WARNING_LINE,
    "liquidation_line": config.RISK_LIQUIDATION_LINE,
    "holdings": [],
}


def load() -> dict:
    if not ACCOUNT_PATH.exists():
        return dict(_DEFAULTS)
    data = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
    return {**_DEFAULTS, **data}


def save(data: dict) -> None:
    ACCOUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
