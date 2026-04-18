#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tools_server.py — CTF 专用 MCP 工具服务器
# 优化点：
#   1. Playwright 深度 CTF 特化（反检测/DOM降维/状态提取/流量拦截/JS注入/Flag狩猎）
#   2. SQLMap 完整 MCP 封装（多模式/结果解析/Cookie注入）
#   3. 统一 Flag 正则扫描管道
#   4. 所有工具结果持久化至题目日志目录

import os
import re
import json
import asyncio
import subprocess
import logging
from datetime import datetime

from mcp.server.fastmcp import FastMCP
from config import LOG_ROOT

# ─────────────────────────────────────────────────────────────
# 日志
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("mcp_calls.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

mcp = FastMCP("local-security-tools")

SCAN_LOG_DIR = os.path.join(LOG_ROOT, "_tool_scans")
os.makedirs(SCAN_LOG_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Flag 正则（通用 + 常见平台变体）
# ─────────────────────────────────────────────────────────────
_FLAG_PATTERNS = [
    re.compile(r"flag\{[^}]{1,128}\}", re.IGNORECASE),
    re.compile(r"ctf\{[^}]{1,128}\}", re.IGNORECASE),
    re.compile(r"NSSCTF\{[^}]{1,128}\}", re.IGNORECASE),
    re.compile(r"[A-Z0-9_]{2,10}\{[^}]{8,128}\}"),           # 通用变体
]

def _hunt_flags(text: str) -> list[str]:
    """在任意文本中提取所有 Flag 候选。"""
    found = []
    for pat in _FLAG_PATTERNS:
        found.extend(pat.findall(text))
    return list(dict.fromkeys(found))   # 去重保序


# ─────────────────────────────────────────────────────────────
# 持久化工具
# ─────────────────────────────────────────────────────────────
def _save_scan(tool: str, target: str, content: str) -> str:
    ts    = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    fname = f"{tool}_{ts}.txt"
    fpath = os.path.join(SCAN_LOG_DIR, fname)
    with open(fpath, "w", encoding="utf-8", errors="ignore") as f:
        f.write(f"[Tool]   {tool}\n")
        f.write(f"[Target] {target}\n")
        f.write(f"[Time]   {datetime.now().isoformat()}\n")
        f.write("─" * 60 + "\n")
        f.write(content)
    return fpath


# ══════════════════════════════════════════════════════════════
# ① PLAYWRIGHT — CTF 专用高级浏览器工具
# ══════════════════════════════════════════════════════════════

# 反检测 JS 注入片段（覆盖 navigator.webdriver 等自动化特征）
_STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins',   {get: () => [1,2,3,4,5]});
Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh','en-US','en']});
window.chrome = { runtime: {} };
Object.defineProperty(navigator, 'permissions', {
    get: () => ({ query: () => Promise.resolve({ state: 'granted' }) })
});
"""

# SPA 框架特征检测
_SPA_PATTERNS = [
    '<div id="app">', '<div id="root">', "ng-app", "data-reactroot",
    "__NUXT__", "__NEXT_DATA__", "window.__", "React.createElement",
    "document.getElementById(\"app\")",
]


def _make_browser_context(playwright, headless: bool = True):
    """创建带反检测配置的浏览器上下文。"""
    browser = playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 800},
        ignore_https_errors=True,
        java_script_enabled=True,
    )
    ctx.add_init_script(_STEALTH_SCRIPT)
    return browser, ctx


# ─────────────────────────────────────────────────────────────
# 1-A  stealth_navigate + extract_ctf_dom（核心侦察工具）
# ─────────────────────────────────────────────────────────────
@mcp.tool()
async def capture_render(
    url: str,
    wait_ms: int = 2500,
    screenshot: bool = True,
    cookies: str = "",          # JSON 字符串，如 '[{"name":"session","value":"xxx"}]'
    extra_headers: str = "",    # JSON 字符串，如 '{"X-Forwarded-For":"127.0.0.1"}'
) -> dict:
    """
    CTF 专用隐身导航 + DOM 降维提取。
    - 反检测浏览器上下文（覆盖 webdriver 特征）
    - 注入自定义 Cookie / Header（绕过鉴权）
    - 精简 DOM：提取表单/注释/隐藏字段/可交互元素
    - 自动扫描页面 Flag
    - 全页截图持久化
    返回：{ html, dom_summary, flags, screenshot, log_path, success }
    """
    logger.info(f"[capture_render] url={url}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "playwright 未安装", "success": False}

    html      = ""
    dom_json  = {}
    scr_path  = ""
    intercept_flags: list[str] = []

    try:
        async with async_playwright() as p:
            browser, ctx = _make_browser_context(p)

            # 注入 Cookie
            if cookies:
                try:
                    ck_list = json.loads(cookies)
                    parsed_url = url.split("?")[0]
                    for ck in ck_list:
                        if "url" not in ck:
                            ck["url"] = parsed_url
                    await ctx.add_cookies(ck_list)
                except Exception as e:
                    logger.warning(f"[capture_render] Cookie 注入失败: {e}")

            # 注入额外 Header
            if extra_headers:
                try:
                    await ctx.set_extra_http_headers(json.loads(extra_headers))
                except Exception as e:
                    logger.warning(f"[capture_render] Header 注入失败: {e}")

            page = await ctx.new_page()

            # ── 全局流量拦截：扫描所有响应 Flag ──────────────
            async def _on_response(response):
                try:
                    ct = response.headers.get("content-type", "")
                    if any(t in ct for t in ("text", "json", "javascript", "html")):
                        body = await response.text()
                        for f in _hunt_flags(body + response.url):
                            if f not in intercept_flags:
                                intercept_flags.append(f)
                except Exception:
                    pass

            page.on("response", _on_response)

            await page.goto(url, timeout=20_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(wait_ms)

            # 等待主要内容加载（SPA 场景）
            try:
                await page.wait_for_load_state("networkidle", timeout=8_000)
            except Exception:
                pass

            html = await page.content()

            # ── CTF DOM 降维提取 ──────────────────────────────
            dom_json = await page.evaluate("""() => {
                // 克隆 DOM，避免破坏当前页面
                const clone = document.cloneNode(true);

                // 提取隐藏输入（常藏 CSRF token / 内部参数）
                const hiddenInputs = [...document.querySelectorAll('input[type=hidden],input[disabled]')]
                    .map(e => ({ name: e.name, value: e.value, id: e.id }));

                // 提取所有 HTML 注释（常含线索/调试信息）
                const walker = document.createTreeWalker(document, NodeFilter.SHOW_COMMENT);
                const comments = [];
                let node;
                while ((node = walker.nextNode())) {
                    const t = node.nodeValue.trim();
                    if (t) comments.push(t);
                }

                // 可交互元素摘要
                const interactables = [...document.querySelectorAll(
                    'a[href], button, input:not([type=hidden]), select, textarea, [onclick], [data-action]'
                )].slice(0, 60).map(e => ({
                    tag: e.tagName,
                    type: e.type || '',
                    id: e.id || '',
                    name: e.name || '',
                    text: (e.innerText || e.textContent || '').trim().substring(0, 60),
                    href: e.href || '',
                    placeholder: e.placeholder || '',
                    onclick: e.getAttribute('onclick') || '',
                }));

                // 表单结构
                const forms = [...document.querySelectorAll('form')].map(f => ({
                    id: f.id, action: f.action, method: f.method,
                    fields: [...f.querySelectorAll('input,select,textarea')].map(i => ({
                        name: i.name, type: i.type, value: i.value,
                        required: i.required, disabled: i.disabled
                    }))
                }));

                // 可疑 JS 全局变量（含 flag/token/secret/key）
                const suspiciousVars = {};
                const keywords = ['flag', 'token', 'secret', 'key', 'admin', 'password', 'auth'];
                try {
                    Object.keys(window).forEach(k => {
                        if (keywords.some(kw => k.toLowerCase().includes(kw))) {
                            try { suspiciousVars[k] = JSON.stringify(window[k]).substring(0, 200); }
                            catch {}
                        }
                    });
                } catch {}

                // 前 40 个链接
                const links = [...document.querySelectorAll('a[href]')]
                    .slice(0, 40)
                    .map(a => ({ text: a.innerText.trim().substring(0, 40), href: a.href }));

                // 页面标题与 meta
                const meta = {
                    title: document.title,
                    description: document.querySelector('meta[name=description]')?.content || '',
                    generator: document.querySelector('meta[name=generator]')?.content || '',
                };

                return { hiddenInputs, comments, interactables, forms, suspiciousVars, links, meta };
            }""")

            # ── 客户端存储提取 ────────────────────────────────
            storage = await page.evaluate("""() => {
                const getData = store => {
                    const obj = {};
                    try { for (let i = 0; i < store.length; i++) {
                        const k = store.key(i);
                        obj[k] = store.getItem(k);
                    }} catch {}
                    return obj;
                };
                return {
                    localStorage:   getData(localStorage),
                    sessionStorage: getData(sessionStorage),
                    cookie:         document.cookie,
                };
            }""")
            dom_json["storage"] = storage

            # ── 截图 ──────────────────────────────────────────
            if screenshot:
                ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                scr_path = os.path.join(SCAN_LOG_DIR, f"screenshot_{ts}.png")
                await page.screenshot(path=scr_path, full_page=True)

            await browser.close()

    except Exception as e:
        logger.error(f"[capture_render] 渲染失败: {e}")
        return {"error": str(e), "html": "", "success": False}

    # ── 持久化 ────────────────────────────────────────────────
    log_content = (
        f"URL: {url}\n"
        f"Flags intercepted: {intercept_flags}\n"
        f"DOM summary:\n{json.dumps(dom_json, ensure_ascii=False, indent=2)[:4000]}\n\n"
        f"--- HTML ---\n{html[:8000]}"
    )
    log_path = _save_scan("playwright", url, log_content)

    # DOM 扫描 Flag
    dom_flags = _hunt_flags(html + json.dumps(dom_json))
    all_flags = list(dict.fromkeys(intercept_flags + dom_flags))

    if all_flags:
        logger.info(f"[capture_render] 🚩 发现 Flag: {all_flags}")

    return {
        "tool":        "capture_render",
        "url":         url,
        "log_path":    log_path,
        "html":        html[:12000],
        "dom_summary": dom_json,
        "flags":       all_flags,
        "screenshot":  scr_path,
        "success":     True,
    }


# ─────────────────────────────────────────────────────────────
# 1-B  smart_interact — 智能鲁棒交互
# ─────────────────────────────────────────────────────────────
@mcp.tool()
async def smart_interact(
    url: str,
    actions: str,           # JSON 数组：[{"action":"type","target":"username","value":"admin"},...]
    cookies: str = "",
    wait_after_ms: int = 2000,
    screenshot: bool = True,
) -> dict:
    """
    在页面上执行一系列交互操作（填表/点击/提交），支持反检测和强制 JS 点击。
    actions JSON 格式：
      [
        {"action": "type",        "target": "CSS选择器或name/id/placeholder文本", "value": "输入值"},
        {"action": "click",       "target": "按钮文本或CSS选择器"},
        {"action": "force_click", "target": "CSS选择器"},
        {"action": "submit",      "target": "form的CSS选择器（可选）"},
        {"action": "wait",        "ms": 1000},
        {"action": "intercept_modify", "pattern": "URL正则", "replace_body": "{\"role\":\"admin\"}"}
      ]
    返回：{ html_after, dom_summary, flags, screenshot, log_path, success }
    """
    logger.info(f"[smart_interact] url={url} actions={actions[:120]}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "playwright 未安装", "success": False}

    try:
        action_list = json.loads(actions)
    except Exception as e:
        return {"error": f"actions JSON 解析失败: {e}", "success": False}

    html_after    = ""
    scr_path      = ""
    results_log   = []
    intercept_flags: list[str] = []

    try:
        async with async_playwright() as p:
            browser, ctx = _make_browser_context(p)

            if cookies:
                try:
                    ck_list = json.loads(cookies)
                    for ck in ck_list:
                        if "url" not in ck:
                            ck["url"] = url.split("?")[0]
                    await ctx.add_cookies(ck_list)
                except Exception as e:
                    logger.warning(f"[smart_interact] Cookie 注入失败: {e}")

            page = await ctx.new_page()

            # 流量拦截 Flag 扫描
            async def _on_resp(response):
                try:
                    ct = response.headers.get("content-type", "")
                    if any(t in ct for t in ("text", "json", "javascript")):
                        body = await response.text()
                        for f in _hunt_flags(body):
                            if f not in intercept_flags:
                                intercept_flags.append(f)
                except Exception:
                    pass

            page.on("response", _on_resp)

            # 响应体篡改路由（intercept_modify 动作）
            _modify_rules: list[dict] = []

            async def _route_handler(route, request):
                for rule in _modify_rules:
                    if re.search(rule["pattern"], request.url):
                        try:
                            resp = await route.fetch()
                            body = rule.get("replace_body", "")
                            await route.fulfill(
                                status=resp.status,
                                headers=dict(resp.headers),
                                body=body,
                            )
                            return
                        except Exception as e:
                            logger.warning(f"[intercept_modify] 失败: {e}")
                await route.continue_()

            await page.route("**/*", _route_handler)
            await page.goto(url, timeout=20_000, wait_until="domcontentloaded")

            for step in action_list:
                act = step.get("action", "")
                try:
                    if act == "type":
                        target = step["target"]
                        value  = step.get("value", "")
                        # 多种定位策略：name → id → placeholder → CSS
                        el = None
                        for loc in [
                            f'[name="{target}"]',
                            f'[id="{target}"]',
                            f'[placeholder*="{target}"]',
                            target,
                        ]:
                            try:
                                el = page.locator(loc).first
                                await el.wait_for(timeout=3000, state="visible")
                                break
                            except Exception:
                                el = None
                        if el:
                            await el.fill("")
                            await el.type(value, delay=30)
                            results_log.append(f"✓ type '{target}' = '{value}'")
                        else:
                            results_log.append(f"✗ type '{target}' — 元素未找到")

                    elif act == "click":
                        target = step["target"]
                        try:
                            await page.get_by_text(target, exact=False).first.click(timeout=5000)
                            results_log.append(f"✓ click by text '{target}'")
                        except Exception:
                            await page.locator(target).first.click(timeout=5000)
                            results_log.append(f"✓ click by selector '{target}'")

                    elif act == "force_click":
                        target = step["target"]
                        await page.evaluate(
                            """(sel) => {
                                const el = document.querySelector(sel)
                                    || [...document.querySelectorAll('*')]
                                        .find(e => (e.innerText||'').includes(sel));
                                if (el) { el.removeAttribute('disabled'); el.click(); }
                            }""",
                            target,
                        )
                        results_log.append(f"✓ force_click '{target}'")

                    elif act == "submit":
                        sel = step.get("target", "form")
                        await page.evaluate(
                            f"document.querySelector('{sel}') && document.querySelector('{sel}').submit()"
                        )
                        results_log.append(f"✓ submit '{sel}'")

                    elif act == "wait":
                        ms = int(step.get("ms", 1000))
                        await page.wait_for_timeout(ms)
                        results_log.append(f"✓ wait {ms}ms")

                    elif act == "intercept_modify":
                        _modify_rules.append({
                            "pattern":      step.get("pattern", ""),
                            "replace_body": step.get("replace_body", ""),
                        })
                        results_log.append(f"✓ intercept_modify pattern='{step.get('pattern')}'")

                    elif act == "execute_js":
                        script = step.get("script", "")
                        result = await page.evaluate(script)
                        results_log.append(f"✓ execute_js → {str(result)[:200]}")
                        # JS 结果中扫描 Flag
                        for f in _hunt_flags(str(result)):
                            if f not in intercept_flags:
                                intercept_flags.append(f)

                    else:
                        results_log.append(f"? 未知动作 '{act}'")

                except Exception as e:
                    results_log.append(f"✗ {act} '{step.get('target','')}' — {e}")

            await page.wait_for_timeout(wait_after_ms)
            html_after = await page.content()

            if screenshot:
                ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                scr_path = os.path.join(SCAN_LOG_DIR, f"interact_{ts}.png")
                await page.screenshot(path=scr_path, full_page=True)

            await browser.close()

    except Exception as e:
        logger.error(f"[smart_interact] 失败: {e}")
        return {"error": str(e), "success": False}

    dom_flags = _hunt_flags(html_after)
    all_flags = list(dict.fromkeys(intercept_flags + dom_flags))

    log_content = (
        f"URL: {url}\nActions: {actions}\n"
        f"Steps:\n" + "\n".join(results_log) + "\n\n"
        f"Flags: {all_flags}\n\n--- HTML after ---\n{html_after[:6000]}"
    )
    log_path = _save_scan("smart_interact", url, log_content)

    if all_flags:
        logger.info(f"[smart_interact] 🚩 Flag: {all_flags}")

    return {
        "tool":        "smart_interact",
        "url":         url,
        "steps":       results_log,
        "html_after":  html_after[:8000],
        "flags":       all_flags,
        "screenshot":  scr_path,
        "log_path":    log_path,
        "success":     True,
    }


# ─────────────────────────────────────────────────────────────
# 1-C  hunt_flag_pattern — 全局 Flag 猎取
# ─────────────────────────────────────────────────────────────
@mcp.tool()
async def hunt_flag_pattern(
    url: str,
    wait_ms: int = 4000,
    trigger_actions: str = "",   # 同 smart_interact 的 actions JSON（可选，触发异步请求）
    cookies: str = "",
) -> dict:
    """
    开启全局流量监听：扫描页面所有 HTTP 响应（XHR/Fetch/WS/重定向 URL）
    和 DOM 文本中的 Flag 特征。
    可配合 trigger_actions 触发特定的异步请求。
    返回：{ flags, response_count, log_path, success }
    """
    logger.info(f"[hunt_flag_pattern] url={url}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "playwright 未安装", "success": False}

    flags_found:  list[str] = []
    resp_log:     list[str] = []

    try:
        async with async_playwright() as p:
            browser, ctx = _make_browser_context(p)

            if cookies:
                try:
                    ck_list = json.loads(cookies)
                    for ck in ck_list:
                        if "url" not in ck:
                            ck["url"] = url.split("?")[0]
                    await ctx.add_cookies(ck_list)
                except Exception:
                    pass

            page = await ctx.new_page()

            async def _on_response(response):
                try:
                    ct = response.headers.get("content-type", "")
                    body_text = ""
                    if any(t in ct for t in ("text", "json", "javascript", "html", "xml")):
                        body_text = await response.text()
                    scan_target = response.url + " " + body_text
                    hits = _hunt_flags(scan_target)
                    for h in hits:
                        if h not in flags_found:
                            flags_found.append(h)
                            logger.info(f"[hunt] 🚩 {h} ← {response.url[:80]}")
                    if hits or response.status in (301, 302, 303, 307, 308):
                        resp_log.append(
                            f"{response.status} {response.url[:100]}"
                            + (f" → flags={hits}" if hits else "")
                        )
                except Exception:
                    pass

            page.on("response", _on_response)
            await page.goto(url, timeout=20_000, wait_until="domcontentloaded")

            # 执行触发动作（可选）
            if trigger_actions:
                try:
                    act_list = json.loads(trigger_actions)
                    for step in act_list:
                        act = step.get("action", "")
                        if act == "click":
                            target = step["target"]
                            try:
                                await page.get_by_text(target, exact=False).first.click(timeout=4000)
                            except Exception:
                                await page.locator(target).first.click(timeout=4000)
                        elif act == "wait":
                            await page.wait_for_timeout(int(step.get("ms", 1000)))
                        elif act == "execute_js":
                            r = await page.evaluate(step.get("script", ""))
                            for f in _hunt_flags(str(r)):
                                if f not in flags_found:
                                    flags_found.append(f)
                except Exception as e:
                    logger.warning(f"[hunt] 触发动作失败: {e}")

            await page.wait_for_timeout(wait_ms)

            # DOM 全文扫描
            try:
                body_text = await page.inner_text("body")
                for f in _hunt_flags(body_text):
                    if f not in flags_found:
                        flags_found.append(f)
            except Exception:
                pass

            # JS 全局变量扫描
            try:
                js_globals = await page.evaluate("""() => {
                    const kw = ['flag','token','secret','key','admin','auth'];
                    const res = {};
                    Object.keys(window).forEach(k => {
                        if (kw.some(w => k.toLowerCase().includes(w))) {
                            try { res[k] = JSON.stringify(window[k]).substring(0, 300); } catch {}
                        }
                    });
                    return res;
                }""")
                for f in _hunt_flags(json.dumps(js_globals)):
                    if f not in flags_found:
                        flags_found.append(f)
            except Exception:
                pass

            await browser.close()

    except Exception as e:
        return {"error": str(e), "success": False}

    log_content = (
        f"URL: {url}\nFlags: {flags_found}\n\n"
        f"Response log:\n" + "\n".join(resp_log[:100])
    )
    log_path = _save_scan("hunt_flag", url, log_content)

    return {
        "tool":           "hunt_flag_pattern",
        "url":            url,
        "flags":          flags_found,
        "response_count": len(resp_log),
        "log_path":       log_path,
        "success":        True,
    }


# ─────────────────────────────────────────────────────────────
# 1-D  execute_js — 任意 JS 注入执行
# ─────────────────────────────────────────────────────────────
@mcp.tool()
async def execute_js(
    url: str,
    script: str,
    cookies: str = "",
    wait_ms: int = 1500,
) -> dict:
    """
    在页面上下文中执行任意 JavaScript，用于：
    - XSS DOM 型漏洞利用
    - SSTI 盲打辅助
    - 读取 Shadow DOM / 隐藏状态
    - 修改前端加密函数输出
    返回：{ result, flags, success }
    """
    logger.info(f"[execute_js] url={url} script={script[:80]}")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "playwright 未安装", "success": False}

    js_result = None

    try:
        async with async_playwright() as p:
            browser, ctx = _make_browser_context(p)

            if cookies:
                try:
                    ck_list = json.loads(cookies)
                    for ck in ck_list:
                        if "url" not in ck:
                            ck["url"] = url.split("?")[0]
                    await ctx.add_cookies(ck_list)
                except Exception:
                    pass

            page = await ctx.new_page()
            await page.goto(url, timeout=20_000, wait_until="domcontentloaded")
            await page.wait_for_timeout(wait_ms)
            js_result = await page.evaluate(script)
            await browser.close()

    except Exception as e:
        return {"error": str(e), "success": False}

    result_str = json.dumps(js_result, ensure_ascii=False) if js_result is not None else ""
    flags      = _hunt_flags(result_str)
    log_path   = _save_scan("execute_js", url, f"Script:\n{script}\n\nResult:\n{result_str}")

    return {
        "tool":     "execute_js",
        "result":   result_str[:4000],
        "flags":    flags,
        "log_path": log_path,
        "success":  True,
    }


# ══════════════════════════════════════════════════════════════
# ② SQLMAP — 完整 MCP 封装
# ══════════════════════════════════════════════════════════════

def _parse_sqlmap_output(output: str) -> dict:
    """
    从 sqlmap 原始输出中提取结构化信息：
    - 是否存在注入点
    - 注入类型和参数
    - 数据库版本/类型
    - 枚举出的数据（tables/columns/dump）
    - Flag 候选
    """
    result = {
        "injectable": False,
        "injection_points": [],
        "dbms": "",
        "db_names": [],
        "tables": [],
        "data_dump": [],
        "flags": [],
    }

    # 注入点
    for m in re.finditer(
        r"Parameter: (.+?) \((.+?)\)\n\s+Type: (.+?)\n.*?Title: (.+?)\n.*?Payload: (.+?)\n",
        output, re.DOTALL
    ):
        result["injectable"] = True
        result["injection_points"].append({
            "parameter": m.group(1).strip(),
            "location":  m.group(2).strip(),
            "type":      m.group(3).strip(),
            "title":     m.group(4).strip(),
            "payload":   m.group(5).strip(),
        })

    # 简单判断是否可注入
    if "is vulnerable" in output or "sqlmap identified the following injection" in output:
        result["injectable"] = True

    # DBMS
    m = re.search(r"back-end DBMS: (.+)", output)
    if m:
        result["dbms"] = m.group(1).strip()

    # 数据库列表
    result["db_names"] = re.findall(r"^\[\*\] (.+)$", output, re.MULTILINE)

    # 表名
    result["tables"] = re.findall(r"\|\s+(\w+)\s+\|", output)

    # dump 数据
    dump_blocks = re.findall(r"\+[-+]+\+\n(.+?)\+[-+]+\+", output, re.DOTALL)
    for block in dump_blocks[:5]:
        rows = [r.strip() for r in block.split("\n") if r.strip().startswith("|")]
        result["data_dump"].extend(rows[:20])

    # Flag 猎取
    result["flags"] = _hunt_flags(output)

    return result


@mcp.tool()
def run_sqlmap(
    target_url: str,
    data: str = "",                     # POST 数据，如 "user=admin&pass=1"
    cookies: str = "",                  # Cookie 字符串，如 "session=xxx"
    headers: str = "",                  # 额外 Header，JSON 格式
    level: int = 2,                     # 注入深度 1-5
    risk: int = 1,                      # 注入风险 1-3
    technique: str = "",                # BEUSTQ 组合，空=全部
    dbms: str = "",                     # 指定 DBMS：mysql/postgres/sqlite/mssql/oracle
    db: str = "",                       # 指定数据库名（--db）
    tbl: str = "",                      # 指定表名（--dump）
    extra_options: str = "",            # 透传额外 sqlmap 参数
    timeout: int = 300,
) -> dict:
    """
    CTF 专用 SQLMap 注入检测与数据提取。
    自动解析输出，提取注入点/DBMS/数据/Flag。
    """
    logger.info(f"[run_sqlmap] target_url={target_url} level={level} risk={risk}")

    cmd = [
        "sqlmap", "-u", target_url,
        "--batch",                  # 全自动，不交互
        "--random-agent",           # 随机 UA
        f"--level={level}",
        f"--risk={risk}",
        "--output-dir", SCAN_LOG_DIR,
        "--flush-session",          # 每次从头扫，避免缓存干扰
    ]

    # POST 数据
    if data:
        cmd += ["--data", data]

    # Cookie
    if cookies:
        cmd += ["--cookie", cookies]

    # 额外 Header
    if headers:
        try:
            hdr_dict = json.loads(headers)
            for k, v in hdr_dict.items():
                cmd += ["--header", f"{k}: {v}"]
        except Exception:
            pass

    # 注入技术
    if technique:
        cmd += [f"--technique={technique}"]

    # DBMS
    if dbms:
        cmd += [f"--dbms={dbms}"]

    # 枚举数据
    if tbl and db:
        cmd += ["--dump", "-D", db, "-T", tbl]
    elif tbl:
        cmd += ["--dump", "-T", tbl]
    elif db:
        cmd += ["-D", db, "--tables"]
    else:
        # 默认：仅探测注入点 + 列数据库
        cmd += ["--dbs"]

    # 透传额外参数
    if extra_options:
        cmd += extra_options.split()

    logger.info(f"[run_sqlmap] cmd={' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n[STDERR]\n" + result.stderr

    except FileNotFoundError:
        output = "ERROR: sqlmap 未安装，请先执行 pip install sqlmap 或安装系统包"
    except subprocess.TimeoutExpired:
        output = f"TIMEOUT: sqlmap 执行超时（{timeout}s）"
    except Exception as e:
        output = f"ERROR: {e}"

    log_path = _save_scan("sqlmap", target_url, output)
    parsed   = _parse_sqlmap_output(output)

    if parsed["flags"]:
        logger.info(f"[run_sqlmap] 🚩 Flag: {parsed['flags']}")

    logger.info(
        f"[run_sqlmap] 完成 injectable={parsed['injectable']} "
        f"points={len(parsed['injection_points'])} log={log_path}"
    )

    return {
        "tool":             "sqlmap",
        "log_path":         log_path,
        "injectable":       parsed["injectable"],
        "injection_points": parsed["injection_points"],
        "dbms":             parsed["dbms"],
        "db_names":         parsed["db_names"],
        "tables":           parsed["tables"][:30],
        "data_dump":        parsed["data_dump"][:50],
        "flags":            parsed["flags"],
        "output":           output[:5000],
        "success":          True,
    }


# ─────────────────────────────────────────────────────────────
# SQLMap 快速扫描（一键探测，推荐首次使用）
# ─────────────────────────────────────────────────────────────
@mcp.tool()
def sqlmap_quick_scan(
    target_url: str,
    data: str = "",
    cookies: str = "",
) -> dict:
    """
    SQLMap 快速注入探测（level=1 risk=1 --dbs）。
    用于快速判断是否存在注入点，不做 dump。
    """
    return run_sqlmap(
        target_url=target_url,
        data=data,
        cookies=cookies,
        level=1,
        risk=1,
        extra_options="--time-sec=5",
        timeout=120,
    )


@mcp.tool()
def sqlmap_dump_table(
    target_url: str,
    db: str,
    tbl: str,
    data: str = "",
    cookies: str = "",
    dbms: str = "",
) -> dict:
    """
    SQLMap dump 指定表（先用 run_sqlmap/sqlmap_quick_scan 确认注入点后调用）。
    """
    return run_sqlmap(
        target_url=target_url,
        data=data,
        cookies=cookies,
        db=db,
        tbl=tbl,
        dbms=dbms,
        level=2,
        risk=1,
        timeout=300,
    )


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("🚀 CTF MCP 工具服务器启动: http://127.0.0.1:8000/mcp")
    print("   工具列表:")
    print("   - capture_render      : 隐身导航 + DOM降维 + Flag扫描")
    print("   - smart_interact      : 智能鲁棒交互 + 响应体篡改")
    print("   - hunt_flag_pattern   : 全局流量 Flag 猎取")
    print("   - execute_js          : 任意 JS 注入执行")
    print("   - run_sqlmap          : SQLMap 完整封装")
    print("   - sqlmap_quick_scan   : SQLMap 快速探测")
    print("   - sqlmap_dump_table   : SQLMap 表数据 Dump")
    mcp.run(transport="streamable-http")