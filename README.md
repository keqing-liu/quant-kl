# quant-kl

A personal quantitative finance research project for:

- downloading Chinese market data
- organizing local financial datasets
- visualizing ETF and stock price movements
- developing future quantitative trading strategies

The project currently focuses on:

- Chinese ETFs
- A-share stocks
- local CSV-based data storage
- market visualization

Future plans include:

- technical indicators
- backtesting systems
- portfolio analysis
- database integration
- automated market updates
- strategy research

---

# Project Structure

```text
quant-kl/
│
├── data_fetch/
│   ├── __init__.py
│   ├── fetch_etf.py
│   ├── fetch_stock.py
│   └── update_market_data.py
│
├── visualization/
│   ├── __init__.py
│   └── plot_etf.py
│
├── config/
│   ├── __init__.py
│   └── watchlist.py
│
├── data/
│   ├── etf/
│   └── stock/
│
├── .gitignore
├── README.md
```

---

# Features

## Market Data Download

The project supports downloading:

- ETF historical data
- A-share stock historical data

Current data source:

- Sina Finance (AKShare interface)

Downloaded data is stored locally as CSV files.

---

## Watchlist System

Assets are managed through:

```python
WATCHLIST = {
    "ETF": [
        "sh510310",
        "sh510100"
    ],

    "STOCK": [
        "sh600519"
    ]
}
```

This allows batch downloading and future automated updates.

---

## Visualization

The project currently supports:

- candlestick charts
- moving averages
- volume visualization

Visualization is implemented with:

- pandas
- matplotlib
- mplfinance

---

# Installation

## Clone the repository

```bash
git clone <your-repository-url>
cd quant-kl
```

---

## Create a virtual environment (recommended)

Using conda:

```bash
conda create -n quant python=3.11
conda activate quant
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install akshare pandas matplotlib mplfinance numpy==1.26.4
```

---

# How to Update Market Data

Run:

```bash
python -m data_fetch.update_market_data
```

This will:

- read the watchlist
- download ETF data
- download stock data
- save CSV files into the local data folder

---

# How to Plot ETF Data

Run:

```bash
python -m visualization.plot_etf
```

This will generate:

- ETF candlestick chart
- moving averages
- trading volume chart

---

# Data Storage

Downloaded CSV files are stored under:

```text
data/
├── etf/
└── stock/
```

Example:

```text
data/etf/sh510310.csv
data/stock/sh600519.csv
```

---

# Recommended .gitignore

```gitignore
__pycache__/
*.pyc

data/
*.csv

.env
venv/
```

---

# Current Development Stage

The project is currently focused on:

## Phase 1 — Data Infrastructure

- [x] market data download
- [x] watchlist management
- [x] local CSV storage
- [x] modular project structure

## Phase 2 — Visualization

- [x] ETF candlestick chart
- [ ] technical indicators
- [ ] multi-asset comparison

## Phase 3 — Quantitative Research

Planned:

- moving average strategies
- momentum strategies
- ETF rotation
- backtesting engine

---

# Disclaimer

This project is for educational and research purposes only.

It does not constitute financial or investment advice.

---

# Author

Keqing Liu