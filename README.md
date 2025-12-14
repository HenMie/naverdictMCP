# Naver Dictionary MCP Server

一个基于 FastMCP 2.0 的 Streamable HTTP MCP 服务器,用于查询 Naver 辞典(韩中、韩英)。

[![Docker Hub](https://img.shields.io/docker/v/chouann/naverdictmcp?label=Docker%20Hub)](https://hub.docker.com/r/chouann/naverdictmcp)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## ✨ 功能特性

- 🔍 **多语言辞典**: 韩中/韩英辞典查询，返回释义、发音、例句
- ⚡ **高性能**: 异步架构 + 连接池 + 智能缓存（TTL + LRU）
- 📦 **批量查询**: 支持一次查询多个单词，并发处理
- 🚦 **限流保护**: 令牌桶算法，全局共享上游限流（默认 60 请求/分钟）
- 🛡️ **健壮性**: 输入验证 + 分类错误处理 + 自动重试
- 🐳 **Docker 就绪**: 多架构镜像（amd64/arm64），~110MB
- ✅ **高质量**: 90% 测试覆盖率 + MyPy 严格类型检查

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 拉取并运行最新镜像
docker pull chouann/naverdictmcp:latest
docker run -d -p 8000:8000 --name naverdictmcp chouann/naverdictmcp:latest

# 或使用 Docker Compose
docker-compose up -d
```

### 本地开发

```bash
# 克隆并安装
git clone <repository-url>
cd naverdictMCP
uv sync

# 启动服务器
python src/server.py
```

服务器将在 `http://localhost:8000` 启动。

## 📖 使用示例

### 单词查询

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
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

### 批量查询

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "batch_search_words",
      "arguments": {
        "words": ["안녕하세요", "감사합니다", "학교"],
        "dict_type": "ko-zh"
      }
    }
  }'
```

## ⚙️ 配置

### 环境变量

创建 `.env` 文件自定义配置（开发模式自动加载，生产环境建议通过容器环境变量注入）：

```env
# 服务器配置
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
LOG_LEVEL=INFO

# 性能配置
HTTP_TIMEOUT=30.0
REQUESTS_PER_MINUTE=60
CACHE_TTL=3600
CACHE_MAX_SIZE=1000
```

<details>
<summary>查看完整配置选项</summary>

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `APP_ENV` | 运行模式：development/testing/production | `development` |
| `SERVER_HOST` | 服务器监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 服务器端口 | `8000` |
| `HTTP_TIMEOUT` | HTTP 请求超时时间(秒) | `30.0` |
| `LOG_LEVEL` | 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL） | `INFO` |
| `REQUESTS_PER_MINUTE` | 上游请求限流（每分钟，全局共享） | `60` |
| `CACHE_TTL` | 缓存 TTL（秒） | `3600` |
| `CACHE_NEGATIVE_TTL` | 负缓存 TTL（秒） | `60` |
| `CACHE_MAX_SIZE` | 缓存最大条目数 | `1000` |
| `UPSTREAM_RETRY_MAX_ATTEMPTS` | 上游重试最大次数 | `3` |
| `BATCH_CONCURRENCY` | 批量查询并发上限 | `5` |

</details>

## 🐳 Docker 部署

### 方式一：Docker Hub 镜像（推荐）

```bash
# 拉取最新版本
docker pull chouann/naverdictmcp:latest
docker run -d -p 8000:8000 --name naverdictmcp chouann/naverdictmcp:latest

# 或使用指定版本（生产环境推荐）
docker pull chouann/naverdictmcp:v1.0.0
docker run -d -p 8000:8000 --name naverdictmcp chouann/naverdictmcp:v1.0.0
```

**镜像仓库：** [Docker Hub - chouann/naverdictmcp](https://hub.docker.com/r/chouann/naverdictmcp)

### 方式二：Docker Compose

```bash
# 启动服务
docker-compose up -d

# 更新镜像并重启
docker-compose pull && docker-compose up -d

# 停止服务
docker-compose down
```

创建 `.env` 文件自定义配置：

```env
SERVER_PORT=8000
LOG_LEVEL=INFO
HTTP_TIMEOUT=30.0
REQUESTS_PER_MINUTE=60
```

### 方式三：本地构建

```bash
# 构建并运行
docker build -t naver-dict-mcp .
docker run -d -p 8000:8000 --name naver-dict-mcp naver-dict-mcp:latest

# 或使用 Makefile
make docker-build
make docker-run
```

## 🔧 API 参考

### search_word

查询单个单词。

**参数:**

- `word` (string, 必需): 要查询的单词或短语（最长 100 字符）
- `dict_type` (string, 可选): 辞典类型 `"ko-zh"`（默认）或 `"ko-en"`

**返回:** JSON 字符串，包含释义、发音、例句等

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

### batch_search_words

批量查询多个单词（最多 10 个）。

**参数:**

- `words` (array[string], 必需): 要查询的单词列表
- `dict_type` (string, 可选): 辞典类型，默认 `"ko-zh"`
- `return_cached_json` (bool, 可选): 是否返回缓存 JSON，默认 `false`

**特性:**

- 并发处理，比顺序查询快 5-10 倍
- 自动去重缓存 miss 的词
- 单个查询失败不影响其他查询

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

## 🛠️ 开发

### 安装开发依赖

```bash
uv sync
pre-commit install
```

### 运行测试

```bash
# 运行所有测试
pytest

# 测试覆盖率
pytest --cov=src --cov-report=html

# 性能测试
pytest tests/test_performance.py -m performance
```

### 代码质量检查

```bash
# 格式化
ruff format src/ tests/

# Lint
ruff check src/ tests/

# 类型检查
mypy src/

# 或使用 Makefile
make format
make lint
make type-check
```

## 🔧 故障排除

### 错误类型

| 错误类型 | 说明 | 常见原因 |
|---------|------|----------|
| `validation` | 输入验证错误 | 空字符串、过长字符串、无效字典类型 |
| `timeout` | 请求超时 | 网络慢、超时设置过短 |
| `upstream_rate_limit` | 上游限流 | 上游返回 429 |
| `rate_limit` | 请求频率限制 | 超过配置的请求上限 |
| `network_error` | 网络连接错误 | 无法连接到 API |
| `parse_error` | 响应解析错误 | API 返回格式变化 |

### 常见问题

<details>
<summary>端口被占用</summary>

修改 `.env` 文件或使用环境变量：

```bash
SERVER_PORT=9000 python src/server.py
```

</details>

<details>
<summary>请求频率限制</summary>

默认限制 60 请求/分钟（全局共享）。调整配置：

```env
REQUESTS_PER_MINUTE=100
```

</details>

<details>
<summary>查看详细日志</summary>

```env
LOG_LEVEL=DEBUG
```

</details>

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

**开发者:** 基于 FastMCP 2.0 构建

**相关链接:**

- [FastMCP 文档](https://github.com/jlowin/fastmcp)
- [Naver 辞典](https://korean.dict.naver.com/)
- [Docker Hub 镜像](https://hub.docker.com/r/chouann/naverdictmcp)
