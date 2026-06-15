"""Map sector features to coarse market-cycle states."""

from src.compute import config


def classify_state(
    strength_rank,
    diffusion,
    fund_inflow,
    vol_amp,
    trend20,
    consecutive_up,
):
    if (
        strength_rank >= 0.95
        and vol_amp >= config.VOLUME_BLOWOFF
        and consecutive_up >= 4
    ):
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
    return "冷启动"
