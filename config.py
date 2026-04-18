#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""config.py — 全局配置"""
import os
import time

# ── DeepSeek ──────────────────────────────────────────────────
DEEPSEEK_API_KEY   = os.environ.get("DEEPSEEK_API_KEY",   "sk-xxx")
DEEPSEEK_BASE_URL  = "http://xxx"
DEEPSEEK_MODEL     = "deepseek-chat"
DEEPSEEK_THINKING  = True

# ── GLM ───────────────────────────────────────────────────────
GLM_API_KEY        = os.environ.get("GLM_API_KEY", "xxx")
GLM_BASE_URL       = "http://xxx"
GLM_MODEL          = "GLM-5.1"

# ── Claude（可选，不用可留空）──────────────────────────────────
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_AUTH_TOKEN", "xxx")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
CLAUDE_MODEL       = "claude-opus-4-5"
ANTHROPIC_VERSION  = "2023-06-01"

# ── MiniMax（可选）────────────────────────────────────────────
MINIMAX_API_KEY    = os.environ.get("MINIMAX_API_KEY", "xxx")
MINIMAX_BASE_URL   = "https://xxx"
MINIMAX_MODEL      = "ep-jsc7o0kw"
MINIMAX_MODEL_NAME = "MiniMax-M2.7"

# ── 子代理（响应分析）─────────────────────────────────────────
SUB_AGENT_BACKEND       = "deepseek"
SUB_AGENT_MODEL         = "deepseek-chat"
SUB_AGENT_BODY_LIMIT    = 12_000
SUB_AGENT_SUMMARY_LIMIT = 3_000

# ── MCP 平台服务器 ─────────────────────────────────────────────
MCP_SERVER_ENABLED = True
MCP_SERVER_URL     = os.environ.get("MCP_SERVER_HOST", "http://10.0.0.44:8000/mcp")
MCP_SERVER_TOKEN   = os.environ.get("MCP_AGENT_TOKEN", "xxx")
MCP_SERVER_NAME    = "pentest-challenge-platform"

# ── 本地工具 MCP 服务器（sqlmap / Playwright）──────────────────
# 启动: python3 tools_server.py
# 端口: 8000（本机，竞赛模式无外网时仍可用）
LOCAL_TOOLS_MCP_ENABLED = True
LOCAL_TOOLS_MCP_URL     = "http://127.0.0.1:8000/mcp"
LOCAL_TOOLS_MCP_NAME    = "local-security-tools"



# ── 竞赛模式 ──────────────────────────────────────────────────
COMPETITION_MODE         = True
MAX_CONCURRENT_INSTANCES = 3   # 平台硬限制，由 instance_semaphore 保证

# ── 每题时间控制 ───────────────────────────────────────────────
CHALLENGE_TIMEOUT_SECONDS = 20 * 60   # 每题 20 分钟
MAX_ROUNDS                = 999        # 不限轮数，由超时控制
PAUSE_EVERY_N             = 1

# ── 协作模式配置 ───────────────────────────────────────────────
# 格式: "thinker_think_checker_check"
# 可选: "ds_think_glm_check" | "glm_think_ds_check" | "deepseek" | "glm"
COOP_MODE = "ds_think_glm_check"

# ── 路径 ──────────────────────────────────────────────────────
LOG_ROOT            = "/home/ubuntu/CTF-Agent-v1-main/logs"
BENCHMARKS_PATH     = "/home/ubuntu/CTF-Agent-v1-main/benchmarks"
KNOWLEDGE_BASE_PATH = "/home/ubuntu/CTF-Agent-v1-main/knowledge"
SKILLS_BASE_PATH    = "/home/ubuntu/CTF-Agent-v1-main/skills"

# ── 知识库 ────────────────────────────────────────────────────
KNOWLEDGE_INJECT_ROUND = 15
KNOWLEDGE_MAX_CHARS    = 3_000
KNOWLEDGE_MAX_FILES    = 1
SKILL_MAX_CHARS        = 3_000

# ── 等待配置 ──────────────────────────────────────────────────
WAIT_BEFORE_START   = 100   # 启动后等待用户开启答题模式（秒）
WAIT_FOR_CHALLENGES = 120    # 轮询正式赛题最长等待（秒）
POLL_INTERVAL       = 10     # 轮询间隔（秒）
THREAD_START_DELAY  = 8      # 每个 worker 启动间隔（秒，错峰调用平台 API）

# ── Provider 菜单 ─────────────────────────────────────────────
PROVIDER_MAP = {
    "ds_think_glm_check": {"label": "协作模式: DeepSeek思考 + GLM审查"},
    "glm_think_ds_check": {"label": "协作模式: GLM思考 + DeepSeek审查"},
    "deepseek":           {"label": f"DeepSeek 单模型 ({DEEPSEEK_MODEL})"},
    "glm":                {"label": f"GLM 单模型 ({GLM_MODEL})"},
}

# 兼容旧引用
COOP_MAP = PROVIDER_MAP

SCAN_LOG_DIR_DEFAULT = "logs/playwright"