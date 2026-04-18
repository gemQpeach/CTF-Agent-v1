# stop_all.py
import platform_client

data = platform_client.list_challenges()
for ch in data.get('challenges', []):
    code = ch.get('code')
    # 平台不直接告诉你实例是否在跑，直接尝试停止，失败忽略
    try:
        r = platform_client.stop_challenge(code)
        print(f"停止 {ch['title']} ({code}): {r.get('message','')}")
    except Exception as e:
        print(f"跳过 {code}: {e}")