from __future__ import annotations

import os
import calendar
from dataclasses import dataclass
from datetime import date
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


def fetch_product_category_product_summaries(
    config: GoogleAdsConfig,
    report_date: date,
    campaigns: list[CampaignRow],
) -> tuple[list[dict], list[dict]]:
    client = _load_google_ads_client(config)
    service = client.get_service("GoogleAdsService")

    query = """
        SELECT
          campaign.name,
          campaign.status,
          segments.product_type_l1,
          segments.product_type_l2,
          segments.product_category_level1,
          segments.product_category_level2,
          segments.product_item_id,
          segments.product_title,
          metrics.cost_micros,
          metrics.conversions_value
        FROM shopping_performance_view
        WHERE campaign.status = 'ENABLED'
          AND segments.date DURING LAST_30_DAYS
          AND segments.product_item_id IS NOT NULL
    """

    stream = service.search_stream(customer_id=config.customer_id, query=query)

    by_category: dict[str, dict[str, float | str | set[str]]] = {}
    by_product: dict[str, dict[str, float | str | set[str]]] = {}
    budget_by_campaign_name = {c.campaign: c.daily_budget for c in campaigns}
    category_campaigns: dict[str, set[str]] = {}
    product_campaigns: dict[str, set[str]] = {}
    product_categories: dict[str, set[str]] = {}

    for batch in stream:
        for row in batch.results:
            campaign_name = str(row.campaign.name)

            product_type_l2 = str(row.segments.product_type_l2 or "").strip()
            product_type_l1 = str(row.segments.product_type_l1 or "").strip()
            level2 = str(row.segments.product_category_level2 or "").strip()
            level1 = str(row.segments.product_category_level1 or "").strip()

            # Prefer merchant-defined product types (readable business structure).
            category_raw = product_type_l2 or product_type_l1 or level2 or level1 or "Uncategorized"
            if category_raw.startswith("productCategoryConstants/LEVEL"):
                category = category_raw.split("~", 1)[-1]
                category = f"GoogleCategoryID {category}"
            else:
                category = category_raw

            product_id = str(row.segments.product_item_id or "").strip()
            product_title = str(row.segments.product_title or "").strip()
            product = product_title or product_id or "Unknown product"

            spend = row.metrics.cost_micros / 1_000_000
            conv_value = row.metrics.conversions_value

            if category not in by_category:
                by_category[category] = {
                    "category": category,
                    "spend_30d": 0.0,
                    "conv_value_30d": 0.0,
                }
                category_campaigns[category] = set()
            by_category[category]["spend_30d"] += spend
            by_category[category]["conv_value_30d"] += conv_value
            category_campaigns[category].add(campaign_name)

            if product not in by_product:
                by_product[product] = {
                    "product": product,
                    "spend_30d": 0.0,
                    "conv_value_30d": 0.0,
                }
                product_campaigns[product] = set()
                product_categories[product] = set()
            by_product[product]["spend_30d"] += spend
            by_product[product]["conv_value_30d"] += conv_value
            product_campaigns[product].add(campaign_name)
            product_categories[product].add(category)

    month_day = report_date.day
    month_days = calendar.monthrange(report_date.year, report_date.month)[1]
    mtd_factor = month_day / month_days if month_days > 0 else 0.0

    category_rows: list[dict] = []
    for category, m in by_category.items():
        spend_30d = float(m["spend_30d"])
        conv_30d = float(m["conv_value_30d"])
        campaigns = category_campaigns[category]
        campaign_list = sorted(campaigns)
        budget_total = sum(budget_by_campaign_name.get(cname, 0.0) for cname in campaigns)
        category_rows.append(
            {
                "report_date": report_date.isoformat(),
                "category": category,
                "campaign_count": len(campaigns),
                "source_campaigns": " | ".join(campaign_list),
                "daily_budget_total": round(budget_total, 2),
                "spend_mtd_est": round(spend_30d * mtd_factor, 2),
                "spend_30d": round(spend_30d, 2),
                "conv_value_30d": round(conv_30d, 2),
                "roas_30d": round((conv_30d / spend_30d) if spend_30d > 0 else 0.0, 3),
            }
        )

    product_rows: list[dict] = []
    for product, m in by_product.items():
        spend_30d = float(m["spend_30d"])
        conv_30d = float(m["conv_value_30d"])
        campaigns = product_campaigns[product]
        categories = sorted(product_categories.get(product, set()))
        campaign_list = sorted(campaigns)
        budget_total = sum(budget_by_campaign_name.get(cname, 0.0) for cname in campaigns)
        product_rows.append(
            {
                "report_date": report_date.isoformat(),
                "product_item_id": product_id,
                "product": product,
                "category": " | ".join(categories),
                "campaign_count": len(campaigns),
                "source_campaigns": " | ".join(campaign_list),
                "daily_budget_total": round(budget_total, 2),
                "spend_mtd_est": round(spend_30d * mtd_factor, 2),
                "spend_30d": round(spend_30d, 2),
                "conv_value_30d": round(conv_30d, 2),
                "roas_30d": round((conv_30d / spend_30d) if spend_30d > 0 else 0.0, 3),
            }
        )

    category_rows.sort(key=lambda x: x["spend_mtd_est"], reverse=True)
    product_rows.sort(key=lambda x: x["spend_mtd_est"], reverse=True)
    return category_rows, product_rows


def export_dict_rows_csv(rows: list[dict], path: str) -> None:
    import csv

    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
