from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .engine import load_campaigns, run_daily
from .google_ads import (
    export_dict_rows_csv,
    export_campaign_rows_csv,
    fetch_product_category_product_summaries,
    fetch_campaign_rows,
    load_config_from_env,
)
from .models import Policy


def main() -> None:
    parser = argparse.ArgumentParser(description="A2T budget control recommend-only runner")
    parser.add_argument("--input", required=False, help="Input campaigns CSV")
    parser.add_argument("--date", required=False, help="Report date YYYY-MM-DD")
    parser.add_argument("--output-dir", default="data/output", help="Output directory")
    parser.add_argument(
        "--from-google-ads",
        action="store_true",
        help="Fetch campaign data from Google Ads API using env credentials",
    )
    parser.add_argument(
        "--export-raw-campaigns",
        default="data/output/google_ads_campaigns_raw.csv",
        help="Where to write raw Google Ads campaign rollup when --from-google-ads is used",
    )
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else date.today()

    if args.from_google_ads:
        cfg = load_config_from_env()
        campaigns = fetch_campaign_rows(cfg)
        export_campaign_rows_csv(campaigns, args.export_raw_campaigns)
        category_rows, product_rows = fetch_product_category_product_summaries(cfg, report_date, campaigns)
    else:
        if not args.input:
            raise SystemExit("--input is required unless --from-google-ads is used")
        campaigns = load_campaigns(Path(args.input))

    run_daily(report_date=report_date, campaigns=campaigns, output_dir=Path(args.output_dir), policy=Policy())
    if args.from_google_ads:
        export_dict_rows_csv(category_rows, str(Path(args.output_dir) / "category_summary.csv"))
        export_dict_rows_csv(product_rows, str(Path(args.output_dir) / "product_summary.csv"))
    print(f"Done. Outputs written to {args.output_dir}")


if __name__ == "__main__":
    main()
