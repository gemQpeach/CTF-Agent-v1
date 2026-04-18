#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — 程序入口
"""
import os, sys, time, threading, queue, urllib3, re
from datetime import datetime
urllib3.disable_warnings()

from config import (LOG_ROOT, KNOWLEDGE_BASE_PATH, SKILLS_BASE_PATH,
                    SUB_AGENT_MODEL, KNOWLEDGE_INJECT_ROUND,
                    MCP_SERVER_ENABLED, MCP_SERVER_URL, COMPETITION_MODE,
                    MAX_CONCURRENT_INSTANCES, COOP_MODE,
                    WAIT_BEFORE_START, WAIT_FOR_CHALLENGES, POLL_INTERVAL,
                    THREAD_START_DELAY, PROVIDER_MAP,
                    DEEPSEEK_MODEL, GLM_MODEL)
from skills    import get_skills
from knowledge import list_kb_files
from session   import run, inject_hint
import master_log as mlog

# ── 颜色 ──────────────────────────────────────────────────────
G="\033[92m"; Y="\033[93m"; R="\033[91m"; C="\033[96m"
M="\033[95m"; B="\033[94m"; X="\033[0m"
SKILL_COLOR="\033[38;5;141m"; KB_COLOR="\033[38;5;208m"
SLOT_COLOR="\033[38;5;226m"
THREAD_COLORS=["\033[92m","\033[94m","\033[95m","\033[93m","\033[96m",
               "\033[91m","\033[97m","\033[33m"]
_print_lock = threading.Lock()

def cprint(msg, color=X):
    with _print_lock:
        print(f"{color}{msg}{X}", flush=True)


# ── Provider  ─────────────────────────────────────────────
def choose_provider() -> str:
    """
    自动轮流模式：每20分钟切换一次单模型。
    偶数周期使用 deepseek，奇数周期使用 glm。
    """
    CYCLE_SECONDS = 20 * 60   # 20分钟 = 1200秒
    current_epoch = int(time.time())
    period = current_epoch // CYCLE_SECONDS
    
    if period % 2 == 0:
        provider = "deepseek"
        label = f"DeepSeek 单模型 ({DEEPSEEK_MODEL})"
    else:
        provider = "glm"
        label = f"GLM 单模型 ({GLM_MODEL})"
    
    # 计算当前周期剩余时间（可选，用于提示）
    elapsed = current_epoch % CYCLE_SECONDS
    remaining = CYCLE_SECONDS - elapsed
    minutes, seconds = divmod(remaining, 60)
    
    cprint(f"\n🤖 自动轮流模式（每20分钟切换）", C)
    cprint(f"   当前使用: {label}", G)
    cprint(f"   距离下次切换: {minutes}分{seconds}秒", SLOT_COLOR)
    print()
    
    return provider


# ── 倒计时 ────────────────────────────────────────────────────

def _countdown(seconds: int, msg: str):
    cprint(f"\n⏳ {msg}（{seconds}s 后自动继续）", Y)
    deadline = time.time() + seconds
    printed  = set()
    while time.time() < deadline:
        remaining = int(deadline - time.time())
        if remaining % 20 == 0 and remaining not in printed and remaining > 0:
            cprint(f"  剩余 {remaining}s ...", SLOT_COLOR)
            printed.add(remaining)
        time.sleep(1)
    cprint("  OK 等待结束，开始执行\n", G)


# ── 平台题目获取 ──────────────────────────────────────────────

def _fetch_raw():
    import platform_client
    data = platform_client.list_challenges()
    return data.get("challenges", []), data.get("current_level", "?")


def _parse_pending(raw_challenges: list) -> list:
    """返回未完成题目: [(code, title, difficulty, score), ...]"""
    result = []
    for ch in raw_challenges:
        if ch.get("flag_got_count", 0) < ch.get("flag_count", 1):
            result.append((
                ch.get("code",""),
                ch.get("title", ch.get("code","")),
                ch.get("difficulty","?"),
                ch.get("total_score", 0)
            ))
    return result


def fetch_challenges_with_poll() -> tuple:
    """轮询等待正式赛题出现，返回 (all_raw, level)"""
    deadline = time.time() + WAIT_FOR_CHALLENGES
    attempt  = 0
    while True:
        attempt += 1
        cprint(f"[平台] 第{attempt}次拉取题目...", C)
        try:
            raw, level = _fetch_raw()
            import master_log as ml
            ml.log_challenges_fetched(raw, level, attempt)
            pending = _parse_pending(raw)
            if pending:
                cprint(f"[平台] 关卡 {level}  共 {len(raw)} 题  "
                       f"待攻 {len(pending)} 题", C)
                return raw, level
        except Exception as e:
            cprint(f"[平台] 拉取异常: {e}", R)

        if time.time() >= deadline:
            cprint("[平台] 等待超时，未检测到正式赛题，退出。", R)
            sys.exit(0)
        cprint(f"[平台] 暂无正式赛题（答题模式可能未开启），"
               f"剩余 {deadline-time.time():.0f}s ...", Y)
        time.sleep(POLL_INTERVAL)


def print_unsolved_list(pending: list):
    cprint(f"\n{'─'*60}", Y)
    cprint(f"  待攻题目（共 {len(pending)} 题）", Y)
    cprint(f"{'─'*60}", Y)
    for i, (code, title, diff, score) in enumerate(pending, 1):
        cprint(f"  {i:2d}. [{diff:6s}] {score:4d}分  {title[:30]:<30}  ({code[:20]})", Y)
    cprint(f"{'─'*60}\n", Y)
    mlog.log_unsolved_list(pending)


# ── Hint 监听 ─────────────────────────────────────────────────

def _hint_listener(active_ids):
    cprint("[Hint] 格式：<code> <内容>  (q退出)", M)
    while True:
        try:    line = sys.stdin.readline().strip()
        except: break
        if not line or line.lower() == "q": break
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[0] in active_ids:
            inject_hint(parts[0], parts[1])
            cprint(f"[Hint注入] {parts[0]}: {parts[1]}", M)


# ── Worker 线程 ───────────────────────────────────────────────

def _worker(worker_id: int, task_queue: queue.Queue, retry_queue: queue.Queue,
            provider: str, session_summary: list,
            instance_semaphore: threading.Semaphore,
            solved_codes: set, locked_codes: set, color: str):
    """
    持续从队列取题，直到队列空为止。
    - level_locked → 放入 retry_queue，等待关卡解锁后重试
    - solved        → 加入 solved_codes
    """
    while True:
        try:
            idx, code, title, diff, score = task_queue.get_nowait()
        except queue.Empty:
            break

        # 跳过已解出或确认锁定的题
        if code in solved_codes:
            task_queue.task_done()
            continue

        cprint(f"[Worker-{worker_id}] 开始 → {title[:30]} ({code[:16]})", color)
        run(
            input_idx          = idx,
            challenge_code     = code,
            challenge_title    = title,
            provider           = provider,
            session_summary    = session_summary,
            color              = color,
            instance_semaphore = instance_semaphore,
        )

        # 检查结果
        last = next((s for s in reversed(session_summary)
                     if s["challenge_id"] == code), None)
        if last:
            if last.get("result") == "success":
                solved_codes.add(code)
                cprint(f"[✓] {title[:30]} 已解出!!！", G)
            elif last.get("level_locked") or last.get("result") == "level_locked":
                locked_codes.add(code)
                cprint(f"[锁] {title[:30]} 关卡未解锁，放入待解锁队列", Y)
                retry_queue.put((idx, code, title, diff, score))

        task_queue.task_done()
        time.sleep(THREAD_START_DELAY)


# ── 横幅 ──────────────────────────────────────────────────────

def _banner(skills, kb_entries, provider):
    cprint("\n" + "═"*62, M)
    cprint("  CTF Web Agent v1 — 智能渗透自动化系统", M)
    cprint("═"*62, M)
    cprint(f"  模式:    {PROVIDER_MAP[provider]['label']}", SLOT_COLOR)
    cprint(f"  Workers: {MAX_CONCURRENT_INSTANCES} 个并发（= 平台实例上限）", C)
    cprint(f"  超时:    每题 {int(20)}min", C)
    if skills:
        cprint(f"[技能库] {len(skills)} 个文件", SKILL_COLOR)
    else:
        cprint(f"[技能库] 空  ({SKILLS_BASE_PATH})", Y)
    cprint(f"[知识库] {len(kb_entries)} 个文件  ({KNOWLEDGE_BASE_PATH})",
           KB_COLOR if kb_entries else Y)
    if COMPETITION_MODE and MCP_SERVER_ENABLED:
        cprint(f"[MCP]    {MCP_SERVER_URL}", C)
    cprint(f"[子代理] {SUB_AGENT_MODEL}", C)
    cprint("═"*62 + "\n", M)


# ── 主程序 ────────────────────────────────────────────────────

def main():
    os.makedirs(LOG_ROOT, exist_ok=True)

    skills     = get_skills()
    kb_entries = list_kb_files()
    provider   = choose_provider()
    _banner(skills, kb_entries, provider)

    log_file = mlog.init(provider)
    cprint(f"[总日志] {log_file}", C)

    # ── 倒计时等待用户开启答题模式 ────────────────────────────
    if COMPETITION_MODE and MCP_SERVER_ENABLED:
        _countdown(WAIT_BEFORE_START, "请在此期间前往平台开启「答题模式」")

    # ── 获取题目 ───────────────────────────────────────────────
    if COMPETITION_MODE and MCP_SERVER_ENABLED:
        all_raw, level = fetch_challenges_with_poll()
        all_challenges = _parse_pending(all_raw)
    else:
        # 本地模式
        all_challenges = []
        cprint("请输入目标 URL（每行一个，done 结束）:", C)
        while len(all_challenges) < 20:
            try:    line = input(f"  目标 {len(all_challenges)+1}: ").strip()
            except EOFError: break
            if line.lower() == "done" or not line: break
            m   = re.search(r':(\d{4,5})(?:/|$)', line)
            cid = str(int(m.group(1))-9000) if m and 9001<=int(m.group(1))<=9200 else line
            all_challenges.append((cid, line, "?", 0))

    if not all_challenges:
        cprint("无待攻题目，退出。", R); sys.exit(0)

    print_unsolved_list(all_challenges)

    # ── 初始化调度结构 ─────────────────────────────────────────
    session_summary    = []
    solved_codes       = set()
    locked_codes       = set()   # 关卡未解锁的题目
    instance_semaphore = threading.Semaphore(MAX_CONCURRENT_INSTANCES)
    SLOT_SECONDS       = 20 * 60   # 每槽 20 分钟

    active_ids = {c[0] for c in all_challenges}
    threading.Thread(target=_hint_listener, args=(active_ids,), daemon=True).start()

    total_start = time.time()
    slot_idx    = 0

    # ── 20 分钟槽轮换主循环 ────────────────────────────────────
    while True:
        pending = [c for c in all_challenges if c[0] not in solved_codes]
        if not pending:
            cprint("\n🎉 所有题目已解出！", G)
            break

        slot_idx += 1
        slot_start = time.time()
        slot_end   = slot_start + SLOT_SECONDS
        end_str    = datetime.fromtimestamp(slot_end).strftime("%H:%M:%S")

        # 本槽主代理：DeepSeek/GLM 轮换
        slot_provider = choose_provider() 
        cprint(f"\n{'─'*60}", SLOT_COLOR)
        cprint(f"  槽 {slot_idx}  [{slot_provider.upper()}]  截止 {end_str}  "
               f"待攻 {len(pending)} 题  "
               f"已解 {len(solved_codes)} 题  "
               f"锁定 {len(locked_codes)} 题", SLOT_COLOR)
        cprint(f"{'─'*60}\n", SLOT_COLOR)

        print_unsolved_list(pending)

        # 本槽的任务队列
        task_queue  = queue.Queue()
        retry_queue = queue.Queue()

        # 锁定题目：如果本槽已解出的题数有增长，解锁条件可能满足，放回主队列重试
        newly_unlocked = [c for c in all_challenges
                          if c[0] in locked_codes and len(solved_codes) > 0]
        if newly_unlocked:
            locked_codes -= {c[0] for c in newly_unlocked}
            pending = pending + newly_unlocked
            cprint(f"[解锁] 尝试重试 {len(newly_unlocked)} 道之前锁定的题目", C)

        for i, (code, title, diff, score) in enumerate(pending):
            task_queue.put((i+1, code, title, diff, score))

        # 启动本槽 Workers（时间到自动结束）
        stop_event = threading.Event()
        threading.Timer(SLOT_SECONDS, stop_event.set).start()

        workers = []
        for w_id in range(MAX_CONCURRENT_INSTANCES):
            color = THREAD_COLORS[w_id % len(THREAD_COLORS)]
            t = threading.Thread(
                target=_worker,
                args=(w_id+1, task_queue, retry_queue, slot_provider,
                      session_summary, instance_semaphore,
                      solved_codes, locked_codes, color),
                daemon=True,
                name=f"W{slot_idx}-{w_id+1}"
            )
            workers.append(t)

        cprint(f"🚀 槽{slot_idx} 启动 {MAX_CONCURRENT_INSTANCES} 个 Worker", C)
        for w in workers:
            w.start()
            time.sleep(THREAD_START_DELAY)

        task_queue.join()
        stop_event.set()
        for w in workers:
            w.join(timeout=5)

        elapsed_slot = round(time.time() - slot_start, 0)
        new_solved   = sum(1 for s in session_summary
                           if s.get("result") == "success")
        cprint(f"\n槽{slot_idx} 结束  耗时{elapsed_slot:.0f}s  "
               f"总解出 {new_solved}/{len(all_challenges)} 题", SLOT_COLOR)

        # 刷新题目列表（可能解锁了新关卡）
        if COMPETITION_MODE and MCP_SERVER_ENABLED:
            try:
                new_raw, _ = _fetch_raw()
                new_all    = _parse_pending(new_raw)
                known      = {c[0] for c in all_challenges}
                added      = [c for c in new_all if c[0] not in known]
                if added:
                    all_challenges.extend(added)
                    active_ids.update(c[0] for c in added)
                    cprint(f"[刷新] 发现 {len(added)} 道新题", G)
            except Exception as e:
                cprint(f"[刷新] 题目列表刷新失败: {e}", Y)

        # 如果还有未解题目且未超总时长，继续下一槽
        remaining_pending = [c for c in all_challenges if c[0] not in solved_codes]
        if not remaining_pending:
            cprint("\n🎉 所有题目已解出！", G)
            break

    # ── 最终汇总 ───────────────────────────────────────────────
    total_elapsed  = round(time.time() - total_start, 1)
    total_main_tok = sum(s.get("tokens",0) for s in session_summary)
    total_sub_tok  = sum(s.get("sub_agent_tokens",0) for s in session_summary)

    mlog.log_session_end(len(solved_codes), len(all_challenges),
                         total_elapsed, total_main_tok, total_sub_tok)

    cprint("\n" + "═"*62, M)
    cprint(f"  最终汇总  总耗时 {total_elapsed}s  "
           f"解出 {len(solved_codes)}/{len(all_challenges)} 题", M)
    cprint("═"*62, M)

    # 按题目聚合最佳结果
    final = {}
    for s in session_summary:
        cid = s["challenge_id"]
        if cid not in final or s["result"] == "success":
            final[cid] = s

    for cid, s in sorted(final.items(), key=lambda x: x[1]["result"]!="success"):
        color   = G if s["result"] == "success" else R
        kb_info = "+".join(s.get("kb_files",[])) if s.get("kb_injected") else "无"
        cprint(f"  {s.get('title','')[:22]:<22}  {s['result']:<12}"
               f"  flag={str(s['flag'])[:30]:<30}"
               f"  {s['elapsed']}s  {s['tokens']}tok  KB={kb_info}", color)

    cprint(f"\n  Token: 主{total_main_tok} + 子{total_sub_tok} = {total_main_tok+total_sub_tok}", M)
    cprint(f"  总日志: {mlog._log_file}", M)
    cprint(f"  日志目录: {LOG_ROOT}", M)
    cprint("═"*62, M)


if __name__ == "__main__":
    main()