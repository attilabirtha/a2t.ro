from __future__ import annotations

import calendar
import csv
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .models import CampaignRow, Policy
from .rules import PacingSnapshot, calc_pacing, recommend_for_campaign


def _normalize_token(token: str) -> str:
    return " ".join(token.strip().split())


def _campaign_parts(name: str) -> list[str]:
    return [_normalize_token(p) for p in name.split("-") if _normalize_token(p)]


def _infer_category_and_product(campaign_name: str) -> tuple[str, str]:
    parts = _campaign_parts(campaign_name)
    if not parts:
        return ("Uncategorized", "Unknown")

    stop_tokens = {
        "pmax",
        "search",
        "dgen",
        "video",
        "new",
        "purchase",
        "views",
        "no rmkt",
        "no product feed",
        "shopping only",
        "no brand",
        "troas",
        "almax",
        "generic",
        "test",
    }

    filtered = []
    for p in parts:
        low = p.lower()
        if low in stop_tokens:
            continue
        filtered.append(p)

    if not filtered:
        fallback = parts[-1]
        return (fallback, fallback)

    category = filtered[0]
    product = filtered[-1]
    return (category, product)


def load_campaigns(path: Path) -> list[CampaignRow]:
    rows: list[CampaignRow] = []
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                CampaignRow(
                    campaign=r["campaign"],
                    channel=r["channel"],
                    status=r.get("status", "ENABLED"),
                    daily_budget=float(r["daily_budget"]),
                    spend_7d=float(r["spend_7d"]),
                    spend_30d=float(r["spend_30d"]),
                    conv_value_7d=float(r["conv_value_7d"]),
                    conv_value_30d=float(r["conv_value_30d"]),
                )
            )
    return rows


def _write_csv(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)


def _upsert_csv_by_key(path: Path, records: list[dict], key_fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        return

    fieldnames = list(records[0].keys())
    existing: list[dict] = []
    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing = list(reader)

    idx: dict[tuple[str, ...], dict] = {}
    for row in existing:
        idx[tuple(str(row.get(k, "")) for k in key_fields)] = row
    for row in records:
        idx[tuple(str(row.get(k, "")) for k in key_fields)] = row

    merged = list(idx.values())
    merged.sort(key=lambda r: tuple(str(r.get(k, "")) for k in key_fields))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)


def run_daily(report_date: date, campaigns: list[CampaignRow], output_dir: Path, policy: Policy) -> None:
    month_days = calendar.monthrange(report_date.year, report_date.month)[1]
    month_day = report_date.day

    spend_30d = sum(c.spend_30d for c in campaigns)
    spend_mtd = spend_30d * (month_day / month_days)

    pacing: PacingSnapshot = calc_pacing(
        report_date=report_date.isoformat(),
        month_day=month_day,
        month_days=month_days,
        spend_mtd=spend_mtd,
        policy=policy,
    )

    account_under_pacing = pacing.forecast_ratio_vs_budget < 1.0
    recs = [recommend_for_campaign(c, account_under_pacing, policy) for c in campaigns]

    pacing_rows = [asdict(pacing)]
    campaign_by_name = {c.campaign: c for c in campaigns}
    rec_rows = []
    for r in sorted(recs, key=lambda x: x.priority):
        c = campaign_by_name.get(r.campaign)
        spend_30d = round(c.spend_30d, 2) if c else 0.0
        conv_30d = round(c.conv_value_30d, 2) if c else 0.0
        spend_mtd_est = round((c.spend_30d * (month_day / month_days)), 2) if c else 0.0
        rec_rows.append(
            asdict(r)
            | {
                "report_date": report_date.isoformat(),
                "roas_30d": round(c.roas_30d, 3) if c else 0.0,
                "spend_30d": spend_30d,
                "spend_mtd_est": spend_mtd_est,
                "conv_value_30d": conv_30d,
            }
        )

    by_channel: dict[str, dict[str, float]] = defaultdict(lambda: {"spend_30d": 0.0, "conv_value_30d": 0.0, "daily_budget": 0.0})
    total_budget = sum(c.daily_budget for c in campaigns) or 1.0
    for c in campaigns:
        by_channel[c.channel]["spend_30d"] += c.spend_30d
        by_channel[c.channel]["conv_value_30d"] += c.conv_value_30d
        by_channel[c.channel]["daily_budget"] += c.daily_budget

    channel_rows = []
    for channel, m in by_channel.items():
        roas = m["conv_value_30d"] / m["spend_30d"] if m["spend_30d"] > 0 else 0.0
        channel_rows.append(
            {
                "report_date": report_date.isoformat(),
                "channel": channel,
                "spend_30d": round(m["spend_30d"], 2),
                "conv_value_30d": round(m["conv_value_30d"], 2),
                "roas_30d": round(roas, 3),
                "daily_budget_total": round(m["daily_budget"], 2),
                "budget_share": round(m["daily_budget"] / total_budget, 4),
            }
        )

    by_category: dict[str, dict[str, float]] = defaultdict(lambda: {"spend_30d": 0.0, "spend_mtd_est": 0.0, "conv_value_30d": 0.0, "budget": 0.0, "campaigns": 0.0})
    by_product: dict[str, dict[str, float]] = defaultdict(lambda: {"spend_30d": 0.0, "spend_mtd_est": 0.0, "conv_value_30d": 0.0, "budget": 0.0, "campaigns": 0.0})
    product_categories: dict[str, set[str]] = defaultdict(set)
    for c in campaigns:
        category, product = _infer_category_and_product(c.campaign)
        spend_mtd_est = c.spend_30d * (month_day / month_days)

        by_category[category]["spend_30d"] += c.spend_30d
        by_category[category]["spend_mtd_est"] += spend_mtd_est
        by_category[category]["conv_value_30d"] += c.conv_value_30d
        by_category[category]["budget"] += c.daily_budget
        by_category[category]["campaigns"] += 1

        by_product[product]["spend_30d"] += c.spend_30d
        by_product[product]["spend_mtd_est"] += spend_mtd_est
        by_product[product]["conv_value_30d"] += c.conv_value_30d
        by_product[product]["budget"] += c.daily_budget
        by_product[product]["campaigns"] += 1
        product_categories[product].add(category)

    category_rows = []
    for category, m in by_category.items():
        roas = m["conv_value_30d"] / m["spend_30d"] if m["spend_30d"] > 0 else 0.0
        category_rows.append(
            {
                "report_date": report_date.isoformat(),
                "category": category,
                "campaign_count": int(m["campaigns"]),
                "daily_budget_total": round(m["budget"], 2),
                "spend_mtd_est": round(m["spend_mtd_est"], 2),
                "spend_30d": round(m["spend_30d"], 2),
                "conv_value_30d": round(m["conv_value_30d"], 2),
                "roas_30d": round(roas, 3),
            }
        )

    product_rows = []
    for product, m in by_product.items():
        roas = m["conv_value_30d"] / m["spend_30d"] if m["spend_30d"] > 0 else 0.0
        categories = sorted(product_categories.get(product, set()))
        product_rows.append(
            {
                "report_date": report_date.isoformat(),
                "product_item_id": "",
                "product": product,
                "category": " | ".join(categories),
                "campaign_count": int(m["campaigns"]),
                "daily_budget_total": round(m["budget"], 2),
                "spend_mtd_est": round(m["spend_mtd_est"], 2),
                "spend_30d": round(m["spend_30d"], 2),
                "conv_value_30d": round(m["conv_value_30d"], 2),
                "roas_30d": round(roas, 3),
            }
        )

    decision_rows = [
        {
            "report_date": report_date.isoformat(),
            "campaign": r.campaign,
            "recommendation": r.recommendation,
            "recommended_budget": round(r.recommended_budget, 2),
            "decision": "PENDING",
            "manual_note": "",
            "applied_by": "",
            "applied_at": "",
        }
        for r in recs
    ]

    _write_csv(output_dir / "daily_pacing.csv", pacing_rows)
    _write_csv(output_dir / "campaign_recommendations.csv", rec_rows)
    _write_csv(output_dir / "channel_summary.csv", channel_rows)
    _write_csv(output_dir / "category_summary.csv", sorted(category_rows, key=lambda x: x["spend_mtd_est"], reverse=True))
    _write_csv(output_dir / "product_summary.csv", sorted(product_rows, key=lambda x: x["spend_mtd_est"], reverse=True))
    _write_csv(output_dir / "decision_log.csv", decision_rows)

    # History tracking with upsert semantics to avoid duplicate rows for the same date.
    _upsert_csv_by_key(output_dir / "history_daily_pacing.csv", pacing_rows, ["report_date"])
    _upsert_csv_by_key(output_dir / "history_campaign_recommendations.csv", rec_rows, ["report_date", "campaign"])
    _upsert_csv_by_key(output_dir / "history_channel_summary.csv", channel_rows, ["report_date", "channel"])
