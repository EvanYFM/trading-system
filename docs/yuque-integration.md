# 语雀连接方案

> 核验日期：2026-06-04。本项目不保存任何语雀 token、账号、密码或 Cookie。

## 结论

目前可走两条路径：

- `yuque-cli`：适合手动在命令行查看、搜索、导出语雀笔记。
- `yuque-mcp`：适合让支持 MCP 的 AI 助手直接搜索、读取、创建和更新语雀文档。

如果目标是“让 Codex 直接去语雀笔记里看内容”，优先考虑 `yuque-mcp`。如果当前 Codex 环境暂时没有接入自定义 MCP，则先用 `yuque-cli` 把笔记拉到本地，再让 Codex 分析。

当前 Codex 会话工具搜索未发现语雀连接器，因此本次不能直接读取语雀账号内容。

## 本机环境

- Node.js 已可用：v24.15.0。
- npx 已可用：11.12.1。
- Windows PowerShell 直接调用 `npm` 可能会被执行策略拦截；本机可用 `npm.cmd` 和 `npx.cmd`。

## 方案 A：使用 yuque-cli

包信息核验：

- npm 包：`yuque-cli`
- 当前 latest：0.1.1
- 描述：Interactive Yuque CLI
- 要求：Node.js >= 18

安装：

```powershell
npm.cmd install -g yuque-cli
```

登录方式：

```powershell
yuque auth login
```

或临时使用环境变量：

```powershell
$env:YUQUE_TOKEN="你的语雀 token"
yuque whoami
```

常用命令：

```powershell
yuque list repos
yuque list docs <repo>
yuque show <repo>/<doc>
yuque search "交易系统" <repo>
```

注意：`yuque-cli` 默认可能把 token 保存到用户目录下的语雀配置文件。不要把该配置文件复制进项目。

## 方案 B：使用 yuque-mcp

包信息核验：

- npm 包：`yuque-mcp`
- 当前 latest：1.0.0
- 描述：MCP server for Yuque，面向 AI 助手暴露语雀知识库。

交互式配置：

```powershell
npx.cmd yuque-mcp setup
```

如果 AI 客户端支持 MCP stdio，可配置为：

```json
{
  "mcpServers": {
    "yuque": {
      "command": "npx.cmd",
      "args": ["-y", "yuque-mcp"],
      "env": {
        "YUQUE_PERSONAL_TOKEN": "你的语雀 token"
      }
    }
  }
}
```

`yuque-mcp` 暴露的能力包括：

- 用户：获取当前用户。
- 搜索：搜索语雀文档。
- 知识库：列出、获取、创建、更新知识库。
- 文档：列出、获取、创建、更新文档。
- 目录：读取和更新目录。
- 小记：列出、获取、创建、更新小记。

## 建议工作流

短期：

1. 用 `yuque-cli` 或语雀导出功能，把重要笔记同步到本地。
2. 本地笔记进入项目后，Codex 按 `docs/trading-system.md` 和 `docs/trading-decision-checklist.md` 归纳、合并、复盘。

长期：

1. 配置 `yuque-mcp`。
2. 让 Codex 搜索语雀中与某个品种、策略、复盘相关的笔记。
3. 每次新交易想法先过系统检查，再把复盘回写为新的语雀笔记或本地项目文档。

## 安全规则

- token 只放环境变量、本机用户配置或 MCP 客户端私有配置。
- 不把 token、Cookie、账号、密码写进 `README.md`、`AGENTS.md`、脚本或提交记录。
- 如果需要我实际连接语雀，请只提供“已完成本机配置”的状态，不要把 token 发到聊天里。
