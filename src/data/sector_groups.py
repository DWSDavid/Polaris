"""Roll fine-grained Eastmoney sectors up to decision-level groups."""

from __future__ import annotations

import pandas as pd

SECTOR_GROUPS: dict[str, str] = {
    "钨": "原材料",
    "钼": "原材料",
    "稀土": "原材料",
    "小金属": "原材料",
    "金属新材料": "原材料",
    "有色金属": "原材料",
    "玻璃玻纤": "原材料",
    "玻纤制造": "原材料",
    "玻璃制造": "原材料",
    "非金属材料": "原材料",
    "橡胶助剂": "原材料",
    "基础化工": "原材料",
    "钢铁": "原材料",
    "煤炭": "能源",
    "石油": "能源",
    "油气": "能源",
    "电力": "公用事业",
    "公用事业": "公用事业",
    "银行": "金融",
    "证券": "金融",
    "保险": "金融",
    "非银金融": "金融",
    "房地产": "地产",
    "地产": "地产",
    "半导体": "半导体",
    "半导体设备": "半导体",
    "元件": "电子",
    "其他电子": "电子",
    "印制电路板": "电子",
    "被动元件": "电子",
    "消费电子": "电子",
    "光学光电子": "电子",
    "电子": "电子",
    "通信": "通信",
    "通信设备": "通信",
    "通信线缆及配套": "通信",
    "计算机": "计算机",
    "软件开发": "计算机",
    "互联网服务": "计算机",
    "传媒": "传媒",
    "游戏": "传媒",
    "医药": "医药",
    "医疗": "医药",
    "中药": "医药",
    "化学制药": "医药",
    "生物制品": "医药",
    "电力设备": "机械/电力设备",
    "锂电池": "机械/电力设备",
    "锂电专用设备": "机械/电力设备",
    "电池": "机械/电力设备",
    "其他电源设备": "机械/电力设备",
    "激光设备": "机械/电力设备",
    "机械设备": "机械/电力设备",
    "专用设备": "机械/电力设备",
    "通用设备": "机械/电力设备",
    "汽车": "汽车",
    "汽车零部件": "汽车",
    "消费": "消费",
    "食品饮料": "消费",
    "白酒": "消费",
    "家电": "消费",
    "商业百货": "消费",
    "农牧饲渔": "消费",
    "军工": "军工",
    "国防军工": "军工",
}

SUM_COLUMNS = (
    "amount",
    "main_net_inflow",
    "inflow_5d",
    "inflow_10d",
    "total_mv",
    "up_count",
    "down_count",
    "stock_count",
)
WEIGHTED_COLUMNS = (
    "pct_chg",
    "diffusion",
    "strength",
    "strength_rank",
    "trend_days",
    "volume_amp",
    "leader_contrib",
    "position_in_box",
    "mainline_score",
)


def map_to_group(name: str) -> str:
    text = str(name or "").strip()
    normalized = _strip_suffix(text)
    for key, group in SECTOR_GROUPS.items():
        if normalized == key or normalized.startswith(key) or key in normalized:
            return group
    return "其他"


def aggregate_to_groups(fine_df: pd.DataFrame) -> pd.DataFrame:
    if fine_df.empty:
        return fine_df.copy()
    frame = fine_df.copy()
    if "group" not in frame.columns:
        frame["group"] = frame["sector"].map(map_to_group)
    if "stock_count" not in frame.columns:
        if {"up_count", "down_count"} <= set(frame.columns):
            frame["stock_count"] = (
                pd.to_numeric(frame["up_count"], errors="coerce").fillna(0)
                + pd.to_numeric(frame["down_count"], errors="coerce").fillna(0)
            )
        else:
            frame["stock_count"] = 1

    rows = []
    for group, part in frame.groupby("group", dropna=False):
        row = {"group": str(group), "sector": str(group)}
        children = part["sector"].dropna().astype(str).drop_duplicates().tolist()
        row["children"] = children
        row["child_count"] = len(children)
        for column in SUM_COLUMNS:
            if column in part.columns:
                row[column] = float(pd.to_numeric(part[column], errors="coerce").fillna(0).sum())
        weights = _weights(part)
        for column in WEIGHTED_COLUMNS:
            if column in part.columns:
                row[column] = _weighted_average(part[column], weights)
        if "turning_point" in part.columns:
            row["turning_point"] = bool(part["turning_point"].fillna(False).astype(bool).any())
        if "fund_inflow" in part.columns:
            row["fund_inflow"] = bool(part["fund_inflow"].fillna(False).astype(bool).any())
        if "top_leaders" in part.columns:
            row["top_leaders"] = _join_unique(part["top_leaders"])
        elif "leading_stock" in part.columns:
            row["top_leaders"] = _join_unique(part["leading_stock"])
        if "state" in part.columns:
            row["state"] = _representative_state(part)
        if "data_quality" in part.columns:
            row["data_quality"] = "group_rollup"
        row["sample_note"] = "样本少，谨慎" if float(row.get("stock_count", 0)) < 20 else "样本充足"
        rows.append(row)
    out = pd.DataFrame(rows)
    if "strength" in out.columns:
        out["strength_rank"] = pd.to_numeric(out["strength"], errors="coerce").rank(pct=True)
        out = out.sort_values(["strength", "amount"], ascending=False, na_position="last")
    elif "amount" in out.columns:
        out = out.sort_values("amount", ascending=False, na_position="last")
    return out.reset_index(drop=True)


def aggregate_timeline_to_groups(timeline: pd.DataFrame) -> pd.DataFrame:
    if timeline.empty:
        return timeline.copy()
    frame = timeline.copy()
    if "date" not in frame.columns:
        return aggregate_to_groups(frame)

    rows = []
    for date, part in frame.groupby("date", dropna=False):
        rolled = aggregate_to_groups(part)
        if rolled.empty:
            continue
        rolled["date"] = date
        rows.append(rolled)
    if not rows:
        return pd.DataFrame()

    out = pd.concat(rows, ignore_index=True)
    if "strength" in out.columns:
        out["rank"] = (
            pd.to_numeric(out["strength"], errors="coerce")
            .groupby(out["date"])
            .rank(method="first", ascending=False)
            .astype(int)
        )
    elif "amount" in out.columns:
        out["rank"] = (
            pd.to_numeric(out["amount"], errors="coerce")
            .groupby(out["date"])
            .rank(method="first", ascending=False)
            .astype(int)
        )
    sort_columns = ["date", "rank"] if "rank" in out.columns else ["date", "sector"]
    return out.sort_values(sort_columns).reset_index(drop=True)


def _strip_suffix(text: str) -> str:
    for suffix in ("Ⅰ", "Ⅱ", "Ⅲ", "IV", "II", "III"):
        text = text.replace(suffix, "")
    return text.strip()


def _weights(frame: pd.DataFrame) -> pd.Series:
    if "stock_count" in frame.columns:
        weights = pd.to_numeric(frame["stock_count"], errors="coerce").fillna(0).clip(lower=1)
    elif "amount" in frame.columns:
        weights = pd.to_numeric(frame["amount"], errors="coerce").fillna(0).clip(lower=1)
    else:
        weights = pd.Series(1.0, index=frame.index)
    return weights


def _weighted_average(values: pd.Series, weights: pd.Series) -> float:
    nums = pd.to_numeric(values, errors="coerce")
    mask = nums.notna()
    if not mask.any():
        return 0.0
    used_weights = weights[mask]
    denominator = float(used_weights.sum())
    if denominator == 0:
        return float(nums[mask].mean())
    return float((nums[mask] * used_weights).sum() / denominator)


def _join_unique(values: pd.Series, limit: int = 5) -> str:
    names = []
    for value in values.dropna().astype(str):
        for name in value.replace("、", ",").split(","):
            clean = name.strip()
            if clean and clean not in names:
                names.append(clean)
            if len(names) >= limit:
                return "、".join(names)
    return "、".join(names)


def _representative_state(part: pd.DataFrame) -> str:
    if "strength" in part.columns:
        ordered = part.assign(_strength=pd.to_numeric(part["strength"], errors="coerce")).sort_values(
            "_strength", ascending=False
        )
        if not ordered.empty:
            return str(ordered.iloc[0].get("state", "未知"))
    return str(part["state"].dropna().astype(str).iloc[0]) if part["state"].notna().any() else "未知"
