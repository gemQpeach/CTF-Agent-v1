#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
platform_client.py — 竞赛平台 MCP 客户端
通过 Python MCP SDK 直接调用平台工具，用于题目生命周期管理。

职责划分：
  本模块  → list / start / stop（基础设施操作，由 session 编排）
  Claude  → submit_flag / view_hint（通过 mcp_servers 参数在对话中自主调用）
"""
import json
import asyncio
import threading
import time as _time
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

from config import MCP_SERVER_URL, MCP_SERVER_TOKEN

_AUTH_HEADERS = {"Authorization": f"Bearer {MCP_SERVER_TOKEN}"}


# ─────────────────────────────────────────────────────────────
#  底层：异步调用单个 MCP 工具
# ─────────────────────────────────────────────────────────────

async def _call(tool_name: str, arguments: dict) -> dict:
    """建立短连接，调用一次工具后关闭。"""
    async with streamablehttp_client(MCP_SERVER_URL, headers=_AUTH_HEADERS) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            for content in result.content:
                if hasattr(content, "text"):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return {"raw": content.text}
    return {}


# 全局锁：序列化所有 MCP 调用，避免连接池竞争和频率超限
_mcp_lock = threading.Lock()
# 实例启动专用锁：确保同时最多 MAX_CONCURRENT_INSTANCES 个实例在运行
_instance_semaphore = threading.Semaphore(3)   # 平台限制最多 3 个

def _run(coro):
    """线程安全的 asyncio 运行器：串行化执行，避免连接池耗尽。"""
    with _mcp_lock:
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(coro)
            return result
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                if pending:
                    loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()


# ─────────────────────────────────────────────────────────────
#  公共同步接口
# ─────────────────────────────────────────────────────────────

def list_challenges() -> dict:
    """
    获取当前关卡及之前关卡的赛题列表。

    返回示例：
    {
      "current_level": 1,
      "total_challenges": 3,
      "solved_challenges": 0,
      "challenges": [
        {
          "code": "BwAMWQASB1ROWFA",
          "title": "SQL注入入门",
          "difficulty": "easy",
          "flag_count": 1,
          "flag_got_count": 0,
          "total_score": 100,
          "total_got_score": 0
        }, ...
      ]
    }
    """
    return _run(_call("list_challenges", {}))


def start_challenge(code: str) -> dict:
    """
    启动赛题实例。
    - 关卡未解锁：立即返回 {"level_locked": True}，调用方应跳过该题
    - 频率超限：自动重试（最多 4 次）
    """
    max_retries = 4
    result = {}
    for attempt in range(max_retries):
        result = _run(_call("start_challenge", {"code": code}))
        raw = result.get("raw", "")
        # 关卡未解锁：立即放弃，不重试
        if "尚未解锁关卡" in raw or "未解锁" in raw or "level" in raw.lower() and "unlock" in raw.lower():
            print(f"\033[93m[平台] 关卡未解锁，跳过此题: {raw}\033[0m")
            result["level_locked"] = True
            return result
        # 频率超限：短暂等待重试
        if "频率超出限制" in raw or ("rate" in raw.lower() and "limit" in raw.lower()):
            _time.sleep(attempt + 1)
            continue
        return result
    return result
def stop_challenge(code: str) -> dict:
    """停止赛题实例，释放资源。"""
    return _run(_call("stop_challenge", {"code": code}))


def submit_flag(code: str, flag: str) -> dict:
    """
    直接提交 Flag（通常 Claude 通过 MCP 自主调用，此接口供程序化验证备用）。

    返回示例：
    {
      "correct": true,
      "message": "恭喜！答案正确（1/1）",
      "flag_got_count": 1,
      "flag_count": 1
    }
    """
    return _run(_call("submit_flag", {"code": code, "flag": flag}))


def view_hint(code: str) -> dict:
    """
    查看赛题提示（首次查看扣除该题总分 10%）。

    返回示例：
    {
      "code": "BwAMWQASB1ROWFA",
      "hint_content": "尝试注入 ' OR 1=1--"
    }
    """
    return _run(_call("view_hint", {"code": code}))