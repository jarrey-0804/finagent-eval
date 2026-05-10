# MCP Server 配置说明

本目录存放 finagent-eval 项目使用的 MCP (Model Context Protocol) 服务器配置文件。

## 目录结构

```
mcp_servers/
├── sec_edgar/config.json    # SEC EDGAR 美股公开文件数据
├── yahoo_finance/config.json # Yahoo Finance 全球行情数据
├── ashare_data/config.json   # A股市场数据（沪深交易所）
├── fund_data/config.json     # 基金/ETF 数据
├── tushare/config.json       # Tushare 中国A股市场数据（行情、财务、资金流向）
├── calculator/config.json    # 金融计算器（收益率、夏普比率、最大回撤等）
├── web_search/config.json    # 网络搜索（金融新闻、研报、公告检索）
├── filesystem/config.json    # 文件系统访问（本地数据文件读写）
└── README.md
```

## 传输协议

- **stdio**: 通过标准输入输出通信，适用于本地进程启动的服务器
- **sse**: 通过 Server-Sent Events 通信，适用于远程或独立部署的服务器

## 添加新服务器

1. 在 `mcp_servers/` 下创建新目录
2. 添加 `config.json` 文件，格式如下：

```json
{
  "mcpServers": {
    "server-name": {
      "command": "uvx",
      "args": ["package-name"],
      "env": { "KEY": "value" },
      "description": "服务器描述"
    }
  }
}
```

## 环境变量

部分服务器需要 API 密钥，请在 config.json 的 `env` 字段中配置：

| 服务器 | 环境变量 | 获取方式 |
|--------|---------|---------|
| SEC EDGAR | `SEC_API_KEY` | [SEC EDGAR](https://www.sec.gov/edgar) 申请 |
| A-Share | `Authorization` Header | 本地部署服务配置 |
| Tushare | `TUSHARE_TOKEN` | [Tushare](https://tushare.pro) 注册获取 |
| Web Search | `SEARCH_API_KEY`, `SEARCH_ENGINE_ID` | 搜索引擎 API 控制台申请 |
