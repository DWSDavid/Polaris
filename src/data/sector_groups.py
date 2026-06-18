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
    "工业金属": "原材料",
    "化学制品": "原材料",
    "化学原料": "原材料",
    "其他化学制品": "原材料",
    "其他化学原料": "原材料",
    "农化制品": "原材料",
    "氟化工": "原材料",
    "塑料": "原材料",
    "改性塑料": "原材料",
    "合成树脂": "原材料",
    "膜材料": "原材料",
    "化学纤维": "原材料",
    "有机硅": "原材料",
    "无机盐": "原材料",
    "磷肥及磷化工": "原材料",
    "钾肥": "原材料",
    "铜": "原材料",
    "铝": "原材料",
    "铅锌": "原材料",
    "锂": "原材料",
    "能源金属": "原材料",
    "贵金属": "原材料",
    "黄金": "原材料",
    "金属制品": "原材料",
    "磁性材料": "原材料",
    "磨具磨料": "原材料",
    "钢铁": "原材料",
    "普钢": "原材料",
    "煤炭": "能源",
    "动力煤": "能源",
    "石油": "能源",
    "油气": "能源",
    "炼化及贸易": "能源",
    "炼油化工": "能源",
    "电力": "公用事业",
    "火力发电": "公用事业",
    "水力发电": "公用事业",
    "热力服务": "公用事业",
    "公用事业": "公用事业",
    "银行": "金融",
    "城商行": "金融",
    "证券": "金融",
    "保险": "金融",
    "多元金融": "金融",
    "非银金融": "金融",
    "房地产": "地产",
    "地产": "地产",
    "住宅开发": "地产",
    "半导体": "半导体",
    "半导体设备": "半导体",
    "数字芯片设计": "半导体",
    "模拟芯片设计": "半导体",
    "集成电路封测": "半导体",
    "集成电路制造": "半导体",
    "分立器件": "半导体",
    "元件": "电子",
    "其他电子": "电子",
    "印制电路板": "电子",
    "被动元件": "电子",
    "消费电子": "电子",
    "光学光电子": "电子",
    "面板": "电子",
    "LED": "电子",
    "电子": "电子",
    "通信": "通信",
    "通信设备": "通信",
    "通信线缆及配套": "通信",
    "计算机": "计算机",
    "IT服务": "计算机",
    "软件开发": "计算机",
    "互联网服务": "计算机",
    "垂直应用软件": "计算机",
    "横向通用软件": "计算机",
    "安防设备": "计算机",
    "传媒": "传媒",
    "游戏": "传媒",
    "广告营销": "传媒",
    "营销代理": "传媒",
    "数字媒体": "传媒",
    "医药": "医药",
    "医疗": "医药",
    "中药": "医药",
    "化学制药": "医药",
    "生物制品": "医药",
    "化学制剂": "医药",
    "原料药": "医药",
    "体外诊断": "医药",
    "电力设备": "机械/电力设备",
    "电网设备": "机械/电力设备",
    "电网自动化设备": "机械/电力设备",
    "输变电设备": "机械/电力设备",
    "配电设备": "机械/电力设备",
    "光伏设备": "机械/电力设备",
    "光伏加工设备": "机械/电力设备",
    "光伏辅材": "机械/电力设备",
    "风电设备": "机械/电力设备",
    "风电零部件": "机械/电力设备",
    "逆变器": "机械/电力设备",
    "锂电池": "机械/电力设备",
    "锂电专用设备": "机械/电力设备",
    "电池": "机械/电力设备",
    "其他电源设备": "机械/电力设备",
    "激光设备": "机械/电力设备",
    "机械设备": "机械/电力设备",
    "自动化设备": "机械/电力设备",
    "其他自动化设备": "机械/电力设备",
    "工控设备": "机械/电力设备",
    "机器人": "机械/电力设备",
    "仪器仪表": "机械/电力设备",
    "能源及重型设备": "机械/电力设备",
    "电机": "机械/电力设备",
    "工程机械": "机械/电力设备",
    "工程机械整机": "机械/电力设备",
    "机床工具": "机械/电力设备",
    "轨交设备": "机械/电力设备",
    "制冷空调设备": "机械/电力设备",
    "专用设备": "机械/电力设备",
    "通用设备": "机械/电力设备",
    "汽车": "汽车",
    "汽车零部件": "汽车",
    "底盘与发动机系统": "汽车",
    "车身附件及饰件": "汽车",
    "乘用车": "汽车",
    "商用车": "汽车",
    "消费": "消费",
    "食品饮料": "消费",
    "白酒": "消费",
    "家电": "消费",
    "家用电器": "消费",
    "空调": "消费",
    "商业百货": "消费",
    "商贸零售": "商贸服务",
    "一般零售": "商贸服务",
    "社会服务": "商贸服务",
    "专业服务": "商贸服务",
    "农牧饲渔": "消费",
    "农林牧渔": "农业",
    "军工": "军工",
    "国防军工": "军工",
    "航空装备": "军工",
    "航天装备": "军工",
    "航海装备": "军工",
    "建筑材料": "建筑建材",
    "建筑装饰": "建筑建材",
    "专业工程": "建筑建材",
    "其他专业工程": "建筑建材",
    "工程咨询服务": "建筑建材",
    "基础建设": "建筑建材",
    "装修建材": "建筑建材",
    "交通运输": "交通运输",
    "航运港口": "交通运输",
    "航运": "交通运输",
    "物流": "交通运输",
    "线缆部件及其他": "交通运输",
    "环保": "环保",
    "环境治理": "环保",
    "固废治理": "环保",
    "环保设备": "环保",
    "轻工制造": "轻工纺服",
    "纺织服饰": "轻工纺服",
    "服装家纺": "轻工纺服",
    "包装印刷": "轻工纺服",
    "家居用品": "轻工纺服",
}

KEYWORD_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("半导体", ("芯片", "集成电路", "封测", "分立器件", "半导体")),
    ("电子", ("面板", "LED", "光学", "电子", "元件", "磁性材料", "照明设备")),
    ("计算机", ("IT服务", "软件", "互联网服务", "安防", "电商")),
    ("通信", ("通信", "电信运营")),
    ("医药", ("医疗", "医药", "制剂", "原料药", "疫苗", "诊断", "生物制品", "医院", "药店", "血液制品", "动物保健", "医美")),
    ("金融", ("银行", "证券", "保险", "多元金融", "城商行", "农商行", "金融", "期货", "资产管理", "信托")),
    ("地产", ("地产", "住宅开发", "物业")),
    ("汽车", ("汽车", "乘用车", "商用车", "载货车", "载客车", "轮胎", "摩托车", "底盘", "车身")),
    ("军工", ("军工", "航空装备", "航天", "航海", "兵装", "民爆")),
    ("机械/电力设备", ("设备", "机器人", "机床", "仪器仪表", "电机", "风电整机", "光伏加工", "光伏主材", "农用机械")),
    ("公用事业", ("发电", "燃气", "电能综合", "热力", "水力", "火力", "核力")),
    ("能源", ("煤", "焦煤", "焦炭", "油服", "油田服务", "石化", "炼油", "炼化")),
    ("环保", ("环保", "环境", "水务", "水治理", "固废", "大气治理")),
    ("交通运输", ("交通运输", "航运", "航空机场", "航空运输", "铁路公路", "铁路运输", "快递", "物流", "港口", "高速公路", "机场", "公交", "公路货运", "供应链服务")),
    ("建筑建材", ("建筑", "建材", "水泥", "装修", "装饰", "工程", "基建", "园林", "板材", "房屋建设", "防水材料", "管材", "瓷砖地板", "卫浴制品")),
    ("农业", ("农业", "农林牧渔", "养殖", "生猪", "种植", "农产品", "饲料", "林业", "种子", "粮油", "食用菌", "渔业", "海洋捕捞")),
    ("消费", ("食品", "饮料", "乳品", "调味", "发酵", "家电", "彩电", "空调", "冰洗", "美容护理", "旅游", "景区", "休闲食品", "啤酒", "零食", "化妆品", "个护", "洗护", "厨卫", "厨房", "肉制品", "果蔬", "酒店", "餐饮", "体育", "娱乐用品", "饰品", "钟表珠宝", "酒类", "保健品", "熟食", "卫浴电器")),
    ("商贸服务", ("零售", "百货", "贸易", "专业服务", "社会服务", "检测服务", "超市", "教育", "培训", "连锁", "租赁", "会展", "人力资源")),
    ("传媒", ("传媒", "广告", "营销", "影视", "动漫", "出版", "游戏", "门户网站", "电视广播", "媒体", "院线")),
    ("轻工纺服", ("轻工", "纺织", "服装", "家纺", "造纸", "纸包装", "包装印刷", "文娱用品", "鞋帽", "家居", "特种纸", "大宗用纸", "生活用纸", "文化用品", "印刷", "棉纺", "印染")),
    ("原材料", ("原材料", "化工", "氯碱", "农药", "聚氨酯", "橡胶", "白银", "黄金", "铜", "铝", "镍", "钴", "锂", "铅锌", "钢", "特钢", "冶钢", "涂料", "油墨", "胶黏剂", "硅料", "硅片", "铁矿", "氮肥", "钛白粉", "复合肥", "粘胶", "耐火材料", "氨纶", "纯碱", "锦纶", "涤纶", "炭黑", "长材", "辅料", "金属", "塑料", "玻璃", "煤化工")),
    ("综合", ("综合",)),
)

SECTOR_GROUP_DESCRIPTIONS: dict[str, str] = {
    "半导体": "芯片设计、制造、封测、设备等半导体产业链。",
    "电子": "面板、LED、元件、消费电子、光学光电子等电子制造方向。",
    "计算机": "软件、IT 服务、互联网服务、安防和信息化应用。",
    "通信": "通信设备、线缆、电信运营等通信基础设施方向。",
    "医药": "药品、医疗服务、诊断、疫苗、血制品和医美相关方向。",
    "金融": "银行、证券、保险、多元金融、期货、信托等金融服务。",
    "地产": "房地产开发、住宅、物业经营等地产链条。",
    "汽车": "整车、零部件、轮胎、底盘、商用车和摩托车。",
    "军工": "航空、航天、航海、兵装和国防军工相关方向。",
    "机械/电力设备": "自动化、机器人、电网、光伏、风电、锂电、工程机械等设备方向。",
    "公用事业": "发电、燃气、热力、水电、核电等偏防守现金流方向。",
    "能源": "煤炭、焦炭、油气、油服、石化炼化等能源链条。",
    "环保": "环保设备、环境治理、水务、固废、大气治理。",
    "交通运输": "航空、航运、港口、铁路、公路、物流、快递和供应链服务。",
    "建筑建材": "建筑施工、基建、市政、建材、水泥、装修装饰等方向。",
    "农业": "养殖、种植、饲料、粮油、种子、农产品加工和渔业。",
    "消费": "食品饮料、家电、美容护理、旅游酒店、珠宝饰品等终端消费。",
    "商贸服务": "零售、百货、贸易、教育培训、会展、人力资源和专业服务。",
    "传媒": "影视、广告营销、出版、游戏、门户网站、电视广播等内容方向。",
    "轻工纺服": "造纸、包装、家居、纺织服装、文娱用品等轻工消费制造。",
    "原材料": "钨、稀土、铜铝、钢铁、化工、玻璃、橡胶等上游材料。",
    "综合": "东财综合类，通常是跨多行业或业务复杂公司；不参与主线领跑，只作明细保留。",
    "其他": "暂未识别到稳定归属的细分行业；正常情况下不应进入主线领跑。",
}

VAGUE_GROUPS = ("综合", "其他")

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
    for group, keywords in KEYWORD_GROUPS:
        if any(keyword in normalized for keyword in keywords):
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
        if "trend_days" in part.columns:
            row["trend_days"] = _representative_trend_days(part, weights)
            row["trend_days_source"] = _representative_child(part)
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


def filter_actionable_groups(
    frame: pd.DataFrame,
    column: str = "sector",
    excluded: tuple[str, ...] = VAGUE_GROUPS,
) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return frame.copy()
    return frame.loc[~frame[column].fillna("").astype(str).isin(excluded)].copy()


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


def _representative_trend_days(part: pd.DataFrame, weights: pd.Series) -> int:
    dominant = _dominant_row(part)
    value = pd.to_numeric(pd.Series([dominant.get("trend_days")]), errors="coerce").iloc[0]
    if pd.notna(value):
        return int(round(float(value)))
    return int(round(_weighted_average(part["trend_days"], weights)))


def _representative_child(part: pd.DataFrame) -> str:
    dominant = _dominant_row(part)
    return str(dominant.get("sector", ""))


def _dominant_row(part: pd.DataFrame) -> pd.Series:
    if part.empty:
        return pd.Series(dtype=object)
    for column in ("strength", "mainline_score", "amount"):
        if column in part.columns:
            ordered = part.assign(
                _dominant=pd.to_numeric(part[column], errors="coerce")
            ).sort_values("_dominant", ascending=False, na_position="last")
            if not ordered.empty:
                return ordered.iloc[0]
    return part.iloc[0]


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
