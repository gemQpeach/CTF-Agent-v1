import requests
import json

# ================= 配置区域 =================
BASE_URL = "http://example.com"  # 修改为实际目标地址
USERNAME = "admin"               # 修改为实际用户名
PASSWORD = "password"            # 修改为实际密码

# 需要遍历的路径列表
PATHS = [
    "/jobs"
]
# ============================================

def main():
    session = requests.Session()
    
    # 设置通用请求头
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    })
    
    # 尝试登录以维护认证状态
    login_url = f"{BASE_URL}/login"
    login_data = {"username": USERNAME, "password": PASSWORD}
    try:
        print(f"[*] Attempting to login at {login_url}...")
        login_resp = session.post(login_url, json=login_data)
        if login_resp.status_code == 200:
            print("[+] Login successful!")
        else:
            print(f"[-] Login failed with status code: {login_resp.status_code}")
    except Exception as e:
        print(f"[!] Login request error: {e}")

    # 遍历路径列表
    for path in PATHS:
        target_url = f"{BASE_URL}{path}"
        print(f"\n[*] Sending POST request to {target_url}...")
        
        try:
            # 发送POST请求，部分API可能需要空JSON体
            resp = session.post(target_url, json={})
            resp.raise_for_status()
            
            # 解析返回的JSON数据
            jobs_data = resp.json()
            
            # 检查是否为数组
            if isinstance(jobs_data, list):
                print(f"[+] Found {len(jobs_data)} job(s) in response.")
                
                for index, job in enumerate(jobs_data):
                    print(f"\n{'='*40}")
                    print(f"Job #{index + 1} Details:")
                    print(f"{'='*40}")
                    
                    # 打印所有字段
                    for key, value in job.items():
                        print(f"  {key}: {value}")
                    
                    # 特别关注 type 和 description 字段
                    print(f"\n[!] Highlighted Fields:")
                    print(f"  Type        : {job.get('type', 'N/A')}")
                    print(f"  Description : {job.get('description', 'N/A')}")
            else:
                # 如果返回的不是数组，直接格式化打印
                print("[*] Response is not a list. Raw JSON:")
                print(json.dumps(jobs_data, indent=2))
                
        except requests.exceptions.HTTPError as http_err:
            print(f"[-] HTTP error occurred: {http_err}")
        except json.JSONDecodeError:
            print(f"[-] Failed to parse JSON. Response text:\n{resp.text}")
        except Exception as err:
            print(f"[-] An error occurred: {err}")

if __name__ == "__main__":
    main()