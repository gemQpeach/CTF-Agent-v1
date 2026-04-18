#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session.py — 单题执行循环（集成版）
"""
import os, json, time, threading, re, shutil
import requests as _req
from datetime import datetime
from pathlib import Path
from config     import (MAX_ROUNDS, CHALLENGE_TIMEOUT_SECONDS, PAUSE_EVERY_N,
                        LOG_ROOT, BENCHMARKS_PATH,
                        KNOWLEDGE_INJECT_ROUND, COMPETITION_MODE, MCP_SERVER_ENABLED)
from tools      import execute_http_request, local_validate_flag
from sub_agent  import analyze_response
# 引入 _base_request 统一处理网络请求
from main_agent import call, append_results, init_messages, append_user_message, append_retry, _base_request
from knowledge  import build_injection
from skills     import build_system_prompt, get_skills, inject_skill_if_needed
import master_log as mlog
from code_agent import write_and_run as _code_agent_run
if COMPETITION_MODE and MCP_SERVER_ENABLED:
    import platform_client
G="\033[92m"; Y="\033[93m"; R="\033[91m"; M="\033[95m"; X="\033[0m"
GRAY="\033[90m"; CYAN2="\033[36m"; KB_COLOR="\033[38;5;208m"
CODE_COLOR="\033[38;5;214m"   # 橙色：code_agent 专用
MCP_COLOR ="\033[38;5;51m"    # 青色：MCP 专用
_print_lock = threading.Lock()
def tprint(msg, color, cid):
    with _print_lock:
        print(f"{color}[{cid[:16]}] {msg}{X}", flush=True)
# ── Hint 队列 ─────────────────────────────────────────────────
_hint_queue = {}; _hint_lock = threading.Lock()
def inject_hint(cid, text):
    with _hint_lock: _hint_queue[cid] = text
def _pop_hint(cid):
    with _hint_lock: return _hint_queue.pop(cid, None)
# ── 5 分钟定时日志保存 ────────────────────────────────────────
class _PeriodicSaver:
    INTERVAL = 5 * 60
    def __init__(self, ch_log, log_path):
        self._log = ch_log; self._path = log_path
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
    def start(self): self._thread.start()
    def stop(self):  self._stop.set()
    def save_now(self):
        try:
            tmp = self._path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._log, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self._path)
        except Exception: pass
    def _run(self):
        while not self._stop.wait(self.INTERVAL):
            self.save_now()
def _sanitize_messages(messages):
    """
    清洗 messages 列表，防止因格式问题触发 400 Bad Request：
    1. 合并连续的同角色消息（特别是连续的 user 消息）
    2. 移除 content 为空的消息
    3. 兼容处理多模态 content 格式（提取纯文本）
    4. 修复 tool 角色前缺失 assistant 的结构错误
    """
    if not messages:
        return messages
    cleaned = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        # 统一处理 content 为 list (多模态格式) 的情况，提取纯文本防错
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            content = "\n".join(text_parts)
            msg["content"] = content
        # 跳过 content 为空的 user 或 assistant 消息
        if role in ("user", "assistant") and not content:
            continue
        # 合并连续的同 role 消息 (特别是连续的 user，常见于多路注入)
        if cleaned and cleaned[-1]["role"] == role and role in ("user", "assistant"):
            cleaned[-1]["content"] += "\n\n" + (content or "")
        else:
            cleaned.append(msg.copy())
    # 确保不以 assistant 开头
    while cleaned and cleaned[0]["role"] == "assistant":
        cleaned.pop(0)
    # 严格校验：tool 消息的前一条必须是带有 tool_calls 的 assistant
    final_cleaned = []
    for i, msg in enumerate(cleaned):
        if msg["role"] == "tool":
            if final_cleaned and final_cleaned[-1]["role"] == "assistant" and final_cleaned[-1].get("tool_calls"):
                final_cleaned.append(msg)
            # 否则丢弃孤立的 tool 消息
        else:
            final_cleaned.append(msg)
    return final_cleaned
# ── 上下文压缩 ────────────────────────────────────────────────
_COMPRESS_EVERY_N = 10
def _compress_history(messages, challenge_code, provider, round_num):
    if round_num % _COMPRESS_EVERY_N != 0: return messages
    if len(messages) <= 8: return messages
    findings = []
    flag_re = re.compile(r'flag\{[^}]+\}', re.IGNORECASE)
    url_re  = re.compile(r'https?://[^\s"\'<>]+')
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(b.get("text","") for b in content if isinstance(b,dict))
        for flag in flag_re.findall(content): findings.append(f"发现 flag: {flag}")
        for url  in url_re.findall(content)[:2]:  findings.append(f"访问过: {url}")
    findings_text = "\n".join(dict.fromkeys(findings)) or "暂无关键发现"
    summary_msg = {
        "role": "user",
        "content": (
            f"[上下文压缩 @ 第{round_num}轮]\n"
            f"历史消息已压缩以节省 token。关键信息摘要：\n"
            f"{findings_text}\n\n请继续基于以上信息推进渗透测试。"
        )
    }
    return [messages[0], summary_msg] + messages[-4:]
# ══════════════════════════════════════════════════════════════
#  MCP 结果解析与日志保存（核心新增）
# ══════════════════════════════════════════════════════════════
def _extract_mcp_text(block) -> str:
    """从 mcp_tool_result block 中提取文本内容。"""
    content = block.get("content") or []
    parts = []
    for item in content:
        if isinstance(item, dict):
            parts.append(item.get("text", "") or item.get("content", ""))
    return "\n".join(p for p in parts if p)
def _call_playwright_mcp(url, action="visit", args=None):
    # 使用全局统一请求方法
    return _base_request("POST", "http://127.0.0.1:8000/tools/call", "Playwright MCP", 0.0,
                            json_body={
                                "tool": "playwright.visit",
                                "arguments": {"url": url, **(args or {})}
                            },
                            timeout=60)
def _save_mcp_artifact(raw_text: str, tool_name: str,
                        challenge_log_dir: str, challenge_code: str) -> dict:
    """
    将 MCP 工具返回的大体积内容（HTML、截图路径等）持久化到题目日志目录。
    返回 {"html_path": str|None, "screenshot_path": str|None, "log_path": str|None}
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    saved = {"html_path": None, "screenshot_path": None, "log_path": None}
    # ── 完整文本日志（sqlmap 输出 / playwright HTML）────────────
    artifact_path = os.path.join(
        challenge_log_dir, f"mcp_{tool_name}_{ts}.txt"
    )
    try:
        with open(artifact_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(raw_text)
        saved["log_path"] = artifact_path
    except Exception:
        pass
    # ── 提取并复制截图（playwright 返回 [截图] /path/to/file.png）──
    scr_match = re.search(r'\[截图\]\s*(.+\.png)', raw_text)
    if scr_match:
        src_path = scr_match.group(1).strip()
        if os.path.exists(src_path):
            dst_path = os.path.join(
                challenge_log_dir, f"screenshot_{tool_name}_{ts}.png"
            )
            try:
                shutil.copy2(src_path, dst_path)
                saved["screenshot_path"] = dst_path
            except Exception:
                pass
    # ── 提取 HTML 片段单独保存（便于后续人工审阅）───────────────
    # playwright 结果里 HTML 从 "\n\n" 之后开始
    if "playwright" in tool_name.lower() and "<html" in raw_text.lower():
        html_start = raw_text.lower().find("<html")
        if html_start == -1: html_start = raw_text.find("\n\n") + 2
        html_content = raw_text[html_start:]
        html_path = os.path.join(
            challenge_log_dir, f"rendered_{ts}.html"
        )
        try:
            with open(html_path, "w", encoding="utf-8", errors="ignore") as f:
                f.write(html_content)
            saved["html_path"] = html_path
        except Exception:
            pass
    return saved
def _parse_mcp_results(mcp_tool_uses, mcp_results,
                        challenge_code, challenge_log_dir, cid, tprint_fn):
    """
    解析 Claude 路径的 MCP 结果，同时：
        - 将完整内容写入题目日志目录
        - 返回结构化结果供 round_log 使用
    """
    parsed = {
        "submit_flag": [], "start_challenge": [],
        "stop_challenge": [], "view_hint": [],
        "mcp_artifacts": [],   # ← 新增：所有 MCP 工具的持久化记录
    }
    call_map = {tc["id"]: (tc["name"], tc["args"]) for tc in mcp_tool_uses}
    for block in mcp_results:
        uid = block.get("tool_use_id", "")
        if uid not in call_map: continue
        name, args = call_map[uid]
        raw_text = _extract_mcp_text(block)
        # ── 持久化所有 MCP 工具输出 ────────────────────────────
        artifacts = _save_mcp_artifact(raw_text, name, challenge_log_dir, challenge_code)
        artifact_record = {
            "tool":            name,
            "args_summary":    {k: str(v)[:80] for k, v in args.items()},
            "result_preview":  raw_text[:300],
            "log_path":        artifacts["log_path"],
            "html_path":       artifacts["html_path"],
            "screenshot_path": artifacts["screenshot_path"],
        }
        parsed["mcp_artifacts"].append(artifact_record)
        # 打印 MCP 结果摘要
        tprint_fn(f"[MCP:{name}] 结果已保存 → {artifacts['log_path']}")
        if artifacts["screenshot_path"]:
            tprint_fn(f"[MCP:{name}] 截图 → {artifacts['screenshot_path']}")
        if artifacts["html_path"]:
            tprint_fn(f"[MCP:{name}] HTML → {artifacts['html_path']}")
        # ── 平台工具解析（与原逻辑保持兼容）──────────────────
        try:    data = json.loads(raw_text)
        except: data = {}
        if name == "submit_flag":
            flag, correct, msg = (
                args.get("flag",""),
                data.get("correct", False),
                data.get("message", raw_text[:100])
            )
            parsed["submit_flag"].append((flag, correct, msg))
            mlog.log_flag_submit(args.get("code",""), flag, correct, msg)
        elif name == "start_challenge":
            eps = data.get("entrypoint", [])
            url = eps[0] if isinstance(eps, list) and eps else (eps or "")
            if url and not str(url).startswith("http"): url = "http://" + url
            parsed["start_challenge"].append((args.get("code",""), url))
            if url: mlog.log_instance_start(args.get("code",""), "", url)
        elif name == "stop_challenge":
            parsed["stop_challenge"].append(args.get("code",""))
            mlog.log_instance_stop(args.get("code",""), "agent_stop")
        elif name == "view_hint":
            parsed["view_hint"].append((args.get("code",""),
                                        data.get("hint_content","")))
    return parsed
# ── 平台工具代理（非 Claude 后端）────────────────────────────
_PLATFORM_TOOLS = {"start_challenge", "stop_challenge", "submit_flag", "view_hint"}
def _proxy_tool(name, args, challenge_code, cid):
    if name == "start_challenge":
        code = args.get("code", challenge_code)
        try:   result = platform_client.start_challenge(code)
        except Exception as exc: return {"error": str(exc)}
        if result.get("level_locked"):
            return {"level_locked": True, "error": result.get("raw","关卡未解锁")}
        eps = result.get("entrypoint", [])
        if eps:
            url = eps[0] if isinstance(eps, list) else eps
            if url and not str(url).startswith("http"): url = "http://" + url
            mlog.log_instance_start(code, "", url)
            _wait_ready(url, cid)
            return {"success": True, "entrypoint": url, "message": result.get("message","")}
        return {"error": result.get("raw", "启动失败")}
    elif name == "stop_challenge":
        code = args.get("code", challenge_code)
        try:
            res = platform_client.stop_challenge(code)
            mlog.log_instance_stop(code, "agent_stop"); return res
        except Exception as exc: return {"error": str(exc)}
    elif name == "submit_flag":
        code, flag = args.get("code", challenge_code), args.get("flag","")
        try:
            result  = platform_client.submit_flag(code, flag)
            correct = result.get("correct", False)
            msg     = result.get("message","")
            mlog.log_flag_submit(code, flag, correct, msg)
            return {"correct": correct, "message": msg,
                    "flag_got_count": result.get("flag_got_count",0),
                    "flag_count":     result.get("flag_count",1)}
        except Exception as exc: return {"error": str(exc)}
    elif name == "view_hint":
        code = args.get("code", challenge_code)
        try:    return platform_client.view_hint(code)
        except Exception as exc: return {"error": str(exc)}
    return {"error": f"未知工具: {name}"}
# ══════════════════════════════════════════════════════════════
#  工具分发（集成 run_code_agent）
# ══════════════════════════════════════════════════════════════
def _dispatch(name, args, challenge_code, cid, provider,
                challenge_log_dir=None):
    """
    统一工具分发。新增 run_code_agent 分支。
    """
    # ── 平台工具（竞赛模式）────────────────────────────────────
    if name in _PLATFORM_TOOLS and provider != "claude":
        return _proxy_tool(name, args, challenge_code, cid)
    # 本地 flag 校验
    if name == "submit_flag" and not (COMPETITION_MODE and MCP_SERVER_ENABLED):
        return local_validate_flag(
            args.get("flag", ""), cid, BENCHMARKS_PATH
        )
    if name == "capture_render":
        url = args.get("url", "")
        action = args.get("action", "visit")
        result = _call_playwright_mcp(url, action, args)
        return result
    # ── HTTP 请求 + 子代理分析 ──────────────────────────────────
    if name == "http_request":
        raw = execute_http_request(args)
        if "error" in raw:
            return raw
        status = raw.get("status_code", 0)
        body = raw.get("body", "")
        content_type = raw.get("content_type", "")
        # ── ❌ 非 200 直接返回（关键优化） ──
        if status != 200:
            return raw
        # ── ❌ 非 HTML 直接返回 ──
        if "text/html" not in content_type and "<html" not in body.lower():
            return raw
        from sub_agent import needs_render
        # ── 是否需要动态渲染 ──
        if not needs_render(body):
            return raw
        tprint("[Playwright MCP] 触发渲染", Y, cid)
        try:
            playwright_result = _call_playwright_mcp(
                url=args.get("url", ""),
                action="visit",
                args=args
            )
            if playwright_result and playwright_result.get("html"):
                raw["body"] = playwright_result["html"]
                tprint("[子代理] 分析渲染内容", GRAY, cid)
                summary, sub_tok = analyze_response(args, raw)
                return {
                    **raw,
                    "analysis": summary,
                    "sub_agent_tokens": sub_tok,
                    "rendered": True
                }
        except Exception as e:
            tprint(f"[Playwright MCP失败] {e}", R, cid)
        return raw
    # ══════════════════════════════════════════════════════════
    # run_code_agent — 生成并执行 Python 脚本
    # ══════════════════════════════════════════════════════════
    if name == "run_code_agent":
        task = args.get("task_description", "")
        context = args.get("context", "")
        tprint(
            f"[CodeAgent] 任务: {task[:80]}",
            CODE_COLOR,
            cid
        )
        result = _code_agent_run(task, context)
        # 保存脚本
        if challenge_log_dir and result.get("script"):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            script_path = os.path.join(
                challenge_log_dir,
                f"code_agent_{ts}.py"
            )
            output_path = os.path.join(
                challenge_log_dir,
                f"code_agent_{ts}.txt"
            )
            try:
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(result["script"])
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"[Task]\n{task}\n\n")
                    f.write(f"[Context]\n{context}\n\n")
                    f.write(f"[Output]\n{result.get('output','')}\n\n")
                    f.write(f"[Stderr]\n{result.get('stderr','')}\n\n")
                    f.write(f"[Flag]\n{result.get('flag','')}\n")
                result["script_path"] = script_path
                result["output_path"] = output_path
            except Exception:
                pass
        tprint(
            f"[CodeAgent] "
            f"{'OK' if result.get('success') else 'FIAL'} "
            f"flag={result.get('flag')} "
            f"tokens={result.get('tokens',0)} "
            f"output={result.get('output','')[:60].replace(chr(10),' ')}",
            CODE_COLOR,
            cid
        )
        return {
            "success": result.get("success", False),
            "flag": result.get("flag"),
            "output": result.get("output", "")[:2000],
            "stderr": result.get("stderr", "")[:500],
            "tokens": result.get("tokens", 0),
            "script_path": result.get("script_path", ""),
            "output_path": result.get("output_path", ""),
            "script_preview": result.get("script", "")[:300],
            "_code_agent_tokens": result.get("tokens", 0),
        }
    return {
        "error": f"未知工具: {name}"
    }
# ── 等待容器就绪 ──────────────────────────────────────────────
def _wait_ready(url, cid, timeout=90, interval=3):
    deadline = time.time() + timeout; attempt = 0
    tprint(f"[等待] 容器就绪中: {url}", Y, cid)
    while time.time() < deadline:
        attempt += 1
        try:
            r = _req.get(url, timeout=5, verify=False, allow_redirects=True)
            tprint(f"[等待] 就绪（第{attempt}次 → {r.status_code}）", G, cid)
            return True
        except Exception:
            tprint(f"[等待] 第{attempt}次未响应，{interval}s 后重试", GRAY, cid)
            time.sleep(interval)
    tprint(f"[等待] 超时 {timeout}s", R, cid)
    return False
def _auto_render(url: str, cid: str,
                    wait_ms: int = 2000, screenshot: bool = True) -> dict:
    """
    自动调用本地 Playwright MCP 渲染页面，保存截图和 HTML 日志。
    返回 {"html": str, "screenshot": str, "log_path": str}
    """
    import asyncio
    from config import SCAN_LOG_DIR_DEFAULT, LOG_ROOT
    scan_dir = os.path.join(LOG_ROOT, "_tool_scans")
    os.makedirs(scan_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    html      = ""
    scr_path  = ""
    log_path  = ""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx     = browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64; CTF-Agent/2.0)",
                ignore_https_errors=True
            )
            page = ctx.new_page()
            page.goto(url, timeout=15_000, wait_until="domcontentloaded")
            page.wait_for_timeout(wait_ms)
            html = page.content()
            if screenshot:
                scr_path = os.path.join(scan_dir, f"pw_{cid[:12]}_{ts}.png")
                page.screenshot(path=scr_path, full_page=True)
            browser.close()
        # 保存 HTML 日志
        log_path = os.path.join(scan_dir, f"pw_{cid[:12]}_{ts}.html")
        with open(log_path, "w", encoding="utf-8", errors="ignore") as f:
            f.write(f"<!-- URL: {url} -->\n<!-- Time: {ts} -->\n")
            f.write(html)
        tprint(f"[Playwright] 截图→{scr_path}", G, cid)
    except ImportError:
        tprint("[Playwright] 未安装，跳过动态渲染", Y, cid)
        return {}
    except Exception as e:
        tprint(f"[Playwright] 渲染失败: {e}", R, cid)
        return {}
    return {"html": html[:12000], "screenshot": scr_path, "log_path": log_path}
# ── 日志路径 ──────────────────────────────────────────────────
def _log_path(cid, provider, dt):
    folder = os.path.join(LOG_ROOT, str(cid)[:20], provider, dt.strftime("%Y%m%d"))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"session_{dt.strftime('%H%M%S')}.json")
def _challenge_log_dir(cid, provider, dt):
    """题目专属目录，用于存放脚本、HTML、截图等大文件。"""
    folder = os.path.join(LOG_ROOT, str(cid)[:20], provider,
                            dt.strftime("%Y%m%d"), "artifacts")
    os.makedirs(folder, exist_ok=True)
    return folder
# ══════════════════════════════════════════════════════════════
#  单题主循环
# ══════════════════════════════════════════════════════════════
def run(input_idx, challenge_code, challenge_title, provider,
        session_summary, color,
        stop_event=None, instance_semaphore=None):
    """
    Returns: found_flag | None
    result 特殊值：
        "level_locked" → 关卡未解锁
    """
    now        = datetime.now()
    sys_prompt = build_system_prompt()
    start_ts   = time.time()
    found_flag    = None
    kb_injected   = False
    used_skills   = set()
    instance_held = False
    # ── 提前建好日志目录 ──────────────────────────────────────
    log_path    = _log_path(challenge_code, provider, now)
    artifact_dir = _challenge_log_dir(challenge_code, provider, now)
    first_msg = (
        f"请解决以下 CTF 赛题：\n"
        f"  Code: {challenge_code}\n  标题: {challenge_title}\n\n"
        f"严格按 MCP 协议流程：\n"
        f"1. start_challenge(code='{challenge_code}') → 获取 URL\n"
        f"2. view_hint(code='{challenge_code}') → 获取提示（解题前必须调用）\n"
        f"3. 用 capture_render/http_request/run_sqlmap 渗透测试\n"
        f"4. 需要代码辅助时调用 run_code_agent(task_description=..., context=...)\n"
        f"5. submit_flag(code='{challenge_code}', flag='...')\n"
        f"6. stop_challenge(code='{challenge_code}')"
    ) if COMPETITION_MODE else (
        f"目标: {challenge_code}\n"
        f"开始渗透测试。可用工具：\n"
        f"- http_request：发送 HTTP 请求\n"
        f"- capture_render：无头浏览器渲染页面（playwright MCP）\n"
        f"- run_sqlmap：SQL 注入自动化检测（sqlmap MCP）\n"
        f"- run_code_agent：生成并执行 Python 脚本（编解码/暴力/序列化等）"
    )
    messages = init_messages(provider, first_msg, sys_prompt)
    ch_log = {
        "challenge_code":   challenge_code,
        "title":            challenge_title,
        "provider":         provider,
        "start_time":       now.isoformat(),
        "end_time":         None,
        "result":           "failed",
        "flag":             None,
        "rounds":           [],
        "total_tokens":     {"prompt":0, "completion":0, "total":0},
        "sub_agent_tokens":  0,
        "code_agent_tokens": 0,   # ← 新增
        "elapsed_seconds":  0,
        "kb_injected":      False,
        "kb_files_loaded":  [],
        "skills_loaded":    [sk["fname"] for sk in get_skills()],
        "level_locked":     False,
        "artifact_dir":     artifact_dir,   # ← 新增：大文件目录
        "mcp_calls":        [],             # ← 新增：所有 MCP 调用汇总
        "code_agent_calls": [],             # ← 新增：所有 code_agent 调用汇总
    }
    saver = _PeriodicSaver(ch_log, log_path)
    saver.start()
    if COMPETITION_MODE and MCP_SERVER_ENABLED and instance_semaphore:
        tprint(f"[实例] 等待实例位...", Y, challenge_code)
        instance_semaphore.acquire()
        instance_held = True
        tprint(f"[实例] 已获取实例位", G, challenge_code)
    tprint(f"开始  [{provider}]  {challenge_title}", color, challenge_code)
    try:
        for round_num in range(1, MAX_ROUNDS + 1):
            if stop_event and stop_event.is_set():
                tprint(f"[中断] 外部信号，退出（第{round_num}轮）", Y, challenge_code)
                ch_log["result"] = "interrupted"
                break
            elapsed = time.time() - start_ts
            if elapsed >= CHALLENGE_TIMEOUT_SECONDS:
                tprint(f"[超时] {elapsed:.0f}s 达到单题时限", R, challenge_code)
                ch_log["result"] = "timeout"
                break
            tprint(f"第{round_num}轮  [{provider}]  {elapsed:.0f}s", color, challenge_code)
            # Hint 注入
            if round_num > 1 and round_num % PAUSE_EVERY_N == 0:
                hint = _pop_hint(challenge_code)
                if hint:
                    tprint(f"[Hint] {hint}", M, challenge_code)
                    append_user_message(provider, messages, f"[Hint] {hint}")
            # 知识库注入
            if round_num == KNOWLEDGE_INJECT_ROUND and not kb_injected:
                kb_text = build_injection(
                    messages, round_num,
                    log_fn=lambda m: tprint(m, KB_COLOR, challenge_code)
                )
                if kb_text:
                    append_user_message(provider, messages, kb_text)
                    kb_injected = True
                    ch_log["kb_injected"] = True
                    for line in kb_text.split("\n"):
                        m = re.match(r'###\s*知识文件:\s*(.+)', line)
                        if m: ch_log["kb_files_loaded"].append(m.group(1).strip())
            # 上下文压缩
            messages = _compress_history(messages, challenge_code, provider, round_num)
            # 技能注入
            skill_text = inject_skill_if_needed(
                messages=messages, provider=provider,
                used_skills=used_skills, round_num=round_num,
                tprint_fn=lambda m: tprint(m, KB_COLOR, challenge_code)
            )
            if skill_text:
                append_user_message(provider, messages, skill_text)
            messages = _sanitize_messages(messages)
            # ── 调用主代理 ────────────────────────────────────
            response = call(provider, messages, sys_prompt)
            if "error" in response:
                err_msg = response["error"]
                if "Bad Request" in err_msg:
                    # 触发上下文重置逻辑（修复原有未定义的 reset_context）
                    messages = init_messages(provider, first_msg, sys_prompt)
                    continue
                break
            usage = response["usage"]
            ch_log["total_tokens"]["prompt"]     += usage["prompt_tokens"]
            ch_log["total_tokens"]["completion"] += usage["completion_tokens"]
            ch_log["total_tokens"]["total"]      += usage["total_tokens"]
            content       = response.get("content") or ""
            tool_calls    = response.get("tool_calls") or []
            mcp_tool_uses = response.get("mcp_tool_uses") or []
            mcp_results   = response.get("mcp_results") or []
            thinking      = response.get("thinking") or ""
            round_log = {
                "round":          round_num,
                "elapsed_s":      round(time.time()-start_ts, 1),
                "tokens":         dict(usage),
                "thinking":       thinking,
                "assistant":      content,
                "tool_calls":     [],
                "mcp_calls":      [],    # ← 本轮 MCP 调用
                "code_agent_calls": [],  # ← 本轮 code_agent 调用
            }
            ch_log["rounds"].append(round_log)
            if thinking: tprint(f"[思考] {thinking[:120]}...", GRAY, challenge_code)
            if content:  tprint(f"[代理] {content[:250]}", color, challenge_code)
            # ── Claude MCP 路径（platform MCP + local tools MCP）──
            if mcp_tool_uses or mcp_results:
                def _mcp_tprint(msg):
                    tprint(msg, MCP_COLOR, challenge_code)
                parsed = _parse_mcp_results(
                    mcp_tool_uses, mcp_results,
                    challenge_code, artifact_dir,
                    challenge_code, _mcp_tprint
                )
                # 将 MCP 调用记录写入 round_log 和 ch_log 汇总
                round_log["mcp_calls"] = parsed["mcp_artifacts"]
                ch_log["mcp_calls"].extend(parsed["mcp_artifacts"])
                for flag, correct, msg in parsed["submit_flag"]:
                    if correct:
                        found_flag = flag
                        ch_log["result"] = "success"
                        ch_log["flag"]   = found_flag
                        tprint(f"FLAG ✓  {found_flag}", G, challenge_code)
                    else:
                        tprint(f"FLAG ✗  {flag}", R, challenge_code)
                        ch_log["result"] = "wrong_flag"
                for _, hint_c in parsed["view_hint"]:
                    tprint(f"[提示] {hint_c[:80]}", M, challenge_code)
            # ── 自定义工具 + 非 Claude 平台工具 ──────────────
            if tool_calls:
                results = []
                for tc in tool_calls:
                    tprint(f"[工具] {tc['name']}  {list(tc['args'].keys())}", Y, challenge_code)
                    result = _dispatch(
                        tc["name"], tc["args"],
                        challenge_code, challenge_code, provider,
                        challenge_log_dir=artifact_dir   # ← 传入目录
                    )
                    # 关卡未解锁
                    if result.get("level_locked"):
                        tprint(f"[关卡] 此题关卡未解锁，立即放弃", R, challenge_code)
                        ch_log["result"]       = "level_locked"
                        ch_log["level_locked"] = True
                        round_log["tool_calls"].append({
                            "name": tc["name"], "args": tc["args"],
                            "result": {"level_locked": True}
                        })
                        results.append(result)
                        break
                    # ── code_agent token 统计 ─────────────────
                    code_tok = result.pop("_code_agent_tokens", 0)
                    if code_tok:
                        ch_log["code_agent_tokens"] += code_tok
                        # 记录到 code_agent_calls
                        ca_record = {
                            "round":       round_num,
                            "task":        tc["args"].get("task_description","")[:120],
                            "success":     result.get("success"),
                            "flag":        result.get("flag"),
                            "tokens":      code_tok,
                            "script_path": result.get("script_path",""),
                            "output_path": result.get("output_path",""),
                        }
                        round_log["code_agent_calls"].append(ca_record)
                        ch_log["code_agent_calls"].append(ca_record)
                    ch_log["sub_agent_tokens"] += result.get("sub_agent_tokens", 0)
                    round_log["tool_calls"].append({
                        "name":   tc["name"],
                        "args":   tc["args"],
                        "result": {k:v for k,v in result.items() if k != "_raw_body"}
                    })
                    time.sleep(2)
                    results.append(result)
                    # flag 检查（code_agent 直接找到）
                    if tc["name"] == "run_code_agent" and result.get("flag"):
                        tprint(f"[CodeAgent] FLAG 候选: {result['flag']}", CODE_COLOR, challenge_code)
                        # 让主 agent 继续决定是否 submit_flag
                    if tc["name"] == "submit_flag":
                        correct   = result.get("correct", False)
                        val       = result.get("validation","")
                        submitted = tc["args"].get("flag","")
                        if correct or val in ("correct","no_env"):
                            found_flag = submitted
                            ch_log["result"] = "success"
                            ch_log["flag"]   = found_flag
                            tprint(f"FLAG ✓  {found_flag}", G, challenge_code)
                        else:
                            tprint(f"FLAG ✗  {submitted}", R, challenge_code)
                            ch_log["result"] = "wrong_flag"
                append_results(provider, messages, response, tool_calls, results)
                if ch_log["result"] in ("level_locked", "success"):
                    break
            elif mcp_tool_uses:
                append_results(provider, messages, response, [], [])
                if found_flag: break
            else:
                append_retry(provider, messages, content)
    finally:
        saver.stop()
        # 释放平台实例
        if COMPETITION_MODE and MCP_SERVER_ENABLED:
            tprint(f"[清理] 释放实例资源...", Y, challenge_code)
            try:
                platform_client.stop_challenge(challenge_code)
                tprint(f"[清理] 实例已停止", G, challenge_code)
            except Exception as e:
                tprint(f"[清理] 停止异常（忽略）: {e}", GRAY, challenge_code)
            finally:
                if instance_held and instance_semaphore:
                    instance_semaphore.release()
                    tprint(f"[实例] 实例位已释放", G, challenge_code)
        # 最终日志
        ch_log["end_time"]        = datetime.now().isoformat()
        ch_log["elapsed_seconds"] = round(time.time()-start_ts, 1)
        saver.save_now()
        mlog.log_challenge_result(
            code=challenge_code, title=challenge_title,
            result=ch_log["result"], flag=found_flag,
            elapsed=ch_log["elapsed_seconds"],
            main_tokens=ch_log["total_tokens"]["total"],
            sub_tokens=ch_log["sub_agent_tokens"],
            rounds=len(ch_log["rounds"])
        )
        end_color = G if found_flag else (
            Y if ch_log["result"] in ("interrupted","level_locked") else R
        )
        kb_info = f"是({len(ch_log['kb_files_loaded'])})" if ch_log["kb_injected"] else "否"
        tprint(
            f"结束  {ch_log['result']}  flag={found_flag or '未找到'}  "
            f"主{ch_log['total_tokens']['total']}tok  "
            f"CodeAgent{ch_log['code_agent_tokens']}tok  "
            f"耗时{ch_log['elapsed_seconds']}s  知识库={kb_info}  "
            f"MCP调用={len(ch_log['mcp_calls'])}次  "
            f"脚本={len(ch_log['code_agent_calls'])}次",
            end_color, challenge_code
        )
        with _print_lock:
            session_summary.append({
                "input_idx":          input_idx,
                "challenge_id":       challenge_code,
                "title":              challenge_title,
                "provider":           provider,
                "result":             ch_log["result"],
                "flag":               found_flag,
                "level_locked":       ch_log.get("level_locked", False),
                "elapsed":            ch_log["elapsed_seconds"],
                "tokens":             ch_log["total_tokens"]["total"],
                "sub_agent_tokens":   ch_log["sub_agent_tokens"],
                "code_agent_tokens":  ch_log["code_agent_tokens"],
                "kb_injected":        ch_log["kb_injected"],
                "kb_files":           ch_log["kb_files_loaded"],
                "mcp_call_count":     len(ch_log["mcp_calls"]),
                "code_agent_count":   len(ch_log["code_agent_calls"]),
                "artifact_dir":       artifact_dir,
                "log_path":           log_path,
            })
    return found_flag