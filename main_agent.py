#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_agent.py — 主代理 
"""
import json
import requests
import time
import threading
import random
import logging
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_THINKING,
    GLM_API_KEY, GLM_BASE_URL, GLM_MODEL,
    ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, CLAUDE_MODEL, ANTHROPIC_VERSION,
    MINIMAX_API_KEY, MINIMAX_BASE_URL, MINIMAX_MODEL,
    MCP_SERVER_ENABLED, MCP_SERVER_URL, MCP_SERVER_TOKEN, MCP_SERVER_NAME,
    LOCAL_TOOLS_MCP_ENABLED, LOCAL_TOOLS_MCP_URL, LOCAL_TOOLS_MCP_NAME,
)
from tools   import get_tools_openai, get_tools_anthropic
from prompts import RETRY_MESSAGE
# ─────────────────────────────────────────────────────────────
#  全局配置与流控 (防 429)
# ─────────────────────────────────────────────────────────────
# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
# 使用 Session 维持持久连接，提升性能并减少握手开销
session = requests.Session()
# 全局锁：确保所有线程/Worker在同一时刻只能有一个在请求API，物理防范并发 429
api_lock = threading.Lock()
# ─────────────────────────────────────────────────────────────
#  后端路由表（所有 OpenAI 兼容接口）
# ─────────────────────────────────────────────────────────────
_BACKENDS = {
    "deepseek": {
        "api_key":  lambda: DEEPSEEK_API_KEY,
        "base_url": lambda: DEEPSEEK_BASE_URL,
        "model":    lambda: DEEPSEEK_MODEL,
        "thinking": True,
        "temperature": 1.0,
    },
    "glm": {
        "api_key":  lambda: GLM_API_KEY,
        "base_url": lambda: GLM_BASE_URL,
        "model":    lambda: GLM_MODEL,
        "thinking": True,
        "temperature": 1.0,
    },
    "minimax": {
        "api_key":  lambda: MINIMAX_API_KEY,
        "base_url": lambda: MINIMAX_BASE_URL,
        "model":    lambda: MINIMAX_MODEL,
        "thinking": False,
        "temperature": 0.6,
    },
}
def _parse_coop(provider: str):
    """
    "ds_think_glm_check"  → ("deepseek", "glm")
    "glm_think_ds_check"  → ("glm", "deepseek")
    返回 None 表示非协作模式。
    """
    if "_think_" not in provider:
        return None
    parts    = provider.split("_think_")
    thinker  = "deepseek" if parts[0] == "ds" else parts[0]
    checker  = parts[1].replace("_check", "")
    checker  = "deepseek" if checker == "ds" else checker
    return thinker, checker
def _base_request(method: str, url: str, backend_name: str, 
                    initial_wait: float = 2.0, headers: dict = None, 
                    json_body: dict = None, timeout: int = 180) -> dict:
    """
    全局唯一的 API 请求函数，统一负责：并发锁控、指数退避重试、异常处理。
    成功返回 resp.json()，失败返回 {"error": ...}
    """
    max_retries = 8
    for attempt in range(max_retries):
        try:
            with api_lock:
                if attempt > 0:
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logging.warning(f"[{backend_name}] 触发重试[{attempt}]，正在休眠 {wait_time:.2f}s...")
                    time.sleep(wait_time)
                else:
                    time.sleep(initial_wait)
                logging.info(f"[{backend_name}] 发起请求 URL: {url}")
                resp = session.request(method, url, headers=headers, json=json_body, timeout=timeout)
                # 针对限流和后端错误的特殊处理
                if resp.status_code in [429, 500, 502, 503, 504]:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text[:100]}")
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logging.error(f"[{backend_name}] 请求崩溃: {str(exc)[:150]}")
            if attempt == max_retries - 1:
                return {"error": f"API 请求最终失败，已重试 {max_retries} 次: {exc}"}
    return {"error": "Unknown error"}
# ─────────────────────────────────────────────────────────────
#  底层：单次 OpenAI 兼容调用 
# ─────────────────────────────────────────────────────────────
def _call_backend(backend_name: str, messages: list,
                    tools: list = None, temperature: float = None) -> dict:
    cfg = _BACKENDS[backend_name]
    headers = {
        "Authorization": f"Bearer {cfg['api_key']()}",
        "Content-Type":  "application/json"
    }
    body = {
        "model":       cfg["model"](),
        "messages":    messages,
        "temperature": temperature if temperature is not None else cfg["temperature"],
        "max_tokens":  8192,      
    }
    if tools:
        body["tools"]       = tools
        body["tool_choice"] = "auto"
    logging.info(f"[{backend_name}] 发起请求模型: {body['model']}")
    data = _base_request("POST", cfg["base_url"](), backend_name, 2.0, headers=headers, json_body=body, timeout=180)
    if "error" in data:
        return data
    # 解析响应
    choice   = data["choices"][0]
    message  = choice["message"]
    tcs      = message.get("tool_calls") or []
    usage    = data.get("usage", {})
    thinking = message.get("reasoning_content") or ""
    tool_calls = []
    for tc in tcs:
        try:    args = json.loads(tc["function"]["arguments"])
        except: args = {}
        tool_calls.append({"id": tc["id"], "name": tc["function"]["name"], "args": args})
    return {
        "content":       message.get("content") or "",
        "thinking":      thinking,
        "tool_calls":    tool_calls,
        "mcp_tool_uses": [],
        "mcp_results":   [],
        "finish_reason": choice.get("finish_reason", ""),
        "_raw_content":  [],
        "usage": {
            "prompt_tokens":     usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens":      usage.get("total_tokens", 0),
        }
    }
# ─────────────────────────────────────────────────────────────
#  协作模式核心
# ─────────────────────────────────────────────────────────────
_THINKER_SUFFIX = """
你现在是【攻击策略制定者】。
任务：基于当前信息，给出下一步的具体攻击方案。
要求：
- 清晰说明漏洞假设和置信度
- 给出具体的 Payload 或操作步骤
- 如需调用工具，明确指出工具名和参数
- 输出格式：[思路] ... [Payload/操作] ... [预期结果] ...
"""
_CHECKER_SUFFIX = """
你现在是【攻击方案审阅者】。
任务：评估上一步 Thinker 给出的攻击方案，并决定是否执行。
规则：
- 如果方案合理且有效，直接调用对应工具执行
- 如果方案有缺陷，给出修正后的 Payload 并调用工具
- 如果方案明显错误，指出原因并提出替代思路并调用工具
- 无论如何，必须调用工具推进攻击流程
"""
def _call_coop(thinker: str, checker: str,
                messages: list, system_prompt: str) -> dict:
    """
    协作调用：Thinker → Checker
    返回标准化响应（以 Checker 的 tool_calls 为准）
    """
    tools = get_tools_openai()
    # Step 1: Thinker 制定方案（不调用工具，只输出策略文本）
    thinker_sys = system_prompt + _THINKER_SUFFIX
    thinker_messages = _rebuild_messages_for_backend(messages, thinker_sys)
    thinker_resp = _call_backend(thinker, thinker_messages,
                                    tools=None, temperature=1.0)
    if "error" in thinker_resp:
        return thinker_resp   # Thinker 出错，降级返回错误
    thinker_content = thinker_resp.get("content", "")
    thinker_thinking = thinker_resp.get("thinking", "")
    # Step 2: Checker 基于 Thinker 方案做决策并调用工具
    checker_sys = system_prompt + _CHECKER_SUFFIX
    checker_context = list(messages)   # 保留原始对话历史
    # 将 Thinker 方案注入作为最后一条 assistant 消息
    thinker_summary = (
        f"[Thinker({thinker}) 方案]\n"
        f"{('思考过程: ' + thinker_thinking[:500]) if thinker_thinking else ''}\n"
        f"{thinker_content}"
    ).strip()
    checker_context.append({"role": "assistant", "content": thinker_summary})
    checker_context.append({"role": "user",
                                "content": "请基于以上方案，执行最有效的攻击操作（调用工具）。"})
    checker_messages = _rebuild_messages_for_backend(checker_context, checker_sys)
    checker_resp = _call_backend(checker, checker_messages,
                                    tools=tools, temperature=0.5)
    if "error" in checker_resp:
        # Checker 出错，用 Thinker 结果降级（但 Thinker 没有 tool_calls）
        return thinker_resp
    # 合并 token 统计
    total_tokens = (thinker_resp["usage"]["total_tokens"]
                    + checker_resp["usage"]["total_tokens"])
    checker_resp["usage"]["total_tokens"] = total_tokens
    checker_resp["usage"]["prompt_tokens"] += thinker_resp["usage"]["prompt_tokens"]
    checker_resp["usage"]["completion_tokens"] += thinker_resp["usage"]["completion_tokens"]
    # 将 Thinker 的思考链保存到 thinking 字段（便于日志展示）
    combined_thinking = ""
    if thinker_thinking:
        combined_thinking += f"[{thinker} 推理链]\n{thinker_thinking[:800]}\n\n"
    if checker_resp.get("thinking"):
        combined_thinking += f"[{checker} 思考]\n{checker_resp['thinking'][:400]}"
    checker_resp["thinking"] = combined_thinking
    # content 中保留 Thinker 方案（便于日志）
    checker_resp["content"] = (
        f"[Thinker({thinker})]\n{thinker_content[:300]}\n\n"
        f"[Checker({checker})]\n{checker_resp.get('content','')}"
    )
    return checker_resp
def _rebuild_messages_for_backend(messages: list, system_prompt: str) -> list:
    result = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            continue  # 系统提示已经添加
        if role in ("user", "assistant"):
            content = msg.get("content", "")
            # 处理 Claude 格式的 content list
            if isinstance(content, list):
                text = " ".join(
                    b.get("text","") or b.get("content","")
                    for b in content if isinstance(b, dict)
                )
                content = text.strip()
            new_msg = {"role": role, "content": content}
            # 保留 tool_calls 字段（如果有）
            if "tool_calls" in msg and msg["tool_calls"]:
                new_msg["tool_calls"] = msg["tool_calls"]
            result.append(new_msg)
        elif role == "tool":
            # 保留完整的 tool 消息（包含 tool_call_id 和 content）
            result.append(msg)
    return result
# ─────────────────────────────────────────────────────────────
#  Claude 后端（含 MCP 注入，已添加健壮重试）
# ─────────────────────────────────────────────────────────────
def _call_claude(messages: list, system_prompt: str) -> dict:
    """
    Claude 调用函数（增强版）
    功能：
    1️⃣ 若使用 Claude API → 原生 MCP 自动执行
    2️⃣ 若使用 DeepSeek / GLM → 自动 fallback 本地 MCP dispatcher
    3️⃣ 自动识别 playwright.* 工具调用
    """
    url = f"{ANTHROPIC_BASE_URL.rstrip('/')}/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json"
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 16384,
        "system": system_prompt,
        "messages": messages,
        "tools": get_tools_anthropic(),
        "temperature": 0.5,
    }
    # ===============================
    # 仅当真实 Claude API 时启用 MCP
    # ===============================
    mcp_servers = []
    if MCP_SERVER_ENABLED:
        mcp_servers.append({
            "type": "url",
            "url": MCP_SERVER_URL,
            "name": MCP_SERVER_NAME,
            "authorization_token": MCP_SERVER_TOKEN,
        })
    if LOCAL_TOOLS_MCP_ENABLED:
        mcp_servers.append({
            "type": "url",
            "url": LOCAL_TOOLS_MCP_URL,
            "name": LOCAL_TOOLS_MCP_NAME,
        })
    if mcp_servers:
        body["mcp_servers"] = mcp_servers
    # ===============================
    # API 请求（统一交由 _base_request 处理）
    # ===============================
    data = _base_request("POST", url, "Claude", 1.5, headers=headers, json_body=body, timeout=180)
    if "error" in data:
        return data
    # ===============================
    # 解析 Claude blocks
    # ===============================
    raw_blocks = data.get("content", [])
    text_parts = []
    tool_calls = []
    mcp_tool_uses = []
    mcp_results = []
    for block in raw_blocks:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append({
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "args": block.get("input", {})
            })
        elif btype == "mcp_tool_use":
            mcp_tool_uses.append({
                "id": block.get("id", ""),
                "name": block.get("name", ""),
                "args": block.get("input", {})
            })
        elif btype == "mcp_tool_result":
            mcp_results.append(block)
    # ===============================
    # fallback：非 Claude API 时自动调用本地 MCP
    # ===============================
    local_mcp_results = []
    if tool_calls:
        for tc in tool_calls:
            tool_name = tc["name"]
            # 自动识别 playwright MCP 工具
            if tool_name.startswith("playwright."):
                # 同样统一使用 _base_request 发送请求给本地 MCP
                r_data = _base_request("POST", LOCAL_TOOLS_MCP_URL, "Local MCP", 0.0, 
                                        json_body={"name": tool_name, "arguments": tc["args"]}, 
                                        timeout=120)
                if "error" not in r_data:
                    local_mcp_results.append(
                        {
                            "tool_call_id": tc["id"],
                            "name": tool_name,
                            "result": r_data
                        }
                    )
                else:
                    logging.error(f"[Local MCP] 调用失败: {r_data['error']}")
    # ===============================
    # token usage
    # ===============================
    usage = data.get("usage", {})
    inp = usage.get("input_tokens", 0)
    out = usage.get("output_tokens", 0)
    return {
        "content": "\n".join(text_parts),
        "thinking": "",
        "tool_calls": tool_calls,
        "mcp_tool_uses": mcp_tool_uses,
        "mcp_results": mcp_results,
        "local_mcp_results": local_mcp_results,
        "finish_reason": data.get("stop_reason", ""),
        "_raw_content": raw_blocks,
        "usage": {
            "prompt_tokens": inp,
            "completion_tokens": out,
            "total_tokens": inp + out
        }
    }
def _append_claude(messages, response, tool_calls, tool_results): # 上下文回填 
    messages.append({"role": "assistant", "content": response.get("_raw_content", [])})
    if tool_calls:
        blocks = [
            {"type": "tool_result", "tool_use_id": tc["id"],
                "content": json.dumps({k:v for k,v in r.items() if k!="_raw_body"},
                                    ensure_ascii=False)[:3000]}
            for tc, r in zip(tool_calls, tool_results)
        ]
        messages.append({"role": "user", "content": blocks})
def _append_openai_compat(messages, response, tool_calls, tool_results):
    raw_tcs = [
        {"id": tc["id"], "type": "function",
            "function": {"name": tc["name"],
                        "arguments": json.dumps(tc["args"], ensure_ascii=False)}}
        for tc in tool_calls
    ]
    messages.append({"role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": raw_tcs})
    for tc, result in zip(tool_calls, tool_results):
        clean = {k: v for k, v in result.items() if k != "_raw_body"}
        messages.append({
            "role": "tool", "tool_call_id": tc["id"],
            "content": json.dumps(clean, ensure_ascii=False)[:3000]
        })
# ─────────────────────────────────────────────────────────────
#  统一公共接口 (增强了异常处理防崩溃)
# ─────────────────────────────────────────────────────────────
def call(provider: str, messages: list, system_prompt: str) -> dict:
    """
    统一调用入口。
    provider: "ds_think_glm_check" | "glm_think_ds_check" | "deepseek" | "glm" | "claude"
    """
    try:
        coop = _parse_coop(provider)
        if coop:
            thinker, checker = coop
            return _call_coop(thinker, checker, messages, system_prompt)
        if provider == "claude":
            return _call_claude(messages, system_prompt)
        if provider in _BACKENDS:
            msgs = _rebuild_messages_for_backend(messages, system_prompt)
            return _call_backend(provider, msgs, tools=get_tools_openai())
        return {"error": f"未知 provider: {provider}"}
    except Exception as e:
        logging.error(f"调用入口发生不可预见的严重异常: {str(e)}")
        return {"error": f"系统崩溃级异常: {str(e)}"}
def append_results(provider, messages, response, tool_calls, tool_results): # 把工具执行结果写回对话历史
    if provider == "claude":
        _append_claude(messages, response, tool_calls, tool_results)
    else:
        _append_openai_compat(messages, response, tool_calls, tool_results)
def init_messages(provider, first_user_msg, system_prompt):
    """初始化消息列表（system_prompt 已在 call() 内部注入，这里只保存对话内容）"""
    if provider == "claude":
        return [{"role": "user", "content": first_user_msg}]
    # 非 claude：消息列表不含 system（call() 内部通过 _rebuild_messages_for_backend 注入）
    return [{"role": "user", "content": first_user_msg}]
def append_user_message(provider, messages, text):
    if provider == "claude" and messages and messages[-1]["role"] == "user":
        last = messages[-1]["content"]
        if isinstance(last, list):
            last.append({"type": "text", "text": text})
        else:
            messages[-1]["content"] = last + "\n\n" + text
        return
    messages.append({"role": "user", "content": text})
def append_retry(provider, messages, assistant_text):
    messages.append({"role": "assistant", "content": assistant_text or ""})
    append_user_message(provider, messages, RETRY_MESSAGE)