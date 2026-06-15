# Polaris V1.5 数据源策略：AKShare 优先，Tushare 作为稳定性升级

## 当前结论

V1.5/V2 先以 AKShare 为主，不建议立刻充值 Tushare Pro。

原因：

- Polaris 现在最需要的是 EOD 日线、涨跌幅、成交额、趋势、连涨、板块聚合，这些 AKShare 可以覆盖。
- AKShare 不需要 token，适合快速迭代产品逻辑和 UI。
- Tushare 当前免费权限可用性有限，充值的价值主要在稳定批量数据、估值/换手字段、复权因子、频率限制和长期可回测数据质量。

## 已核对的 AKShare 能力

真实调用 `ak.stock_zh_a_hist(symbol="600519", period="daily", start_date="20240603", end_date="20240607", adjust="qfq")` 曾返回以下列：

- `日期`
- `股票代码`
- `开盘`
- `收盘`
- `最高`
- `最低`
- `成交量`
- `成交额`
- `振幅`
- `涨跌幅`
- `涨跌额`
- `换手率`

当前代码已把 AKShare 日线归一成：

- `trade_date`
- `close`
- `pct_chg`
- `amount`

本轮实现还补了：

- 用完整日线序列计算 `trend20`
- 用完整涨跌幅序列计算 `consecutive_up`
- AKShare 日线失败时诚实回退 `seed_static`
- `signals_confirmed=False` 标记静态兜底，不把占位状态当真实信号
- AKShare individual fund flow 可用时，按板块聚合 `主力净流入-净额`
- AKShare fund flow 不可用时，继续用日线成交额方向代理，主流程不断

## AKShare 当前风险

AKShare 的最大问题不是字段不够，而是稳定性。

本机烟测结果：

- `stock_zh_a_hist` 曾成功返回真实日线列。
- 之后同一接口多次出现 `RemoteDisconnected`。
- `stock_individual_fund_flow` 也出现过远端断连。
- `stock_sector_fund_flow_rank` 在当前 shell 编码/接口组合下不稳定。

所以产品层必须保留：

- retry
- cache
- fallback
- `signals_confirmed`
- 数据源/数据质量展示

## Tushare 的不可替代性

Tushare 不是现在必须，但它在以下场景明显有价值：

- 稳定的全市场批量 EOD：官方建议按 `trade_date` 拉日线，比逐股票循环更高效。
- `daily_basic` 等估值和换手数据：PE/PB/总市值/流通市值/换手率等字段适合做更认真排序。
- 复权和长期历史：`pro_bar`、复权因子等更适合回测和跨周期一致性。
- API 权限和频率：积分越高，可用接口和调用频率越好。
- 数据一致性：比网页接口型数据源更适合做每日自动任务。

官方参考：

- Tushare 权限说明：https://tushare.pro/document/1?doc_id=108
- Tushare 积分与调用频次：https://tushare.pro/document/1?doc_id=290
- Tushare 常见问题和频率限制：https://tushare.pro/document/1?doc_id=122
- Tushare 高效调取日线建议：https://tushare.pro/document/1?doc_id=230
- Tushare `pro_bar` 文档：https://tushare.pro/wctapi/documents/109.md

## 充值建议

暂时不充值：

- 你现在还在验证 Polaris 的信息架构、解释质量、风险驾驶舱和 V2 工作流。
- AKShare 足够支撑 V1.5 的真实日线、趋势、连涨和部分资金流探索。
- 先把“哪些信号真的有用”验证出来，再决定买稳定数据。

可以考虑充值的触发点：

- 你要每天稳定跑完整 110 股票池或更大股票池。
- 你要把估值、换手、市值、复权、历史回测做成核心功能。
- AKShare 连续几天不稳定，影响你正常使用。
- 你要让 Polaris 从个人实验变成稳定的日更决策系统。

初步建议：

- V1.5/V2 alpha：AKShare 优先，不充值。
- V2 beta：如果每天都在用，并且需要稳定日更，再考虑 Tushare 2000+。
- 真正要做长期回测、自动日报、全市场扫描，再考虑更高积分档。
