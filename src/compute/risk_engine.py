"""Margin risk calculations.

Amounts are in 10k CNY, prices are in CNY, and shares are in 10k shares.
"""

from src.compute import config


def guarantee_ratio(total_assets: float, debt: float) -> float:
    return total_assets / debt


def guarantee_ratio_after_buy(
    total_assets: float,
    debt: float,
    buy_amount: float,
) -> float:
    return (total_assets + buy_amount) / (debt + buy_amount)


def liquidation_price(
    shares: float,
    cash: float,
    debt: float,
    line: float | None = None,
) -> float:
    line = config.RISK_LIQUIDATION_LINE if line is None else line
    required_assets = line * debt
    required_market_value = required_assets - cash
    return required_market_value / shares


def drawdown_scenarios(
    price: float,
    shares: float,
    cash: float,
    debt: float,
    drops: list[float],
) -> list[dict]:
    rows = []
    for drop in drops:
        scenario_price = price * (1 - drop)
        market_value = scenario_price * shares
        gr = guarantee_ratio(cash + market_value, debt)
        rows.append(
            {
                "drop": drop,
                "price": round(scenario_price, 2),
                "guarantee_ratio": gr,
                "breaches_warning": gr < config.RISK_WARNING_LINE,
                "breaches_liquidation": gr < config.RISK_LIQUIDATION_LINE,
            }
        )
    return rows


def interest_carry(debt: float, annual_rate: float) -> dict:
    per_year = debt * annual_rate
    return {"per_year": per_year, "per_month": per_year / 12.0}
