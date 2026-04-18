#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import platform_client
from config import COMPETITION_MODE, MCP_SERVER_ENABLED

def check_platform_status():
    if not (COMPETITION_MODE and MCP_SERVER_ENABLED):
        print("错误: 配置文件中未开启竞赛模式或 MCP 服务器。")
        return

    print("正在从平台获取题目列表...\n")
    try:
        data = platform_client.list_challenges()
        challenges = data.get("challenges", [])
        
        if not challenges:
            print("平台未返回任何题目。")
            return

        solved = []
        pending = []

        for ch in challenges:
            code = ch.get("code")
            title = ch.get("title")
            got = ch.get("flag_got_count", 0)
            total = ch.get("flag_count", 0)
            
            # 判断逻辑：如果拿到的 flag 数量等于总数，则视为已完成（关闭）
            if got >= total and total > 0:
                solved.append(f"[{code}] {title} ({got}/{total})")
            else:
                pending.append(f"[{code}] {title} ({got}/{total})")

        # 打印统计结果
        print("=" * 50)
        print(f"统计概览: 总计 {len(challenges)} 题 | 已解出 {len(solved)} 题 | 待攻克 {len(pending)} 题")
        print("=" * 50)

        print("\n✅ 已解出（已关闭）的题目:")
        if solved:
            for line in solved:
                print(f"  \033[92m{line}\033[0m")
        else:
            print("  暂无")

        print("\n🚀 待处理（开启中）的题目:")
        if pending:
            for line in pending:
                print(f"  \033[93m{line}\033[0m")
        else:
            print("  恭喜！所有题目已解完。")
            
    except Exception as e:
        print(f"获取状态失败: {e}")

if __name__ == "__main__":
    check_platform_status()