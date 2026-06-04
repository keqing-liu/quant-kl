# AGENT.md

This file gives future coding agents project-specific context for `quant-kl`.

## Project Purpose

`quant-kl` is a personal quantitative research project for China ETF / A-share data and watchlist-based US stock / ETF price data. It stores market data, technical indicators, stock universe data, financial indicators, Sina financial statements, and derived Buffett-style metrics in a local SQLite database.

This repository is for personal research and learning only. Do not present outputs as investment advice.

## Core Commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the regular market-data workflow:

```bash
python -m main
```

Sync the A-share stock universe:

```bash
python -m data_fetch.update_stock_universe
```

Download financial data:

```bash
python -m data_fetch.update_financial_data --sleep 12 --retries 2
```

Download financial data for one stock:

```bash
python -m data_fetch.update_financial_data --symbol sh600519 --sleep 0 --retries 1
```

Calculate Buffett-style metrics:

```bash
python -m analysis.calculate_buffett_metrics --annual-only
```

Show one stock's annual financial snapshot:

```bash
python -m analysis.stock_financial_snapshot --symbol sh600519 --years 10
```

Run the ROE screen:

```bash
python -m analysis.fundamental_screen
```

## Financial Data Policy

Current financial data downloads intentionally include only:

- `indicators`: Sina financial indicators, stored in `financial_indicators`.
- `statements`: Sina income statement, balance sheet, and cash flow statement, stored as narrow rows in `financial_statement_items`.

Do not add Eastmoney financial-statement endpoints unless the user explicitly asks. The user has reported repeated Eastmoney download failures.

Do not add dividend-event downloads for now. Giant/third-party dividend endpoints were unstable, so `financial_dividend_events` was removed in schema v7 and dividend-related metric fields were removed in v8.

Do not store daily valuation data as a financial table. Financial data should remain report-period or event structured. If market cap is needed for derived metrics, compute it as a report-period result rather than storing a daily valuation table.

US market data policy:

- US stock and ETF prices use Stooq CSV.
- Stooq CSV requires `STOOQ_API_KEY` in the environment. Without it, US price downloads should fail with a clear message instead of being treated as valid empty data.
- Internal US symbols use `us_` prefix, e.g. `AAPL` becomes `us_aapl`, `BRK-B` becomes `us_brk_b`.
- US stocks and US ETFs are price-only for now.
- Do not download US company financial data unless the user explicitly asks to re-enable it. `data_fetch.update_us_financial_data` is currently a disabled placeholder.
- ADR / foreign issuer names such as `TSM` and `ASML` may require 20-F, IFRS, and non-USD handling; do not mix those facts into the A-share/Sina financial structure without a separate design.

## Database Rules

The SQLite database path is:

```text
database/quant.db
```

Schema maintenance must update all of these together:

- `database/schema/base.sql`
- a new `database/migrations/00N_*.sql`
- `database/db_utils.py` with `CURRENT_SCHEMA_VERSION` and a migration function

Existing migrations:

- v6 added expanded financial indicators, `financial_statement_items`, and `buffett_metrics`.
- v7 removed `financial_dividend_events`.
- v8 removed dividend-related metric fields.
- v9 added `us_company_map`.

After schema changes, run:

```bash
python - <<'PY'
from database.db_utils import initialize_database
initialize_database()
PY
```

## Data Shape Notes

`financial_indicators` keeps directly downloadable Sina financial ratios and selected fields. `ocf_to_net_profit` is the cash-flow-to-net-profit ratio. Do not confuse it with `operating_cash_flow`, which may contain per-share operating cash flow when the Sina indicator endpoint does not provide an absolute operating cash flow amount.

`financial_statement_items` is intentionally a narrow table:

```text
symbol, report_date, statement_type, item_name, item_value
```

This avoids hard-coding hundreds of statement columns into the schema.

US company financial downloads are currently disabled, so `financial_statement_items` should be treated as A-share Sina statement data unless the user explicitly requests a future US financial-data redesign.

`buffett_metrics` stores report-period derived metrics, including FCF, ROIC, net debt ratio, and working capital metrics.

## Code Style And Safety

Prefer small, focused changes. Preserve existing scripts and command-line behavior unless the user asks for a change.

Use `rg` for searching. Use `apply_patch` for manual file edits.

Do not delete or overwrite user data files such as `database/quant.db`, `data/`, or local CSVs unless explicitly requested.

When changing financial fields, keep comments in `data_fetch/fetch_financial.py` updated so field meaning remains clear.

## Useful Smoke Tests

Syntax check:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/quantkl-pycache python3 -m py_compile \
  data_fetch/fetch_financial.py \
  data_fetch/update_financial_data.py \
  analysis/calculate_buffett_metrics.py \
  analysis/stock_financial_snapshot.py \
  data_fetch/fetch_us_market.py \
  data_fetch/update_us_financial_data.py \
  database/db_utils.py
```

Financial smoke test:

```bash
python -m data_fetch.update_financial_data --symbol sh600519 --datasets indicators,statements --sleep 0 --retries 1
python -m analysis.calculate_buffett_metrics --symbol sh600519 --annual-only
python -m analysis.stock_financial_snapshot --symbol sh600519 --years 10
```

US market smoke test:

```bash
python -m main
python -m analysis.indicators
```
