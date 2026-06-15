from src.compute import risk_engine as rk

DEBT = 1860.0
SHARES = 159.21
CASH = 0.0


def test_guarantee_ratio():
    gr = rk.guarantee_ratio(total_assets=3143.0, debt=DEBT)
    assert abs(gr - 1.69) < 0.01


def test_liquidation_price():
    price = rk.liquidation_price(shares=SHARES, cash=CASH, debt=DEBT, line=1.30)
    assert abs(price - 15.19) < 0.05


def test_drawdown_scenarios():
    rows = rk.drawdown_scenarios(
        price=19.7,
        shares=SHARES,
        cash=CASH,
        debt=DEBT,
        drops=[0.05, 0.10, 0.20],
    )
    d20 = next(r for r in rows if r["drop"] == 0.20)
    assert abs(d20["guarantee_ratio"] - 1.349) < 0.02
    assert d20["breaches_warning"] is True


def test_position_sizing():
    after = rk.guarantee_ratio_after_buy(
        total_assets=3143.0,
        debt=DEBT,
        buy_amount=200.0,
    )
    assert abs(after - (3343.0 / 2060.0)) < 1e-6


def test_interest_carry():
    carry = rk.interest_carry(debt=1800.0, annual_rate=0.035)
    assert abs(carry["per_year"] - 63.0) < 1e-6
    assert abs(carry["per_month"] - 5.25) < 0.01
