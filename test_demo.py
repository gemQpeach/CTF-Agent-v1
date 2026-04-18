import platform_client
# 1. 尝试获取列表
print("尝试获取列表...")
challenges = platform_client.list_challenges()
print(challenges)

# 2. 尝试只启动一个题目，看是否能返回有效 URL
code = challenges['challenges'][0]['code']
print(f"尝试启动 {code}...")
res = platform_client.start_challenge(code)
print(f"启动结果: {res}")