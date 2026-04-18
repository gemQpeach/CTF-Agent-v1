#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
code_agent.py — Python 脚本编写子代理 GLM 

职责：
  接收渗透测试中遇到的需要代码解决的问题（编码/解码、暴力遍历、
  哈希破解、JWT 伪造、序列化构造等），输出可直接运行的 Python 脚本。

调用方式：
  result = write_and_run(task_description, context="")
  → 返回 {"script": str, "output": str, "success": bool, "error": str}

特点：
  - GLM 模型：擅长代码生成，成本低
  - 沙箱执行：脚本在子进程中运行，超时 30s 自动终止
  - 结果回注：执行输出自动返回给主代理
"""
import json
import subprocess
import tempfile
import os
import requests

from config import GLM_API_KEY, GLM_BASE_URL, GLM_MODEL

# ── 代码生成专用 Prompt ────────────────────────────────────────
_CODE_AGENT_SYSTEM = """你是一名专业 CTF 渗透测试的 Python 脚本工程师。
你的唯一任务是编写高质量、可直接运行的 Python 脚本来解决具体问题。

擅长领域：
- Base64 / URL / HTML / Hex / ROT13 / Unicode 等各种编解码
- JWT token 解析、伪造（HS256 弱密钥爆破、none 算法绕过）
- 暴力遍历（用户 ID、文件名、路径、参数值）
- 哈希计算与破解（MD5/SHA1/SHA256 + 字典攻击）
- SQL 注入 payload 生成（盲注自动化、UNION 列数探测）
- Cookie/Session 序列化对象构造与反序列化
- 自动化 HTTP 请求序列（登录→操作→提取）
- 正则提取、HTML 解析、JSON 深度遍历

输出规范（严格遵守）：
1. 只输出 Python 代码，不要任何解释文字
2. 代码必须是完整可运行的脚本
3. 用 print() 输出所有关键结果（包括找到的 flag）
4. 目标 URL 等变量写在脚本开头便于修改
5. 包含必要的错误处理
6. 不得使用需要安装的非标准库（requests 除外）
7. 脚本最后必须有 if __name__ == "__main__": main() 结构
"""

# ── 代码模板 ────────────────────────
_TASK_HINTS = {
    "base64":    "使用 import base64，注意 padding",
    "jwt":       "使用 import base64, hmac, hashlib，手动处理 header.payload.signature",
    "idor":      "使用 requests.Session() 保持 cookie，循环遍历 id 参数",
    "hash":      "使用 hashlib，对字典文件逐行计算并比对",
    "sql_blind": "使用 requests + 二分查找，通过响应长度或时间判断",
    "traverse":  "使用 requests.Session()，维护认证状态，遍历路径列表",
}


def _detect_task_type(description: str) -> str:
    desc = description.lower()
    if any(k in desc for k in ["base64", "编码", "解码", "encode", "decode"]):
        return "base64"
    if any(k in desc for k in ["jwt", "token", "bearer"]):
        return "jwt"
    if any(k in desc for k in ["idor", "遍历", "id=", "userid", "用户id"]):
        return "idor"
    if any(k in desc for k in ["hash", "md5", "sha", "哈希", "密码"]):
        return "hash"
    if any(k in desc for k in ["盲注", "blind", "boolean", "time-based"]):
        return "sql_blind"
    return "traverse"


def generate_script(task_description: str, context: str = "") -> tuple:
    """
    调用 GLM 生成解题 Python 脚本。
    返回 (script: str, tokens: int)
    """
    task_type = _detect_task_type(task_description)
    hint      = _TASK_HINTS.get(task_type, "")

    user_msg = f"""任务描述：
{task_description}

{"上下文信息（已发现的关键数据）：" + chr(10) + context if context else ""}

{"提示：" + hint if hint else ""}

请直接输出完整 Python 脚本，不要任何解释："""

    headers = {
        "Authorization": f"Bearer {GLM_API_KEY}",
        "Content-Type":  "application/json"
    }
    body = {
        "model":       GLM_MODEL,
        "messages":    [
            {"role": "system",  "content": _CODE_AGENT_SYSTEM},
            {"role": "user",    "content": user_msg}
        ],
        "temperature": 0.2,   # 低：代码生成要确定性
        "max_tokens":  4096,
    }

    try:
        resp = requests.post(GLM_BASE_URL, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        data    = resp.json()
        script  = data["choices"][0]["message"].get("content", "")
        tokens  = data.get("usage", {}).get("total_tokens", 0)
        # 清理 markdown 代码块包装
        script  = _clean_script(script)
        return script, tokens
    except Exception as exc:
        return f"# 代码生成失败: {exc}", 0


def _clean_script(raw: str) -> str:
    """去除 GLM 可能输出的 ```python ... ``` 包装"""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        # 去掉首行 ```python 和末行 ```
        start = 1
        end   = len(lines)
        if lines[-1].strip() == "```":
            end = len(lines) - 1
        raw = "\n".join(lines[start:end])
    return raw.strip()


def run_script(script: str, timeout: int = 30) -> dict:
    """
    在沙箱子进程中执行脚本，返回执行结果。
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False # 创建临时 Python 脚本文件用于沙箱执行
    ) as f:
        f.write(script)
        tmp_path = f.name

    try:
        proc = subprocess.run(
            ["python3", tmp_path],
            capture_output=True, text=True,
            timeout=timeout, errors="replace"
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # 尝试从输出中提取 flag
        import re
        flag_match = re.search(r'flag\{[^}]+\}', stdout, re.IGNORECASE)
        flag = flag_match.group(0) if flag_match else None

        return {
            "success":   proc.returncode == 0,
            "output":    stdout[:3000] if stdout else "",
            "stderr":    stderr[:500]  if stderr else "",
            "flag":      flag,
            "exit_code": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "stderr": f"执行超时（>{timeout}s）",
                "flag": None, "exit_code": -1}
    except Exception as exc:
        return {"success": False, "output": "", "stderr": str(exc),
                "flag": None, "exit_code": -1}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def write_and_run(task_description: str, context: str = "",
                  max_retries: int = 2) -> dict:
    """
    Returns:
        {
          "script":  最终脚本代码,
          "output":  执行输出,
          "flag":    提取到的 flag（或 None）,
          "success": bool,
          "tokens":  消耗的 token 数,
          "error":   错误信息（如有）,
        }
    """
    total_tokens = 0
    last_result  = {}
    script       = ""

    for attempt in range(1, max_retries + 1):
        # 第二次尝试时，将上次的错误信息反馈给模型
        desc = task_description
        if attempt > 1 and last_result.get("stderr"):
            desc += (
                f"\n\n上次脚本执行失败，错误信息：\n{last_result['stderr'][:300]}\n"
                f"上次脚本输出：\n{last_result.get('output','(无)')[:200]}\n"
                f"请修复错误并重新生成完整脚本。"
            )

        script, tokens = generate_script(desc, context)
        total_tokens  += tokens

        if not script or script.startswith("# 代码生成失败"):
            last_result = {"success": False, "output": "", "stderr": script,
                           "flag": None, "exit_code": -1}
            continue

        result      = run_script(script)
        last_result = result

        if result["success"] or result.get("flag"):
            break

    return {
        "script":  script,
        "output":  last_result.get("output", ""),
        "flag":    last_result.get("flag"),
        "success": last_result.get("success", False),
        "stderr":  last_result.get("stderr", ""),
        "tokens":  total_tokens,
    }