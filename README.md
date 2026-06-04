# quant-kl

一个简化的私人量化交易研究系统，主要用于下载中国市场 ETF / A 股行情、保存到本地 SQLite 数据库、计算技术指标、生成摘要、绘图，并验证简单的股债轮动策略。

> 本项目用于个人学习和研究，不构成任何投资建议。

## 功能概览

- 使用 `akshare` 下载 ETF 和 A 股历史行情
- 使用 SQLite (`database/quant.db`) 本地存储行情、技术指标、资产信息和数据更新日志
- 支持按 `config/watchlist.py` 批量更新关注标的
- 支持同步沪深 A 股股票池，并按股票池批量下载 A 股财务指标和三大报表
- 支持 watchlist 中的美国股票和 ETF：当前只下载行情，用 Stooq CSV
- 支持用 Cboe 官方 CSV 下载 VIX / VXN 日度市场风险指标
- 支持基于新浪财报数据计算自由现金流、ROIC、净负债率等巴菲特式基本面指标
- 支持基于年报 ROE、负债率、净利润增长率等指标做基本面筛选
- 通过 `database/schema/base.sql` 初始化新数据库，并使用 `database/migrations/` 管理旧数据库结构迁移
- 记录每次行情更新结果，方便追踪成功、失败、空数据和无新增数据等状态
- 提供简单数据质量检查，覆盖重复交易日、OHLC 异常、缺失价格和成交量等问题
- 计算均线、收益率、波动率、布林带、成交量均线、KDJ、CCI 等指标
- 支持按分组输出最近交易日技术指标摘要、VIX / VXN 价格序列和简单打分结果
- 绘制 K 线图、均线、布林带、KDJ、CCI 等图表
- 回测沪深 300 ETF 与债券 ETF 的简单动态轮动策略

## 项目结构

```text
quant-kl/
├── main.py
├── README.md
├── requirements.txt
├── .gitignore
├── analysis/
│   ├── __init__.py
│   ├── indicators.py
│   ├── calculate_buffett_metrics.py
│   ├── stock_financial_snapshot.py
│   ├── summary.py
│   ├── fundamental_screen.py
│   ├── scoring2.py
│   ├── scoring_benchmark.py
│   └── bond_stock_yearly_return.py
├── backtest/
│   ├── __init__.py
│   ├── strategy_stock300bond.py
│   └── strategy_stock300bond_multi_start.py
├── config/
│   ├── __init__.py
│   └── watchlist.py
├── data/
│   └── *.csv
├── data_fetch/
│   ├── __init__.py
│   ├── fetch_etf.py
│   ├── fetch_cboe_market.py
│   ├── fetch_financial.py
│   ├── fetch_us_market.py
│   ├── fetch_stock.py
│   ├── update_financial_data.py
│   ├── update_us_financial_data.py
│   └── update_stock_universe.py
├── data_manager/
│   ├── __init__.py
│   └── data_manager.py
├── database/
│   ├── __pycache__/
│   ├── schema/
│   │   └── base.sql
│   ├── migrations/
│   │   ├── 001_add_timestamps_to_price_tables.sql
│   │   ├── 002_create_stock_universe.sql
│   │   ├── 003_create_financial_indicators.sql
│   │   ├── 004_noop_fixed_asset_ratio_removed.sql
│   │   ├── 005_drop_fixed_asset_ratio_from_financial_indicators.sql
│   │   ├── 006_expand_financial_data_for_buffett_metrics.sql
│   │   ├── 007_drop_financial_dividend_events.sql
│   │   ├── 008_drop_dividend_metric_fields.sql
│   │   └── 009_create_us_company_map.sql
│   ├── db_utils.py
│   ├── init_asset_info.py
│   ├── data_quality_check.py
│   └── quant.db
└── visualization/
    ├── __init__.py
    ├── plot_etf.py
    └── plot_indicators.py
```

## 文件说明

### 根目录

| 文件 | 用途 |
| --- | --- |
| `main.py` | 项目主入口。初始化数据库，读取 watchlist，更新 ETF / 股票 / 市场风险指标行情，并计算技术指标；不再自动输出摘要。 |
| `README.md` | 项目说明文档。 |
| `requirements.txt` | Python 依赖清单。新环境可用 `pip install -r requirements.txt` 一次性安装运行依赖。 |
| `.gitignore` | Git 忽略规则，忽略缓存、虚拟环境、本地数据、数据库和日志文件。 |

### `config/`

| 文件 | 用途 |
| --- | --- |
| `watchlist.py` | 维护关注标的列表。`WATCHLIST["ETF"]` 保存 ETF 代码，`WATCHLIST["STOCK"]` 保存股票代码。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `data_fetch/`

| 文件 | 用途 |
| --- | --- |
| `fetch_cboe_market.py` | 使用 Cboe 官方 CSV 下载 VIX / VXN 日度市场风险指标，并整理成 `price_data` 兼容字段。 |
| `fetch_etf.py` | 使用 `akshare.fund_etf_hist_sina` 下载单只 ETF 历史行情。 |
| `fetch_financial.py` | 使用 AkShare 下载并整理单只 A 股财务指标和三大报表。三大报表使用新浪端口，不使用东方财富端口。 |
| `fetch_us_market.py` | 使用 Stooq CSV 下载美国股票和 ETF 历史行情，并整理成 `price_data` 兼容字段。 |
| `fetch_stock.py` | 使用 `akshare.stock_zh_a_daily` 下载单只 A 股前复权日线行情。 |
| `update_financial_data.py` | 从 `stock_universe` 读取股票池，批量下载财务指标和三大报表，并写入 SQLite。 |
| `update_us_financial_data.py` | 美国公司财务下载占位脚本。当前策略是美股和 ETF 只下载行情，因此该脚本运行后会直接退出。 |
| `update_stock_universe.py` | 使用交易所名单接口同步沪深 A 股股票池到 `stock_universe` 表。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `data_manager/`

| 文件 | 用途 |
| --- | --- |
| `data_manager.py` | 数据管理层。负责调用下载函数、判断数据库中最新日期、过滤增量数据，写入 `price_data` 表，并记录 `data_update_log`。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `database/`

| 文件 | 用途 |
| --- | --- |
| `schema/base.sql` | SQLite 新库建表脚本。一次性创建当前最新版 `price_data`、`indicators`、`asset_info`、`stock_universe`、财务数据表、`data_update_log`、`schema_version` 等表。 |
| `migrations/*.sql` | 旧数据库结构迁移脚本。每个文件对应一个 schema version，后续改表时按版本追加。 |
| `db_utils.py` | SQLite 工具函数。包含数据库连接、执行 `schema/base.sql` 初始化、按版本执行迁移、查询单个标的最新行情日期、写入更新日志等功能。 |
| `init_asset_info.py` | 初始化或刷新 `asset_info` 表中的资产基础信息。 |
| `data_quality_check.py` | 运行简单数据质量检查，包括重复日期、OHLC 价格逻辑、缺失价格和成交量检查。 |
| `quant.db` | 本地 SQLite 数据库文件，保存行情和指标数据。通常属于本地运行产物，不建议提交到公开仓库。 |

当前数据库主要包含：

| 表名 | 内容 |
| --- | --- |
| `price_data` | 原始行情数据：`symbol`、`date`、`open`、`high`、`low`、`close`、`volume`。 |
| `indicators` | 技术指标数据：均线、收益率、波动率、布林带、成交量均线、KDJ、CCI 等。 |
| `asset_info` | 资产基础信息：名称、资产类型、资产类别、市场、数据源、基准和备注等。 |
| `stock_universe` | 全市场股票池：股票代码、名称、交易所、是否 ST、是否退市风险、上市日期等基础状态信息。 |
| `us_company_map` | 美国上市公司 ticker / CIK 映射，用于请求 SEC companyfacts。 |
| `financial_indicators` | 新浪财务指标数据：报告期、ROE、ROA、利润率、周转率、资产负债率、现金流比率、EPS 等。 |
| `financial_statement_items` | 财务报表明细窄表：当前保存 A 股新浪三大报表科目；美国股票暂不下载公司财务。 |
| `buffett_metrics` | 巴菲特式衍生指标：自由现金流、ROIC、净负债率、现金流覆盖、营运资本等报告期指标。 |
| `data_update_log` | 数据更新日志：每次更新的起止日期、下载行数、实际插入行数、状态和错误信息等。 |
| `schema_version` | 数据库结构版本记录，用于判断旧数据库是否需要执行迁移。 |

### `analysis/`

| 文件 | 用途 |
| --- | --- |
| `indicators.py` | 从 `price_data` 读取行情，计算技术指标，并写入 `indicators` 表。 |
| `calculate_buffett_metrics.py` | 从财务指标、三大报表和行情数据计算巴菲特式基本面指标，并写入 `buffett_metrics` 表。 |
| `stock_financial_snapshot.py` | 输出单只股票近 N 年年报 ROE、净利润、毛利率、资产负债率；默认示例为贵州茅台。 |
| `summary.py` | 读取最近 5 个交易日的价格和指标，输出终端摘要表。 |
| `fundamental_screen.py` | 筛选近 10 年每年年报 ROE 大于阈值的公司，并输出平均 ROE、负债率和净利润增长率。 |
| `scoring2.py` | 基于 KDJ、CCI、布林带、均线和成交量等条件，对标的进行短期关注度打分。 |
| `scoring_benchmark.py` | 用趋势和波动率规则，对指定 ETF 最近 5 个交易日进行打分。 |
| `bond_stock_yearly_return.py` | 计算债券 ETF、沪深 300 ETF、中证 1000 ETF 等标的最近 10 个自然年的年度收益率。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `backtest/`

| 文件 | 用途 |
| --- | --- |
| `strategy_stock300bond.py` | 单一起始日期的沪深 300 ETF / 债券 ETF 动态轮动回测。 |
| `strategy_stock300bond_multi_start.py` | 多个起始年份的股债轮动回测，用于观察策略在不同起点下的表现。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `visualization/`

| 文件 | 用途 |
| --- | --- |
| `plot_etf.py` | 从 SQLite 读取行情数据，使用 `mplfinance` 绘制 K 线、成交量和均线图。 |
| `plot_indicators.py` | 从 SQLite 读取价格和指标数据，使用 `matplotlib` 绘制价格、均线、布林带、KDJ 和 CCI。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `data/`

`data/` 目录中保存了一些历史 CSV 文件和指标 CSV 文件，例如：

```text
data/sh510310.csv
data/sh510310_indicators.csv
```

当前主流程以 SQLite 为核心，CSV 文件更像是历史数据备份或早期开发阶段的本地产物。`.gitignore` 已配置忽略 `data/` 和 `*.csv`。

## 安装

建议使用 Python 3.10+ 或 Python 3.11。

```bash
git clone <your-repository-url>
cd quant-kl
```

创建并激活虚拟环境：

```bash
python -m venv venv
source venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 快速开始

运行主流程：

```bash
python main.py
```

该命令会执行：

1. 初始化 SQLite 数据库
2. 读取 `config/watchlist.py`
3. 更新 ETF、股票和市场风险指标序列到 `price_data`
4. 将每个标的的更新结果写入 `data_update_log`
5. 为可计算的价格资产计算技术指标并写入 `indicators`

`main.py` 不会自动输出指标摘要。查看摘要请使用 `python -m analysis.summary --group ...`。

## 常用命令

初始化或刷新资产基础信息：

```bash
python -m database.init_asset_info
```

运行数据质量检查：

```bash
python -m database.data_quality_check
```

### 股票池和财务数据

财务数据流程分成三步：

1. 先同步 `stock_universe`，也就是本地股票池。
2. 再根据股票池批量下载财务原始数据：新浪财务指标和新浪三大报表。
3. 最后根据已经入库的财报数据计算巴菲特式衍生指标，并写入 `buffett_metrics`。

这些步骤没有放进 `python main.py`，是因为全市场财报更新很慢，也更容易受到 AkShare 接口限速或字段变化影响。把它独立成脚本，可以避免日常行情更新被重任务拖慢。

同步沪深 A 股股票池：

```bash
python -m data_fetch.update_stock_universe
```

推荐完整更新顺序：

```bash
python -m data_fetch.update_stock_universe
python -m data_fetch.update_financial_data --sleep 12 --retries 2
python -m analysis.calculate_buffett_metrics --annual-only
```

如果只想先试跑一只股票：

```bash
python -m data_fetch.update_financial_data --symbol sh600519 --sleep 0 --retries 1
python -m analysis.calculate_buffett_metrics --symbol sh600519 --annual-only
```

批量更新股票财务原始数据：

```bash
python -m data_fetch.update_financial_data
```

默认会下载两个数据集：

- `indicators`：新浪财务指标，写入 `financial_indicators`。
- `statements`：新浪三大报表，写入 `financial_statement_items`。

脚本会按各表主键判断增量：如果本地已经有接口返回的最新数据，则跳过写入；如果本地缺少最新数据，则只写入缺少的新记录。

默认从 2015 年开始下载财务指标和三大报表；以后年份增加时，旧数据会保留，新股票也会尽量补齐 2015 年至今的可得数据。

分批慢速更新股票财务原始数据：

```bash
python -m data_fetch.update_financial_data --limit 100 --offset 0 --sleep 12 --retries 2
```

只下载新浪财务指标：

```bash
python -m data_fetch.update_financial_data --datasets indicators
```

强制刷新已有财务记录，用于更新字段口径：

```bash
python -m data_fetch.update_financial_data --symbol sh600519 --force-refresh
```

只更新单只股票财务原始数据：

```bash
python -m data_fetch.update_financial_data --symbol sh600519
```

### 美国股票、ETF 和市场风险指标数据

美国行情数据来自 Stooq CSV，watchlist 中的 ticker 会统一写成 `us_` 前缀的内部 symbol，例如 `AAPL` 入库为 `us_aapl`，`BRK-B` 入库为 `us_brk_b`。Stooq 下载符号会自动转换为 `aapl.us`、`spy.us`、`brk-b.us` 这种格式。

Stooq 现在的 CSV 下载需要免费 apikey。先打开类似下面的页面，按 Stooq 页面提示完成 captcha 并复制带 apikey 的下载链接：

```text
https://stooq.com/q/d/?s=aapl.us&get_apikey
```

然后把 key 设置到当前终端：

```bash
export STOOQ_API_KEY="你的StooqKey"
```

如需每次打开终端都自动生效，可以写入 `~/.zshrc`：

```bash
echo 'export STOOQ_API_KEY="你的StooqKey"' >> ~/.zshrc
source ~/.zshrc
```

注意：Stooq 的 `Close` 会直接写入 `price_data.close`。这和旧版 `yfinance auto_adjust=True` 的复权价格口径可能不完全一致；如果未来要做严格跨源回测，需要单独校验复权口径。

VIX / VXN 不走 Stooq，而是使用 Cboe 官方日度 CSV。watchlist 中仍然写成 `^vix`、`^vxn`，入库时会转换为内部 symbol：

| watchlist 代码 | 入库 symbol | 数据源 |
| --- | --- | --- |
| `^vix` | `cboe_vix` | Cboe `VIX_History.csv` |
| `^vxn` | `cboe_vxn` | Cboe `VXN_History.csv` |

Cboe CSV 没有成交量字段，因此 `price_data.volume` 会填 `0`。VIX / VXN 本身就是市场风险指标，不会写入 `indicators` 表，也不会计算 MA、KDJ、CCI 等技术指标。

`python main.py` 会自动读取 `WATCHLIST["US_ETF"]`、`WATCHLIST["US_STOCK"]`、`WATCHLIST["US_INDEX"]` 和 `WATCHLIST["US_MARKET_INDICATOR"]` 并更新行情 / 指标序列：

```bash
python main.py
```

`main.py` 只负责更新数据和计算可计算的技术指标，不再自动输出所有标的的摘要。需要查看最近几天摘要时，使用 `analysis.summary` 的筛选命令。

当前美国市场只下载行情，不下载美国上市公司财务数据。`TSM`、`ASML` 这类 ADR / foreign issuer 的 SEC 披露口径常见 `20-F`、IFRS、非 USD 币种，和美国本土公司 `10-K/10-Q`、US-GAAP 口径不可直接混用，因此暂时不把 `WATCHLIST["US_STOCK"]` 纳入财务下载范围。

`data_fetch.update_us_financial_data` 目前只是占位脚本，运行后会提示美国财务下载已关闭，不会访问 SEC，也不会写入 `financial_statement_items`：

```bash
python -m data_fetch.update_us_financial_data
```

下载完成后，计算巴菲特式衍生指标：

```bash
python -m analysis.calculate_buffett_metrics
```

只计算年报口径的巴菲特式衍生指标：

```bash
python -m analysis.calculate_buffett_metrics --annual-only
```

只计算单只股票：

```bash
python -m analysis.calculate_buffett_metrics --symbol sh600519 --annual-only
```

输出单只股票近 10 年核心财务指标，例如贵州茅台：

```bash
python -m analysis.stock_financial_snapshot --symbol sh600519 --years 10
```

也可以直接使用默认示例：

```bash
python -m analysis.stock_financial_snapshot
```

运行 ROE 基本面筛选或巴菲特式指标计算前，建议至少先执行过一次：

```bash
python -m data_fetch.update_stock_universe
python -m data_fetch.update_financial_data --limit 100 --sleep 12
python -m analysis.calculate_buffett_metrics --annual-only
```

如果要全市场更新，可以去掉 `--limit`，但耗时会明显更长。

当前财务数据口径：

- 三大报表只使用新浪端口，不使用东方财富端口。
- 当前暂不下载巨潮分红事件，数据库也不保留分红事件表。
- 财务数据不保存日频估值表；`buffett_metrics` 中涉及市值的字段只作为报告期衍生结果保存。
- 如果 `financial_indicators` 中某些年份毛利率为空，`stock_financial_snapshot.py` 会尝试用新浪利润表的营业收入和营业成本补算。

计算或刷新技术指标：

```bash
python -m analysis.indicators
```

输出最近 5 个交易日摘要。`analysis.summary` 支持用 `--group` 按分组筛选，也支持用 `--symbols` 手动指定内部 symbol：

```bash
python -m analysis.summary --group cn-etf --days 5
```

常用分组：

| 分组 | 含义 | 示例命令 |
| --- | --- | --- |
| `cn-etf` | 中国 ETF 指数类标的，来自 `WATCHLIST["ETF"]` | `python -m analysis.summary --group cn-etf` |
| `cn-stock` | 中国股票，来自 `WATCHLIST["STOCK"]` | `python -m analysis.summary --group cn-stock` |
| `us-etf` | 美国 ETF，来自 `WATCHLIST["US_ETF"]` | `python -m analysis.summary --group us-etf` |
| `us-stock` | 美国股票，来自 `WATCHLIST["US_STOCK"]` | `python -m analysis.summary --group us-stock` |
| `us-market-indicator` | Cboe VIX / VXN，只输出价格序列 | `python -m analysis.summary --group us-market-indicator` |
| `us-risk` | 美国风险监控组合，默认包含 QQQ、SMH、VIX、VXN | `python -m analysis.summary --group us-risk` |

手动指定标的：

```bash
python -m analysis.summary --symbols sh510310 us_qqq us_smh cboe_vix cboe_vxn --days 5
```

运行 ROE 基本面筛选：

```bash
python -m analysis.fundamental_screen
```

默认筛选近 10 年每一年年报 ROE 都大于 15% 的公司，并按平均 ROE 从高到低排列。

导出 ROE 基本面筛选结果：

```bash
python -m analysis.fundamental_screen --output data/roe_screen.csv
```

运行短期技术指标打分：

```bash
python -m analysis.scoring2
```

运行趋势 / 波动率打分示例：

```bash
python -m analysis.scoring_benchmark
```

查看最近 10 年自然年度收益率：

```bash
python -m analysis.bond_stock_yearly_return
```

绘制 K 线图：

```bash
python -m visualization.plot_etf
```

绘制技术指标图：

```bash
python -m visualization.plot_indicators
```

运行单一起始日期股债轮动回测：

```bash
python -m backtest.strategy_stock300bond
```

运行多起始年份股债轮动回测：

```bash
python -m backtest.strategy_stock300bond_multi_start
```

## Watchlist 配置

关注标的在 `config/watchlist.py` 中维护：

```python
WATCHLIST = {
    "ETF": [
        "sh510310",
        "sh510100",
        "sh511010",
    ],
    "STOCK": [
        "sh600519",
    ],
    "US_ETF": [
        "QQQ",
        "SMH",
    ],
    "US_STOCK": [
        "AAPL",
        "MSFT",
        "NVDA",
    ],
    "US_MARKET_INDICATOR": [
        "^vix",
        "^vxn",
    ],
}
```

添加或删除标的后，重新运行 `python main.py` 即可按新列表更新数据。

内部 symbol 命名规则：

- 中国 ETF / 股票保持 watchlist 里的原始 symbol，例如 `sh510310`。
- 美国 ETF / 股票会转成 `us_` 前缀，例如 `QQQ` 入库为 `us_qqq`，`BRK-B` 入库为 `us_brk_b`。
- Cboe 市场风险指标会转成 `cboe_` 前缀，例如 `^vix` 入库为 `cboe_vix`。

## 数据流

### 日线行情与技术指标

```text
database/schema/base.sql
database/migrations/*.sql
        |
        v
database/quant.db: price_data / indicators / asset_info / data_update_log

config/watchlist.py
        |
        v
data_fetch/fetch_etf.py / data_fetch/fetch_stock.py
data_fetch/fetch_us_market.py / data_fetch/fetch_cboe_market.py
        |
        v
data_manager/data_manager.py
        |------------------------------+
        v
database/quant.db: price_data
        |
        +--> database/quant.db: data_update_log
        |
        v
analysis/indicators.py
        |
        v
database/quant.db: indicators
        |
        +--> analysis/summary.py --group ...
        +--> analysis/scoring2.py
        +--> analysis/scoring_benchmark.py
        +--> visualization/
        +--> backtest/

database/init_asset_info.py
        |
        v
database/quant.db: asset_info

database/data_quality_check.py
        |
        v
database/quant.db: price_data
```

### 股票池与财务数据

```text
data_fetch/update_stock_universe.py
        |
        v
database/quant.db: stock_universe
        |
        v
data_fetch/update_financial_data.py
        |
        v
data_fetch/fetch_financial.py
        |------------------------------+
        |                              |
        v                              v
database/quant.db: financial_indicators / financial_statement_items
        |
        v
analysis/calculate_buffett_metrics.py
        |
        v
database/quant.db: buffett_metrics
        |
        +--> analysis/fundamental_screen.py
```

## 数据库结构维护

数据库结构现在分成两类文件：

| 文件 | 作用 |
| --- | --- |
| `database/schema/base.sql` | 全新数据库使用的完整结构。它应该始终代表“当前最新版本”。 |
| `database/migrations/00N_*.sql` | 旧数据库升级到新结构时执行的增量步骤。每个版本号对应一个迁移文件。 |
| `database/db_utils.py` | 负责判断当前数据库版本、执行迁移、写入 `schema_version`。 |

以后如果要新增或删除字段，推荐按这个顺序做：

1. 修改 `database/schema/base.sql`，让新数据库直接拥有最新结构。
2. 新增一份迁移文件，例如 `database/migrations/006_add_xxx.sql`。
3. 在 `database/db_utils.py` 中新增 `_migrate_to_v6()`。
4. 在 `_run_migrations()` 中追加版本判断。
5. 把 `CURRENT_SCHEMA_VERSION` 改成新的版本号。

这样可以同时照顾两种情况：新机器第一次建库，以及你本地已有旧 `quant.db` 需要平滑升级。

当前迁移版本：

| 版本 | 内容 |
| --- | --- |
| v1 | 为旧版 `price_data` 和 `indicators` 补充 `created_at`、`updated_at`。 |
| v2 | 新增 `stock_universe` 股票池表。 |
| v3 | 新增 `financial_indicators` 财务指标表。 |
| v4 | 历史占位版本。曾用于固定资产比重字段，后续已移除。 |
| v5 | 从旧库的 `financial_indicators` 中删除 `fixed_asset_ratio` 字段。 |
| v6 | 扩展财务指标字段，新增三大报表明细和巴菲特式衍生指标表。 |
| v7 | 暂停分红事件下载，删除 `financial_dividend_events` 表。 |
| v8 | 移除分红相关指标字段。 |
| v9 | 新增 `us_company_map`。当前美国公司财务下载已关闭，该表仅作为未来重新启用 SEC 数据时的预留结构。 |

## 注意事项

- 本项目依赖 `akshare` 的数据接口，数据可用性和字段格式可能随上游接口变化。
- `database/quant.db`、`data/`、`*.csv` 属于本地数据文件，通常不应提交到公开仓库。
- 新建数据库会通过 `database/schema/base.sql` 创建完整表结构；旧数据库会通过 `schema_version` 和 `database/migrations/` 执行版本迁移。
- 后续修改数据库结构时，推荐同时更新 `database/schema/base.sql` 和新增一份 `database/migrations/00N_*.sql`，再递增 `database/db_utils.py` 中的 `CURRENT_SCHEMA_VERSION`。
- 当前 v1 迁移会为旧版 `price_data` 和 `indicators` 补齐 `created_at`、`updated_at` 字段，并记录版本号。
- 第一版迁移机制保持简单，不重建历史表，也不会为已有旧表补复合外键约束。如需完全采用最新约束，建议先备份旧数据库，再重建数据库或后续补充更完整的迁移脚本。
- `asset_info` 暂时由 `database/init_asset_info.py` 手工维护，不从 `akshare` 自动同步。
- `financial_indicators.announce_date` 目前保留为空字段；新浪三大报表的公告日保存在 `financial_statement_items.announce_date`。做严格历史回测时，应按公告日判断当时哪些财报已经可见，避免未来函数。
- 财务数据不保存日频估值表；`buffett_metrics` 中涉及市值的字段只作为报告期层面的衍生结果保存。

## 免责声明

本仓库仅用于个人量化研究、编程练习和策略验证。所有输出、指标、评分和回测结果都不代表未来收益，也不构成任何投资建议。
