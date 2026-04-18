#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
master_log.py — 总日志模块
以 JSON Lines 格式记录完整会话生命周期：
  获取题目 → 启动实例 → 解题过程 → 提交 Flag → 停止实例 → 汇总
"""
import os
import json
import threading
from datetime import datetime
from config import LOG_ROOT

_lock     = threading.Lock()
_log_file = None   # 全局日志文件路径


# ─────────────────────────────────────────────────────────────
#  初始化
# ─────────────────────────────────────────────────────────────

def init(provider: str) -> str:
    """
    创建本次运行的总日志文件。
    返回日志文件路径。
    """
    global _log_file
    folder = os.path.join(LOG_ROOT, "_master")
    os.makedirs(folder, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    _log_file = os.path.join(folder, f"master_{ts}.jsonl")
    _write("session_start", {"provider": provider, "log_file": _log_file})
    return _log_file


def _write(event: str, data: dict = None):
    """写入一条 JSON Lines 事件记录"""
    if not _log_file:
        return
    entry = {
        "event":     event,
        "timestamp": datetime.now().isoformat(),
    }
    if data:
        entry.update(data)
    with _lock:
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ─────────────────────────────────────────────────────────────
#  事件接口
# ─────────────────────────────────────────────────────────────

def log_challenges_fetched(challenges: list, level, attempt: int = 1):
    """记录题目列表获取结果"""
    _write("challenges_fetched", {
        "attempt":   attempt,
        "level":     level,
        "total":     len(challenges),
        "challenges": [
            {
                "code":       ch.get("code"),
                "title":      ch.get("title"),
                "difficulty": ch.get("difficulty"),
                "score":      ch.get("total_score"),
                "solved":     ch.get("flag_got_count", 0) >= ch.get("flag_count", 1),
            }
            for ch in challenges
        ]
    })


def log_unsolved_list(unsolved: list):
    """记录当前未解出的题目列表（每个攻击槽开始前调用）"""
    _write("unsolved_list", {
        "count":    len(unsolved),
        "codes":    [c[0] for c in unsolved],
        "titles":   [c[1] for c in unsolved],
    })


def log_slot_start(slot_idx: int, provider: str, pending: int, deadline_str: str):
    """记录时间槽开始"""
    _write("slot_start", {
        "slot":        slot_idx + 1,
        "provider":    provider,
        "pending":     pending,
        "deadline":    deadline_str,
    })


def log_slot_end(slot_idx: int, provider: str, new_solved: int, total_solved: int):
    """记录时间槽结束"""
    _write("slot_end", {
        "slot":         slot_idx + 1,
        "provider":     provider,
        "new_solved":   new_solved,
        "total_solved": total_solved,
    })


def log_instance_start(code: str, title: str, url: str):
    """记录题目实例启动"""
    _write("instance_start", {"code": code, "title": title, "url": url})


def log_instance_stop(code: str, reason: str = "completed"):
    """记录题目实例停止"""
    _write("instance_stop", {"code": code, "reason": reason})


def log_flag_submit(code: str, flag: str, correct: bool, message: str = ""):
    """记录 Flag 提交"""
    _write("flag_submit", {
        "code":    code,
        "flag":    flag,
        "correct": correct,
        "message": message,
    })


def log_challenge_result(code: str, title: str, result: str,
                         flag: str, elapsed: float,
                         main_tokens: int, sub_tokens: int,
                         rounds: int):
    """记录单题最终结果"""
    _write("challenge_result", {
        "code":        code,
        "title":       title,
        "result":      result,
        "flag":        flag,
        "elapsed_s":   elapsed,
        "main_tokens": main_tokens,
        "sub_tokens":  sub_tokens,
        "rounds":      rounds,
    })


def log_challenges_refresh(new_challenges: list, reason: str = "slot_end"):
    """记录题目列表刷新（如升级解锁新关卡）"""
    _write("challenges_refresh", {
        "reason":          reason,
        "new_count":       len(new_challenges),
        "new_titles":      [c[1] for c in new_challenges],
    })


def log_session_end(total_solved: int, total_challenges: int,
                    elapsed_s: float, main_tokens: int, sub_tokens: int):
    """记录会话结束汇总"""
    _write("session_end", {
        "total_solved":     total_solved,
        "total_challenges": total_challenges,
        "elapsed_s":        elapsed_s,
        "main_tokens":      main_tokens,
        "sub_tokens":       sub_tokens,
    })