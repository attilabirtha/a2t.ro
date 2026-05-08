from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Policy:
    monthly_budget_ron: float = 575000.0
    daily_target_ron: float = 17000.0
    roas_floor_low: float = 4.0
    roas_floor_high: float = 5.0
    roas_scale_up_threshold: float = 7.0
    overspend_forecast_ratio_trigger: float = 1.05
    max_reduction_ratio: float = 0.20
    max_increase_ratio: float = 0.10
    budget_too_wide_multiplier: float = 5.0


@dataclass(frozen=True)
class CampaignRow:
    campaign: str
    channel: str
    status: str
    daily_budget: float
    spend_7d: float
    spend_30d: float
    conv_value_7d: float
    conv_value_30d: float

    @property
    def roas_7d(self) -> float:
        return self.conv_value_7d / self.spend_7d if self.spend_7d > 0 else 0.0

    @property
    def roas_30d(self) -> float:
        return self.conv_value_30d / self.spend_30d if self.spend_30d > 0 else 0.0

    @property
    def avg_daily_spend_30d(self) -> float:
        return self.spend_30d / 30.0
