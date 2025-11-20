# Naver Dictionary MCP Server

一个基于 FastMCP 2.0 的 Streamable HTTP MCP 服务器,用于查询 Naver 辞典(韩中、韩英)。

## 📋 目录

- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [安装](#安装)
- [配置](#配置)
- [使用示例](#使用示例)
- [开发](#开发)
- [API 参考](#api-参考)
- [故障排除](#故障排除)
- [许可证](#许可证)

## ✨ 功能特性

- 🔍 **多语言辞典支持**: 韩中辞典和韩英辞典查询
- 🌐 **Streamable HTTP 模式**: 基于 FastMCP 2.0 的现代 HTTP 传输
- ⚡ **异步架构**: 使用 httpx 异步 HTTP 客户端,性能优异
- 📝 **丰富的查询结果**: 返回单词释义、发音、例句等详细信息
- 🔧 **灵活配置**: 支持环境变量配置端口、超时等参数
- ✅ **完整测试**: 使用 pytest 编写的全面单元测试

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

# 运行容器
docker run -d -p 8000:8000 --name naver-dict-mcp naver-dict-mcp
```

## ⚙️ 配置

### 环境变量

创建 `.env` 文件来自定义配置(可选):

```bash
# 复制示例配置文件
cp .env.example .env
```

支持的配置项:

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `SERVER_HOST` | 服务器监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 服务器端口 | `8000` |
| `HTTP_TIMEOUT` | HTTP 请求超时时间(秒) | `30.0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `NAVER_BASE_URL` | Naver API 基础 URL | `https://korean.dict.naver.com/api3` |

### 配置示例

**.env 文件示例:**

```env
SERVER_HOST=127.0.0.1
SERVER_PORT=9000
HTTP_TIMEOUT=60.0
LOG_LEVEL=DEBUG
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
result = asyncio.run(search_korean_word("안녕하세요"))
print(result)
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

## 🛠️ 开发

### 运行测试

项目包含两类测试:

#### 单元测试

使用 pytest 运行单元测试:

```bash
# 安装 pytest (如果尚未安装)
pip install pytest pytest-asyncio

# 运行所有单元测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_parser.py -v

# 运行特定测试类
pytest tests/test_parser.py::TestParseSearchResults -v
```

#### 集成测试

集成测试需要 MCP 服务器运行在 `http://127.0.0.1:8000`。

**方式 1: 使用 pytest**

```bash
# 1. 启动服务器
python src/server.py

# 2. 在另一个终端运行集成测试
pytest tests/test_integration.py -v
```

**方式 2: 独立运行**

```bash
# 1. 启动服务器
python src/server.py

# 2. 在另一个终端运行集成测试
python tests/test_integration.py
```

独立运行模式会显示详细的测试过程和结果摘要。

### 测试覆盖率

```bash
# 生成覆盖率报告
pytest --cov=src --cov-report=html --cov-report=term

# 查看 HTML 报告
# 打开 htmlcov/index.html
```

当前测试覆盖率目标: **≥ 80%**

### 代码结构

```
naverdictMCP/
├── src/
│   ├── __init__.py
│   ├── server.py      # MCP 服务器主入口
│   ├── client.py      # HTTP 客户端
│   ├── parser.py      # JSON 响应解析器
│   └── config.py      # 配置管理
├── tests/
│   ├── __init__.py
│   ├── conftest.py    # pytest 配置和 fixtures
│   ├── test_server.py # 服务器单元测试
│   ├── test_client.py # 客户端单元测试
│   ├── test_parser.py # 解析器单元测试
│   ├── test_config.py # 配置单元测试
│   └── test_integration.py  # HTTP 集成测试
├── pyproject.toml     # 项目配置和依赖
├── pytest.ini         # pytest 配置
├── .env.example       # 环境变量示例
└── README.md
```

### 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

**代码规范:**

- 遵循 PEP 8 代码风格
- 为新功能添加单元测试
- 保持测试覆盖率 ≥ 80%
- 更新相关文档

## 📚 API 参考

### search_word

查询 Naver 辞典中的单词。

**参数:**

- `word` (string, 必需): 要查询的单词或短语
- `dict_type` (string, 可选): 辞典类型
  - `"ko-zh"`: 韩中辞典 (默认)
  - `"ko-en"`: 韩英辞典

**返回:**

格式化的字符串,包含:
- 单词/短语
- 发音(如果有)
- 释义列表
- 例句(最多 3 个)

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

## 🔧 故障排除

### 常见问题

#### 1. 服务器无法启动

**问题:** `Address already in use` 错误

**解决方案:**
- 检查端口 8000 是否被占用
- 在 `.env` 文件中更改 `SERVER_PORT` 为其他端口

```env
SERVER_PORT=9000
```

#### 2. 请求超时

**问题:** HTTP 请求超时

**解决方案:**
- 检查网络连接
- 增加超时时间:

```env
HTTP_TIMEOUT=60.0
```

#### 3. 找不到模块

**问题:** `ModuleNotFoundError: No module named 'src'`

**解决方案:**
- 确保从项目根目录运行服务器
- 或使用绝对导入:

```bash
cd /path/to/naverdictMCP
python src/server.py
```

#### 4. 测试失败

**问题:** 某些测试失败

**解决方案:**
- 确保安装了所有开发依赖:

```bash
uv sync  # 或 pip install -e ".[dev]"
```

- 检查是否有环境变量干扰测试

#### 5. API 返回空结果

**问题:** 查询返回 "未找到相关结果"

**可能原因:**
- 单词拼写错误
- Naver 辞典中确实没有该词条
- API 响应格式变化

**调试方法:**
- 在浏览器中访问 Naver 辞典验证词条是否存在
- 检查日志输出(设置 `LOG_LEVEL=DEBUG`)

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
