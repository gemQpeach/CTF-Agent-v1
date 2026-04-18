#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
knowledge.py — 知识库模块
在第 KNOWLEDGE_INJECT_ROUND 轮自动根据对话中识别到的漏洞类型，
加载匹配的知识文件并注入到对话上下文。
"""
import os
import re

from config  import (KNOWLEDGE_BASE_PATH, KNOWLEDGE_INJECT_ROUND,
                     KNOWLEDGE_MAX_CHARS, KNOWLEDGE_MAX_FILES)
from prompts import KNOWLEDGE_INJECTION_TEMPLATE


# ─────────────────────────────────────────────────────────────
#  漏洞关键词分组
#  键：规范漏洞类型名；值：匹配模式列表（全小写）
# ─────────────────────────────────────────────────────────────
VULN_KEYWORD_GROUPS = {
    "sql_injection": [
        "sql injection", "sqli", "sql注入", "union select",
        "blind sql", "boolean sql", "error-based sql",
        "time-based sql", "sqlmap"
    ],
    "xss": [
        "xss", "cross-site scripting", "跨站脚本",
        "reflected xss", "stored xss", "dom xss"
    ],
    "idor": [
        "idor", "insecure direct object", "越权", "水平越权",
        "垂直越权", "privilege escalation", "access control"
    ],
    "ssrf": [
        "ssrf", "server-side request forgery", "服务端请求伪造",
        "internal network", "metadata service"
    ],
    "lfi_rfi": [
        "lfi", "rfi", "local file inclusion", "remote file inclusion",
        "文件包含", "path traversal", "目录遍历", "directory traversal",
        "../", "php://"
    ],
    "command_injection": [
        "command injection", "命令注入", "rce",
        "remote code execution", "os command", "shell injection",
        "exec(", "system(", "popen("
    ],
    "jwt": [
        "jwt", "json web token", "algorithm confusion",
        "none algorithm", "hs256", "rs256", "jwt forging"
    ],
    "ssti": [
        "ssti", "server-side template injection", "模板注入",
        "jinja2", "twig", "freemarker", "velocity", "{{", "}}"
    ],
    "xxe": [
        "xxe", "xml external entity", "xml注入",
        "doctype", "entity injection"
    ],
    "deserialization": [
        "deserialization", "反序列化", "pickle",
        "java deserialization", "ysoserial", "phpggc", "unserialize"
    ],
    "authentication_bypass": [
        "authentication bypass", "认证绕过", "login bypass",
        "default credentials", "weak password", "admin bypass",
        "session fixation", "session hijacking"
    ],
    "race_condition": [
        "race condition", "竞争条件", "toctou",
        "time of check", "concurrent request"
    ],
    "csrf":           ["csrf", "cross-site request forgery", "跨站请求伪造"],
    "file_upload": [
        "file upload", "文件上传", "webshell", "malicious upload",
        "mime bypass", "extension bypass"
    ],
    "prototype_pollution": [
        "prototype pollution", "原型链污染",
        "__proto__", "constructor.prototype"
    ],
    "graphql":  ["graphql", "introspection", "graphql injection"],
    "nosql": [
        "nosql injection", "nosql注入", "mongodb injection",
        "$where", "$gt", "$regex"
    ],
}


# ─────────────────────────────────────────────────────────────
#  内部工具函数
# ─────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower().strip())


def extract_vuln_types(text: str) -> set:
    """从文本中识别漏洞类型，返回匹配到的规范键集合"""
    norm    = _normalize(text)
    matched = set()
    for vuln_key, patterns in VULN_KEYWORD_GROUPS.items():
        if any(pat in norm for pat in patterns):
            matched.add(vuln_key)
    return matched


def _scan_kb() -> list:
    """
    扫描知识库目录。
    返回 [{"path", "first_line", "vuln_keys"}, ...]
    """
    entries = []
    if not os.path.isdir(KNOWLEDGE_BASE_PATH):
        return entries

    for root, _, files in os.walk(KNOWLEDGE_BASE_PATH):
        for fname in sorted(files):
            if not fname.lower().endswith(".txt"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    first_line = f.readline().strip()
            except Exception:
                continue
            if not first_line:
                continue
            entries.append({
                "path":       fpath,
                "first_line": first_line,
                "vuln_keys":  extract_vuln_types(first_line)
            })
    return entries


def _load_file(fpath: str) -> str:
    try:
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(KNOWLEDGE_MAX_CHARS)
        if os.path.getsize(fpath) > KNOWLEDGE_MAX_CHARS:
            content += "\n... [内容已截断]"
        return content
    except Exception as exc:
        return f"[读取失败: {exc}]"


def _collect_conv_text(messages: list) -> str:
    """从消息历史中提取所有文本（兼容字符串和 Claude 内容块格式）"""
    parts = []
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    parts.append(block.get("text", ""))
                    inner = block.get("content", "")
                    if isinstance(inner, str):
                        parts.append(inner)
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────
#  公共接口
# ─────────────────────────────────────────────────────────────

def build_injection(messages: list, round_num: int, log_fn=None) -> str | None:
    """
    构建知识库注入消息。

    Args:
        messages:  当前对话历史
        round_num: 当前轮次（用于注入消息模板）
        log_fn:    可选日志回调 fn(msg: str)

    Returns:
        注入文本字符串，或 None（无匹配）
    """
    def _log(msg):
        if log_fn:
            log_fn(msg)

    conv_text      = _collect_conv_text(messages)
    detected_vulns = extract_vuln_types(conv_text)
    _log(f"[知识库] 识别漏洞类型: {detected_vulns or '未识别（加载全部）'}")

    entries = _scan_kb()
    if not entries:
        _log(f"[知识库] 目录为空或不存在: {KNOWLEDGE_BASE_PATH}")
        return None

    # 匹配策略：精准 → 模糊回退 → 全部
    if detected_vulns:
        matched = [e for e in entries if e["vuln_keys"] & detected_vulns]
        if not matched:
            # 模糊回退：用对话中 4 字以上词匹配文件标签行
            norm_conv = _normalize(conv_text)
            matched = [
                e for e in entries
                if any(kw in _normalize(e["first_line"])
                       for kw in norm_conv.split() if len(kw) > 3)
            ]
    else:
        matched = entries

    if not matched:
        _log("[知识库] 未找到匹配文件")
        return None

    matched = matched[:KNOWLEDGE_MAX_FILES]

    sections = []
    for entry in matched:
        rel = os.path.relpath(entry["path"], KNOWLEDGE_BASE_PATH)
        _log(f"[知识库] 加载: {rel}  ({entry['first_line'][:60]})")
        content = _load_file(entry["path"])
        sections.append(
            f"### 知识文件: {rel}\n"
            f"**主题:** {entry['first_line']}\n\n"
            f"{content}"
        )

    text = KNOWLEDGE_INJECTION_TEMPLATE.format(
        round      = round_num,
        vuln_types = "、".join(detected_vulns) if detected_vulns else "通用",
        count      = len(sections),
        sections   = "\n\n---\n\n".join(sections)
    )

    _log(f"[知识库] 已注入 {len(sections)} 个文件")
    return text


def list_kb_files() -> list:
    """返回知识库文件摘要列表（用于启动时预检）"""
    return _scan_kb()