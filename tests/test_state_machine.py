from src.compute.state_machine import classify_state


def test_zhusheng_kuosan():
    state = classify_state(
        strength_rank=0.9,
        diffusion=0.7,
        fund_inflow=True,
        vol_amp=1.3,
        trend20=1,
        consecutive_up=2,
    )
    assert state == "主升扩散"


def test_longtou_guli():
    state = classify_state(
        strength_rank=0.8,
        diffusion=0.3,
        fund_inflow=True,
        vol_amp=1.5,
        trend20=1,
        consecutive_up=1,
    )
    assert state == "龙头孤立"


def test_gaowei_jiasu():
    state = classify_state(
        strength_rank=0.97,
        diffusion=0.65,
        fund_inflow=True,
        vol_amp=2.4,
        trend20=1,
        consecutive_up=5,
    )
    assert state == "高位加速"
