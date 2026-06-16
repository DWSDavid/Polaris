from src.compute.glossary import TERMS, explain_term


def test_terms_present():
    for term in [
        "冷启动",
        "主升扩散",
        "龙头孤立",
        "高位加速",
        "分歧退潮",
        "低位修复",
        "主力分化",
        "拐点",
        "对冲度",
    ]:
        assert term in TERMS
        assert len(explain_term(term)) > 10


def test_unknown_term_returns_clear_placeholder():
    assert "暂无解释" in explain_term("不存在的词")
