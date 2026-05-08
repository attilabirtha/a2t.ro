from __future__ import annotations

from dataclasses import dataclass

from .models import CampaignRow, Policy


@dataclass(frozen=True)
class Recommendation:
    campaign: str
    channel: str
    current_budget: float
    recommended_budget: float
    recommendation: str
    priority: int
    reason: str


@dataclass(frozen=True)
class PacingSnapshot:
    report_date: str
    month_day: int
    month_days: int
    monthly_budget: float
    spend_mtd: float
    spend_expected: float
    pacing_ratio: float
    forecast_month_end: float
    remaining_budget: float
    forecast_ratio_vs_budget: float


def calc_pacing(
    report_date: str,
    month_day: int,
    month_days: int,
    spend_mtd: float,
    policy: Policy,
) -> PacingSnapshot:
    spend_expected = policy.monthly_budget_ron * (month_day / month_days)
    pacing_ratio = (spend_mtd / spend_expected) if spend_expected > 0 else 0.0
    forecast = (spend_mtd / month_day) * month_days if month_day > 0 else 0.0
    remaining = policy.monthly_budget_ron - spend_mtd
    forecast_ratio = (forecast / policy.monthly_budget_ron) if policy.monthly_budget_ron > 0 else 0.0
    return PacingSnapshot(
        report_date=report_date,
        month_day=month_day,
        month_days=month_days,
        monthly_budget=policy.monthly_budget_ron,
        spend_mtd=spend_mtd,
        spend_expected=spend_expected,
        pacing_ratio=pacing_ratio,
        forecast_month_end=forecast,
        remaining_budget=remaining,
        forecast_ratio_vs_budget=forecast_ratio,
    )


def recommend_for_campaign(
    row: CampaignRow,
    account_under_pacing: bool,
    policy: Policy,
) -> Recommendation:
    low_data = row.spend_30d < 1000
    if low_data:
        return Recommendation(
            campaign=row.campaign,
            channel=row.channel,
            current_budget=row.daily_budget,
            recommended_budget=row.daily_budget,
            recommendation="Hold",
            priority=6,
            reason="Date insuficiente: spend_30d sub pragul minim.",
        )

    budget_too_wide = row.daily_budget > policy.budget_too_wide_multiplier * row.avg_daily_spend_30d
    roas = row.roas_30d

    if row.conv_value_30d <= 0:
        rec_budget = row.daily_budget * (1 - policy.max_reduction_ratio)
        return Recommendation(
            campaign=row.campaign,
            channel=row.channel,
            current_budget=row.daily_budget,
            recommended_budget=rec_budget,
            recommendation="Reduce 20% / Pause candidate",
            priority=1,
            reason="Zero valoare conversii in 30d.",
        )

    if roas < 2.5:
        rec_budget = row.daily_budget * 0.8
        return Recommendation(
            campaign=row.campaign,
            channel=row.channel,
            current_budget=row.daily_budget,
            recommended_budget=rec_budget,
            recommendation="Reduce 20%",
            priority=2,
            reason="ROAS sub 2.5.",
        )

    if roas < 4.0:
        rec_budget = row.daily_budget * 0.85
        return Recommendation(
            campaign=row.campaign,
            channel=row.channel,
            current_budget=row.daily_budget,
            recommended_budget=rec_budget,
            recommendation="Reduce 15%",
            priority=3,
            reason="ROAS intre 2.5 si 4.0.",
        )

    if roas <= 5.0:
        rec_budget = row.daily_budget * 0.9
        return Recommendation(
            campaign=row.campaign,
            channel=row.channel,
            current_budget=row.daily_budget,
            recommended_budget=rec_budget,
            recommendation="Reduce 10%",
            priority=4,
            reason="ROAS intre 4.0 si 5.0.",
        )

    if budget_too_wide:
        return Recommendation(
            campaign=row.campaign,
            channel=row.channel,
            current_budget=row.daily_budget,
            recommended_budget=row.daily_budget,
            recommendation="Hold / Preventive cap",
            priority=5,
            reason="Buget > 5x spend mediu zilnic 30d.",
        )

    if roas > policy.roas_scale_up_threshold and account_under_pacing:
        rec_budget = row.daily_budget * (1 + policy.max_increase_ratio)
        return Recommendation(
            campaign=row.campaign,
            channel=row.channel,
            current_budget=row.daily_budget,
            recommended_budget=rec_budget,
            recommendation="Increase up to 10%",
            priority=6,
            reason="ROAS > 7.0 si cont sub pacing.",
        )

    return Recommendation(
        campaign=row.campaign,
        channel=row.channel,
        current_budget=row.daily_budget,
        recommended_budget=row.daily_budget,
        recommendation="Hold",
        priority=6,
        reason="Fara trigger de ajustare.",
    )
