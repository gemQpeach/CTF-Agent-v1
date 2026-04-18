# CTF-Agent-v1

面向 Web 类 CTF 竞赛的自主渗透测试智能体。

## 简介

CTF-Agent 是一个模块化的多模型 AI Agent 系统，支持对 Web 应用自动完成漏洞识别、利用与 Flag 提交的完整流程。系统采用"主代理 + 响应分析子代理"的双层架构，主代理负责策略推理与工具调用，子代理负责 HTTP 响应的结构化信息提取。支持接入腾讯云黑客松竞赛平台（MCP 协议），实现题目拉取、实例启停与 Flag 提交的全自动化。

## 模块结构

| 文件 | 职责 |
|---|---|
| `config.py` | 全局配置：API Key、路径、超参数 |
| `prompts.py` | 所有提示词（主代理 / 子代理 / 知识库注入模板）|
| `main_agent.py` | 主代理，支持 DeepSeek / Claude / MiniMax / GLM |
| `sub_agent.py` | HTTP 响应分析子代理，提取表单、注释、端点等关键信息 |
| `tools.py` | 工具定义（双格式）及 HTTP 请求执行层 |
| `platform_client.py` | MCP 平台客户端，管理题目生命周期 |
| `knowledge.py` | 知识库模块，按漏洞类型自动注入参考文档 |
| `skills.py` | 技能库模块，启动时加载攻击方法论追加到系统提示词 |
| `session.py` | 单题执行循环：轮次控制、工具分发、日志持久化 |
| `main.py` | 程序入口：Provider 选择、并发调度、汇总报告 |

## 快速开始

```bash
# 安装依赖
pip install requests mcp

# 配置环境变量（竞赛模式）
export MCP_SERVER_HOST="http://<SERVER_HOST>/mcp"
export MCP_AGENT_TOKEN="<YOUR_AGENT_TOKEN>"
export DEEPSEEK_API_KEY="sk-..."   # 至少配置一个 LLM Key

# 虚拟环境
source .venv/bin/activate

# 启动
python3 /home/ubuntu/CTF-Agent-v1-main/main.py

# 查看日志：
python3 /home/ubuntu/CTF-Agent-v1-main/build_dashbord.py
```

启动后选择主代理模型（DeepSeek / Claude / MiniMax / GLM），竞赛模式下系统自动拉取题目列表并开始并行攻击。本地测试模式（`COMPETITION_MODE = False`）下手动输入目标 URL 即可。

## 运行时干预

程序运行中可通过标准输入注入提示：

```
<challenge_code> <提示内容>
```

## 知识库与技能库

- `knowledge/` 目录下放置漏洞参考文档（`.txt`），第一行为漏洞类型标签，系统在第 20 轮自动检索注入。
- `skills/` 目录下放置攻击方法论文件，启动时全部加载追加到系统提示词。

## 支持的漏洞类型

SQL 注入、XSS、IDOR、SSRF、文件包含、命令注入、JWT 伪造、SSTI、XXE、反序列化、身份认证绕过、文件上传、原型链污染、GraphQL 注入、NoSQL 注入等。

---

> 本项目仅用于合法授权的安全竞赛与研究环境。




