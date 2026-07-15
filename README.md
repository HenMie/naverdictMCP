# Naver Dictionary MCP

部署在 Vercel 上的无状态 Naver 韩中/韩英辞典 MCP 服务。服务只暴露一个
`search_words` 工具，并使用 Bearer Token 保护公网入口。

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FHenMie%2FnaverdictMCP&env=MCP_API_KEY&envDescription=Required%20Bearer%20token%20with%20at%20least%2032%20bytes&project-name=naver-dictionary-mcp&repository-name=naver-dictionary-mcp)

## 一键部署

1. 点击上方 **Deploy with Vercel**。
2. 在 Vercel 页面填写 `MCP_API_KEY`。可使用 `openssl rand -hex 32` 生成。
3. 部署完成后，MCP 地址为 `https://<你的域名>/mcp`。

部署不需要 Redis、数据库或其他 Marketplace 服务。`GET /health` 可用于健康检查，
该路由不需要认证。

## MCP 客户端配置

支持自定义 HTTP Header 的 MCP 客户端可使用以下配置：

```json
{
  "mcpServers": {
    "naver-dictionary": {
      "url": "https://<你的域名>/mcp",
      "headers": {
        "Authorization": "Bearer <你的 MCP_API_KEY>"
      }
    }
  }
}
```

无 Token 或 Token 错误的 `/mcp` 请求统一返回 `401 Unauthorized`。

## 工具接口

### `search_words`

参数：

- `words`：1 至 10 个字符串，每项最长 100 字符。
- `dict_type`：`ko-zh`（默认）或 `ko-en`。

结果为结构化 MCP 内容，并保持原始输入顺序：

```json
{
  "dict_type": "ko-zh",
  "summary": {"total": 2, "succeeded": 1, "failed": 1},
  "items": [
    {
      "index": 0,
      "word": "사랑",
      "success": true,
      "entries": []
    },
    {
      "index": 1,
      "word": "",
      "success": false,
      "error": {
        "code": "validation_error",
        "message": "搜索词不能为空"
      }
    }
  ]
}
```

重复词会在同一次调用中合并为一次上游请求，再按各自输入位置返回。已知的单词级错误
会返回稳定错误码；未预期异常不会被吞掉，会作为工具调用失败并记录完整服务日志。

错误码包括：`validation_error`、`timeout`、`upstream_rate_limit`、
`upstream_server_error`、`upstream_response_error`、`network_error` 和
`invalid_upstream_payload`。

## 本地开发

需要 Python 3.12 和 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync --locked
cp .env.example .env.local
# 编辑 .env.local，填入至少 32 字节的 MCP_API_KEY
make dev
```

`make dev` 在 `http://127.0.0.1:3000` 启动与 Vercel 相同的 `app.py` ASGI 入口。

质量检查：

```bash
make check
```

## 运行约束

- Python 3.12，Vercel Function 区域为首尔 `icn1`。
- 单次函数最大运行 60 秒。
- Naver 请求超时 10 秒，只对网络错误、超时、HTTP 429 和 5xx 重试一次。
- 单次最多 10 个词、最多 5 个上游并发。
- 不提供跨实例缓存或全局请求限流，避免在 Serverless 环境中制造错误语义。

## License

[MIT](LICENSE)
