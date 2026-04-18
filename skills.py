#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skills.py — 技能库模块（按需注入，单次使用）

设计原则：
  - System Prompt 只包含基础指令，不预加载任何 skill 内容（节省 token）
  - 每轮开始前，根据当前对话内容匹配最相关的 1 个 skill
  - 匹配到的 skill 以用户消息形式注入，用完即丢，不保留在历史中
  - 每个 skill 每题最多注入 1 次（去重）

skill 文件命名规范（影响匹配优先级）：
  第一行 = 技能标签，用于关键词匹配
  例: # sql_injection xss union select 注入
"""
import os
import re
import threading

from config  import SKILLS_BASE_PATH, SKILL_MAX_CHARS, COMPETITION_MODE
from prompts import COMPETITION_SYSTEM, MAIN_AGENT_SYSTEM

_cache = None
_lock  = threading.Lock()

# ── 技能触发关键词（与 knowledge.py 对齐）──────────────────────
_SKILL_TRIGGERS = {
    "sql_injection":         ["sql", "sqli", "union", "select", "注入", "盲注",
                               "sqlmap", "报错注入", "布尔", "时间盲注"],
    "xss":                   ["xss", "script", "跨站", "dom", "reflected", "stored"],
    "idor":                  ["idor", "越权", "遍历", "uid=", "id=", "access"],
    "ssrf":                  ["ssrf", "redirect", "内网", "169.254", "metadata",
                               "fetch", "curl", "gopher"],
    "lfi_rfi":               ["lfi", "rfi", "include", "文件包含", "path", "traversal",
                               "../", "php://", "/etc/passwd"],
    "command_injection":     ["rce", "命令", "执行", "shell", "exec", "system",
                               "popen", "bash", "cmd", "whoami", "反弹"],
    "jwt":                   ["jwt", "token", "bearer", "hs256", "rs256",
                               "none", "algorithm", "签名"],
    "ssti":                  ["ssti", "template", "模板", "jinja", "twig",
                               "{{", "}}", "render", "flask"],
    "xxe":                   ["xxe", "xml", "doctype", "entity", "外部实体"],
    "deserialization":       ["序列化", "unserialize", "pickle", "ysoserial",
                               "phpggc", "java", "反序列化"],
    "file_upload":           ["上传", "upload", "webshell", "mime", "multipart",
                               "filename", "extension", ".php"],
    "authentication_bypass": ["登录", "login", "bypass", "admin", "弱口令",
                               "默认密码", "认证", "session", "cookie"],
    "prototype_pollution":   ["prototype", "__proto__", "constructor", "污染"],
    "nosql":                 ["nosql", "mongodb", "mongoose", "$where", "$gt",
                               "$regex", "注入"],
    "graphql":               ["graphql", "introspection", "query", "mutation"],
}


# ── 扫描技能文件（懒加载）─────────────────────────────────────

def _scan() -> list:
    skills = []
    if not os.path.isdir(SKILLS_BASE_PATH):
        return skills
    for root, _, files in os.walk(SKILLS_BASE_PATH):
        for fname in sorted(files):
            if not fname.lower().endswith((".txt", ".md")):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    raw = f.read(SKILL_MAX_CHARS)
            except Exception:
                continue
            lines = raw.strip().splitlines()
            if not lines:
                continue
            tag_line = lines[0].strip().lower()
            # 从标签行推断该技能覆盖的漏洞类型
            vuln_keys = set()
            for vk, patterns in _SKILL_TRIGGERS.items():
                if any(p in tag_line for p in patterns):
                    vuln_keys.add(vk)
            skills.append({
                "fname":     fname,
                "path":      fpath,
                "title":     lines[0].strip(),
                "content":   raw.strip(),
                "vuln_keys": vuln_keys,
            })
    return skills


def get_skills() -> list:
    """返回所有技能元信息（不含 content，仅用于启动横幅展示）"""
    global _cache
    with _lock:
        if _cache is None:
            _cache = _scan()
        return _cache


# ── System Prompt（不含 skill，保持精简）─────────────────────

def build_system_prompt() -> str:
    """
    返回精简版 System Prompt，不预加载任何 skill 内容。
    skill 内容通过 inject_skill_if_needed() 按需注入到对话中。
    """
    return COMPETITION_SYSTEM if COMPETITION_MODE else MAIN_AGENT_SYSTEM


# ── 按需注入：从对话中匹配最相关 skill ───────────────────────

def _extract_context_text(messages: list) -> str:
    """从消息历史中提取文本，用于关键词匹配"""
    parts = []
    for msg in messages[-6:]:   # 只看最近 6 条，避免过远的上下文干扰
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for b in content:
                if isinstance(b, dict):
                    parts.append(b.get("text","") or b.get("content",""))
    return " ".join(parts).lower()


def _score_skill(skill: dict, context: str) -> int:
    """计算 skill 与当前对话的相关性得分"""
    score = 0
    for vk in skill["vuln_keys"]:
        patterns = _SKILL_TRIGGERS.get(vk, [])
        for pat in patterns:
            if pat in context:
                score += 1
    return score


def inject_skill_if_needed(
    messages: list,
    provider: str,
    used_skills: set,
    round_num: int,
    tprint_fn=None
) -> str | None:
    """
    检查当前对话是否需要注入技能。

    Args:
        messages:    当前对话历史
        provider:    当前 provider（用于格式化消息）
        used_skills: 本题已注入过的 skill fname 集合（防重复）
        round_num:   当前轮次
        tprint_fn:   可选日志函数

    Returns:
        注入的技能内容字符串（已追加到 messages），或 None
    """
    if round_num < 15:
        return None   # 第 不注入

    skills = get_skills()
    if not skills:
        return None

    context = _extract_context_text(messages)
    if not context.strip():
        return None

    # 找出未使用且得分最高的 skill
    best_skill  = None
    best_score  = 0
    for sk in skills:
        if sk["fname"] in used_skills:
            continue
        score = _score_skill(sk, context)
        if score > best_score:
            best_score = score
            best_skill = sk

    if best_skill is None or best_score == 0:
        return None

    used_skills.add(best_skill["fname"])

    inject_text = (
        f"[技能库注入 — 第{round_num}轮 | 匹配得分:{best_score}]\n"
        f"技能: {best_skill['title']}\n\n"
        f"{best_skill['content']}\n\n"
        f"请参考以上技能内容，调整本轮攻击策略。"
    )

    if tprint_fn:
        tprint_fn(f"[技能] 注入: {best_skill['fname']} (score={best_score})")

    return inject_text


def build_system_prompt_with_skills() -> str:
    """向后兼容接口，等同于 build_system_prompt()"""
    return build_system_prompt()