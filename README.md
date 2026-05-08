# A2T.ro Budget Control v1

Recommend-only daily budget control for Google Ads, based on:
- monthly planning budget: `575000 RON`
- daily target: `~17000 RON`
- ROAS thresholds: `4.0-5.0`
- conservative change limits: max `-20%` cut, max `+10%` increase

## What this implementation does
- Computes monthly pacing (`MTD vs expected spend`).
- Forecasts month-end spend from current pace.
- Flags campaign risks:
  - low ROAS
  - zero conversion value
  - budget too wide (`daily_budget > 5x avg_daily_spend_30d`)
- Generates recommend-only budget actions (no direct Google Ads writes).
- Produces flat files for `evidence.dev` reporting.

## Run from CSV
```bash
PYTHONPATH=src python -m a2t_budget_control.cli --input data/sample_campaigns.csv --date 2026-05-08
```

## Run from Google Ads API
1. Install dependency:
```bash
pip install google-ads
```
2. Create local env file from template:
```bash
cp .env.example .env
```
3. Export env vars in your shell (`.env` example values are placeholders):
```bash
set -a; source .env; set +a
```
4. Run:
```bash
PYTHONPATH=src python -m a2t_budget_control.cli --from-google-ads --date 2026-05-08
```

Outputs in `data/output/`:
- `daily_pacing.csv`
- `campaign_recommendations.csv`
- `channel_summary.csv`
- `decision_log.csv`
- `google_ads_campaigns_raw.csv` (when using `--from-google-ads`)
- `history_daily_pacing.csv` (upsert by `report_date`)
- `history_campaign_recommendations.csv` (upsert by `report_date + campaign`)
- `history_channel_summary.csv` (upsert by `report_date + channel`)

## Evidence reporting
Use the `evidence/` folder as your Evidence project root, and point it to the CSV outputs from `data/output`.

The starter page is:
- `evidence/pages/index.md`
