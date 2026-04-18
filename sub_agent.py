#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sub_agent.py — HTTP 响应分析子代理（CTF 强化版）

改进点：
  1. needs_render() 更精准：多维度打分代替简单阈值
  2. analyze_response() 提取结构化 CTF 线索
  3. 新增 analyze_sqlmap_result() 供 session.py 调用
  4. 支持 deepseek / minimax / glm 后端
"""

import json
import re
import requests
import time

from config import (
    SUB_AGENT_BACKEND, SUB_AGENT_MODEL,
    SUB_AGENT_BODY_LIMIT, SUB_AGENT_SUMMARY_LIMIT,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    MINIMAX_API_KEY,  MINIMAX_BASE_URL,
    GLM_API_KEY,      GLM_BASE_URL,
)
from prompts import SUB_AGENT_SYSTEM

# ─────────────────────────────────────────────────────────────
# 后端路由
# ─────────────────────────────────────────────────────────────
_BACKENDS = {
    "deepseek": {"api_key": lambda: DEEPSEEK_API_KEY, "base_url": lambda: DEEPSEEK_BASE_URL},
    "minimax":  {"api_key": lambda: MINIMAX_API_KEY,  "base_url": lambda: MINIMAX_BASE_URL},
    "glm":      {"api_key": lambda: GLM_API_KEY,      "base_url": lambda: GLM_BASE_URL},
}

# ─────────────────────────────────────────────────────────────
# SPA / 动态渲染特征（带权重）
# ─────────────────────────────────────────────────────────────
_RENDER_SIGNALS: list[tuple[str, int]] = [
    # 强信号（2分）
    ('<div id="app"',        2),
    ('<div id="root"',       2),
    ("ng-app",               2),
    ("data-reactroot",       2),
    ("__NUXT__",             2),
    ("__NEXT_DATA__",        2),
    ("React.createElement",  2),
    ("document.getElementById(\"app\")", 2),
    # 中信号（1分）
    ("window.__",            1),
    ("</script>\n</body>",   1),
    ("vue.js",               1),
    ("angular.js",           1),
    ("require.js",           1),
    ("webpack",              1),
    ("<noscript>",           1),
    # 空壳信号（2分）
    ("<body></body>",        2),
    ("<body>\n</body>",      2),
    ("<body>\r\n</body>",    2),
]

# 极短页面 / 空页面（几乎肯定需要渲染）
_SHORT_THRESHOLD  = 400     # 字节数低于此值 → 直接渲染
_SCORE_THRESHOLD  = 3       # 加权得分 ≥ 此值 → 需要渲染


def needs_render(html_body: str) -> bool:
    """
    判断页面是否需要 Playwright 动态渲染。

    策略：
    1. body 极短（< 400 字符）→ True
    2. 有效内容极少（<body> 内可见文字 < 50 字）→ True
    3. SPA/动态框架特征加权得分 ≥ 3 → True
    4. 否则 → False
    """
    if not html_body:
        return False

    # 规则 1：页面体积极小
    if len(html_body) < _SHORT_THRESHOLD:
        return True

    body_lower = html_body.lower()

    # 规则 2：<body> 内有效文字极少（排除标签后）
    body_tag_content = re.sub(r"<[^>]+>", " ", html_body)
    visible_text     = re.sub(r"\s+", " ", body_tag_content).strip()
    if len(visible_text) < 50:
        return True

    # 规则 3：SPA 特征加权打分
    score = 0
    for pattern, weight in _RENDER_SIGNALS:
        if pattern.lower() in body_lower:
            score += weight
            if score >= _SCORE_THRESHOLD:
                return True

    return False


# ─────────────────────────────────────────────────────────────
# Flag 正则（同 tools_server.py，保持一致）
# ─────────────────────────────────────────────────────────────
_FLAG_PATTERNS = [
    re.compile(r"flag\{[^}]{1,128}\}", re.IGNORECASE),
    re.compile(r"ctf\{[^}]{1,128}\}",  re.IGNORECASE),
    re.compile(r"NSSCTF\{[^}]{1,128}\}", re.IGNORECASE),
    re.compile(r"[A-Z0-9_]{2,10}\{[^}]{8,128}\}"),
]

def _hunt_flags(text: str) -> list[str]:
    found = []
    for pat in _FLAG_PATTERNS:
        found.extend(pat.findall(text))
    return list(dict.fromkeys(found))


# ─────────────────────────────────────────────────────────────
# CTF 线索预提取（减轻 LLM 压力）
# ─────────────────────────────────────────────────────────────
def _extract_ctf_hints(body: str, headers: dict, cookies: dict) -> dict:
    """
    在调用 LLM 之前预先提取高价值 CTF 线索。
    返回结构化 hints dict，直接拼入 LLM 提示词。
    """
    hints = {
        "flags_found":    _hunt_flags(body),
        "html_comments":  [],
        "hidden_inputs":  [],
        "suspicious_headers": {},
        "jwt_tokens":     [],
        "base64_candidates": [],
        "error_messages": [],
        "interesting_paths": [],
    }

    # HTML 注释
    hints["html_comments"] = re.findall(r"<!--(.*?)-->", body, re.DOTALL)[:10]
    hints["html_comments"] = [c.strip() for c in hints["html_comments"] if c.strip()]

    # 隐藏表单字段
    hints["hidden_inputs"] = [
        {"name": m.group(1), "value": m.group(2)}
        for m in re.finditer(
            r'<input[^>]+type=["\']hidden["\'][^>]+name=["\']([^"\']+)["\'][^>]+value=["\']([^"\']*)["\']',
            body, re.IGNORECASE
        )
    ][:10]

    # 可疑响应头（Server/X-Powered-By/Debug 类）
    suspicious_hdr_keys = ["server", "x-powered-by", "x-debug", "x-flag",
                            "x-secret", "x-token", "x-admin", "set-cookie"]
    for k, v in headers.items():
        if any(s in k.lower() for s in suspicious_hdr_keys):
            hints["suspicious_headers"][k] = v

    # Cookie 中的可疑字段
    for k, v in cookies.items():
        if any(s in k.lower() for s in ["admin", "role", "token", "flag", "secret"]):
            hints["suspicious_headers"][f"[Cookie] {k}"] = v

    # JWT Token（Header.Payload.Signature 格式）
    hints["jwt_tokens"] = re.findall(
        r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", body
    )[:5]

    # Base64 候选（长度 ≥ 20，且不像普通 CSS/JS 路径）
    b64_candidates = re.findall(r"[A-Za-z0-9+/]{20,}={0,2}", body)
    hints["base64_candidates"] = [
        c for c in b64_candidates
        if len(c) % 4 == 0 and len(c) < 200
    ][:8]

    # 错误信息（常含路径泄露/技术栈信息）
    error_patterns = [
        r"(Warning|Error|Exception|Traceback|Fatal)[:\s].{10,200}",
        r"(mysql|sqlite|postgresql|oracle)[^<]{0,100}error[^<]{0,100}",
        r"(syntax error|undefined variable|undefined index)[^<]{0,100}",
        r"(php|python|java|ruby)[^<]{0,50}(error|exception)[^<]{0,100}",
    ]
    for pat in error_patterns:
        hints["error_messages"].extend(
            re.findall(pat, body, re.IGNORECASE)[:3]
        )
    hints["error_messages"] = hints["error_messages"][:10]

    # 有趣路径/接口
    hints["interesting_paths"] = list(set(re.findall(
        r'(?:href|src|action|url)[=:\s]+["\']?(/[a-zA-Z0-9_/.-]+)["\']?',
        body, re.IGNORECASE
    )))[:20]

    return hints


# ─────────────────────────────────────────────────────────────
# 主分析函数
# ─────────────────────────────────────────────────────────────
def _call_sub_agent(system: str, user_content: str) -> tuple[str, int]:
    """调用子代理 LLM，返回 (summary, tokens)。"""
    cfg = _BACKENDS.get(SUB_AGENT_BACKEND, _BACKENDS["deepseek"])
    headers_req = {
        "Authorization": f"Bearer {cfg['api_key']()}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":       SUB_AGENT_MODEL,
        "messages":    [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens":  2048,
    }
    try:
        resp = requests.post(
            cfg["base_url"](), headers=headers_req, json=payload, timeout=30
        )
        time.sleep(2)
        resp.raise_for_status()
        data    = resp.json()
        summary = data["choices"][0]["message"].get("content", "")
        tokens  = data.get("usage", {}).get("total_tokens", 0)
        return summary[:SUB_AGENT_SUMMARY_LIMIT], tokens
    except Exception as exc:
        return f"[子代理({SUB_AGENT_BACKEND})失败: {str(exc)[:120]}]", 0


def analyze_response(request_info: dict, response_data: dict) -> tuple[str, int]:
    """
    分析 HTTP 响应，提取 CTF 渗透测试关键信息。
    返回 (summary: str, tokens: int)
    """
    body        = response_data.get("body", "")
    headers     = response_data.get("headers", {})
    cookies     = response_data.get("cookies", {})
    status      = response_data.get("status_code", "")
    final_url   = response_data.get("final_url", "")
    truncated   = len(body) > SUB_AGENT_BODY_LIMIT
    body_excerpt= body[:SUB_AGENT_BODY_LIMIT]

    # 预提取线索（减少 LLM token 消耗）
    hints = _extract_ctf_hints(body, headers, cookies)

    # 如果已经直接找到 Flag，直接返回，不调用 LLM
    if hints["flags_found"]:
        summary = (
            f"🚩 直接发现 Flag：{hints['flags_found']}\n"
            f"状态码: {status}  最终URL: {final_url}\n"
        )
        return summary[:SUB_AGENT_SUMMARY_LIMIT], 0

    hints_text = json.dumps(hints, ensure_ascii=False, indent=2)

    user_content = (
        "请分析以下 HTTP 响应，提取 CTF 渗透测试关键信息并给出下一步建议：\n\n"
        "【请求信息】\n"
        f"  方法: {request_info.get('method','GET')}\n"
        f"  URL:  {request_info.get('url','')}\n"
        f"  最终URL: {final_url}\n\n"
        "【响应信息】\n"
        f"  状态码: {status}\n"
        f"  响应头:\n{json.dumps(headers, ensure_ascii=False, indent=2)[:600]}\n"
        f"  Cookies: {json.dumps(cookies, ensure_ascii=False)[:300]}\n\n"
        "【自动提取的 CTF 线索】\n"
        f"{hints_text[:1500]}\n\n"
        f"【响应体{'（已截断，原始长度 ' + str(len(body)) + ' 字符）' if truncated else ''}】\n"
        f"{body_excerpt}"
    )

    return _call_sub_agent(SUB_AGENT_SYSTEM, user_content)


# ─────────────────────────────────────────────────────────────
# SQLMap 结果分析
# ─────────────────────────────────────────────────────────────
_SQLMAP_ANALYSIS_SYSTEM = """你是一名 CTF Web 安全专家，专注于 SQL 注入分析。
请对 sqlmap 扫描结果进行简洁分析：
1. 是否存在注入点（参数名/类型/Payload）
2. 数据库类型和版本
3. 发现的数据库/表/字段
4. 是否包含 Flag 或敏感数据
5. 下一步建议（dump 哪个表？使用哪种技术？）
输出格式：简洁的中文分析，重点突出，不超过 600 字。"""


def analyze_sqlmap_result(sqlmap_result: dict) -> tuple[str, int]:
    """
    分析 sqlmap MCP 工具的返回结果。
    返回 (summary: str, tokens: int)
    """
    # 直接发现 Flag
    if sqlmap_result.get("flags"):
        summary = (
            f"🚩 SQLMap 发现 Flag：{sqlmap_result['flags']}\n"
            f"数据库: {sqlmap_result.get('dbms','')}  "
            f"注入点: {len(sqlmap_result.get('injection_points',[]))} 个\n"
        )
        return summary, 0

    if not sqlmap_result.get("injectable"):
        return "SQLMap 未发现注入点。建议检查参数覆盖度或提升 level/risk。", 0

    user_content = (
        "请分析以下 sqlmap 扫描结果：\n\n"
        f"注入点: {json.dumps(sqlmap_result.get('injection_points',[]), ensure_ascii=False)}\n"
        f"DBMS: {sqlmap_result.get('dbms','')}\n"
        f"数据库列表: {sqlmap_result.get('db_names',[])}\n"
        f"表列表: {sqlmap_result.get('tables',[])[:20]}\n"
        f"数据样本: {sqlmap_result.get('data_dump',[])[:10]}\n\n"
        f"原始输出（前 2000 字符）:\n{sqlmap_result.get('output','')[:2000]}"
    )

    return _call_sub_agent(_SQLMAP_ANALYSIS_SYSTEM, user_content)


# ─────────────────────────────────────────────────────────────
# Playwright DOM 摘要分析
# ─────────────────────────────────────────────────────────────
_DOM_ANALYSIS_SYSTEM = """你是一名 CTF Web 安全专家。
请对浏览器渲染后的页面 DOM 摘要进行分析：
1. 页面功能和登录/交互点
2. 隐藏字段/注释中的线索
3. 可疑的 JS 全局变量/本地存储
4. 漏洞假设（SQL注入/XSS/越权/序列化等）
5. 具体的下一步操作建议（填写哪些字段/点击哪个按钮/发送哪个请求）
格式：简洁中文，重点突出，不超过 500 字。"""


def analyze_dom_summary(dom_summary: dict, url: str = "") -> tuple[str, int]:
    """
    分析 capture_render 返回的 DOM 摘要。
    返回 (summary: str, tokens: int)
    """
    # 先检查 Flag
    dom_text = json.dumps(dom_summary, ensure_ascii=False)
    flags    = []
    for pat in _FLAG_PATTERNS:
        flags.extend(pat.findall(dom_text))

    if flags:
        return f"🚩 DOM 中发现 Flag：{list(dict.fromkeys(flags))}", 0

    user_content = (
        f"URL: {url}\n\n"
        f"DOM 摘要:\n{json.dumps(dom_summary, ensure_ascii=False, indent=2)[:3000]}"
    )

    return _call_sub_agent(_DOM_ANALYSIS_SYSTEM, user_content)