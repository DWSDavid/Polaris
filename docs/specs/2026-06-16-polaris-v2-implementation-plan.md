# Polaris v2 Implementation Plan

> **执行说明(给 Codex):** 按 **v2.0 → v2.1 → v2.2 → v2.3(UI最后)** 顺序。纯逻辑走 TDD(失败测试→跑挂→实现→跑过→commit);数据/AI/UI 任务按"验收点 + 真网冒烟"。**每个 Task 单独 commit。** 标 ⚠️ 的地方先跑一次真实 API 核对中文列名再写死。**UI 美化整体放最后(v2.3)** —— v2.0/v2.1 的页面只求"能读、能 track",不追求好看。

**Goal:** 把 Polaris 从"市值静态伪信号"重做为"东财行业 + 真实资金流 + 中期波段 + AI 决策辅助"的可用决策台。

**Tech additions:** `stock_board_industry_*_em` / `stock_sector_fund_flow_rank` / `stock_zh_a_spot_em`(AKShare 东财);DeepSeek/OpenAI HTTP 客户端。

参考:[v2 设计](2026-06-16-polaris-v2-design.md)。保留 v1 的 `risk_engine`/`cache`/`account`/`config`。

---

## 前置冒烟(必须先过,否则 v2 全免谈)
- [ ] 在用户机器跑通东财四个接口,确认能拿到数 + 打印真实列名:
```python
import akshare as ak
print(ak.stock_board_industry_name_em().head())          # 行业实时
print(ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流").head())
print(ak.stock_zh_a_spot_em().head())                    # 全市场快照
print(ak.stock_board_industry_cons_em(symbol="银行").head())
```
确认无误再开 Task 1。把真实列名记到各 client 的 `_COLS`。

---

# v2.0 — 接东财 + 让它有用

## Task 1：东财行业数据客户端 `em_client.py`

**Files:** Create `src/data/em_client.py`;Test `tests/test_em_client.py`

- [ ] **Step 1: 写失败测试(mock akshare,验证缓存 + 规范化)**
```python
# tests/test_em_client.py
import pandas as pd
from unittest.mock import patch
from src.data import em_client as em

def test_industry_realtime_cached(tmp_path):
    from src.data import cache
    cache.CACHE_DIR = tmp_path
    fake = pd.DataFrame({"板块名称":["银行","电子"], "涨跌幅":[1.2,-0.8],
                         "成交额":[3e10,5e10], "主力净流入-净额":[2e8,-1e8]})
    with patch.object(em, "_raw_industry_realtime", return_value=fake) as m:
        d1 = em.industry_realtime()
        d2 = em.industry_realtime()
    assert m.call_count == 1
    assert {"sector","pct_chg","amount","main_net_inflow"} <= set(d1.columns)
    assert d1.loc[d1["sector"]=="银行","main_net_inflow"].iloc[0] == 2e8
```
- [ ] **Step 2: 跑挂** → FAIL
- [ ] **Step 3: 实现** —— `industry_realtime()`(规范化列:sector/pct_chg/amount/main_net_inflow)、`industry_fund_flow(period)`（period∈{今日,5日,10日}→多周期资金趋势）、`industry_cons(sector)`（成分股）、`industry_hist(sector,start,end)`、`market_spot()`（全市场快照:code/name/pct_chg/amount/turnover/total_mv）。实时类 TTL 10 分钟(缓存写入带时间戳,读时超 10 分钟视为 miss)。`_raw_*` 真打 akshare 便于 mock。⚠️ 真实列名按前置冒烟核对。
- [ ] **Step 4: 跑过** → PASS
- [ ] **Step 5: 真网冒烟** + 据实修列名
- [ ] **Step 6: commit** — `git commit -am "feat(v2.0): 东财行业数据客户端(实时/资金流/成分/历史/快照)"`

---

## Task 2：噪声过滤 + 股票池重建 `universe_v2.py`

**Files:** Create `src/data/universe_v2.py`;Test `tests/test_universe_v2.py`

- [ ] **Step 1: 写失败测试**
```python
# tests/test_universe_v2.py
import pandas as pd
from src.data.universe_v2 import filter_noise, pick_leaders

def test_filter_noise():
    df = pd.DataFrame({
        "name":["银行A","ST差","次新B","小盘C","龙头D"],
        "is_st":[False,True,False,False,False],
        "list_days":[2000,2000,120,2000,3000],
        "total_mv":[5e10,1e10,2e10,8e8,9e10],   # 小盘C 市值过小
        "amount":[3e9,1e9,2e9,1e7,5e9],          # 小盘C 成交过低
    })
    out = filter_noise(df, min_mv=2e9, min_amount=1e8, min_list_days=365)
    assert set(out["name"]) == {"银行A","龙头D"}   # 剔掉 ST/次新/小盘

def test_pick_leaders_blends_score():
    df = pd.DataFrame({"name":["大慢","小热"], "total_mv":[9e10,1e10],
                       "amount":[1e9,8e9], "turnover":[0.5,9.0]})
    out = pick_leaders(df, top_n=2)              # 综合分:市值+成交额+换手
    assert list(out["name"]) == ["大慢","小热"] or list(out["name"]) == ["小热","大慢"]
    assert "leader_score" in out.columns
```
- [ ] **Step 2: 跑挂** → FAIL
- [ ] **Step 3: 实现** —— `filter_noise(df, ...)` 按 ST/次新/市值/成交额硬过滤;`pick_leaders(df, top_n)` 综合分 = z(market_mv)+z(amount)+z(turnover) 排序取 TopN,加 `leader_score`、`leader_type="market_cap"`;`add_momentum_leaders(df, manual_list)` 手工人气龙头(`leader_type="momentum"`);`build_universe()` 遍历东财行业 `industry_cons` → 合并 `market_spot` 指标 → 过滤 → 选龙头 → 合并手工名单。
- [ ] **Step 4: 跑过** → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(v2.0): 噪声过滤 + 双龙头股票池重建(市值/成交额/换手综合分)"`

---

## Task 3：趋势持续 & 拐点 `trend_v2.py`

**Files:** Create `src/compute/trend_v2.py`;Test `tests/test_trend_v2.py`

- [ ] **Step 1: 写失败测试**
```python
# tests/test_trend_v2.py
import pandas as pd
from src.compute.trend_v2 import streak_days, inflow_streak_days, turning_point_flag

def test_streak_up():
    pct = pd.Series([ -1, 0.5, 1.0, 2.0, 0.3])   # 末尾连涨 3 天(0 不算)
    assert streak_days(pct) == 3

def test_inflow_streak():
    flow = pd.Series([1e8, 2e8, 3e8, 1e8])        # 连续 4 天净流入
    assert inflow_streak_days(flow) == 4

def test_turning_point_when_inflow_flips():
    flow = pd.Series([3e8, 2e8, 1e8, -5e7])        # 由流入转流出
    assert turning_point_flag(flow, pct=pd.Series([2,1,0.5,-1])) is True
```
- [ ] **Step 2: 跑挂** → FAIL
- [ ] **Step 3: 实现** —— `streak_days(pct)`(末尾连续同号天数,正为连涨负为连跌,返回带符号或正数+方向);`inflow_streak_days(flow)`(末尾连续净流入天数);`turning_point_flag(flow, pct)`(资金由流入转流出 或 量价背离 → True)。板块和龙头都用这套。
- [ ] **Step 4: 跑过** → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(v2.0): 趋势持续天数 + 拐点信号"`

---

## Task 4：板块中期(1–3周)趋势 & 资金 track 聚合 `sector_panel_v2.py`

**Files:** Create `src/pipeline/sector_panel_v2.py`;Test `tests/test_sector_panel_v2.py`

- [ ] **Step 1: 写失败测试** —— 给 mock 的 industry_realtime + 多周期 fund_flow + hist,产出每行业面板含:`pct_chg, amount, main_net_inflow, inflow_5d, inflow_10d, trend_days, turning_point, top_leaders, state`。断言列存在且 `state` 由真实指标经 `state_machine` 得出。
```python
# tests/test_sector_panel_v2.py
from src.pipeline.sector_panel_v2 import build_sector_panel_v2
def test_panel_schema(fake_inputs):   # fixture 提供 mock 数据
    panel = build_sector_panel_v2(**fake_inputs)
    need = {"pct_chg","main_net_inflow","inflow_10d","trend_days","turning_point","top_leaders","state"}
    assert need <= set(panel.columns)
```
- [ ] **Step 2: 跑挂** → FAIL
- [ ] **Step 3: 实现** —— 组装 features(relative_return=行业涨跌、fund_flow=主力净流入、inflow_5d/10d=多周期、breadth/diffusion=成分股上涨占比、leader_contrib、volume_amp=成交额/近20日均),调用现有 `indicators.sector_strength` + `state_machine.classify_state`,并附 `trend_days`(用 `trend_v2`)、`turning_point`。复用 v1 `build_sector_panel` 的 strength/rank 逻辑。
- [ ] **Step 4: 跑过** → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(v2.0): 东财板块中期趋势+多周期资金面板"`

---

## Task 5：名词解释词典 `glossary.py`

**Files:** Create `src/compute/glossary.py`;Test `tests/test_glossary.py`

- [ ] **Step 1: 写失败测试**
```python
# tests/test_glossary.py
from src.compute.glossary import explain_term, TERMS
def test_terms_present():
    for t in ["冷启动","主升扩散","龙头孤立","高位加速","分歧退潮","低位修复","主力分化","拐点","对冲度"]:
        assert t in TERMS and len(explain_term(t)) > 10
```
- [ ] **Step 2: 跑挂** → FAIL
- [ ] **Step 3: 实现** —— `TERMS: dict[str,str]` 每个名词一句人话定义 + `explain_term(t)`。供 UI 的 `?` tooltip 与 AI prompt 共用(AI 解释时引用此定义,避免乱讲)。
- [ ] **Step 4: 跑过** → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(v2.0): 名词解释词典"`

---

## Task 6：AI 层 `ai_client.py` + 板块综述

**Files:** Create `src/ai/__init__.py`、`src/ai/ai_client.py`、`src/ai/summarize.py`;Test `tests/test_ai.py`

- [ ] **Step 1: 写失败测试(mock HTTP,不打真网;验证 prompt 只含真实数值、解析正常)**
```python
# tests/test_ai.py
from unittest.mock import patch
from src.ai.summarize import build_sector_prompt, summarize_sector

def test_prompt_only_contains_given_numbers():
    facts = {"sector":"电力设备","state":"主升扩散","trend_days":9,
             "inflow_10d":12.3,"diffusion":0.72,"top_leaders":"阳光电源、宁德时代"}
    p = build_sector_prompt(facts)
    assert "电力设备" in p and "9" in p and "12.3" in p
    assert "禁止" in p or "不要编造" in p     # 硬约束写进 prompt

def test_summarize_parses_response():
    with patch("src.ai.ai_client.chat", return_value="电力设备主升扩散,已持续9天…"):
        out = summarize_sector({"sector":"电力设备","state":"主升扩散","trend_days":9,
                                "inflow_10d":12.3,"diffusion":0.72,"top_leaders":"阳光电源"})
    assert "电力设备" in out
```
- [ ] **Step 2: 跑挂** → FAIL
- [ ] **Step 3: 实现** ——
  - `ai_client.chat(messages)`:读 `DEEPSEEK_API_KEY`/`DEEPSEEK_MODEL`(默认),无则回退 `OPENAI_API_KEY`/`OPENAI_MODEL`;统一 OpenAI 兼容 `/chat/completions` HTTP(DeepSeek 兼容 OpenAI 协议)。无 key 时返回降级文案而非报错。
  - `summarize.build_sector_prompt(facts)`:**只插入传入的真实数值**,system prompt 写死「只能用我给的数字,禁止编造价格/资金/个股名,用中文一段话」。
  - `summarize_sector(facts)`:组 prompt → chat → 返回文本。
- [ ] **Step 4: 跑过** → PASS
- [ ] **Step 5: 真网冒烟**(配好 `DEEPSEEK_API_KEY`):跑一条真实综述,确认中文通顺、不编数。
- [ ] **Step 6: commit** — `git commit -am "feat(v2.0): AI 客户端(DeepSeek默认)+ grounded 板块综述"`

---

## Task 7：首页重做 —— 大盘云图修复 + 决策条(功能版,不美化)

**Files:** Modify `src/app/Home.py`;(可删 v1 里失效的 seed_static 渲染)

- [ ] **Step 1: 决策条** —— 顶部:取最强板块 facts → `summarize_sector` 渲染一段;非接通(无东财数据)时**标红**"行情未接入,以下为占位"。
- [ ] **Step 2: 大盘云图修复** —— 用 `industry_realtime`:`px.treemap(values=amount, color=pct_chg, color_continuous_scale="RdYlGn")`,label=行业名+state,hover 含主力净流入/趋势持续天数。**确认它能正常渲染(修 v1 不见了的问题)**。
- [ ] **Step 3: 主线候选表** —— 板块面板按 strength+trend_days 排序,列:行业/state/已持续天数/10日净流入/龙头;状态用文字(色板留到 v2.3)。
- [ ] **Step 4: 删除无意义代码块** —— 排查页面里渲染出的 `st.code`/裸代码/占位块并清掉(用户反馈"时不时冒出代码块")。
- [ ] **Step 5: 验收** —— `streamlit run src/app/Home.py`:云图回来了、决策条有真话、候选表能读、无莫名代码块。截图自检。
- [ ] **Step 6: commit** — `git commit -am "feat(v2.0): 首页大盘云图修复 + AI决策条 + 候选表"`

---

## Task 8：行业下钻页 `pages/1_行业下钻.py`

**Files:** Create `src/app/pages/1_行业下钻.py`(替代旧"板块轮动排名"主功能)

- [ ] **Step 1:** 行业下拉 → 显示:① 行业近 N 周走势 + **每日主力净流入柱**;② 「**趋势已持续 X 天**」+ 拐点提示;③ AI 该行业综述 + 名词 `?` 解释。
- [ ] **Step 2:** 龙头列表(来自 universe_v2 + market_spot):每行 连涨/连跌天数、涨跌、换手、成交额、相对板块强弱、角色;`st.expander` 展开看该龙头近期走势(line chart)与更多指标。
- [ ] **Step 3: 验收** —— 选不同行业,走势/资金/持续天数/龙头展开都正确。
- [ ] **Step 4: commit** — `git commit -am "feat(v2.0): 行业下钻页(中期趋势+资金track+龙头展开)"`

---

# v2.1 — 决策辅助

## Task 9：分化/对冲引擎 `divergence.py`

**Files:** Create `src/compute/divergence.py`;Test `tests/test_divergence.py`

- [ ] **Step 1: 写失败测试**
```python
# tests/test_divergence.py
import pandas as pd, numpy as np
from src.compute.divergence import correlation_matrix, hedge_score

def test_hedge_score_flags_opposite():
    # 银行与电子近20日收益负相关
    rets = pd.DataFrame({"银行":[1,-1,1,-1,1.0], "电子":[-1,1,-1,1,-1.0]})
    corr = correlation_matrix(rets)
    assert corr.loc["银行","电子"] < -0.5
    score = hedge_score(["银行","电子"], corr)   # 选了对冲的两个
    assert score > 0.5                           # 高对冲度 → 警告
```
- [ ] **Step 2: 跑挂** → FAIL
- [ ] **Step 3: 实现** —— `correlation_matrix(sector_returns)`(近 20 日行业收益相关性);`hedge_score(selected_sectors, corr)`(所选板块两两相关性里负相关的程度 → [0,1]);`hedge_warning(selected, corr)` 返回人话警告(哪两个在对冲)。标注"老登/新兴"分组辅助。
- [ ] **Step 4: 跑过** → PASS
- [ ] **Step 5: commit** — `git commit -am "feat(v2.1): 分化/对冲引擎(相关性+对冲度警告)"`

---

## Task 10：决策条增强 + 风控打通

**Files:** Modify `src/app/Home.py`、`src/app/pages/2_风险驾驶舱.py`

- [ ] **Step 1:** 首页加"候选篮子"多选(从龙头/行业选 3–4 只)→ 调 `hedge_score`,跨负相关 → 决策条**标红**"你在自我对冲:银行↔电子"。
- [ ] **Step 2:** 风险驾驶舱:选板块 + 拟加仓额 → `risk_engine.guarantee_ratio_after_buy` 情景 + 该板块 state/综述;3–5 等分加仓的担保比阶梯表(沿用 v1.5 Task F 设计)。
- [ ] **Step 3: 验收** —— 选对冲组合必警告;加仓情景实时算。
- [ ] **Step 4: commit** — `git commit -am "feat(v2.1): 候选对冲警告 + 风控加仓打通"`

---

## Task 11：AI 决策辅助综述

**Files:** Create `src/ai/advise.py`;Modify `Home.py`;Test `tests/test_advise.py`

- [ ] **Step 1: 写失败测试(mock chat)** —— `advise(facts)` 的 prompt 含:全板块 state/持续天数/资金、候选篮子、对冲度、风控担保比;输出含"主线建议/对冲提醒/该撤提醒"。断言 prompt 只含传入数值。
- [ ] **Step 2: 跑挂** → FAIL
- [ ] **Step 3: 实现** —— `build_advice_prompt(facts)` + `advise(facts)`,system 写死"基于数值给倾向性建议,不下单、不编价,提示风险与对冲,中文"。
- [ ] **Step 4: 跑过** → PASS
- [ ] **Step 5: 真网冒烟** + commit `feat(v2.1): AI 决策辅助综述(主线/对冲/拐点提醒)`

---

# v2.2 — 进阶(数据稳了再做)
- 龙头联动历史胜率(龙头放量大涨后中军 T+1/3/5 跟涨概率)。
- 拐点信号打磨(量价背离、资金衰减多因子)。
- "还能走多久"历史类比:相似 state+持续天数 的历史样本,之后中位持续天数/收益分布。

---

# v2.3 — UI 设计美化(用户要求:放最后)
- [ ] 统一设计语言(治"太抽"):状态色板、卡片、间距、字体层级。
- [ ] 大盘云图视觉打磨;龙头展开交互;名词 `?` tooltip 视觉。
- [ ] 全表 column_config(进度条/色块/单位);数据时间戳展示。
- [ ] 复查并清除一切无意义代码块/占位。
- 验收:整体观感不再"抽",一屏能读出结论。

---

## 自检
- **覆盖根因:** v2.0 Task1–4 用东财真实数据替掉 seed_static 伪信号(治"没用");Task5/6 名词解释+AI综述(治"没解释/不会判断持续多久");Task7 修大盘云图+删代码块(治"云图不见/莫名代码块")。
- **覆盖痛点:** v2.1 Task9/10 分化对冲警告(治"利润被对冲");Task10 风控打通(护担保比)。
- **顺序:** 先真→再决策辅助→最后才美化 UI(尊重"现在太抽,最后再优化")。
- **类型一致:** 板块面板列名(state/trend_days/turning_point/main_net_inflow/inflow_10d/top_leaders)在 Task4/7/8/11 一致;AI facts 字典键在 Task6/11 一致;沿用 v1 `risk_engine`/`state_machine`/`indicators` 签名不变。
