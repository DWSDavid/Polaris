# Polaris 北极星 Implementation Plan

> **执行说明(给 Codex / 执行者):** 本计划按任务(Task)逐个实现,每个任务内按步骤(Step)走 **TDD**:先写失败测试 → 跑挂 → 写最小实现 → 跑过 → commit。Step 用 `- [ ]` 勾选跟踪。**按顺序做,不要跳。** 不清楚的外部 API 字段,在该任务的"⚠️ 需对真实 API 核对"处用一次真实调用确认后再写死。

**Goal:** 搭一个单用户、收盘级、人在环中的 A 股板块轮动决策仪表盘,进攻(轮动+联动)建立在风控(担保比)脊柱之上。

**Architecture:** 三层 —— 数据层(AKShare/Tushare 拉取 + parquet 缓存 + Excel 股票池)→ 计算层(纯函数:指标 / 状态机 / 风控引擎)→ 展示层(Streamlit + Plotly 五页)。展示层只读缓存与计算结果,不直连外部 API。

**Tech Stack:** Python 3.10+ · pandas · numpy · pyarrow · akshare · tushare · streamlit · plotly · pytest

参考设计:[`2026-06-15-polaris-design.md`](2026-06-15-polaris-design.md)

---

## 文件结构(本计划锁定的边界)

| 文件 | 职责 |
|---|---|
| `src/data/universe.py` | 读股票池 Excel → 规范化 DataFrame;双龙头标签 |
| `src/data/cache.py` | parquet 读写,按 (source, dataset, key) 缓存 |
| `src/data/akshare_client.py` | AKShare 行情/资金流封装(带缓存) |
| `src/data/tushare_client.py` | Tushare daily/daily_basic 封装(带缓存) |
| `src/compute/indicators.py` | 扩散率、龙头贡献度、板块强度 Score(纯函数) |
| `src/compute/state_machine.py` | 指标 → 6 个阶段标签(纯函数) |
| `src/compute/risk_engine.py` | 担保比/强平价/回撤情景/仓位计算器/利息(纯函数) |
| `src/compute/config.py` | 指标权重、状态机阈值、风控两条线等可调参数 |
| `src/data/account.py` | 账户参数 `account.json` 读写 |
| `src/pipeline/refresh.py` | 收盘后全量更新编排 |
| `src/app/Home.py` | Streamlit 首页:大盘云图 |
| `src/app/pages/1_板块轮动排名.py` | 决策页 |
| `src/app/pages/2_风险驾驶舱.py` | 风控页 |
| `tests/` | 对应单测 |

> Phase 1 (MVP) = Task 1–11。Phase 2/3 见文末路线图,不在本次执行范围。

---

## Task 1: 配置中心 `config.py`

把所有可调参数集中,后续任务都从这里取。

**Files:** Create `src/compute/config.py`; Test `tests/test_config.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
from src.compute import config

def test_risk_lines_defaults():
    assert config.RISK_WARNING_LINE == 1.50
    assert config.RISK_LIQUIDATION_LINE == 1.30

def test_strength_weights_sum_to_one():
    assert abs(sum(config.STRENGTH_WEIGHTS.values()) - 1.0) < 1e-9
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_config.py -v` → FAIL (module/attr missing)

- [ ] **Step 3: 写实现**

```python
# src/compute/config.py
"""集中所有可调参数。改这里,不要在各模块里硬编码。"""

# 风控两条线(担保比),用户后续在账户配置覆盖
RISK_WARNING_LINE = 1.50      # 警戒线 150%
RISK_LIQUIDATION_LINE = 1.30  # 平仓线 130%

# 板块强度 Score 五项权重(默认等权,可调)
STRENGTH_WEIGHTS = {
    "relative_return": 0.20,   # 板块超额收益
    "volume_amp": 0.20,        # 成交额放大
    "fund_flow": 0.20,         # 主力资金净流入
    "breadth": 0.20,           # 上涨家数扩散
    "leader_contrib": 0.20,    # 龙头贡献
}

# 状态机阈值
DIFFUSION_HIGH = 0.60   # 扩散率高
DIFFUSION_LOW = 0.40    # 扩散率低(龙头孤立判定)
VOLUME_BLOWOFF = 2.0    # 成交额 / 20日均 的高位加速阈值

# 滚动窗口
WINDOW_SHORT = 5
WINDOW_LONG = 20
```

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_config.py -v` → PASS
- [ ] **Step 5: commit** — `git add src/compute/config.py tests/test_config.py && git commit -m "feat: 配置中心"`

---

## Task 2: 股票池加载 `universe.py`

读 `data/universe/sector_leaders_seed.xlsx`(sheet `板块Top10`)→ 规范化英文列名 DataFrame,并打 `leader_type` 标签。

真实列名(已核对):`板块, 排名, 代码, 完整代码, 股票名称, 交易所, 总市值(亿元), 指数权重(%), 占板块总市值`。

**Files:** Create `src/data/universe.py`; Test `tests/test_universe.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_universe.py
from pathlib import Path
from src.data.universe import load_universe

SEED = Path("data/universe/sector_leaders_seed.xlsx")

def test_load_universe_schema():
    df = load_universe(SEED)
    assert {"sector","code","symbol","name","exchange","market_cap","leader_type"} <= set(df.columns)
    assert len(df) == 110
    assert df["leader_type"].eq("market_cap").all()   # 种子全是市值龙头
    # 茅台在主要消费板块
    row = df[df["code"] == "600519"].iloc[0]
    assert row["sector"] == "主要消费"
    assert row["symbol"] == "SH600519"
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_universe.py -v` → FAIL

- [ ] **Step 3: 写实现**

```python
# src/data/universe.py
"""股票池加载:读种子 Excel,规范化,打双龙头标签。"""
from pathlib import Path
import pandas as pd

_COLMAP = {
    "板块": "sector", "代码": "code", "完整代码": "symbol",
    "股票名称": "name", "交易所": "exchange",
    "总市值(亿元)": "market_cap", "排名": "rank",
}

def load_universe(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="板块Top10")
    df = df.rename(columns=_COLMAP)
    df["code"] = df["code"].astype(str).str.zfill(6)
    df["market_cap"] = pd.to_numeric(df["market_cap"], errors="coerce")
    df["leader_type"] = "market_cap"   # 种子全部为市值龙头
    cols = ["sector","rank","code","symbol","name","exchange","market_cap","leader_type"]
    return df[cols].reset_index(drop=True)

def add_momentum_leader(df: pd.DataFrame, sector: str, code: str, symbol: str, name: str) -> pd.DataFrame:
    """人工加入人气龙头(题材龙头),leader_type=momentum。"""
    new = {"sector": sector, "rank": None, "code": str(code).zfill(6),
           "symbol": symbol, "name": name, "exchange": symbol[:2],
           "market_cap": None, "leader_type": "momentum"}
    return pd.concat([df, pd.DataFrame([new])], ignore_index=True)
```

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_universe.py -v` → PASS
- [ ] **Step 5: commit** — `git commit -am "feat: 股票池加载 + 双龙头标签"`

---

## Task 3: 缓存层 `cache.py`

所有外部拉取先落 parquet,计算/展示只读缓存。

**Files:** Create `src/data/cache.py`; Test `tests/test_cache.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cache.py
import pandas as pd
from src.data import cache

def test_roundtrip(tmp_path):
    cache.CACHE_DIR = tmp_path
    df = pd.DataFrame({"a":[1,2], "b":[3,4]})
    cache.write("akshare", "hist", "SH600519", df)
    assert cache.exists("akshare", "hist", "SH600519")
    got = cache.read("akshare", "hist", "SH600519")
    pd.testing.assert_frame_equal(got, df)

def test_missing_returns_none(tmp_path):
    cache.CACHE_DIR = tmp_path
    assert cache.read("akshare", "hist", "NOPE") is None
    assert cache.exists("akshare", "hist", "NOPE") is False
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_cache.py -v` → FAIL

- [ ] **Step 3: 写实现**

```python
# src/data/cache.py
"""parquet 缓存,按 (source, dataset, key) 落盘。"""
from pathlib import Path
import pandas as pd

CACHE_DIR = Path("data/cache")

def _path(source: str, dataset: str, key: str) -> Path:
    return CACHE_DIR / source / dataset / f"{key}.parquet"

def write(source: str, dataset: str, key: str, df: pd.DataFrame) -> None:
    p = _path(source, dataset, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)

def read(source: str, dataset: str, key: str):
    p = _path(source, dataset, key)
    return pd.read_parquet(p) if p.exists() else None

def exists(source: str, dataset: str, key: str) -> bool:
    return _path(source, dataset, key).exists()
```

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_cache.py -v` → PASS
- [ ] **Step 5: commit** — `git commit -am "feat: parquet 缓存层"`

---

## Task 4: 风控引擎 `risk_engine.py`(系统脊柱,纯函数,最高优先)

完全确定性,完整代码 + 完整测试。**这是整个系统最该先做对的部分。**

**Files:** Create `src/compute/risk_engine.py`; Test `tests/test_risk_engine.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_risk_engine.py
import math
from src.compute import risk_engine as rk

# 用设计文档里的算例:负债 1860w,持仓 159.2 万股,担保比 169% → 现价≈19.7
DEBT = 1860.0      # 万元
SHARES = 159.21    # 万股
CASH = 0.0

def test_guarantee_ratio():
    # 总资产 = 现金 + 持仓市值;持仓市值 = 股数 * 价
    gr = rk.guarantee_ratio(total_assets=3143.0, debt=DEBT)
    assert abs(gr - 1.69) < 0.01

def test_liquidation_price():
    # 触平仓线 130% 所需总资产 = 1.30 * 1860 = 2418w → 价 = 2418/159.21
    price = rk.liquidation_price(shares=SHARES, cash=CASH, debt=DEBT, line=1.30)
    assert abs(price - 15.19) < 0.05

def test_drawdown_scenarios():
    rows = rk.drawdown_scenarios(price=19.7, shares=SHARES, cash=CASH, debt=DEBT,
                                 drops=[0.05, 0.10, 0.20])
    d20 = next(r for r in rows if r["drop"] == 0.20)
    # 现价市值 ≈ 3136w,跌20% → 2509w,担保比 ≈ 1.349
    assert abs(d20["guarantee_ratio"] - 1.349) < 0.02
    assert d20["breaches_warning"] is True   # < 150%

def test_position_sizing():
    # 想加仓 X 万,担保品(总资产)+X,负债+X(融资买入),问加完担保比
    after = rk.guarantee_ratio_after_buy(total_assets=3143.0, debt=DEBT, buy_amount=200.0)
    assert abs(after - (3343.0/2060.0)) < 1e-6

def test_interest_carry():
    c = rk.interest_carry(debt=1800.0, annual_rate=0.035)
    assert abs(c["per_year"] - 63.0) < 1e-6
    assert abs(c["per_month"] - 5.25) < 0.01
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_risk_engine.py -v` → FAIL

- [ ] **Step 3: 写实现**

```python
# src/compute/risk_engine.py
"""融资融券风控引擎。所有金额单位:万元;价格:元;股数:万股。

担保比 = 总资产 / 融资负债。
总资产 = 现金 + 持仓市值;持仓市值(万元) = 价格(元) * 股数(万股) / 100? 否。
约定:股数用"万股",价格"元",则市值(万元) = 价格 * 股数。 (1元*1万股=1万元)
"""
from src.compute import config

def guarantee_ratio(total_assets: float, debt: float) -> float:
    return total_assets / debt

def guarantee_ratio_after_buy(total_assets: float, debt: float, buy_amount: float) -> float:
    """融资买入 buy_amount:担保品与负债同增。"""
    return (total_assets + buy_amount) / (debt + buy_amount)

def liquidation_price(shares: float, cash: float, debt: float, line: float = None) -> float:
    """持仓股跌到该价,担保比触 line(默认平仓线)。"""
    line = line if line is not None else config.RISK_LIQUIDATION_LINE
    required_assets = line * debt          # 触线所需总资产
    required_mkt_value = required_assets - cash
    return required_mkt_value / shares

def drawdown_scenarios(price, shares, cash, debt, drops):
    rows = []
    for d in drops:
        mv = price * (1 - d) * shares
        gr = guarantee_ratio(cash + mv, debt)
        rows.append({
            "drop": d,
            "price": round(price * (1 - d), 2),
            "guarantee_ratio": gr,
            "breaches_warning": gr < config.RISK_WARNING_LINE,
            "breaches_liquidation": gr < config.RISK_LIQUIDATION_LINE,
        })
    return rows

def interest_carry(debt: float, annual_rate: float) -> dict:
    per_year = debt * annual_rate
    return {"per_year": per_year, "per_month": per_year / 12.0}
```

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_risk_engine.py -v` → PASS(如算例小数有偏差,核对单位约定后调测试容差,不要改公式逻辑)
- [ ] **Step 5: commit** — `git commit -am "feat: 风控引擎(担保比/强平价/回撤/仓位/利息)"`

---

## Task 5: 指标 `indicators.py`(纯函数)

**Files:** Create `src/compute/indicators.py`; Test `tests/test_indicators.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_indicators.py
import pandas as pd
from src.compute import indicators as ind

def test_diffusion_rate():
    # 5 只票,3 只涨 → 0.6
    changes = pd.Series([0.02, -0.01, 0.03, 0.00, 0.01])  # 0.00 不算涨
    assert abs(ind.diffusion_rate(changes) - 0.6) < 1e-9

def test_leader_contribution():
    turnover = pd.Series([100, 80, 60, 40, 20])  # 总 300, top3=240
    assert abs(ind.leader_contribution(turnover, top_n=3) - 0.8) < 1e-9

def test_volume_amplification():
    hist = pd.Series([10,10,10,10,20])  # 今日 20 vs 前均(可含今日)
    assert ind.volume_amplification(hist, window=5) > 1.0
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_indicators.py -v` → FAIL

- [ ] **Step 3: 写实现**

```python
# src/compute/indicators.py
"""板块指标(纯函数,输入已对齐的 pandas 结构)。"""
import pandas as pd

def diffusion_rate(pct_changes: pd.Series) -> float:
    """上涨家数 / 总家数。pct_change > 0 记为涨。"""
    n = pct_changes.notna().sum()
    return float((pct_changes > 0).sum() / n) if n else 0.0

def leader_contribution(turnover: pd.Series, top_n: int = 3) -> float:
    total = turnover.sum()
    if total <= 0:
        return 0.0
    return float(turnover.nlargest(top_n).sum() / total)

def volume_amplification(turnover_hist: pd.Series, window: int = 20) -> float:
    """今日成交额 / 近 window 日均值。"""
    if len(turnover_hist) == 0:
        return 0.0
    avg = turnover_hist.tail(window).mean()
    return float(turnover_hist.iloc[-1] / avg) if avg else 0.0

def zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd else s * 0.0

def sector_strength(features: pd.DataFrame, weights: dict) -> pd.Series:
    """features: index=板块, 列含 weights 的键(原始值)。各列 z-score 后加权求和。"""
    score = pd.Series(0.0, index=features.index)
    for col, w in weights.items():
        score = score + w * zscore(features[col])
    return score
```

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_indicators.py -v` → PASS
- [ ] **Step 5: commit** — `git commit -am "feat: 板块指标(扩散率/龙头贡献/放量/强度)"`

---

## Task 6: 状态机 `state_machine.py`(纯函数)

**Files:** Create `src/compute/state_machine.py`; Test `tests/test_state_machine.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_state_machine.py
from src.compute.state_machine import classify_state

def test_zhusheng_kuosan():
    s = classify_state(strength_rank=0.9, diffusion=0.7, fund_inflow=True,
                       vol_amp=1.3, trend20=1, consecutive_up=2)
    assert s == "主升扩散"

def test_longtou_guli():
    s = classify_state(strength_rank=0.8, diffusion=0.3, fund_inflow=True,
                       vol_amp=1.5, trend20=1, consecutive_up=1)
    assert s == "龙头孤立"

def test_gaowei_jiasu():
    s = classify_state(strength_rank=0.97, diffusion=0.65, fund_inflow=True,
                       vol_amp=2.4, trend20=1, consecutive_up=5)
    assert s == "高位加速"
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_state_machine.py -v` → FAIL

- [ ] **Step 3: 写实现**

```python
# src/compute/state_machine.py
"""指标组合 → 6 个阶段标签。strength_rank ∈ [0,1] 为板块强度的横截面分位。"""
from src.compute import config

def classify_state(strength_rank, diffusion, fund_inflow, vol_amp, trend20, consecutive_up):
    # 优先判高位加速
    if strength_rank >= 0.95 and vol_amp >= config.VOLUME_BLOWOFF and consecutive_up >= 4:
        return "高位加速"
    if strength_rank >= 0.7 and diffusion < config.DIFFUSION_LOW:
        return "龙头孤立"
    if strength_rank >= 0.7 and diffusion >= config.DIFFUSION_HIGH and fund_inflow:
        return "主升扩散"
    if trend20 <= 0 and fund_inflow and diffusion >= config.DIFFUSION_LOW:
        return "低位修复"
    if not fund_inflow and strength_rank < 0.5:
        return "分歧退潮"
    if trend20 == 0 and strength_rank >= 0.6 and fund_inflow:
        return "冷启动"
    return "冷启动"   # 兜底
```

> ⚠️ 阈值是初版直觉值。执行后用历史数据回看微调(Phase 2)。

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_state_machine.py -v` → PASS
- [ ] **Step 5: commit** — `git commit -am "feat: 阶段状态机"`

---

## Task 7: 账户参数 `account.py`

**Files:** Create `src/data/account.py`; Test `tests/test_account.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_account.py
from src.data import account

def test_save_load(tmp_path):
    account.ACCOUNT_PATH = tmp_path / "account.json"
    data = {"total_assets": 3143.0, "debt": 1860.0, "cash": 0.0,
            "annual_rate": 0.035, "warning_line": 1.50, "liquidation_line": 1.30,
            "holdings": [{"code":"601688","name":"华泰证券","shares":159.21,"cost":22.7}]}
    account.save(data)
    got = account.load()
    assert got["debt"] == 1860.0
    assert got["holdings"][0]["name"] == "华泰证券"

def test_load_missing_returns_defaults(tmp_path):
    account.ACCOUNT_PATH = tmp_path / "nope.json"
    d = account.load()
    assert d["warning_line"] == 1.50 and d["holdings"] == []
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_account.py -v` → FAIL

- [ ] **Step 3: 写实现**

```python
# src/data/account.py
"""账户参数本地读写(data/account/account.json,不进 git)。金额单位:万元。"""
import json
from pathlib import Path
from src.compute import config

ACCOUNT_PATH = Path("data/account/account.json")

_DEFAULTS = {
    "total_assets": 0.0, "debt": 0.0, "cash": 0.0, "annual_rate": 0.035,
    "warning_line": config.RISK_WARNING_LINE,
    "liquidation_line": config.RISK_LIQUIDATION_LINE,
    "holdings": [],   # [{code,name,shares(万股),cost(元)}]
}

def load() -> dict:
    if not ACCOUNT_PATH.exists():
        return dict(_DEFAULTS)
    return {**_DEFAULTS, **json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))}

def save(data: dict) -> None:
    ACCOUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_account.py -v` → PASS
- [ ] **Step 5: commit** — `git commit -am "feat: 账户参数读写"`

---

## Task 8: AKShare 客户端 `akshare_client.py`

封装 + 缓存。**⚠️ 需对真实 API 核对**:AKShare 各函数返回的中文列名随版本变化,在 Step 3 前先跑一次真实调用打印 `df.columns`,据实填 `_COL`。

涉及函数(执行时确认签名):
- 日线:`ak.stock_zh_a_hist(symbol="600519", period="daily", start_date=..., end_date=..., adjust="qfq")`
- 个股资金流:`ak.stock_individual_fund_flow(stock="600519", market="sh")`
- 板块资金流排名:`ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")`

**Files:** Create `src/data/akshare_client.py`; Test `tests/test_akshare_client.py`

- [ ] **Step 1: 写失败测试(mock 掉 akshare,不打真网)**

```python
# tests/test_akshare_client.py
import pandas as pd
from unittest.mock import patch
from src.data import akshare_client as ac

def test_daily_hist_uses_cache(tmp_path, monkeypatch):
    from src.data import cache
    cache.CACHE_DIR = tmp_path
    fake = pd.DataFrame({"date":["2026-05-29"], "close":[10.0], "amount":[1e8]})
    with patch.object(ac, "_raw_daily_hist", return_value=fake) as m:
        d1 = ac.daily_hist("SH600519", "20260101", "20260529")  # 拉网+缓存
        d2 = ac.daily_hist("SH600519", "20260101", "20260529")  # 命中缓存
    assert m.call_count == 1                 # 第二次没再打网
    assert list(d1["close"]) == [10.0]
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_akshare_client.py -v` → FAIL

- [ ] **Step 3: 写实现**(`_raw_*` 真正调 akshare;公开函数负责缓存与规范化)

```python
# src/data/akshare_client.py
"""AKShare 封装。公开函数带缓存;_raw_* 真正打网,便于测试 mock。
规范化输出英文列:date, close, amount(成交额), pct(涨跌幅), main_net(主力净流入)。
⚠️ 真实列名按版本核对后在 _norm_* 调整。"""
import akshare as ak
import pandas as pd
from src.data import cache

def _raw_daily_hist(code6, start, end):
    return ak.stock_zh_a_hist(symbol=code6, period="daily",
                              start_date=start, end_date=end, adjust="qfq")

def _norm_daily(df):
    ren = {"日期":"date","收盘":"close","成交额":"amount","涨跌幅":"pct"}
    return df.rename(columns=ren)[[c for c in ["date","close","amount","pct"] if c in df.rename(columns=ren).columns]]

def daily_hist(symbol, start, end):
    key = f"{symbol}_{start}_{end}"
    hit = cache.read("akshare", "daily", key)
    if hit is not None:
        return hit
    df = _norm_daily(_raw_daily_hist(symbol[2:], start, end))
    cache.write("akshare", "daily", key, df)
    return df

def _raw_sector_fund_flow():
    return ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")

def sector_fund_flow():
    hit = cache.read("akshare", "sector_flow", "today")
    if hit is not None:
        return hit
    df = _raw_sector_fund_flow()   # 列名按真实核对后规范化
    cache.write("akshare", "sector_flow", "today", df)
    return df
```

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_akshare_client.py -v` → PASS
- [ ] **Step 5: 真网冒烟(手动一次,不进 CI)** — 跑 `python -c "from src.data.akshare_client import daily_hist; print(daily_hist('SH600519','20260501','20260529').tail())"`,据实修正 `_norm_daily` 列名。
- [ ] **Step 6: commit** — `git commit -am "feat: AKShare 客户端(带缓存)"`

---

## Task 9: Tushare 客户端 `tushare_client.py`

**⚠️ 需 `TUSHARE_TOKEN`(用户已获取,放 `.env`)。** Tushare 代码格式 `600519.SH`。

**Files:** Create `src/data/tushare_client.py`; Test `tests/test_tushare_client.py`

- [ ] **Step 1: 写失败测试(mock pro_api)**

```python
# tests/test_tushare_client.py
import pandas as pd
from unittest.mock import patch
from src.data import tushare_client as tc

def test_to_ts_code():
    assert tc.to_ts_code("SH600519") == "600519.SH"
    assert tc.to_ts_code("SZ000858") == "000858.SZ"

def test_daily_cached(tmp_path):
    from src.data import cache
    cache.CACHE_DIR = tmp_path
    fake = pd.DataFrame({"trade_date":["20260529"], "close":[1700.0], "amount":[1e6]})
    with patch.object(tc, "_raw_daily", return_value=fake) as m:
        tc.daily("SH600519", "20260101", "20260529")
        tc.daily("SH600519", "20260101", "20260529")
    assert m.call_count == 1
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_tushare_client.py -v` → FAIL

- [ ] **Step 3: 写实现**

```python
# src/data/tushare_client.py
"""Tushare Pro 封装。token 从 .env(TUSHARE_TOKEN)。"""
import os
import tushare as ts
from dotenv import load_dotenv
from src.data import cache

load_dotenv()
_pro = None

def _pro_api():
    global _pro
    if _pro is None:
        _pro = ts.pro_api(os.environ["TUSHARE_TOKEN"])
    return _pro

def to_ts_code(symbol: str) -> str:
    return f"{symbol[2:]}.{symbol[:2]}"

def _raw_daily(ts_code, start, end):
    return _pro_api().daily(ts_code=ts_code, start_date=start, end_date=end)

def daily(symbol, start, end):
    key = f"{symbol}_{start}_{end}"
    hit = cache.read("tushare", "daily", key)
    if hit is not None:
        return hit
    df = _raw_daily(to_ts_code(symbol), start, end)
    cache.write("tushare", "daily", key, df)
    return df
```

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_tushare_client.py -v` → PASS
- [ ] **Step 5: 真网冒烟** — 配好 `.env` 后 `python -c "from src.data.tushare_client import daily; print(daily('SH600519','20260501','20260529').head())"`
- [ ] **Step 6: commit** — `git commit -am "feat: Tushare 客户端(带缓存)"`

---

## Task 10: 收盘后编排 `pipeline/refresh.py`

把数据层 + 计算层串起来,产出一张"板块面板" DataFrame 缓存给展示层读。

**Files:** Create `src/pipeline/__init__.py`, `src/pipeline/refresh.py`; Test `tests/test_refresh.py`

- [ ] **Step 1: 写失败测试(mock 数据客户端,验证编排产出 schema)**

```python
# tests/test_refresh.py
import pandas as pd
from unittest.mock import patch
from src.pipeline import refresh

def test_build_sector_panel_schema():
    # 给两个板块的假指标,验证产出含状态标签列
    feats = pd.DataFrame({
        "relative_return":[0.02,-0.01], "volume_amp":[1.3,0.9],
        "fund_flow":[1e8,-1e8], "breadth":[0.7,0.3], "leader_contrib":[0.5,0.9],
        "diffusion":[0.7,0.3], "fund_inflow":[True,False],
        "trend20":[1,1], "consecutive_up":[2,1],
    }, index=["证券","半导体"])
    panel = refresh.build_sector_panel(feats)
    assert "strength" in panel.columns and "state" in panel.columns
    assert panel.loc["证券","state"] == "主升扩散"
```

- [ ] **Step 2: 跑测试确认失败** — `pytest tests/test_refresh.py -v` → FAIL

- [ ] **Step 3: 写实现**

```python
# src/pipeline/refresh.py
"""收盘后编排:拉数 → 算指标 → 状态机 → 缓存面板。
build_sector_panel 是纯函数,便于测试;refresh_eod 负责真实拉数填 features。"""
import pandas as pd
from src.compute import indicators, config
from src.compute.state_machine import classify_state
from src.data import cache

def build_sector_panel(features: pd.DataFrame) -> pd.DataFrame:
    out = features.copy()
    out["strength"] = indicators.sector_strength(features, config.STRENGTH_WEIGHTS)
    out["strength_rank"] = out["strength"].rank(pct=True)
    out["state"] = [
        classify_state(r.strength_rank, r.diffusion, r.fund_inflow,
                       r.volume_amp, r.trend20, r.consecutive_up)
        for r in out.itertuples()
    ]
    return out

def refresh_eod() -> pd.DataFrame:
    """真实流程:用 universe + akshare/tushare 计算 features → build_sector_panel → 缓存。
    Phase 1 先用 AKShare 板块资金流 + 成分股日线聚合得到 features 各列。"""
    # TODO(执行时按 Task 8/9 的客户端组装 features;此处编排骨架)
    raise NotImplementedError("接 akshare/tushare 客户端组装 features 后实现")
```

> 注:`refresh_eod` 的真实拉数组装在执行时依据 Task 8/9 的实际返回字段完成;`build_sector_panel`(核心逻辑)已被测试覆盖。

- [ ] **Step 4: 跑测试确认通过** — `pytest tests/test_refresh.py -v` → PASS
- [ ] **Step 5: commit** — `git commit -am "feat: 收盘编排(板块面板构建)"`

---

## Task 11: Streamlit 三页(MVP 展示层)

展示层只读 `build_sector_panel` 产出与 `account` / `risk_engine`,不直连外部 API。UI 难做自动化单测,**验收靠手动跑通**(见每页验收点)。

**Files:** Create `src/app/Home.py`, `src/app/pages/1_板块轮动排名.py`, `src/app/pages/2_风险驾驶舱.py`

- [ ] **Step 1: Home.py — 大盘云图(Plotly treemap)**

```python
# src/app/Home.py
import streamlit as st
import plotly.express as px
import pandas as pd
from src.pipeline.refresh import refresh_eod  # 或读缓存的面板

st.set_page_config(page_title="Polaris 北极星", layout="wide")
st.title("🧭 Polaris 北极星 · 大盘云图")

@st.cache_data(ttl=600)
def get_panel():
    # MVP:若 refresh_eod 未接通,读 data/cache 里的面板;开发期可用示例数据
    return refresh_eod()

panel = get_panel()
fig = px.treemap(
    panel.reset_index(names="sector"),
    path=["sector"], values="volume_amp",
    color="strength", color_continuous_scale="RdYlGn_r",
    custom_data=["state"],
)
fig.update_traces(texttemplate="%{label}<br>%{customdata[0]}")
st.plotly_chart(fig, use_container_width=True)
```

验收点:`streamlit run src/app/Home.py` 能打开,色块=板块,颜色=强弱,标签带状态。

- [ ] **Step 2: pages/1 板块轮动排名**

```python
# src/app/pages/1_板块轮动排名.py
import streamlit as st
from src.app.Home import get_panel

st.title("📊 板块轮动排名")
panel = get_panel().sort_values("strength", ascending=False)
st.dataframe(
    panel[["strength","strength_rank","diffusion","fund_flow","leader_contrib","state"]],
    use_container_width=True,
)
st.caption("输出的是状态识别,不是买卖信号。决策由人做。")
```

验收点:每板块一行,按强度排序,有状态列。

- [ ] **Step 3: pages/2 风险驾驶舱**

```python
# src/app/pages/2_风险驾驶舱.py
import streamlit as st
from src.data import account
from src.compute import risk_engine as rk

st.title("🛡️ 风险驾驶舱")
acct = account.load()

with st.form("acct"):
    c1, c2, c3 = st.columns(3)
    total = c1.number_input("总资产(万)", value=float(acct["total_assets"]))
    debt = c2.number_input("融资负债(万)", value=float(acct["debt"]))
    cash = c3.number_input("现金(万)", value=float(acct["cash"]))
    rate = c1.number_input("年利率", value=float(acct["annual_rate"]), format="%.3f")
    warn = c2.number_input("警戒线", value=float(acct["warning_line"]))
    liq  = c3.number_input("平仓线", value=float(acct["liquidation_line"]))
    code = c1.text_input("持仓代码", value=acct["holdings"][0]["code"] if acct["holdings"] else "601688")
    shares = c2.number_input("股数(万股)", value=float(acct["holdings"][0]["shares"]) if acct["holdings"] else 159.21)
    price = c3.number_input("现价(元)", value=19.7)
    saved = st.form_submit_button("保存并计算")

if saved:
    account.save({**acct, "total_assets":total,"debt":debt,"cash":cash,"annual_rate":rate,
                  "warning_line":warn,"liquidation_line":liq,
                  "holdings":[{"code":code,"name":"持仓","shares":shares,"cost":price}]})

gr = rk.guarantee_ratio(total, debt)
st.metric("当前担保比", f"{gr*100:.1f}%", delta=f"距平仓线 {(gr-liq)*100:.1f}pp")
st.metric("强平价(触平仓线)", f"{rk.liquidation_price(shares, cash, debt, liq):.2f} 元")

st.subheader("回撤情景")
st.dataframe(rk.drawdown_scenarios(price, shares, cash, debt, [0.05,0.10,0.20]))

st.subheader("加仓影响(仓位计算器)")
buy = st.number_input("拟融资买入(万)", value=200.0)
st.write(f"加仓后担保比:{rk.guarantee_ratio_after_buy(total, debt, buy)*100:.1f}%")

car = rk.interest_carry(debt, rate)
st.caption(f"利息拖累:{car['per_year']:.1f} 万/年 ≈ {car['per_month']:.2f} 万/月")
```

验收点:输入账户参数后,担保比、强平价、回撤表、加仓影响、利息全部正确显示并随输入变化。

- [ ] **Step 4: 手动跑通三页**,确认无报错。
- [ ] **Step 5: commit** — `git commit -am "feat: Streamlit MVP 三页(云图/排名/风控)"`

---

## Phase 2 / 3 路线图(本次不实现)

- **Phase 2:** 接 Tushare 干净历史 →
  - `src/compute/linkage_stats.py`:龙头带动系数、内部联动强度、事件回测(龙头放量大涨后 T+1/3/5 板块胜率/收益/回撤)。
  - 页面 `3_龙头联动分析.py`(龙头→中军→补涨链条)、`4_历史联动验证.py`。
  - 用历史回看微调 `state_machine` 阈值。
- **Phase 3:** 人气龙头自动识别(放量突破次数/领先天数)、盘中快照刷新、(验证后)掘金/QMT 实时、可选 LLM 中文盘面综述(建议 Claude API)。

---

## 自检(Self-Review)

- **Spec 覆盖:** 数据层(Task 2/3/8/9)、指标(5)、状态机(6)、风控引擎(4)、账户(7)、编排(10)、三页展示(11)= 设计 §3–§7 的 MVP 部分全覆盖;§7 的联动分析/历史验证两页明确归 Phase 2。
- **占位扫描:** `refresh_eod` 与 AKShare/Tushare 的 `_norm_*`/`_raw_*` 真实字段标注为"执行时对真实 API 核对"——这是真实工程步骤(外部 API schema 随版本变),非偷懒占位;其余纯函数均给出完整代码与测试。
- **类型一致:** `build_sector_panel` 用的列名(strength/strength_rank/diffusion/fund_inflow/volume_amp/trend20/consecutive_up/state)与 `state_machine.classify_state` 参数、测试一致;`risk_engine` 各函数签名与 Task 11 调用一致;金额单位统一"万元"、股数"万股"、价格"元"。
