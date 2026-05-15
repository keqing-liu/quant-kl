# quant-kl

This project is for analyzing financial data and give trading advices.

# Structure

data_fetch/
    |----__init__.py
    |----fetch_etf.py
    |----fetch_stock.py
    |----update_market_data.py

visualization/
    |----__init__.py
    |----plot_etf.py

config/
    |----__init__.py
    |----watchlist.py

data/


.gitignore
README.md




how to update the data?

run python -m data_fetch.update_market_data

how to plot etf data?

run python -m visualization.plot_etf