from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

from .models import CampaignRow


@dataclass(frozen=True)
class GoogleAdsConfig:
    developer_token: str
    customer_id: str
    json_key_file_path: str
    use_proto_plus: bool = True
    login_customer_id: str | None = None


class GoogleAdsDependencyError(RuntimeError):
    pass


def _load_google_ads_client(config: GoogleAdsConfig):
    try:
        from google.ads.googleads.client import GoogleAdsClient
    except Exception as exc:  # pragma: no cover
        raise GoogleAdsDependencyError(
            "Missing dependency 'google-ads'. Install with: pip install google-ads"
        ) from exc

    payload = {
        "developer_token": config.developer_token,
        "json_key_file_path": config.json_key_file_path,
        "use_proto_plus": config.use_proto_plus,
    }
    if config.login_customer_id:
        payload["login_customer_id"] = config.login_customer_id

    return GoogleAdsClient.load_from_dict(payload)


def load_config_from_env() -> GoogleAdsConfig:
    developer_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip()
    customer_id = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "").strip()
    json_key_file_path = os.environ.get("GOOGLE_ADS_JSON_KEY_PATH", "").strip()
    login_customer_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").strip() or None

    missing = []
    if not developer_token:
        missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not customer_id:
        missing.append("GOOGLE_ADS_CUSTOMER_ID")
    if not json_key_file_path:
        missing.append("GOOGLE_ADS_JSON_KEY_PATH")

    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")

    return GoogleAdsConfig(
        developer_token=developer_token,
        customer_id=customer_id,
        json_key_file_path=json_key_file_path,
        login_customer_id=login_customer_id,
    )


def fetch_campaign_rows(config: GoogleAdsConfig) -> list[CampaignRow]:
    client = _load_google_ads_client(config)
    service = client.get_service("GoogleAdsService")

    # 30-day reporting window for alignment with v1 recommendation rules.
    query = """
        SELECT
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          campaign_budget.amount_micros,
          metrics.cost_micros,
          metrics.conversions_value
        FROM campaign
        WHERE campaign.status = 'ENABLED'
          AND segments.date DURING LAST_30_DAYS
    """

    stream = service.search_stream(customer_id=config.customer_id, query=query)
    by_campaign: dict[str, dict[str, float | str]] = {}

    for batch in stream:
        for row in batch.results:
            name = row.campaign.name
            channel = str(row.campaign.advertising_channel_type)
            status = str(row.campaign.status)
            budget = row.campaign_budget.amount_micros / 1_000_000
            spend = row.metrics.cost_micros / 1_000_000
            conv_value = row.metrics.conversions_value

            if name not in by_campaign:
                by_campaign[name] = {
                    "campaign": name,
                    "channel": channel,
                    "status": status,
                    "daily_budget": budget,
                    "spend_30d": 0.0,
                    "conv_value_30d": 0.0,
                }

            by_campaign[name]["spend_30d"] += spend
            by_campaign[name]["conv_value_30d"] += conv_value

    rows: list[CampaignRow] = []
    for c in by_campaign.values():
        spend_30d = float(c["spend_30d"])
        conv_value_30d = float(c["conv_value_30d"])
        rows.append(
            CampaignRow(
                campaign=str(c["campaign"]),
                channel=str(c["channel"]),
                status=str(c["status"]),
                daily_budget=float(c["daily_budget"]),
                spend_7d=spend_30d * (7.0 / 30.0),
                spend_30d=spend_30d,
                conv_value_7d=conv_value_30d * (7.0 / 30.0),
                conv_value_30d=conv_value_30d,
            )
        )

    return rows


def export_campaign_rows_csv(rows: Iterable[CampaignRow], path: str) -> None:
    import csv

    fieldnames = [
        "campaign",
        "channel",
        "status",
        "daily_budget",
        "spend_7d",
        "spend_30d",
        "conv_value_7d",
        "conv_value_30d",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "campaign": r.campaign,
                    "channel": r.channel,
                    "status": r.status,
                    "daily_budget": round(r.daily_budget, 2),
                    "spend_7d": round(r.spend_7d, 2),
                    "spend_30d": round(r.spend_30d, 2),
                    "conv_value_7d": round(r.conv_value_7d, 2),
                    "conv_value_30d": round(r.conv_value_30d, 2),
                }
            )
