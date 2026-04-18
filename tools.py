#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools.py — 工具定义 + HTTP 执行层

工具列表：
  http_request        → HTTP 渗透请求
  write_python_script → 代码编写子代理（GLM）
  start/stop/submit/hint → 平台工具（竞赛模式）
"""
import os
import re
import requests
import urllib3
urllib3.disable_warnings()

from config import COMPETITION_MODE, MCP_SERVER_ENABLED

_USE_PLATFORM = COMPETITION_MODE and MCP_SERVER_ENABLED

# ─────────────────────────────────────────────────────────────
#  Schema 定义
# ─────────────────────────────────────────────────────────────

_HTTP_SCHEMA = {
    "type": "object",
    "properties": {
        "method":           {"type": "string", "enum": ["GET","POST","PUT","DELETE","PATCH","HEAD"]},
        "url":              {"type": "string",  "description": "完整请求 URL"},
        "headers":          {"type": "object",  "description": "自定义请求头"},
        "cookies":          {"type": "object",  "description": "Cookie 字典"},
        "params":           {"type": "object",  "description": "URL 查询参数"},
        "data":             {"type": "object",  "description": "表单数据"},
        "json_body":        {"type": "object",  "description": "JSON 请求体"},
        "raw_body":         {"type": "string",  "description": "原始请求体"},
        "follow_redirects": {"type": "boolean", "description": "是否跟随重定向，默认 true"},
        "timeout":          {"type": "integer", "description": "超时秒数，默认 15"}
    },
    "required": ["method", "url"]
}

_SUBMIT_FLAG_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "赛题 code"},
        "flag": {"type": "string", "description": "找到的 flag 字符串"}
    },
    "required": ["code", "flag"]
}

_SUBMIT_FLAG_LOCAL_SCHEMA = {
    "type": "object",
    "properties": {
        "flag": {"type": "string", "description": "找到的 flag 字符串"}
    },
    "required": ["flag"]
}

_PLATFORM_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "赛题 code"}
    },
    "required": ["code"]
}

_HINT_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string", "description": "赛题 code（注意：首次查看扣分 10%）"}
    },
    "required": ["code"]
}

_SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "description": (
                "需要脚本解决的具体任务描述。"
                "包含：目标URL、参数名、已知数据、期望输出。"
                "例如：对字符串 eyJhbGc 做 Base64 解码 / "
                "遍历 id=1..200 找flag / "
                "伪造 JWT admin=true"
            )
        },
        "context": {
            "type": "string",
            "description": "已发现的关键信息（Cookie、URL、参数值等），可选"
        }
    },
    "required": ["task"]
}

# ══════════════════════════════════════════════════════════════
#  run_code_agent 工具定义
# ══════════════════════════════════════════════════════════════
 
# ── Anthropic 格式（用于 Claude 后端）───────────────────────
_CODE_AGENT_TOOL_ANTHROPIC = {
    "name": "run_code_agent",
    "description": (
        "调用 Python 代码子代理，自动生成并执行 Python 脚本来解决需要代码辅助的子任务。\n"
        "适用场景：\n"
        "- Base64/URL/Hex/JWT 编解码\n"
        "- 生成反序列化 Payload（PHP/Python Pickle）\n"
        "- 暴力遍历（IDOR、路径枚举、参数爆破）\n"
        "- Hash 计算与字典破解\n"
        "- SQL 盲注自动化脚本\n"
        "- 自动化 HTTP 请求序列（登录→操作→提取 flag）\n"
        "- 任何需要循环计算或批量处理的任务\n"
        "注意：该工具会真实执行代码，执行结果会直接返回给你。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": (
                    "详细描述需要代码完成的任务。包含：\n"
                    "1. 目标是什么（如：解码 Base64 字符串、爆破 IDOR id）\n"
                    "2. 已知条件（URL、参数名、响应特征等）\n"
                    "3. 期望输出（flag 格式、文件内容等）"
                )
            },
            "context": {
                "type": "string",
                "description": (
                    "可选。提供给代码代理的上下文信息，如：\n"
                    "- 已发现的 Cookie/Token 值\n"
                    "- 响应体片段\n"
                    "- 序列化字符串原文\n"
                    "- 其他已知数据"
                )
            }
        },
        "required": ["task_description"]
    }
}
 
# ── OpenAI 兼容格式（用于 DeepSeek/GLM 后端）────────────────
_CODE_AGENT_TOOL_OPENAI = {
    "type": "function",
    "function": {
        "name": "run_code_agent",
        "description": (
            "调用 Python 代码子代理，自动生成并执行 Python 脚本来解决需要代码辅助的子任务。"
            "适用：编解码、反序列化 Payload 生成、暴力遍历、Hash 破解、"
            "SQL 盲注自动化、自动化 HTTP 序列等。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "详细描述任务：目标、已知条件、期望输出"
                },
                "context": {
                    "type": "string",
                    "description": "可选上下文：Cookie、Token、响应片段、序列化原文等"
                }
            },
            "required": ["task_description"]
        }
    }
}

# ─────────────────────────────────────────────────────────────
#  构造工具列表
# ─────────────────────────────────────────────────────────────

def _ot(name, desc, schema):
    """OpenAI 格式工具"""
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": schema}}

def _at(name, desc, schema):
    """Anthropic 格式工具"""
    return {"name": name, "description": desc, "input_schema": schema}


def get_tools_openai() -> list:
    tools = [
        _ot("http_request",
            "向目标 Web 应用发送 HTTP 请求，响应由子代理预处理返回结构化摘要。",
            _HTTP_SCHEMA),
        _ot("write_python_script",
            "调用代码编写子代理（GLM）生成并在本地执行 Python 脚本。"
            "适用：Base64/URL/Hex 编解码、JWT 伪造、ID 遍历、哈希破解、盲注自动化等。"
            "脚本在沙箱中执行，输出结果直接返回。",
            _SCRIPT_SCHEMA),
        _CODE_AGENT_TOOL_OPENAI, 
    ]
    if _USE_PLATFORM:
        tools += [
            _ot("start_challenge", "启动赛题容器实例，获取入口 URL。同时最多 3 个实例。", _PLATFORM_SCHEMA),
            _ot("stop_challenge",  "停止赛题容器实例，释放资源。完成或放弃时调用。",      _PLATFORM_SCHEMA),
            _ot("submit_flag",     "提交找到的 Flag，系统自动判分。需传入 code 和 flag。", _SUBMIT_FLAG_SCHEMA),
            _ot("view_hint",       "查看赛题提示（首次查看扣该题总分 10%，谨慎使用）。",  _HINT_SCHEMA),
        ]
    else:
        tools.append(_ot("submit_flag", "找到 FLAG 后调用此工具提交。", _SUBMIT_FLAG_LOCAL_SCHEMA))
    return tools


def get_tools_anthropic() -> list:
    """Claude 后端：竞赛模式下不含 submit_flag（由 MCP 直接提供）"""
    tools = [
        _at("http_request",
            "向目标 Web 应用发送 HTTP 请求，响应由子代理预处理返回结构化摘要。",
            _HTTP_SCHEMA),
        _at("write_python_script",
            "调用代码编写子代理（GLM）生成并在本地执行 Python 脚本。"
            "适用：Base64/URL/Hex 编解码、JWT 伪造、ID 遍历、哈希破解、盲注自动化等。",
            _SCRIPT_SCHEMA),
        _CODE_AGENT_TOOL_ANTHROPIC,
    ]
    if not _USE_PLATFORM:
        tools.append(_at("submit_flag", "找到 FLAG 后调用此工具提交。", _SUBMIT_FLAG_LOCAL_SCHEMA))
    return tools


# 向后兼容常量
TOOLS_OPENAI    = get_tools_openai()
TOOLS_ANTHROPIC = get_tools_anthropic()


# ─────────────────────────────────────────────────────────────
#  HTTP 请求执行
# ─────────────────────────────────────────────────────────────

_DEFAULT_UA = "Mozilla/5.0 (X11; Linux x86_64; CTF-Agent/2.0) AppleWebKit/537.36"

def execute_http_request(args: dict) -> dict:
    method  = args.get("method", "GET").upper()
    url     = args.get("url", "")
    headers = {"User-Agent": _DEFAULT_UA, **(args.get("headers") or {})}
    cookies = args.get("cookies") or {}
    params  = args.get("params")  or {}
    data    = args.get("data")
    json_b  = args.get("json_body")
    raw_b   = args.get("raw_body")
    follow  = args.get("follow_redirects", True)
    timeout = args.get("timeout", 15)
    try:
        resp = requests.request(
            method=method, url=url,
            headers=headers, cookies=cookies, params=params,
            data=raw_b if raw_b else data, json=json_b,
            allow_redirects=follow, timeout=timeout, verify=False
        )
        return {
            "status_code": resp.status_code,
            "headers":     dict(resp.headers),
            "cookies":     dict(resp.cookies),
            "body":        resp.text,
            "final_url":   resp.url,
            "elapsed_ms":  int(resp.elapsed.total_seconds() * 1000)
        }
    except Exception as exc:
        return {"error": str(exc)}


# ─────────────────────────────────────────────────────────────
#  本地 Flag 验证（非竞赛模式）
# ─────────────────────────────────────────────────────────────

def local_validate_flag(submitted: str, challenge_id: str, benchmarks_path: str) -> dict:
    env_path = os.path.join(benchmarks_path, str(challenge_id).zfill(3), ".env")
    correct  = None
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    m = re.match(r'^\s*FLAG\s*=\s*["\']?(.+?)["\']?\s*$',
                                 line.strip(), re.IGNORECASE)
                    if m:
                        correct = m.group(1).strip(); break
        except Exception:
            pass
    if correct is None:
        return {"status": "submitted", "flag": submitted,
                "validation": "no_env", "note": "无法自动验证，默认接受"}
    ok = submitted.strip().lower() == correct.strip().lower()
    return {"status": "submitted", "flag": submitted,
            "validation": "correct" if ok else "wrong",
            "note": "Flag 正确" if ok else "Flag 错误，请继续寻找"}