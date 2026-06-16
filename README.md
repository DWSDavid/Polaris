# Polaris 北极星

**A股板块轮动与龙头联动决策平台** — 单用户、收盘级(EOD)、人在环中的决策仪表盘。

> 它不预测、不自动交易。只回答四件事:
> **钱往哪走 / 龙头是否真带动 / 现在是哪个阶段 / 这一笔会不会动到我的担保比。**

面向一个**有杠杆(融资融券)、高集中度、"不能亏"**的个人账户。因此除了进攻(板块轮动 + 龙头联动),
系统的脊柱是**风控层**(担保比 / 强平线 / 仓位)。

---

## 文档(先读这两份)

- 设计 spec:[`docs/specs/2026-06-15-polaris-design.md`](docs/specs/2026-06-15-polaris-design.md)
- 实施计划(给执行者按步骤做):[`docs/specs/2026-06-15-polaris-implementation-plan.md`](docs/specs/2026-06-15-polaris-implementation-plan.md)

## 快速开始

```bash
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
copy .env.example .env                              # 填入 TUSHARE_TOKEN
streamlit run src/app/Home.py
```

AI 总结默认走 DeepSeek。在 `.env` 中填入 `DEEPSEEK_API_KEY` 即可；`DEEPSEEK_MODEL` 默认是 `deepseek-v4-flash`，用于快速解释和盘面总结。需要备用 ChatGPT 时再填 `OPENAI_API_KEY`。

## 五个页面

1. **大盘云图** — 板块热力图(强弱/成交额/资金流/扩散率/领涨龙头)
2. **板块轮动排名** — 决策页,输出"状态"而非买卖信号
3. **龙头联动分析** — 单板块的 龙头→中军→补涨 链条
4. **历史联动验证** — 把"感觉有联动"变成历史胜率
5. **风险驾驶舱** — 担保比 / 强平价模拟 / 回撤情景 / 仓位计算器 / 利息拖累

## 数据

- **AKShare**(免费,MVP 主力)+ **Tushare Pro**(需 `TUSHARE_TOKEN`,干净历史/资金流)
- 股票池种子:[`data/universe/sector_leaders_seed.xlsx`](data/universe/sector_leaders_seed.xlsx)(中证11一级行业 × 市值 Top10)
- 拉取数据缓存到 `data/cache/`(parquet),账户参数在 `data/account/`(均不进 git)

## 技术栈

Python 3.10+ · pandas · Streamlit · Plotly · AKShare/Tushare · pytest
