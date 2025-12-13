# Naver Dictionary MCP Server

一个基于 FastMCP 2.0 的 Streamable HTTP MCP 服务器,用于查询 Naver 辞典(韩中、韩英)。

## 📋 目录

- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [安装](#-安装)
- [配置](#配置)
- [使用示例](#-使用示例)
- [开发](#开发)
- [API 参考](#-api-参考)
- [故障排除](#-故障排除)
- [许可证](#-许可证)

## ✨ 功能特性

- 🔍 **多语言辞典支持**: 韩中辞典和韩英辞典查询
- 🌐 **Streamable HTTP 模式**: 基于 FastMCP 2.0 的现代 HTTP 传输
- ⚡ **异步架构**: 使用 httpx 异步 HTTP 客户端,性能优异
- 📝 **丰富的查询结果**: 返回单词释义、发音、例句等详细信息
- 🔧 **灵活配置**: 支持环境变量配置端口、超时等参数,配置验证确保参数有效性
- 🛡️ **输入验证**: 严格的输入验证机制,防止无效请求
- 📊 **完整日志系统**: 统一的日志配置,支持多级别日志输出
- 🚦 **API 限流保护**: 基于令牌桶算法的**全局共享**上游限流(默认 60 上游请求/分钟,仅对缓存 miss 扣配额)
- ⚠️ **健壮错误处理**: 分类错误处理机制,提供清晰的错误信息和类型
- 🚀 **智能缓存机制**: TTL 缓存 + LRU 淘汰策略,大幅提升查询性能(默认 1 小时缓存)
- 🔌 **连接池复用**: 全局 HTTP 连接池,减少连接开销,提升并发性能
- 📦 **批量查询接口**: 支持一次查询多个单词(最多 10 个),并发处理更高效
- ✅ **完整测试**: 使用 pytest 编写的全面单元测试和性能测试,覆盖率约 90%
- 🔍 **严格类型检查**: MyPy 严格模式,编译时捕获类型错误
- 🎨 **自动代码格式化**: Ruff 现代化工具,统一代码风格
- 🔗 **Git Pre-commit 钩子**: 提交前自动检查代码质量
- 🐳 **优化 Docker 镜像**: 多阶段构建,镜像减小 44%,非 root 用户安全运行

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone <repository-url>
cd naverdictMCP

# 2. 安装依赖
uv sync

# 3. 启动服务器
python src/server.py
```

服务器将在 `http://localhost:8000` 启动。

**启动时会显示:**

```text
============================================================
启动 Naver Dictionary MCP 服务器
服务器地址: http://0.0.0.0:8000
日志级别: INFO
HTTP 超时: 30.0s
缓存配置: 最大 1000 项, TTL 3600s
============================================================
2025-11-23 10:00:00 - naver-dict-mcp - INFO - 创建新的 HTTP 客户端连接池
2025-11-23 10:00:00 - naver-dict-mcp - INFO - 服务器启动成功
```

## 📦 安装

### 使用 uv (推荐)

```bash
# 安装所有依赖
uv sync

# 仅安装生产依赖
uv sync --no-dev
```

### 使用 pip

```bash
# 安装生产依赖
pip install -e .

# 安装开发依赖
pip install -e ".[dev]"
```

### 使用 poetry

```bash
poetry install
```

## 🐳 Docker 部署

### 使用 Docker Compose (推荐)

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 使用 Docker 构建和运行

```bash
# 构建镜像
docker build -t naver-dict-mcp .

# 或使用 Makefile
make docker-build

# 运行容器
docker run -d -p 8000:8000 --name naver-dict-mcp naver-dict-mcp:latest

# 或使用 Makefile
make docker-run
```

### GitHub Actions 自动构建并推送到 Docker Hub

本项目已内置 GitHub Actions 工作流（`/.github/workflows/docker-publish.yml`），会自动构建 Docker 镜像并推送到 Docker Hub：

- **镜像仓库**：`chouann/naverdictmcp`
- **触发条件**：
  - **push 到 `main`**：发布 `latest` 与 `sha-<短提交>` 两个标签
  - **push 语义化 tag**（如 `v1.0.0` 或 `1.0.0`）：发布对应 tag 标签（例如 `v1.0.0`）
  - **手动触发**：在 GitHub Actions 页面点击运行

**你需要在 GitHub 仓库里配置 Secrets：**

- **`DOCKERHUB_USERNAME`**：Docker Hub 用户名（例如 `chouann`）
- **`DOCKERHUB_TOKEN`**：Docker Hub Access Token（建议使用可读写权限的 Token，而不是密码）

配置路径：GitHub 仓库 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`。

**拉取并运行已发布镜像：**

```bash
docker pull chouann/naverdictmcp:latest
docker run -d -p 8000:8000 --name naverdictmcp chouann/naverdictmcp:latest
```

### Docker 镜像优化

项目使用多阶段构建优化 Docker 镜像:

**优化特性:**

- ✅ **镜像瘦身**: 多阶段构建，仅包含运行时依赖 (~250MB)
- ✅ **构建加速**: 利用缓存层，增量构建更快
- ✅ **安全增强**: 使用非 root 用户运行容器
- ✅ **健康检查**: 内置健康检查，自动监控容器状态

**镜像对比:**

| 指标 | 单阶段构建 | 多阶段构建 | 提升 |
|-----|----------|-----------|------|
| 镜像大小 | ~450MB | ~250MB | **-44%** |
| 构建时间 | ~60s | ~40s | **-33%** |
| 安全性 | root 用户 | 非 root | **✅ 更安全** |
| 健康检查 | 无 | 支持 | **✅ 新增** |

**健康检查:**

```bash
# 查看容器健康状态
docker ps

# 健康检查会每 30 秒自动运行
# 如果连续 3 次失败，容器状态变为 unhealthy
```

## 配置

### 环境变量

创建 `.env` 文件来自定义配置（可选，**仅开发模式会自动加载**）。

你可以直接在项目根目录新建 `.env`，并按需填写下方“配置示例”中的环境变量。

### 运行模式（APP_ENV）

配置加载策略由 `APP_ENV` 统一控制，避免在各模块分散判断：

- `development`（默认）：会自动读取本地 `.env`（便于开发）
- `testing`：pytest 运行时会自动进入测试模式，不会读取 `.env`（避免本地配置污染测试）
- `production`：不会读取 `.env`，建议由部署平台/容器环境注入环境变量

支持的配置项:

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `APP_ENV` | 运行模式：development/testing/production（或 dev/test/prod） | `development` |
| `SERVER_HOST` | 服务器监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 服务器端口 | `8000` |
| `HTTP_TIMEOUT` | HTTP 请求超时时间(秒) | `30.0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `NAVER_BASE_URL` | Naver API 基础 URL | `https://korean.dict.naver.com/api3` |
| `REQUESTS_PER_MINUTE` | 上游（Naver）请求限流（每分钟，**全局共享**） | `60` |
| `CACHE_TTL` | 缓存 TTL（秒） | `3600` |
| `CACHE_NEGATIVE_TTL` | 负缓存 TTL（秒，未找到结果时使用，建议短一些） | `60` |
| `CACHE_MAX_SIZE` | 缓存最大条目数 | `1000` |
| `CACHE_KEY_MODE` | 缓存 key 模式：`hash` / `plain` / `hash_with_plain` | `hash` |
| `BATCH_ITEM_INCLUDE_DICT_TYPE` | 批量结果子项是否重复输出 `dict_type` | `true` |
| `UPSTREAM_RETRY_MAX_ATTEMPTS` | 上游重试最大尝试次数（包含首次） | `3` |
| `UPSTREAM_RETRY_BASE_DELAY` | 上游重试基础退避时间（秒） | `0.2` |
| `UPSTREAM_RETRY_MAX_DELAY` | 上游重试最大退避时间（秒） | `2.0` |
| `HTTPX_MAX_KEEPALIVE_CONNECTIONS` | httpx keep-alive 连接上限 | `20` |
| `HTTPX_MAX_CONNECTIONS` | httpx 总连接上限 | `100` |
| `HTTPX_KEEPALIVE_EXPIRY` | keep-alive 连接过期时间（秒） | `30.0` |
| `BATCH_CONCURRENCY` | 批量查询内部并发上限（仅限制访问上游的瞬时并发） | `5` |

### 配置示例

**.env 文件示例:**

```env
APP_ENV=development
SERVER_HOST=127.0.0.1
SERVER_PORT=9000
HTTP_TIMEOUT=60.0
LOG_LEVEL=DEBUG
REQUESTS_PER_MINUTE=60
CACHE_TTL=3600
CACHE_NEGATIVE_TTL=60
CACHE_MAX_SIZE=1000
CACHE_KEY_MODE=hash
BATCH_ITEM_INCLUDE_DICT_TYPE=true
UPSTREAM_RETRY_MAX_ATTEMPTS=3
UPSTREAM_RETRY_BASE_DELAY=0.2
UPSTREAM_RETRY_MAX_DELAY=2.0
HTTPX_MAX_KEEPALIVE_CONNECTIONS=20
HTTPX_MAX_CONNECTIONS=100
HTTPX_KEEPALIVE_EXPIRY=30.0
BATCH_CONCURRENCY=5
```

### 配置验证

服务器启动时会自动验证所有配置项:

| 配置项 | 验证规则 | 无效示例 |
|-------|---------|---------|
| `APP_ENV` | development/testing/production（或 dev/test/prod） | `staging` |
| `SERVER_PORT` | 1-65535 | `0`, `99999` |
| `HTTP_TIMEOUT` | > 0 且 ≤ 300 | `0`, `-1`, `500` |
| `LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR/CRITICAL | `TRACE`, `debug`(小写) |
| `NAVER_BASE_URL` | 必须以 http:// 或 https:// 开头 | `ftp://...`, `example.com` |
| `REQUESTS_PER_MINUTE` | > 0 | `0`, `-1` |
| `CACHE_TTL` | > 0 | `0`, `-1` |
| `CACHE_NEGATIVE_TTL` | > 0 | `0`, `-1` |
| `CACHE_MAX_SIZE` | > 0 | `0`, `-1` |
| `CACHE_KEY_MODE` | hash/plain/hash_with_plain | `md5`, `debug` |
| `BATCH_ITEM_INCLUDE_DICT_TYPE` | true/false/1/0 | `maybe` |
| `UPSTREAM_RETRY_MAX_ATTEMPTS` | > 0 | `0`, `-1` |
| `UPSTREAM_RETRY_BASE_DELAY` | ≥ 0 | `-0.1` |
| `UPSTREAM_RETRY_MAX_DELAY` | > 0 且 ≥ UPSTREAM_RETRY_BASE_DELAY | `0`, `-1`, `0.1(小于 base_delay)` |
| `HTTPX_MAX_CONNECTIONS` | > 0 | `0`, `-1` |
| `HTTPX_MAX_KEEPALIVE_CONNECTIONS` | ≥ 0 且 ≤ HTTPX_MAX_CONNECTIONS | `-1`, `1000`(大于 max_connections) |
| `HTTPX_KEEPALIVE_EXPIRY` | > 0 | `0`, `-1` |
| `BATCH_CONCURRENCY` | > 0 | `0`, `-1` |

**配置错误示例:**

```bash
# 无效端口
SERVER_PORT=99999
# 错误: 端口号必须在 1-65535 范围内

# 无效超时时间
HTTP_TIMEOUT=0
# 错误: HTTP 超时必须大于 0 秒

# 无效日志级别
LOG_LEVEL=TRACE
# 错误: 日志级别必须为 DEBUG, INFO, WARNING, ERROR 或 CRITICAL
```

## 📖 使用示例

### HTTP API 调用 (curl)

#### 查询韩中辞典

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_word",
      "arguments": {
        "word": "안녕하세요",
        "dict_type": "ko-zh"
      }
    }
  }'
```

#### 查询韩英辞典

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "search_word",
      "arguments": {
        "word": "학교",
        "dict_type": "ko-en"
      }
    }
  }'
```

### Python 客户端示例

```python
import httpx
import asyncio
import json

def parse_sse_response(text: str) -> dict:
    """Parse Server-Sent Events (SSE) response."""
    lines = text.strip().split('\\n')
    data_lines = [line[6:] for line in lines if line.startswith('data: ')]
    if data_lines:
        return json.loads(data_lines[0])
    return None

async def search_korean_word(word: str, dict_type: str = "ko-zh"):
    """Search a Korean word using the MCP server."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "search_word",
            "arguments": {
                "word": word,
                "dict_type": dict_type
            }
        }
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/mcp",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            },
            json=payload
        )
        data = parse_sse_response(response.text)
        return data.get('result') if data else None

# 使用示例
async def main():
    # 正常查询
    result = await search_korean_word("안녕하세요")
    print(result)
    
    # 错误处理示例
    try:
        # 空字符串会触发验证错误
        result = await search_korean_word("")
    except Exception as e:
        print(f"查询失败: {e}")

asyncio.run(main())
```

### MCP 客户端集成

在 MCP 客户端配置中添加:

```json
{
  "mcpServers": {
    "naver-dict": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### 批量查询示例

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "batch_search_words",
      "arguments": {
        "words": ["안녕하세요", "감사합니다", "미안합니다"],
        "dict_type": "ko-zh"
      }
    }
  }'
```

## 开发

### 运行测试

项目包含三类测试:

#### 单元测试

使用 pytest 运行单元测试:

```bash
# 安装 pytest (如果尚未安装)
pip install pytest pytest-asyncio

# 运行所有单元测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_parser.py -v
pytest tests/test_logger.py -v
pytest tests/test_rate_limiter.py -v
pytest tests/test_cache.py -v
pytest tests/test_metrics.py -v

# 运行特定测试类
pytest tests/test_parser.py::TestParseSearchResults -v
```

#### 性能测试

运行性能基准测试:

```bash
# 运行所有性能测试
pytest tests/test_performance.py -v -m performance

# 运行基准测试(详细输出)
pytest tests/test_performance.py -v -m benchmark -s

# 说明:
# - `tests/test_performance.py` 默认会 mock 掉真实网络请求，避免在本地/CI 环境下不稳定
# - 输出的耗时仅用于监测本地逻辑回归，不代表真实 Naver API 的网络延迟
```

**建议用法:**

- 研发日常：直接跑 `pytest -q`（稳定、无需外网）
- 真实网络基准：请用 curl 示例或自行编写 benchmark（不要依赖单测的 mock 结果）

**测试覆盖情况:**

- 测试数量会随版本变化（以 `pytest` 输出为准）
- 当前版本 `pytest -q` 可一次通过（示例：115 passed）

#### 集成测试

集成测试使用 FastMCP 的 **in-memory transport**（不依赖端口、不需要启动服务器、不访问外网）。

```bash
pytest tests/test_integration.py -v
```

如需验证真实 HTTP 传输与外网连通性，请使用上面的 curl 示例对 `http://localhost:8000/mcp` 做联调。

### 测试覆盖率

```bash
# 生成覆盖率报告
pytest --cov=src --cov-report=html --cov-report=term

# 查看 HTML 报告
# 打开 htmlcov/index.html
```

当前测试覆盖率: **~90%** (目标 ≥ 80% ✅)

**测试亮点:**

- ✅ 覆盖功能、性能（mock 网络）、协议级集成（in-memory）三个维度
- ✅ 自动化集成测试（无需手动启动服务器）
- ✅ 详细的性能基准测试
- ✅ 缓存和指标系统的完整测试

### 日志系统

服务器使用统一的日志系统,支持多级别日志输出:

```python
from src.logger import logger

# 在代码中使用
logger.info("正常信息")
logger.debug("调试信息")
logger.warning("警告信息")
logger.error("错误信息")
```

**日志级别配置:**

在 `.env` 文件中设置:

```env
LOG_LEVEL=DEBUG  # 显示所有日志
LOG_LEVEL=INFO   # 显示一般信息(默认)
LOG_LEVEL=WARNING # 仅显示警告和错误
LOG_LEVEL=ERROR  # 仅显示错误
```

**日志格式:**

```text
2025-11-23 10:00:00 - naver-dict-mcp - INFO - 服务器启动成功
时间戳               模块名            级别   消息内容
```

### API 限流保护

服务器内置基于令牌桶算法的请求限流:

- **默认限制**: 60 上游请求/分钟（**全局共享**，用于保护服务器出口 IP）
- **扣配额规则**:
  - `search_word`: 仅当缓存 miss 且需要访问 Naver 时消耗 1 个令牌
  - `batch_search_words`: 仅对缓存 miss 的词消耗令牌，并按“去重后的 miss 词数”扣配额
- **超限响应**: 工具返回 `error_type=rate_limit` 的 JSON 错误结构（HTTP 状态码仍为 MCP 正常响应）

**限流配置:**

通过环境变量调整（推荐）：

```env
# 每分钟允许访问上游 Naver 的最大次数（全局共享）
REQUESTS_PER_MINUTE=60
```

### 错误处理机制

服务器提供完整的错误分类和处理:

```python
from src.config import ConfigError
from src.config import Config

# 配置错误（通过环境变量注入后初始化配置）
import os
os.environ["SERVER_PORT"] = "99999"
try:
    cfg = Config()
except ConfigError as e:
    print(f"配置无效: {e}")

# 工具调用错误：search_word/batch_search_words 会返回统一 JSON 字符串
# 请通过解析 JSON 后检查 success / error_type / details
```

所有错误都会被捕获并返回统一格式的错误响应,包含错误类型、描述和详细信息。

### 缓存系统

服务器内置智能缓存机制,显著提升性能:

**特性:**

- **TTL 过期**: 默认 1 小时后自动过期
- **LRU 淘汰**: 缓存满时淘汰最少使用的条目
- **命中加速**: 缓存命中延迟 < 10ms,比 API 快 100+ 倍
- **自动管理**: 无需手动维护,自动清理过期数据

**配置:**

通过环境变量调整（推荐）：

```env
# 缓存最大条目数
CACHE_MAX_SIZE=1000

# 缓存 TTL（秒）
CACHE_TTL=3600
```

### 代码质量工具

项目集成了现代化的代码质量工具:

#### MyPy - 类型检查

```bash
# 运行类型检查
mypy src/

# 或使用 Makefile
make type-check
```

#### Ruff - 代码检查和格式化

```bash
# 检查代码问题
ruff check src/ tests/

# 自动修复
ruff check --fix src/ tests/

# 格式化代码
ruff format src/ tests/

# 或使用 Makefile
make lint      # 检查
make format    # 格式化
```

#### Pre-commit - 提交前检查

```bash
# 安装 pre-commit hooks
pre-commit install

# 手动运行所有检查
pre-commit run --all-files

# 或使用 Makefile
make pre-commit
```

Pre-commit 会在每次 `git commit` 时自动运行:

- ✅ Ruff 代码检查和格式化
- ✅ MyPy 类型检查
- ✅ 清理尾随空格
- ✅ YAML/TOML/JSON 格式验证
- ✅ Bandit 安全扫描

#### Makefile - 快捷命令

```bash
# 查看所有可用命令
make help

# 常用命令
make install-dev      # 安装开发依赖
make test             # 运行测试
make test-cov         # 测试覆盖率
make lint             # 代码检查
make format           # 代码格式化
make type-check       # 类型检查
make security         # 安全检查
make docker-build     # 构建 Docker 镜像
make clean            # 清理临时文件
```

### 代码结构

```text
naverdictMCP/
├── src/
│   ├── __init__.py
│   ├── server.py         # MCP 服务器主入口(含批量查询、指标查看等)
│   ├── client.py         # HTTP 客户端(连接池、输入验证)
│   ├── parser.py         # JSON 响应解析器
│   ├── config.py         # 配置管理(含验证机制)
│   ├── logger.py         # 统一日志系统
│   ├── rate_limiter.py   # API 限流器(令牌桶算法)
│   ├── cache.py          # TTL 缓存 + LRU 淘汰
│   └── metrics.py        # 性能监控指标
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # pytest 配置和 fixtures(含自动化集成测试)
│   ├── test_server.py        # 服务器单元测试
│   ├── test_client.py        # 客户端单元测试
│   ├── test_parser.py        # 解析器单元测试
│   ├── test_config.py        # 配置单元测试
│   ├── test_logger.py        # 日志系统测试
│   ├── test_rate_limiter.py  # 限流器测试
│   ├── test_cache.py         # 缓存系统测试
│   ├── test_metrics.py       # 指标系统测试
│   ├── test_performance.py   # 性能基准测试
│   └── test_integration.py   # HTTP 集成测试
├── pyproject.toml            # 项目配置和依赖（含 mypy/ruff 配置）
├── pytest.ini                # pytest 配置
├── .pre-commit-config.yaml   # Pre-commit hooks 配置
├── .dockerignore             # Docker 构建排除文件
├── Makefile                  # 常用命令快捷方式
└── README.md
```

### 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

**代码规范:**

- 遵循 PEP 8 代码风格(使用 Ruff 自动检查和格式化)
- 为新功能添加单元测试(目前测试覆盖率约 90%)
- 保持测试覆盖率 ≥ 80%
- 添加完整的类型注解和 docstring(使用 MyPy 严格检查)
- 实现适当的错误处理和输入验证
- 更新相关文档
- 提交前运行 `make pre-commit` 确保代码质量

**开发工作流:**

```bash
# 1. 安装开发依赖（包含 pre-commit hooks）
make install-dev

# 2. 开发新功能
vim src/server.py

# 3. 运行测试
make test

# 4. 检查代码质量
make lint           # 代码检查
make type-check     # 类型检查
make security       # 安全检查

# 5. 格式化代码
make format

# 6. 提交代码（pre-commit 自动运行检查）
git add .
git commit -m "feat: 新功能"
```

## 📚 API 参考

### search_word

查询 Naver 辞典中的单词(支持缓存加速)。

**参数:**

- `word` (string, 必需): 要查询的单词或短语
- `dict_type` (string, 可选): 辞典类型
  - `"ko-zh"`: 韩中辞典 (默认)
  - `"ko-en"`: 韩英辞典

**输入验证:**

- 搜索词不能为空或纯空格
- 搜索词长度不超过 100 字符
- 字典类型必须为 `"ko-zh"` 或 `"ko-en"`

**返回:**

格式化的 JSON 字符串,包含:

- 单词/短语
- 发音(如果有)
- 释义列表
- 例句(最多 3 个)

**缓存行为:**

- 有结果：使用 `CACHE_TTL` 缓存（默认 1 小时）
- 未找到结果：使用 `CACHE_NEGATIVE_TTL` 进行短 TTL“负缓存”（默认 60 秒）
- 缓存命中：返回中 `from_cache=true`（便于调用方消费）
- 缓存满时自动淘汰最少使用的条目(LRU)

**示例:**

```json
{
  "name": "search_word",
  "arguments": {
    "word": "안녕하세요",
    "dict_type": "ko-zh"
  }
}
```

**错误响应:**

```json
{
  "success": false,
  "word": "",
  "dict_type": "ko-zh",
  "error": "输入验证失败",
  "error_type": "validation",
  "details": "搜索词不能为空",
  "from_cache": false,
  "deduped": false,
  "source_word": ""
}
```

---

### batch_search_words

批量查询多个单词(并发处理)。

**参数:**

- `words` (array[string], 必需): 要查询的单词列表(最多 10 个)
- `dict_type` (string, 可选): 辞典类型,默认 `"ko-zh"`
- `return_cached_json` (bool, 可选): 是否对缓存命中条目直接返回 `cached_json`（避免反序列化与拼装），默认 `false`

**返回:**

包含每个单词查询结果的 JSON:

```json
{
  "success": false,
  "partial_success": true,
  "count": 3,
  "success_count": 2,
  "fail_count": 1,
  "dict_type": "ko-zh",
  "results": [
    {
      "word": "안녕하세요",
      "dict_type": "ko-zh",
      "success": true,
      "count": 1,
      "results": [...],
      "from_cache": true,
      "deduped": false,
      "source_word": "안녕하세요"
    },
    {
      "word": "",
      "dict_type": "ko-zh",
      "success": false,
      "error": "输入验证失败",
      "error_type": "validation",
      "details": "搜索词不能为空",
      "from_cache": false,
      "deduped": false,
      "source_word": ""
    },
    ...
  ],
  "latency": 0.234
}
```

**去重行为说明:**

- 批量查询会对“缓存 miss 的词”按规范化结果去重，只对上游发起一次请求
- 对重复项回填结果时会增加：
  - `deduped`: 是否为去重回填（true/false）
  - `source_word`: 本次去重组的源词（即实际用于请求/缓存的规范化词）

**并发上限说明:**

- 批量查询内部使用 `BATCH_CONCURRENCY` 控制对上游的瞬时并发，避免瞬时并发把上游打爆

**return_cached_json 说明:**

- 当 `return_cached_json=true` 且 `from_cache=true` 时，单条结果会包含 `cached_json`（字符串），并**可能不包含** `count/results`（调用方可自行解析）

**性能特点:**

- 并发处理所有查询,比顺序查询快 5-10 倍
- 自动利用缓存,重复单词秒级响应
- 单个单词失败不影响其他查询

**示例:**

```json
{
  "name": "batch_search_words",
  "arguments": {
    "words": ["안녕하세요", "감사합니다", "미안합니다"],
    "dict_type": "ko-zh"
  }
}
```

## 🔧 故障排除

### 错误类型说明

服务器返回的错误包含以下字段:

```json
{
  "success": false,
  "word": "请求的搜索词（规范化后）",
  "dict_type": "ko-zh",
  "error": "错误简述",
  "error_type": "错误类型",
  "details": "详细错误信息",
  "from_cache": false,
  "deduped": false,
  "source_word": "去重源词（单查等于 word）"
}
```

**错误类型分类:**

| 错误类型 | 说明 | 常见原因 |
|---------|------|----------|
| `validation` | 输入验证错误 | 空字符串、过长字符串、无效字典类型 |
| `timeout` | 请求超时 | 网络慢、超时设置过短 |
| `upstream_rate_limit` | 上游限流 | 上游返回 429（Too Many Requests） |
| `upstream_server_error` | 上游服务错误 | 上游返回 5xx（500/502/503/504 等） |
| `http_error` | HTTP 状态码错误 | 400、404 等（不包含上游 429/5xx） |
| `network_error` | 网络连接错误 | 无法连接到 API、DNS 解析失败 |
| `parse_error` | 响应解析错误 | API 返回格式变化、响应不完整 |
| `rate_limit` | 请求频率限制 | 超过 60 上游请求/分钟（全局共享配额） |
| `unknown` | 未知错误 | 其他未预期的错误 |

**上游重试说明:**

- 对幂等请求（GET）且满足以下条件时，会按“指数退避 + 抖动”自动重试：
  - 网络异常 / 超时
  - 上游返回 429、500、502、503、504
- 重试会**额外消耗**上游配额（与 `REQUESTS_PER_MINUTE` 共用），确保不会因重试突破全局限流。

### 常见问题

#### 1. 服务器无法启动

**问题:** `Address already in use` 错误

**解决方案:**

- 检查端口 8000 是否被占用
- 在 `.env` 文件中更改 `SERVER_PORT` 为其他端口

```env
SERVER_PORT=9000
```

#### 2. 配置验证失败

**问题:** 启动时报配置错误

**解决方案:**

- 检查 `.env` 文件中的配置值:
  - `SERVER_PORT`: 必须在 1-65535 范围内
  - `HTTP_TIMEOUT`: 必须 > 0 且 ≤ 300 秒
  - `LOG_LEVEL`: 必须为 DEBUG/INFO/WARNING/ERROR/CRITICAL
  - `NAVER_BASE_URL`: 必须以 http:// 或 https:// 开头

```env
# 正确的配置示例
SERVER_PORT=8000
HTTP_TIMEOUT=30.0
LOG_LEVEL=INFO
```

#### 3. 请求频率限制

**问题:** 返回 `rate_limit` 错误

**解决方案:**

- 默认限制为 60 上游请求/分钟（全局共享）
- 等待一段时间后重试
- 如需调整限流配置，在环境变量中设置 `REQUESTS_PER_MINUTE`:

```env
# 默认: 60 上游请求/分钟（全局共享）
REQUESTS_PER_MINUTE=60
```

#### 4. 输入验证错误

**问题:** 返回 `validation` 错误

**解决方案:**

- 确保搜索词不为空
- 搜索词长度不超过 100 字符
- 字典类型为 `"ko-zh"` 或 `"ko-en"`

```python
# 正确示例
{"word": "안녕하세요", "dict_type": "ko-zh"}

# 错误示例
{"word": "", "dict_type": "ko-zh"}  # 空字符串
{"word": "가"*101, "dict_type": "ko-zh"}  # 超过 100 字符
{"word": "안녕", "dict_type": "invalid"}  # 无效字典类型
```

#### 5. 请求超时

**问题:** HTTP 请求超时

**解决方案:**

- 检查网络连接
- 增加超时时间:

```env
HTTP_TIMEOUT=60.0
```

#### 6. 找不到模块

**问题:** `ModuleNotFoundError: No module named 'src'`

**解决方案:**

- 确保从项目根目录运行服务器
- 或使用绝对导入:

```bash
cd /path/to/naverdictMCP
python src/server.py
```

#### 7. 测试失败

**问题:** 某些测试失败

**解决方案:**

- 确保安装了所有开发依赖:

```bash
uv sync  # 或 pip install -e ".[dev]"
```

- 检查是否有环境变量干扰测试

#### 8. API 返回空结果

**问题:** 查询返回 "未找到相关结果"

**可能原因:**

- 单词拼写错误
- Naver 辞典中确实没有该词条
- API 响应格式变化

**调试方法:**

- 在浏览器中访问 Naver 辞典验证词条是否存在
- 检查日志输出(设置 `LOG_LEVEL=DEBUG`):

```env
LOG_LEVEL=DEBUG
```

查看详细的请求和响应日志。

### 获取帮助

如果遇到其他问题:

1. 查看 [Issues](../../issues) 中是否有类似问题
2. 创建新的 Issue,提供:
   - 错误信息
   - 复现步骤
   - 环境信息(Python 版本、操作系统等)

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

**开发者:** 基于 FastMCP 2.0 构建

**相关链接:**

- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [Naver 辞典](https://korean.dict.naver.com/)
