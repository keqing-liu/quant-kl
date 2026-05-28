# quant-kl

一个简化的私人量化交易研究系统，主要用于下载中国市场 ETF / A 股行情、保存到本地 SQLite 数据库、计算技术指标、生成摘要、绘图，并验证简单的股债轮动策略。

> 本项目用于个人学习和研究，不构成任何投资建议。

## 功能概览

- 使用 `akshare` 下载 ETF 和 A 股历史行情
- 使用 SQLite (`database/quant.db`) 本地存储行情、技术指标、资产信息和数据更新日志
- 支持按 `config/watchlist.py` 批量更新关注标的
- 通过 `database/schema.sql` 统一初始化数据库表结构
- 记录每次行情更新结果，方便追踪成功、失败、空数据和无新增数据等状态
- 提供简单数据质量检查，覆盖重复交易日、OHLC 异常、缺失价格和成交量等问题
- 计算均线、收益率、波动率、布林带、成交量均线、KDJ、CCI 等指标
- 输出最近交易日技术指标摘要和简单打分结果
- 绘制 K 线图、均线、布林带、KDJ、CCI 等图表
- 回测沪深 300 ETF 与债券 ETF 的简单动态轮动策略

## 项目结构

```text
quant-kl/
├── main.py
├── README.md
├── .gitignore
├── analysis/
│   ├── __init__.py
│   ├── indicators.py
│   ├── summary.py
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
│   ├── fetch_stock.py
│   └── update_market_data.py
├── data_manager/
│   ├── __init__.py
│   └── data_manager.py
├── database/
│   ├── __pycache__/
│   ├── schema.sql
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
| `main.py` | 项目主入口。初始化数据库，读取 watchlist，更新 ETF / 股票行情，计算技术指标，并输出摘要。 |
| `README.md` | 项目说明文档。 |
| `.gitignore` | Git 忽略规则，忽略缓存、虚拟环境、本地数据、数据库和日志文件。 |

### `config/`

| 文件 | 用途 |
| --- | --- |
| `watchlist.py` | 维护关注标的列表。`WATCHLIST["ETF"]` 保存 ETF 代码，`WATCHLIST["STOCK"]` 保存股票代码。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `data_fetch/`

| 文件 | 用途 |
| --- | --- |
| `fetch_etf.py` | 使用 `akshare.fund_etf_hist_sina` 下载单只 ETF 历史行情。 |
| `fetch_stock.py` | 使用 `akshare.stock_zh_a_daily` 下载单只 A 股前复权日线行情。 |
| `update_market_data.py` | 批量下载 watchlist 中的 ETF / 股票数据的脚本。当前主流程已由 `main.py` + `DataManager` 接管。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `data_manager/`

| 文件 | 用途 |
| --- | --- |
| `data_manager.py` | 数据管理层。负责调用下载函数、判断数据库中最新日期、过滤增量数据，写入 `price_data` 表，并记录 `data_update_log`。 |
| `__init__.py` | 将目录标记为 Python 包。 |

### `database/`

| 文件 | 用途 |
| --- | --- |
| `schema.sql` | SQLite 建表脚本。统一定义 `price_data`、`indicators`、`asset_info`、`data_update_log` 等表。 |
| `db_utils.py` | SQLite 工具函数。包含数据库连接、执行 `schema.sql` 初始化、查询单个标的最新行情日期、写入更新日志等功能。 |
| `init_asset_info.py` | 初始化或刷新 `asset_info` 表中的资产基础信息。 |
| `data_quality_check.py` | 运行简单数据质量检查，包括重复日期、OHLC 价格逻辑、缺失价格和成交量检查。 |
| `quant.db` | 本地 SQLite 数据库文件，保存行情和指标数据。通常属于本地运行产物，不建议提交到公开仓库。 |

当前数据库主要包含：

| 表名 | 内容 |
| --- | --- |
| `price_data` | 原始行情数据：`symbol`、`date`、`open`、`high`、`low`、`close`、`volume`。 |
| `indicators` | 技术指标数据：均线、收益率、波动率、布林带、成交量均线、KDJ、CCI 等。 |
| `asset_info` | 资产基础信息：名称、资产类型、资产类别、市场、数据源、基准和备注等。 |
| `data_update_log` | 数据更新日志：每次更新的起止日期、下载行数、实际插入行数、状态和错误信息等。 |

### `analysis/`

| 文件 | 用途 |
| --- | --- |
| `indicators.py` | 从 `price_data` 读取行情，计算技术指标，并写入 `indicators` 表。 |
| `summary.py` | 读取最近 5 个交易日的价格和指标，输出终端摘要表。 |
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
pip install akshare pandas numpy matplotlib mplfinance
```

## 快速开始

运行主流程：

```bash
python main.py
```

该命令会执行：

1. 初始化 SQLite 数据库
2. 读取 `config/watchlist.py`
3. 更新 ETF 和股票行情到 `price_data`
4. 将每个标的的更新结果写入 `data_update_log`
5. 计算技术指标并写入 `indicators`
6. 输出最近 5 个交易日的指标摘要

## 常用命令

初始化或刷新资产基础信息：

```bash
python -m database.init_asset_info
```

运行数据质量检查：

```bash
python -m database.data_quality_check
```

计算或刷新技术指标：

```bash
python -m analysis.indicators
```

输出最近 5 个交易日摘要：

```bash
python -m analysis.summary
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
}
```

添加或删除标的后，重新运行 `python main.py` 即可按新列表更新数据。

## 数据流

```text
database/schema.sql
        |
        v
database/quant.db: price_data / indicators / asset_info / data_update_log

config/watchlist.py
        |
        v
data_fetch/fetch_etf.py / data_fetch/fetch_stock.py
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
        +--> analysis/summary.py
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

## 注意事项

- 本项目依赖 `akshare` 的数据接口，数据可用性和字段格式可能随上游接口变化。
- `database/quant.db`、`data/`、`*.csv` 属于本地数据文件，通常不应提交到公开仓库。
- 新建数据库会通过 `database/schema.sql` 创建完整表结构；`initialize_database()` 使用 `CREATE TABLE IF NOT EXISTS`，不会自动迁移已经存在的旧表。
- 如果本地已有旧版 `database/quant.db`，它不会自动补齐新 schema 中的 `created_at`、`updated_at` 或外键约束。如需完全采用新结构，建议先备份旧数据库，再重建数据库或后续补充迁移脚本。
- `asset_info` 暂时由 `database/init_asset_info.py` 手工维护，不从 `akshare` 自动同步。
- `data_fetch/update_market_data.py` 中导入的函数名与当前 `fetch_etf.py` / `fetch_stock.py` 中的 `download_*` 函数名不完全一致，推荐优先使用 `python main.py` 作为主入口。

## 免责声明

本仓库仅用于个人量化研究、编程练习和策略验证。所有输出、指标、评分和回测结果都不代表未来收益，也不构成任何投资建议。
