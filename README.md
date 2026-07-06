# quant-kl

一个简化的私人量化交易研究系统，主要用于下载中国市场 ETF / A 股行情、保存到本地 SQLite 数据库、计算技术指标、生成摘要、绘图，并验证简单的股债轮动策略。

> 本项目用于个人学习和研究，不构成任何投资建议。

## ETF 日常短命令

如果只是日常观察 ETF，可以优先使用 `python -m quant e ...` 这一组短命令，不必记住分散在各个模块里的脚本名。

| 任务 | 命令 |
| --- | --- |
| 更新行情并计算技术指标 | `python -m quant e update` |
| 查看中美 ETF、加拿大/美国个股和美国指数摘要 | `python -m quant e summary --days 5` |
| 只看中国 ETF 摘要 | `python -m quant e cn --days 5` |
| 只看美国 ETF 摘要 | `python -m quant e us --days 5` |
| 查看美国风险观察组合 | `python -m quant e risk --days 5` |
| 短期技术指标打分 | `python -m quant e score` |
| 趋势 / 波动率打分示例 | `python -m quant e trend` |
| 聚合周线并计算周线指标 | `python -m quant e weekly` |
| 查看中美 ETF、个股和美国指数周线摘要 | `python -m quant e weekly-summary --days 5` |
| 补全单个美国股票 / ETF / 指数历史行情 | `python -m quant e backfill NDQ` |
| 生成每日交易研究日报 | `python -m quant report daily` |

也可以给当前 shell 加一个别名，让命令更短：

```bash
alias q='python -m quant'
```

之后可以这样运行：

```bash
q e update
q e summary
q e risk
q e weekly
q e weekly-summary
q report daily
```

日报默认读取本地 SQLite 数据库，不重新下载行情，生成到
`reports/daily/YYYY-MM-DD.md`。可以用 `--date` 指定日报日期，用
`--output-dir` 指定输出目录。

## A 股财务数据短命令

下载一只 A 股从指定会计年度开始的财务指标和三大报表，并写入 SQLite：

```bash
python -m quant f download sh600519 --start-year 2022
```

股票代码也可以写成 `sz000001` 或不带市场前缀的六位代码。默认下载
`indicators,statements` 两个数据集，分别 upsert 到
`financial_indicators` 和 `financial_statement_items`。

可以只选择其中一个数据集，或在本地已是最新时强制刷新已有记录：

```bash
python -m quant f download 600519 --start-year 2022 --datasets indicators
python -m quant fundamental download sh600519 --start-year 2022 --force-refresh
```

`--start-year` 只限制本次下载和写入的数据范围，不会删除数据库中该股票更早的历史记录。原始模块命令仍然可用：

```bash
python -m data_fetch.update_financial_data --symbol sh600519 --start-year 2022
```

## 功能概览

- 使用 `akshare` 下载 ETF 和 A 股历史行情
- 使用 SQLite (`database/quant.db`) 本地存储行情、技术指标、资产信息和数据更新日志
- 支持按 `config/watchlist.py` 批量更新关注标的
- 支持同步沪深 A 股股票池，并按股票池批量下载 A 股财务指标和三大报表
- 支持 watchlist 中的美国股票、ETF 和指数：当前只下载行情，优先使用 FMP Basic，失败时使用 Twelve Data
- 支持 watchlist 中的加拿大多伦多股票：使用 Alpha Vantage 下载日线行情，例如 `RY.TRT` / `TD.TRT`
- 支持用 Cboe 官方 CSV 下载 VIX / VXN / VVIX / SKEW 日度市场风险指标
- 支持用 FRED 下载 10Y / 2Y 美债收益率，并在本地计算 10Y-2Y 利差
- 支持基于新浪财报数据计算自由现金流、ROIC、净负债率等巴菲特式基本面指标
- 支持基于年报 ROE、负债率、净利润增长率等指标做基本面筛选
- 通过 `database/schema/base.sql` 初始化新数据库，并使用 `database/migrations/` 管理旧数据库结构迁移
- 记录每次行情更新结果，方便追踪成功、失败、空数据和无新增数据等状态
- 提供简单数据质量检查，覆盖重复交易日、OHLC 异常、缺失价格和成交量等问题
- 计算均线、收益率、波动率、布林带、成交量均线、KDJ、CCI 等指标
- 支持由日线行情聚合周线行情，并计算周级别均线、布林带、KDJ、CCI 等指标
- 支持按分组输出最近交易日技术指标摘要、Cboe / FRED 市场指标均线和简单打分结果
- 支持每日交易研究日报展示美国国债收益率曲线摘要和加拿大个股摘要
- 支持估算 TD Science & Technology Fund - D (TDB3098) 单日涨跌幅
- 绘制 K 线图、均线、布林带、KDJ、CCI、VIX / VXN / VVIX / SKEW 风险指标等图表
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
│   ├── short_term_oversold_score.py
│   ├── etf_trend_volatility_score.py
│   ├── tdb3098_daily_return.py
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
│   ├── fetch_alpha_vantage_ca.py
│   ├── fetch_etf.py
│   ├── fetch_cboe_market.py
│   ├── fetch_financial.py
│   ├── fetch_fred_treasury.py
│   ├── fetch_us_market.py
│   ├── fetch_stock.py
│   ├── update_financial_data.py
│   ├── update_us_financial_data.py
│   └── update_stock_universe.py
├── data_manager/
│   ├── __init__.py
│   └── data_manager.py
├── repositories/
│   ├── __init__.py
│   ├── price_repository.py
│   └── update_log_repository.py
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
│   │   ├── 009_create_us_company_map.sql
│   │   └── 010_create_weekly_price_and_indicators.sql
│   ├── db_utils.py
│   ├── init_asset_info.py
│   ├── data_quality_check.py
│   └── quant.db
└── visualization/
    ├── __init__.py
    ├── plot_etf.py
    ├── plot_indicators.py
    └── plot_vix_vxn.py
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
| `watchlist.py` | 维护关注标的列表。包括中国 ETF / A 股、加拿大股票、美国 ETF / 股票 / 指数、Cboe 风险指标和 FRED 美债收益率序列。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `data_fetch/`

| 文件 | 用途 |
| --- | --- |
| `fetch_alpha_vantage_ca.py` | 使用 Alpha Vantage 下载加拿大多伦多股票日线行情，并整理成 `price_data` 兼容字段。 |
| `fetch_cboe_market.py` | 使用 Cboe 官方 CSV 下载 VIX / VXN / VVIX / SKEW 日度市场风险指标，并整理成 `price_data` 兼容字段。 |
| `fetch_etf.py` | 使用 `akshare.fund_etf_hist_sina` 下载单只 ETF 历史行情。 |
| `fetch_financial.py` | 使用 AkShare 下载并整理单只 A 股财务指标和三大报表。三大报表使用新浪端口，不使用东方财富端口。 |
| `fetch_fred_treasury.py` | 使用 FRED CSV 下载 10Y / 2Y 美债收益率，并整理成 `price_data` 兼容字段。 |
| `fetch_us_market.py` | 使用 FMP Basic / Twelve Data 下载美国股票、ETF 和指数历史行情，并整理成 `price_data` 兼容字段。 |
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

### `repositories/`

| 文件 | 用途 |
| --- | --- |
| `price_repository.py` | `price_data` 表读写封装，包括查询最新日期和批量插入行情。 |
| `update_log_repository.py` | `data_update_log` 表写入封装，记录每次行情更新结果。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `database/`

| 文件 | 用途 |
| --- | --- |
| `schema/base.sql` | SQLite 新库建表脚本。一次性创建当前最新版日线/周线行情和指标表、资产信息、财务数据、更新日志、`schema_version` 等表。 |
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
| `weekly_price_data` | 周线行情数据：由 `price_data` 聚合生成，字段与日线行情一致。 |
| `weekly_indicators` | 周线技术指标数据：基于 `weekly_price_data` 计算，字段与日线指标一致。 |
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
| `indicators.py` | 从 `price_data` 读取行情，计算日线技术指标；也可聚合生成周线行情并计算周线技术指标。 |
| `calculate_buffett_metrics.py` | 从财务指标、三大报表和行情数据计算巴菲特式基本面指标，并写入 `buffett_metrics` 表。 |
| `stock_financial_snapshot.py` | 输出单只股票近 N 年年报 ROE、净利润、毛利率、资产负债率；默认示例为贵州茅台。 |
| `summary.py` | 读取最近 5 个交易日的价格和指标，输出终端摘要表。 |
| `fundamental_screen.py` | 筛选近 10 年每年年报 ROE 大于阈值的公司，并输出平均 ROE、负债率和净利润增长率。 |
| `short_term_oversold_score.py` | 基于 KDJ、CCI、布林带和均线等条件，对标的进行短期超跌关注度打分。 |
| `etf_trend_volatility_score.py` | 用趋势和波动率规则，对指定 ETF 最近 5 个交易日进行打分。 |
| `tdb3098_daily_return.py` | 根据 TD Science & Technology Fund - D 前十大持仓权重估算基金单日涨跌幅；Samsung / SK Hynix return 由手动百分比输入。 |
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
| `plot_vix_vxn.py` | 从 SQLite 读取 Cboe 市场风险指标，绘制最近两个月 VIX / VXN、SKEW、VVIX 和 VXN-VIX 差值 subplot。 |
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
3. 更新 ETF、股票、加拿大股票、美国指数、Cboe 风险指标和 FRED 美债收益率序列到 `price_data`
4. 将每个标的的更新结果写入 `data_update_log`
5. 本地生成 `fred_t10y2y` 10Y-2Y 美债利差序列
6. 为可计算的价格资产计算技术指标并写入 `indicators`

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

### 北美股票、ETF 和市场风险指标数据

美国股票、ETF 和美国指数行情优先来自 FMP Basic，Twelve Data 作为备用源。watchlist 中的 ticker 会统一写成 `us_` 前缀的内部 symbol，例如 `AAPL` 入库为 `us_aapl`，`BRK-B` 入库为 `us_brk_b`。Nasdaq Composite 仍可在配置中写成 `NDQ`，入库为 `nasdaq`，下载时会优先映射到 FMP 指数符号，并在备用源中映射到 Twelve Data 指数符号。

加拿大多伦多股票来自 Alpha Vantage，使用其加拿大交易所后缀，例如 `RY.TRT` 入库为 `ca_ry_trt`，`TD.TRT` 入库为 `ca_td_trt`。Alpha Vantage 免费版 `TIME_SERIES_DAILY` 的 `compact` 模式返回最近 100 条日线；项目会把每天新增的数据继续累积到本地 SQLite，因此长期运行后历史会逐步增加。

FRED 美债收益率不需要 API key。项目会下载 `DGS10` 和 `DGS2`，并在本地按同日 close 生成 `fred_t10y2y`：

| 数据 | 入库 symbol | 说明 |
| --- | --- | --- |
| `DGS10` | `fred_dgs10` | 10Y 美债收益率，数值 `4.25` 表示 `4.25%` |
| `DGS2` | `fred_dgs2` | 2Y 美债收益率 |
| 本地计算 | `fred_t10y2y` | 10Y - 2Y 利差，数值 `-0.35` 表示 `-0.35 个百分点` |

FMP、Twelve Data 和 Alpha Vantage 下载需要设置环境变量。这里的中文只是占位符，实际使用时要替换成你账户后台复制出来的真实 key：

```bash
export FMP_API_KEY="你的FMP key"
export TWELVE_DATA_API_KEY="你的Twelve Data key"
export ALPHA_VANTAGE_API_KEY="你的Alpha Vantage key"
```

如需每次打开终端都自动生效，可以写入 `~/.zshrc`：

```bash
echo 'export FMP_API_KEY="你的FMP key"' >> ~/.zshrc
echo 'export TWELVE_DATA_API_KEY="你的Twelve Data key"' >> ~/.zshrc
echo 'export ALPHA_VANTAGE_API_KEY="你的Alpha Vantage key"' >> ~/.zshrc
source ~/.zshrc
```

可以用下面的命令检查当前终端是否已经读到 key：

```bash
echo $FMP_API_KEY
echo $TWELVE_DATA_API_KEY
echo $ALPHA_VANTAGE_API_KEY
```

FMP 返回 `adjClose` 时，项目会用 `adjClose / close` 对 `open`、`high`、`low`、`close` 做同比例前复权，写入 `price_data` 的 `close` 为复权后的收盘价。Twelve Data 备用源当前按其 time series 返回的 OHLC 写入。Alpha Vantage 加拿大股票当前按其 daily OHLC 写入。已有标的日常增量更新会从数据库最新日期的下一天下载到今天；如果美国标的数据库里还没有记录，会按 FMP Basic 免费历史范围默认下载最近约 5 年。

如果要给单个美国股票、ETF 或美国指数补历史，不想跑完整 watchlist，可以继续使用原来的 `backfill` 命令。它只补缺失日期，不覆盖已有同日记录；完成后会自动重新计算日线指标：

```bash
python -m quant e backfill NDQ
python -m quant e backfill QQQ
python -m quant e backfill AAPL
```

如果只想补最近几天，可以显式指定日期区间。FMP 和 Twelve Data 都会使用这个区间：

```bash
python -m quant e backfill QQQ --start-date 2026-06-13 --end-date 2026-06-16
python -m quant e backfill BRK-B --start-date 2026-06-13 --end-date 2026-06-16
```

如果 FMP 下载失败，程序会尝试 Twelve Data 备用源，不再自动请求 Stooq，避免再次触发 Stooq 人工验证码。

常见失败排查：

| 现象 | 常见原因 | 处理 |
| --- | --- | --- |
| `缺少 FMP_API_KEY` | 当前终端没有读到 FMP key | 重新执行 `source ~/.zshrc`，或检查 `echo $FMP_API_KEY` |
| `缺少 TWELVE_DATA_API_KEY` | 当前终端没有读到 Twelve Data key | 重新执行 `source ~/.zshrc`，或检查 `echo $TWELVE_DATA_API_KEY` |
| `缺少 ALPHA_VANTAGE_API_KEY` | 当前终端没有读到 Alpha Vantage key | 免费注册 key 后写入 `~/.zshrc`，再执行 `source ~/.zshrc` |
| `HTTP Error 402: Payment Required` | FMP Basic 对该 symbol、接口或日期范围没有权限 | 程序会自动尝试 Twelve Data；也可以用 `--start-date/--end-date` 缩小范围 |
| Twelve Data 返回额度或权限错误 | 免费额度用完，或该 symbol 不支持 | 稍后重试，或登录 Twelve Data 后台检查额度 |
| Alpha Vantage 返回额度提示 | 免费版每日请求数用完 | 减少 `CA_STOCK` 数量，或等第二天额度恢复 |

VIX / VXN / VVIX / SKEW 使用 Cboe 官方日度 CSV。watchlist 中仍然写成 `^vix`、`^vxn`、`^vvix`、`^skew`，入库时会转换为内部 symbol：

| watchlist 代码 | 入库 symbol | 数据源 |
| --- | --- | --- |
| `^vix` | `cboe_vix` | Cboe `VIX_History.csv` |
| `^vxn` | `cboe_vxn` | Cboe `VXN_History.csv` |
| `^vvix` | `cboe_vvix` | Cboe `VVIX_History.csv` |
| `^skew` | `cboe_skew` | Cboe `SKEW_History.csv` |

Cboe CSV 和 FRED 收益率序列没有成交量字段，因此 `price_data.volume` 会填 `0`。这些市场指标会写入 `indicators` 表，但只计算 `MA20` 和 `MA60`，不会计算 KDJ、CCI、布林带等价格交易指标。

`python main.py` 会自动读取 `WATCHLIST["CA_STOCK"]`、`WATCHLIST["US_ETF"]`、`WATCHLIST["US_STOCK"]`、`WATCHLIST["US_INDEX"]`、`WATCHLIST["US_MARKET_INDICATOR"]` 和 `WATCHLIST["US_TREASURY_YIELD"]` 并更新行情 / 指标序列：

```bash
python main.py
```

`main.py` 只负责更新数据和计算可计算的技术指标，不再自动输出所有标的的摘要。需要查看最近几天摘要时，使用 `analysis.summary` 的筛选命令。

当前美国市场只下载行情，不下载美国上市公司财务数据。`TSM`、`ASML` 这类 ADR / foreign issuer 的 SEC 披露口径常见 `20-F`、IFRS、非 USD 币种，和美国本土公司 `10-K/10-Q`、US-GAAP 口径不可直接混用，因此暂时不把 `WATCHLIST["US_STOCK"]` 纳入财务下载范围。

`data_fetch.update_us_financial_data` 目前只是占位脚本，运行后会提示美国财务下载已关闭，不会访问 SEC，也不会写入 `financial_statement_items`：

```bash
python -m data_fetch.update_us_financial_data
```

### TDB3098 基金单日涨跌幅估算

`analysis.tdb3098_daily_return` 用 TD Science & Technology Fund - D 当前前十大持仓权重估算基金单日涨跌幅。脚本会从 `price_data` 读取 NVDA、TSM、AMD、AVGO、AAPL、INTC、ASML 的相邻交易日收盘价计算 return；Samsung 和 SK Hynix 的当日涨跌幅需要手动输入；Anthropic 和剩余未知持仓暂按这 7 支可下载股票的简单平均 return 估算。

手动输入一律按百分比数值理解：

```bash
python -m analysis.tdb3098_daily_return \
  --date 2026-06-24 \
  --samsung-return 1.2 \
  --sk-hynix-return -0.8
```

上例中 `1.2` 表示上涨 `1.2%`，`-0.8` 表示下跌 `0.8%`。

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

默认只计算日线指标，并写入 `indicators`。如果要计算周线指标，可以先确保日线行情已经更新，再运行：

```bash
python -m analysis.indicators --frequency weekly
```

也可以一次计算日线和周线：

```bash
python -m analysis.indicators --frequency all
```

周线行情会写入 `weekly_price_data`，周线指标会写入 `weekly_indicators`。聚合规则为：周内第一根日线作为 `open`，最高价取最大值，最低价取最小值，收盘价取该周最新一根日线的 `close`，成交量求和。如果在周中运行，最后一根周线会使用本周一到最新交易日的数据，`date` 记录最新交易日；下次运行会按 symbol 重建周线派生数据，避免保留过期的周中临时周线。

输出最近 5 个交易日摘要。`analysis.summary` 默认读取日线表，支持用 `--group` 按分组筛选，也支持用 `--symbols` 手动指定内部 symbol：

```bash
python -m analysis.summary --group cn-etf --days 5
```

如果已经运行过周线聚合和周线指标计算，可以输出最近 5 根周线摘要：

```bash
python -m quant e weekly-summary --days 5
python -m analysis.summary --group cn-etf --days 5 --frequency weekly
```

常用分组：

| 分组 | 含义 | 示例命令 |
| --- | --- | --- |
| `cn-etf` | 中国 ETF 指数类标的，来自 `WATCHLIST["ETF"]` | `python -m analysis.summary --group cn-etf` |
| `cn-stock` | 中国股票，来自 `WATCHLIST["STOCK"]` | `python -m analysis.summary --group cn-stock` |
| `ca-stock` | 加拿大股票，来自 `WATCHLIST["CA_STOCK"]` | `python -m analysis.summary --group ca-stock` |
| `us-etf` | 美国 ETF，来自 `WATCHLIST["US_ETF"]` | `python -m analysis.summary --group us-etf` |
| `us-stock` | 美国股票，来自 `WATCHLIST["US_STOCK"]` | `python -m analysis.summary --group us-stock` |
| `us-index` | 美国指数，来自 `WATCHLIST["US_INDEX"]`，例如 `NDQ` / Nasdaq Composite | `python -m analysis.summary --group us-index` |
| `us-market-indicator` | Cboe VIX / VXN / VVIX / SKEW，输出价格和 MA20 / MA60 | `python -m analysis.summary --group us-market-indicator` |
| `us-treasury-yield` | FRED 10Y / 2Y 美债收益率和 10Y-2Y 利差 | `python -m analysis.summary --group us-treasury-yield` |
| `us-risk` | 美国风险监控组合，默认包含 QQQ、SMH、VIX、VXN、VVIX、SKEW | `python -m analysis.summary --group us-risk` |

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
python -m analysis.short_term_oversold_score
```

运行趋势 / 波动率打分示例：

```bash
python -m analysis.etf_trend_volatility_score
```

查看最近 10 年自然年度收益率：

```bash
python -m analysis.bond_stock_yearly_return
```

绘制 K 线图：

```bash
python -m visualization.plot_etf
```

默认绘制 `sh510310` 的完整历史 K 线。如果只想看最近 18 个月：

```bash
python -m visualization.plot_etf --symbol sh510310 --months 18
```

绘制美国 ETF 或风险监控 ETF：

```bash
python -m visualization.plot_etf --group us-etf --months 18
python -m visualization.plot_etf --group us-risk --months 18
```

手动指定多个标的并保存图片：

```bash
python -m visualization.plot_etf --symbols sh510310 us_qqq us_smh --months 18 --output data/etf_recent_18m.png
```

多标的保存时，脚本会自动把 symbol 加到文件名里，避免图片互相覆盖，例如 `etf_recent_18m_us_qqq.png`。

绘制技术指标图：

```bash
python -m visualization.plot_indicators
```

绘制 Cboe 市场风险指标图：

```bash
python -m visualization.plot_vix_vxn
```

该图默认读取最近 2 个月数据，并生成 4 个 subplot：

- VIX 和 VXN 同图
- SKEW 单独一图
- VVIX 单独一图
- VXN - VIX 差值单独一图

保存 Cboe 市场风险指标图到图片文件：

```bash
python -m visualization.plot_vix_vxn --output data/cboe_risk_indicators_recent_2m.png
```

如果想调整回看月份数，可以使用 `--months`：

```bash
python -m visualization.plot_vix_vxn --months 3 --output data/cboe_risk_indicators_recent_3m.png
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
    "CA_STOCK": [
        "RY.TRT",
        "TD.TRT",
    ],
    "US_ETF": [
        "QQQ",
        "SMH",
    ],
    "US_INDEX": [
        "NDQ",
    ],
    "US_STOCK": [
        "AAPL",
        "MSFT",
        "NVDA",
    ],
    "US_MARKET_INDICATOR": [
        "^vix",
        "^vxn",
        "^vvix",
        "^skew",
    ],
    "US_TREASURY_YIELD": [
        "DGS10",
        "DGS2",
    ],
}
```

添加或删除标的后，重新运行 `python main.py` 即可按新列表更新数据。

内部 symbol 命名规则：

- 中国 ETF / 股票保持 watchlist 里的原始 symbol，例如 `sh510310`。
- 加拿大股票会转成 `ca_` 前缀，例如 `RY.TRT` 入库为 `ca_ry_trt`，`TD.TRT` 入库为 `ca_td_trt`。
- 美国 ETF / 股票会转成 `us_` 前缀，例如 `QQQ` 入库为 `us_qqq`，`BRK-B` 入库为 `us_brk_b`。
- 美国指数会转成对应指数名，例如 `NDQ` / Nasdaq Composite 入库为 `nasdaq`。
- Cboe 市场风险指标会转成 `cboe_` 前缀，例如 `^vix` 入库为 `cboe_vix`。
- FRED 美债收益率会转成 `fred_` 前缀，例如 `DGS10` 入库为 `fred_dgs10`；10Y-2Y 利差本地生成为 `fred_t10y2y`。

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
data_fetch/fetch_alpha_vantage_ca.py / data_fetch/fetch_fred_treasury.py
        |
        v
data_manager/data_manager.py
        |------------------------------+
        v
repositories/price_repository.py ---> database/quant.db: price_data
        |
        +--> repositories/update_log_repository.py ---> database/quant.db: data_update_log
        |
        v
analysis/indicators.py
        |------------------------------+
        |                              |
        v                              v
database/quant.db: indicators          database/quant.db: weekly_price_data / weekly_indicators
        |
        +--> analysis/summary.py --group ...
        +--> analysis/short_term_oversold_score.py
        +--> analysis/etf_trend_volatility_score.py
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
| v10 | 新增 `weekly_price_data` 和 `weekly_indicators`，支持由日线派生周线行情和周线技术指标。 |

## 注意事项

- 本项目依赖 `akshare` 的数据接口，数据可用性和字段格式可能随上游接口变化。
- `database/quant.db`、`data/`、`*.csv` 属于本地数据文件，通常不应提交到公开仓库。
- 新建数据库会通过 `database/schema/base.sql` 创建完整表结构；旧数据库会通过 `schema_version` 和 `database/migrations/` 执行版本迁移。
- 后续修改数据库结构时，推荐同时更新 `database/schema/base.sql` 和新增一份 `database/migrations/00N_*.sql`，再递增 `database/db_utils.py` 中的 `CURRENT_SCHEMA_VERSION`。
- 当前 v1 迁移会为旧版 `price_data` 和 `indicators` 补齐 `created_at`、`updated_at` 字段，并记录版本号。
- 第一版迁移机制保持简单，不重建历史表，也不会为已有旧表补复合外键约束。如需完全采用最新约束，建议先备份旧数据库，再重建数据库或后续补充更完整的迁移脚本。
- 周线行情是从本地 `price_data` 派生出来的周级别数据，不额外请求外部周线接口；Cboe VIX / VXN / VVIX / SKEW 和 FRED 美债收益率这类市场指标只计算 MA20 / MA60，跳过 KDJ、CCI、布林带等价格交易指标。
- `asset_info` 暂时由 `database/init_asset_info.py` 手工维护，不从 `akshare` 自动同步。
- `financial_indicators.announce_date` 目前保留为空字段；新浪三大报表的公告日保存在 `financial_statement_items.announce_date`。做严格历史回测时，应按公告日判断当时哪些财报已经可见，避免未来函数。
- 财务数据不保存日频估值表；`buffett_metrics` 中涉及市值的字段只作为报告期层面的衍生结果保存。

## 免责声明

本仓库仅用于个人量化研究、编程练习和策略验证。所有输出、指标、评分和回测结果都不代表未来收益，也不构成任何投资建议。
