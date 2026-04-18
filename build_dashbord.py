#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_dashboard.py

日志路径结构（固定4层）：
  logs/{challenge_id}/{provider}/{YYYYMMDD}/session_{HHMMSS}.json

示例：
  logs/14VweC4xsQKw2veAJAt2/ds_think_glm_check/20260414/session_112632.json
  logs/JoBpwaMHddgIdotuEoAj/deepseek/20260414/session_090216.json
  logs/JoBpwaMHddgIdotuEoAj/glm/20260414/session_094627.json
"""
import os, sys, json, glob, argparse
from datetime import datetime
from collections import defaultdict


# ─────────────────────────────────────────────────────────────
#  数据加载（重写：严格按4层路径解析，支持任意provider名称）
# ─────────────────────────────────────────────────────────────

def load_all_logs(log_root):
    """
    扫描 log_root 下所有 session_*.json。
    返回结构：
      {
        challenge_id: {
          provider_name: [session_dict, ...],
          ...
        },
        ...
      }
    路径结构严格为：log_root/cid/provider/date/session_*.json
    """
    data = {}
    if not os.path.exists(log_root):
        return data

    # 第1层：challenge_id 目录
    try:
        cid_entries = sorted(os.listdir(log_root))
    except Exception:
        return data

    for cid in cid_entries:
        cid_path = os.path.join(log_root, cid)
        if not os.path.isdir(cid_path):
            continue
        # 跳过总日志目录（_master）
        if cid.startswith("_"):
            continue

        data[cid] = {}

        # 第2层：provider 目录
        try:
            prov_entries = sorted(os.listdir(cid_path))
        except Exception:
            continue

        for provider in prov_entries:
            prov_path = os.path.join(cid_path, provider)
            if not os.path.isdir(prov_path):
                continue

            sessions = []

            # 第3层：date 目录
            try:
                date_entries = sorted(os.listdir(prov_path))
            except Exception:
                continue

            for date_dir in date_entries:
                date_path = os.path.join(prov_path, date_dir)
                if not os.path.isdir(date_path):
                    continue

                # 第4层：session_*.json 文件
                pattern = os.path.join(date_path, "session_*.json")
                files   = sorted(glob.glob(pattern))

                for fp in files:
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                            ch = json.load(f)
                    except Exception as e:
                        print(f"[WARN] 无法加载 {fp}: {e}")
                        continue

                    ch["_filepath"] = fp
                    ch["_session"]  = os.path.basename(fp).replace(".json", "")
                    ch["_date"]     = date_dir
                    ch["_provider"] = provider   # 保存解析到的 provider 名

                    # 兼容不同字段名
                    if not ch.get("url") and ch.get("target_url"):
                        ch["url"] = ch["target_url"]

                    sessions.append(ch)

            if sessions:
                # 按 start_time 排序（最新在前）
                sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
                data[cid][provider] = sessions

        # 删除没有任何 session 的空 challenge_id
        if not data[cid]:
            del data[cid]

    return data


# ─────────────────────────────────────────────────────────────
#  统计
# ─────────────────────────────────────────────────────────────

def global_stats(data):
    """
    返回 (solved_count, has_run_count, total_tokens, total_challenges)
    solved：任意 provider 下有 success 的题目数
    has_run：有任意运行记录的题目数
    total_tokens：所有 session 的 total tokens 之和
    """
    solved     = 0
    has_run    = 0
    total_tok  = 0

    for cid, providers in data.items():
        all_sessions = []
        for sessions in providers.values():
            all_sessions.extend(sessions)

        if all_sessions:
            has_run += 1

        if any(s.get("result") == "success" for s in all_sessions):
            solved += 1

        for s in all_sessions:
            tok = s.get("total_tokens", {})
            if isinstance(tok, dict):
                total_tok += tok.get("total", 0)
            elif isinstance(tok, (int, float)):
                total_tok += int(tok)

    return solved, has_run, total_tok, len(data)


# ─────────────────────────────────────────────────────────────
#  工具函数（原样保留）
# ─────────────────────────────────────────────────────────────

def fmt_n(n):
    try:    return "{:,}".format(int(n))
    except: return str(n)

def esc(s):
    if not isinstance(s, str): s = str(s)
    return (s.replace("&","&amp;")
             .replace("<","&lt;")
             .replace(">","&gt;")
             .replace('"',"&quot;"))

def _prov_label(provider):
    """将 provider 字段转换为显示标签"""
    p = provider.lower()
    if   "deepseek" in p: return "DeepSeek"
    elif "ds_think_glm_check" in p: return "ds_think_glm_check"
    elif "glm_think_ds_check" in p: return "glm_think_ds_check"
    elif "claude"   in p: return "Claude"
    elif "minimax"  in p: return "MiniMax"
    elif "glm"      in p: return "GLM"
    else:                 return provider.upper()[:16]


# ─────────────────────────────────────────────────────────────
#  渲染函数（原样保留）
# ─────────────────────────────────────────────────────────────

def render_tool(tc):
    name    = tc.get("name","")
    args    = tc.get("args",{})
    result  = tc.get("result",{})
    is_flag = name == "submit_flag"

    sc = result.get("status_code","") if isinstance(result, dict) else ""
    sc_cls = ""
    if sc:
        try:
            sc_cls = "sc-ok" if int(sc)<300 else ("sc-redir" if int(sc)<400 else "sc-err")
        except ValueError:
            pass

    method  = args.get("method","") if name == "http_request" else ""
    url_val = args.get("url","")    if name == "http_request" else args.get("flag","")

    body_html = ""
    result_meta_html = ""
    if isinstance(result, dict) and name == "http_request":
        body = result.get("body","")
        result_meta = {k: v for k, v in result.items() if k != "body"}
        if body:
            body_html = """<div class="code-lbl">Response Body</div>
<pre class="code-pre code-body">{}</pre>""".format(esc(body[:3000]))
        result_meta_html = """<div class="code-lbl">Response Meta</div>
<pre class="code-pre">{}</pre>""".format(esc(json.dumps(result_meta, ensure_ascii=False, indent=2)))
    else:
        result_meta_html = """<div class="code-lbl">Result</div>
<pre class="code-pre">{}</pre>""".format(esc(json.dumps(result, ensure_ascii=False, indent=2)))

    flag_val = args.get("flag","") if is_flag else ""
    flag_inline = '<span class="flag-inline">🏁 {}</span>'.format(esc(flag_val)) if is_flag else ""

    return """<details class="tool-d {flag_cls}">
  <summary class="tool-s">
    <span class="tname{flag_n}">{name}</span>
    <span class="tprev">{method} {url}</span>
    {sc}
    {flag_inline}
  </summary>
  <div class="tool-body">
    <div class="code-lbl">Request Args</div>
    <pre class="code-pre">{args}</pre>
    {result_meta}
    {body}
  </div>
</details>""".format(
        flag_cls     = "tool-flag" if is_flag else "",
        name         = esc(name),
        flag_n       = " tname-flag" if is_flag else "",
        method       = esc(method),
        url          = esc(str(url_val)[:80]),
        sc           = '<span class="sc {}">{}</span>'.format(sc_cls, sc) if sc else "",
        flag_inline  = flag_inline,
        args         = esc(json.dumps(args, ensure_ascii=False, indent=2)),
        result_meta  = result_meta_html,
        body         = body_html
    )

def render_round(r):
    rnum    = r.get("round", 0)
    elapsed = r.get("elapsed_s", 0)
    tok     = r.get("tokens", {})
    text    = (r.get("assistant_text") or r.get("assistant") or "").strip()
    thinking= (r.get("thinking") or "").strip()
    tools   = r.get("tool_calls", []) or []

    thinking_html = ""
    if thinking:
        thinking_html = """<details class="think-d">
  <summary class="think-s">💭 思考过程 ({} chars)</summary>
  <div class="think-body">{}</div>
</details>""".format(len(thinking), esc(thinking))

    text_html = ""
    if text:
        text_html = '<div class="atext">{}</div>'.format(esc(text))

    tools_html = "\n".join(render_tool(tc) for tc in tools)

    tok_detail = "prompt:{} comp:{} total:{}".format(
        fmt_n(tok.get("prompt_tokens", tok.get("prompt",0))),
        fmt_n(tok.get("completion_tokens", tok.get("completion",0))),
        fmt_n(tok.get("total",0))
    )

    return """<details class="round-d">
  <summary class="round-s">
    <span class="rnum">R{rnum}</span>
    <span class="rtc">{ntc} tool(s)</span>
    {think_badge}
    <span class="rmeta">{el}s &nbsp;·&nbsp; {tok_detail}</span>
  </summary>
  <div class="round-body">
    {thinking}
    {text}
    {tools}
  </div>
</details>""".format(
        rnum        = rnum,
        ntc         = len(tools),
        think_badge = '<span class="think-badge">💭</span>' if thinking else "",
        el          = elapsed,
        tok_detail  = tok_detail,
        thinking    = thinking_html,
        text        = text_html,
        tools       = tools_html
    )

def render_run(ch, label, provider):
    result  = ch.get("result","failed")
    flag    = ch.get("flag")
    rounds  = ch.get("rounds",[]) or []
    elapsed = ch.get("elapsed_seconds",0)
    tok     = ch.get("total_tokens",{})
    date    = ch.get("_date","")
    session = ch.get("_session","")
    url     = ch.get("url", ch.get("target_url",""))
    model   = ch.get("model","")

    flag_html = ""
    if flag:
        flag_html = '<div class="flag-banner">🏁 FLAG: {}</div>'.format(esc(flag))

    total_rounds  = len(rounds)
    total_tools   = sum(len(r.get("tool_calls",[]) or []) for r in rounds)
    has_thinking  = any((r.get("thinking") or "").strip() for r in rounds)
    think_rounds  = sum(1 for r in rounds if (r.get("thinking") or "").strip())

    stats_html = """<div class="run-stats">
  <span class="stat-item">🔄 {rounds} rounds</span>
  <span class="stat-item">🔧 {tools} tool calls</span>
  <span class="stat-item">⏱ {el}s</span>
  <span class="stat-item">🪙 {tok} tokens</span>
  {think_stat}
</div>""".format(
        rounds     = total_rounds,
        tools      = total_tools,
        el         = elapsed,
        tok        = fmt_n(tok.get("total",0) if isinstance(tok,dict) else tok),
        think_stat = '<span class="stat-item stat-think">💭 {}轮思考</span>'.format(think_rounds) if has_thinking else ""
    )

    return """<div class="run-block run-{result}">
  <div class="run-hdr">
    <span class="run-label">{label}</span>
    <span class="rbadge rbadge-{result}">{RESULT}</span>
    <span class="prov-ds">{prov}</span>
    <span class="run-model">{model}</span>
    <span class="run-date">{date} {session}</span>
  </div>
  <div class="run-url">🌐 {url}</div>
  {stats}
  {flag_html}
  <div class="rounds-wrap">{rounds_html}</div>
</div>""".format(
        result     = result,
        RESULT     = result.upper(),
        label      = esc(label),
        prov       = esc(_prov_label(provider)),
        model      = esc(model),
        date       = date,
        session    = session,
        url        = esc(url),
        stats      = stats_html,
        flag_html  = flag_html,
        rounds_html= "\n".join(render_round(r) for r in rounds)
    )

def render_no_run():
    return '<div class="no-run">暂无记录</div>'

def render_pane_content(runs, provider):
    if not runs:
        return render_no_run()
    html_parts = []
    for i, ch in enumerate(runs, start=1):
        date    = ch.get("_date", "")
        session = ch.get("_session", "")
        label   = "运行{} ({})".format(i, date) if date else "运行{}".format(i)
        html_parts.append(render_run(ch, label, provider))
    return "\n".join(html_parts)


# ─────────────────────────────────────────────────────────────
#  侧边栏条目（重写：显示所有 provider 的圆点）
# ─────────────────────────────────────────────────────────────

def _dot_cls(sessions):
    """根据 session 列表返回圆点 CSS 类"""
    if not sessions:
        return "dot-none"
    if any(s.get("result") == "success" for s in sessions):
        return "dot-ok"
    if any(s.get("result") == "timeout" for s in sessions):
        return "dot-to"
    return "dot-fail"

def render_sidebar_item(cid, data):
    providers   = data[cid]          # {provider: [sessions]}
    all_sessions = [s for ss in providers.values() for s in ss]
    solved       = any(s.get("result") == "success" for s in all_sessions)

    # 每个 provider 渲染一个圆点，最多显示 4 个
    dot_html = ""
    for prov, sessions in list(providers.items())[:4]:
        cls   = _dot_cls(sessions)
        label = _prov_label(prov)
        dot_html += '<span class="dot {}" title="{}"></span>'.format(cls, esc(label))

    return """<div class="si" data-idx="{cid}" onclick="sel('{cid}')">
  <span class="si-num">{cid}</span>
  <span class="si-dots">{dots}</span>
  {check}
</div>""".format(
        cid   = esc(cid),
        dots  = dot_html,
        check = '<span class="si-ok">✓</span>' if solved else ""
    )


# ─────────────────────────────────────────────────────────────
#  Challenge 面板（重写：每个 provider 独立一个 pane）
# ─────────────────────────────────────────────────────────────

def render_challenge_panel(cid, data):
    providers = data[cid]   # {provider: [sessions]}

    panes_html = ""
    for provider, sessions in providers.items():
        label = _prov_label(provider)
        panes_html += """<div class="pane" id="pane-{p}-{cid}">
  <div class="pane-resizer"></div>
  <div class="pane-tb">
    <span class="pane-lbl">{label}</span>
    <span style="font-size:10px;color:#aaa">{cnt} 次运行</span>
  </div>
  <div class="pane-body">{content}</div>
</div>""".format(
            p       = esc(provider),
            cid     = esc(cid),
            label   = esc(label),
            cnt     = len(sessions),
            content = render_pane_content(sessions, provider)
        )

    if not panes_html:
        panes_html = render_no_run()

    return """<div class="ch-panel" id="ch-{cid}" style="display:none">
  <div class="single-wrap" id="sw-{cid}" style="height:100%;overflow:hidden;">
    {panes}
  </div>
</div>""".format(cid=esc(cid), panes=panes_html)


# ─────────────────────────────────────────────────────────────
#  主构建函数（重写）
# ─────────────────────────────────────────────────────────────

def build(log_root, out_path):
    data                          = load_all_logs(log_root)
    solved, has_run, total_tok, total = global_stats(data)

    # 按 challenge_id 排序（字母序）
    cids       = sorted(data.keys())
    cids_js    = json.dumps(cids)

    sidebar    = "\n".join(render_sidebar_item(cid, data) for cid in cids)
    panels     = "\n".join(render_challenge_panel(cid, data) for cid in cids)

    html = HTML_TEMPLATE.format(
        total     = total,
        has_run   = has_run,
        solved    = solved,
        total_tok = fmt_n(total_tok),
        gen_time  = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        sidebar   = sidebar,
        panels    = panels,
        cids_js   = cids_js,
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("✓ Dashboard -> {}  ({} challenges, {} solved)".format(out_path, total, solved))

    # 打印各 challenge 统计摘要
    print("\n─── 题目摘要 ───")
    for cid in cids:
        providers = data[cid]
        all_s     = [s for ss in providers.values() for s in ss]
        best      = "success" if any(s.get("result")=="success" for s in all_s) else \
                    "timeout" if any(s.get("result")=="timeout" for s in all_s) else "failed"
        flag      = next((s.get("flag") for s in all_s if s.get("flag")), "—")
        prov_list = ", ".join(sorted(providers.keys()))
        print("  {:35s}  {:12s}  flag={:30s}  providers=[{}]".format(
            cid[:35], best, str(flag)[:30], prov_list))

    # 启动临时 HTTP 服务供下载
    import http.server
    out_dir  = os.path.dirname(os.path.abspath(out_path))
    out_file = os.path.basename(out_path)
    port     = 8898
    print("\n✓ 临时下载服务已启动:")
    print("  浏览器访问: http://127.0.0.1:{}/{}".format(port, out_file))
    print("  Ctrl+C 停止\n")
    os.chdir(out_dir)
    handler = http.server.SimpleHTTPRequestHandler
    httpd   = http.server.HTTPServer(("127.0.0.1", port), handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")


# ─────────────────────────────────────────────────────────────
#  HTML 模板（已修复所有未转义的花括号引发的问题）
# ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>CTF Agent Dashboard</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Syne:wght@500;700&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#fff;--text:#111;--g50:#f8f8f8;--g100:#eee;--g200:#ddd;--g400:#999;--g600:#555;
  --green:#1a6e3c;--green-bg:#edf7f1;--red:#c0392b;--red-bg:#fdf3f2;
  --orange:#b85c00;--orange-bg:#fef7ee;--blue:#1a4fa0;
  --purple:#7c3aed;--purple-bg:#f5f3ff;
  --ds:#e67e00;
  --sb:220px;--tb:46px;
  --mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif;
}}
html,body{{height:100%;overflow:hidden}}
body{{background:var(--bg);color:var(--text);font-family:var(--sans);font-size:13px}}

.topbar{{position:fixed;top:0;left:0;right:0;height:var(--tb);z-index:200;
  background:var(--text);color:#fff;display:flex;align-items:center;
  padding:0 20px;gap:20px;font-family:var(--mono);font-size:11px;letter-spacing:.05em}}
.t-logo{{font-weight:700;font-size:13px;letter-spacing:.1em;margin-right:4px}}
.t-stat{{display:flex;align-items:center;gap:5px;color:#aaa}}
.t-stat strong{{color:#fff}}
.t-ds{{color:var(--ds)!important}}
.t-right{{margin-left:auto;color:#555;font-size:10px}}

.layout{{display:flex;position:fixed;top:var(--tb);left:0;right:0;bottom:0}}

.sidebar{{width:var(--sb);min-width:150px;max-width:320px;background:var(--g50);
  border-right:1.5px solid var(--text);display:flex;flex-direction:column;overflow:hidden;position:relative}}
.sb-hdr{{padding:10px 12px 8px;border-bottom:1px solid var(--g200);
  font-family:var(--mono);font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--g600);
  display:flex;justify-content:space-between}}
.sb-legend{{display:flex;align-items:center;gap:8px;padding:6px 12px;
  border-bottom:1px solid var(--g200);font-family:var(--mono);font-size:9px;color:var(--g400)}}
.sb-search{{padding:6px 10px;border-bottom:1px solid var(--g200)}}
.sb-search input{{width:100%;padding:4px 8px;border:1px solid var(--g200);background:var(--bg);
  font-family:var(--mono);font-size:11px;color:var(--text);outline:none}}
.sb-search input:focus{{border-color:var(--text)}}
.sb-list{{flex:1;overflow-y:auto}}
.sb-list::-webkit-scrollbar{{width:3px}}
.sb-list::-webkit-scrollbar-thumb{{background:var(--g200)}}
.si{{display:flex;align-items:center;gap:6px;padding:6px 12px;cursor:pointer;
  border-bottom:1px solid var(--g100);font-family:var(--mono);font-size:11px;transition:background .1s}}
.si:hover{{background:var(--g100)}}.si.active{{background:var(--text);color:#fff}}
.si.active .si-ok{{color:#6fcf97}}
.si-num{{flex:1;font-weight:600}}
.si-dots{{display:flex;gap:3px}}
.si-ok{{font-size:10px;color:var(--green);width:12px;text-align:center}}
.dot{{width:7px;height:7px;border-radius:50%;border:1.5px solid var(--g400)}}
.dot-ok  {{background:var(--green);border-color:var(--green)}}
.dot-fail{{background:var(--red);  border-color:var(--red)}}
.dot-to  {{background:var(--orange);border-color:var(--orange)}}
.dot-none{{background:transparent}}
.sb-resizer{{position:absolute;right:0;top:0;bottom:0;width:4px;cursor:col-resize;z-index:10}}
.sb-resizer:hover{{background:rgba(0,0,0,.08)}}

.main{{flex:1;overflow:hidden;display:flex;flex-direction:column}}
.main-hdr{{padding:10px 18px;border-bottom:1px solid var(--g200);
  display:flex;align-items:center;gap:14px;flex-shrink:0}}
.main-title{{font-family:var(--mono);font-size:14px;font-weight:700;letter-spacing:.04em}}
.main-body{{flex:1;overflow:hidden;position:relative}}

.welcome{{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:10px;color:var(--g400)}}
.welcome h2{{font-family:var(--mono);font-size:18px;color:var(--g200)}}
.welcome p{{font-family:var(--mono);font-size:12px}}

.ch-panel{{position:absolute;inset:0;overflow:hidden}}
.single-wrap{{display:flex;height:100%;overflow:hidden}}
.pane{{
  display:flex;
  flex-direction:column;
  overflow:hidden;
  min-width:180px;
  flex:1 1 auto;
  border-right:1px solid var(--g200);
  position:relative;
}}
.pane:last-child{{border-right:none}}
.pane-resizer{{
  position:absolute;
  right:0;
  top:0;
  bottom:0;
  width:4px;
  cursor:col-resize;
  z-index:20;
}}
.pane-resizer:hover{{
  background:rgba(0,0,0,.1);
}}
.pane-tb{{display:flex;align-items:center;justify-content:space-between;
  padding:5px 12px;border-bottom:1px solid var(--g200);background:var(--g50);flex-shrink:0;
  font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--g600)}}
.pane-lbl{{font-weight:700}}
.pane-body{{flex:1;overflow-y:auto;padding:14px}}
.pane-body::-webkit-scrollbar{{width:4px}}
.pane-body::-webkit-scrollbar-thumb{{background:var(--g200)}}
.no-run{{height:200px;display:flex;align-items:center;justify-content:center;
  color:var(--g400);font-family:var(--mono);font-size:12px}}

/* run block */
.run-block{{margin-bottom:16px;border:1px solid var(--g200);border-radius:2px;overflow:hidden}}
.run-hdr{{display:flex;align-items:center;flex-wrap:wrap;gap:8px;
  padding:8px 12px;border-bottom:1px solid var(--g200);background:var(--g50)}}
.run-label{{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}}
.rbadge{{display:inline-block;padding:1px 6px;font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:.08em}}
.rbadge-success{{background:var(--green-bg);color:var(--green);border:1px solid var(--green)}}
.rbadge-failed {{background:var(--red-bg);  color:var(--red);  border:1px solid var(--red)}}
.rbadge-timeout{{background:var(--orange-bg);color:var(--orange);border:1px solid var(--orange)}}
.rbadge-interrupted{{background:var(--g50);color:var(--g600);border:1px solid var(--g400)}}
.rbadge-api_error{{background:var(--red-bg);color:var(--red);border:1px solid var(--red)}}
.rbadge-wrong_flag{{background:var(--orange-bg);color:var(--orange);border:1px solid var(--orange)}}
.prov-ds{{font-family:var(--mono);font-size:9px;font-weight:700;background:#fff8f0;color:var(--ds);border:1px solid var(--ds);padding:1px 5px}}
.run-model{{font-family:var(--mono);font-size:9px;color:var(--g400)}}
.run-date{{font-family:var(--mono);font-size:10px;color:var(--g400)}}
.run-url{{font-family:var(--mono);font-size:11px;color:var(--blue);
  padding:6px 12px;border-bottom:1px solid var(--g100);word-break:break-all;background:var(--bg)}}

/* stats bar */
.run-stats{{display:flex;flex-wrap:wrap;gap:6px;padding:6px 12px;
  border-bottom:1px solid var(--g100);background:var(--bg)}}
.stat-item{{font-family:var(--mono);font-size:10px;color:var(--g600);
  background:var(--g50);border:1px solid var(--g200);padding:2px 8px}}
.stat-think{{background:var(--purple-bg);color:var(--purple);border-color:var(--purple)}}

/* flag */
.flag-banner{{background:var(--green-bg);border-bottom:1px solid var(--green);
  padding:8px 12px;font-family:var(--mono);font-size:12px;color:var(--green);font-weight:700}}
.flag-inline{{font-family:var(--mono);font-size:10px;color:var(--green);font-weight:700;
  background:var(--green-bg);border:1px solid var(--green);padding:1px 6px;margin-left:4px}}

/* rounds */
.rounds-wrap{{padding:10px;display:flex;flex-direction:column;gap:5px}}
.round-d{{border:1px solid var(--g200);overflow:hidden}}
.round-s{{display:flex;align-items:center;gap:8px;padding:6px 10px;
  cursor:pointer;background:var(--g50);font-family:var(--mono);font-size:11px;list-style:none}}
.round-s::-webkit-details-marker{{display:none}}
.round-d[open] .round-s,.round-s:hover{{background:var(--g100)}}
.rnum{{background:var(--text);color:#fff;padding:0 6px;font-size:10px;font-weight:700}}
.rtc{{color:var(--g600)}}
.think-badge{{font-size:12px}}
.rmeta{{margin-left:auto;color:var(--g400);font-size:10px}}
.round-body{{padding:10px;display:flex;flex-direction:column;gap:6px}}

/* thinking block */
.think-d{{border:1px solid #c4b5fd;overflow:hidden;background:var(--purple-bg)}}
.think-s{{display:flex;align-items:center;gap:8px;padding:5px 10px;
  cursor:pointer;background:#ede9fe;font-family:var(--mono);font-size:11px;
  list-style:none;color:var(--purple);font-weight:600}}
.think-s::-webkit-details-marker{{display:none}}
.think-d[open] .think-s,.think-s:hover{{background:#ddd6fe}}
.think-body{{padding:10px 12px;font-family:var(--mono);font-size:11px;
  line-height:1.7;color:#5b21b6;white-space:pre-wrap;word-break:break-word;
  max-height:400px;overflow-y:auto;border-top:1px solid #c4b5fd}}
.think-body::-webkit-scrollbar{{width:3px}}
.think-body::-webkit-scrollbar-thumb{{background:#c4b5fd}}

/* agent text */
.atext{{border-left:3px solid var(--text);padding:8px 12px;font-size:12px;
  line-height:1.75;color:var(--g600);white-space:pre-wrap;word-break:break-word;
  background:var(--bg)}}

/* tools */
.tool-d{{border:1px solid var(--g200);overflow:hidden}}
.tool-flag{{border-color:var(--green);}}
.tool-s{{display:flex;align-items:center;gap:7px;padding:5px 10px;
  cursor:pointer;background:var(--g50);font-family:var(--mono);font-size:11px;list-style:none}}
.tool-s::-webkit-details-marker{{display:none}}
.tool-s:hover,.tool-d[open] .tool-s{{background:var(--g100)}}
.tname{{background:var(--text);color:#fff;padding:0 6px;font-size:10px;font-weight:700;white-space:nowrap}}
.tname-flag{{background:var(--green)}}
.tprev{{color:var(--g600);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.sc{{padding:1px 5px;font-size:10px;font-weight:700;font-family:var(--mono)}}
.sc-ok{{color:var(--green)}}.sc-redir{{color:var(--blue)}}.sc-err{{color:var(--red)}}
.tool-body{{background:var(--bg)}}
.code-lbl{{padding:3px 10px;background:var(--g100);font-family:var(--mono);font-size:9px;
  letter-spacing:.1em;text-transform:uppercase;color:var(--g600);border-top:1px solid var(--g200)}}
.code-pre{{padding:8px 10px;font-family:var(--mono);font-size:10px;line-height:1.55;
  white-space:pre-wrap;word-break:break-all;max-height:280px;overflow-y:auto;background:var(--g50)}}
.code-body{{max-height:400px;background:#fafff8;border-left:2px solid var(--green)}}
.code-pre::-webkit-scrollbar{{width:3px;height:3px}}
.code-pre::-webkit-scrollbar-thumb{{background:var(--g200)}}
</style>
</head>
<body>

<div class="topbar">
  <span class="t-logo">CTF AGENT</span>
  <span class="t-stat">共 <strong>{total}</strong></span>
  <span class="t-stat">已运行 <strong>{has_run}</strong></span>
  <span class="t-stat">Solved <strong class="t-ds">{solved}</strong></span>
  <span class="t-stat">Tokens <strong>{total_tok}</strong></span>
  <span class="t-right">Generated {gen_time}</span>
</div>

<div class="layout">
  <div class="sidebar" id="sidebar">
    <div class="sb-hdr"><span>Challenges</span><span style="color:var(--text)">{total}</span></div>
    <div class="sb-legend">
      <span class="dot dot-ok"></span>solved
      <span class="dot dot-fail" style="margin-left:6px"></span>failed
      <span class="dot dot-to"  style="margin-left:6px"></span>timeout
    </div>
    <div class="sb-search"><input type="text" id="sb-input" placeholder="搜索题目ID..." oninput="filterSb(this.value)"></div>
    <div class="sb-list" id="sb-list">{sidebar}</div>
    <div class="sb-resizer" id="sb-resizer"></div>
  </div>

  <div class="main" id="main">
    <div class="main-hdr" id="main-hdr" style="display:none">
      <div class="main-title" id="main-title">—</div>
    </div>
    <div class="main-body" id="main-body">
      <div class="welcome" id="welcome">
        <h2>← 选择一道题目</h2>
        <p>左侧圆点代表各 Provider 的运行状态（多个圆点 = 多个 Provider）</p>
        <p style="margin-top:4px;font-size:11px">💭 紫色块 = 思考过程 &nbsp;|&nbsp; 多 pane = 多 Provider 对比</p>
      </div>
      {panels}
    </div>
  </div>
</div>

<script>
var cur=null;
var cids = {cids_js};

/* ===============================
   challenge 切换逻辑
=============================== */

function sel(cid){{

  document.querySelectorAll('.ch-panel').forEach(function(p){{
    p.style.display='none';
  }});

  document.getElementById('welcome').style.display='none';

  var p=document.getElementById('ch-'+cid);
  if(p) p.style.display='block';

  document.querySelectorAll('.si').forEach(function(s){{
    s.classList.remove('active');
  }});

  var si=document.querySelector('.si[data-idx="'+cid+'"]');

  if(si){{
    si.classList.add('active');
    si.scrollIntoView({{block:'nearest'}});
  }}

  document.getElementById('main-title').textContent=cid;
  document.getElementById('main-hdr').style.display='flex';

  cur=cid;
}}


/* ===============================
   sidebar 拖拽
=============================== */

(function(){{

  var rs=document.getElementById('sb-resizer');
  var sb=document.getElementById('sidebar');

  var dr=false,sx,sw;

  if(rs){{

    rs.addEventListener('mousedown',function(e){{
      dr=true;
      sx=e.clientX;
      sw=sb.offsetWidth;
      document.body.style.cursor='col-resize';
      e.preventDefault();
    }});

    document.addEventListener('mousemove',function(e){{

      if(!dr) return;

      sb.style.width=Math.max(
        150,
        Math.min(
          400,
          sw+e.clientX-sx
        )
      )+'px';

    }});

    document.addEventListener('mouseup',function(){{

      dr=false;
      document.body.style.cursor='';

    }});

  }}

}})();


/* ===============================
   pane 拖拽（正确初始化位置）
=============================== */

document.querySelectorAll('.pane-resizer').forEach(function(r){{

  let dragging=false;
  let startX,startW,pane;

  r.addEventListener('mousedown',function(e){{

    dragging=true;

    pane=r.parentElement;

    startX=e.clientX;
    startW=pane.offsetWidth;

    document.body.style.cursor='col-resize';

  }});

  document.addEventListener('mousemove',function(e){{

    if(!dragging) return;

    let w=startW+(e.clientX-startX);

    pane.style.flex='0 0 '+w+'px';

  }});

  document.addEventListener('mouseup',function(){{

    dragging=false;

    document.body.style.cursor='';

  }});
}});

function filterSb(q){{
  q=q.toLowerCase();
  document.querySelectorAll('.si').forEach(function(s){{
    var t=s.querySelector('.si-num').textContent.toLowerCase();
    s.style.display=(!q||t.includes(q))?'':'none';
  }});
}}

document.addEventListener('keydown',function(e){{
  if(!cur) return;
  var idx = cids.indexOf(cur);
  if(e.key==='ArrowDown'){{
    e.preventDefault();
    if(idx < cids.length - 1) sel(cids[idx+1]);
  }}
  if(e.key==='ArrowUp')  {{
    e.preventDefault();
    if(idx > 0) sel(cids[idx-1]);
  }}
}});
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
#  入口
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CTF Agent Dashboard 生成器")
    parser.add_argument("-l", "--logs",
                        default="/home/ubuntu/CTF-Agent-v1-main/logs",
                        help="日志根目录")
    parser.add_argument("-o", "--output",
                        default="/home/ubuntu/CTF-Agent-v1-main/dashboard.html",
                        help="输出 HTML 路径")
    args = parser.parse_args()

    if not os.path.isdir(args.logs):
        print("日志目录不存在: {}".format(args.logs))
        sys.exit(1)

    build(args.logs, args.output)
