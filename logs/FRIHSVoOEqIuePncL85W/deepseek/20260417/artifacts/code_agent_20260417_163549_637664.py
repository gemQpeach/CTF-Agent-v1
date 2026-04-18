import requests
import os
import sys

# ================= 配置区域 =================
BASE_URL = "http://example.com"  # 请修改为实际目标 URL
UPLOAD_PATHS = [
    "/upload",
    "/api/upload",
    "/file/upload",
    "/upload.php",
    "/api/v1/upload",
    "/profile/upload"
]
FILE_NAME = "test_upload.txt"
FILE_CONTENT = "test document content"
# ============================================

def main():
    # 1. 创建本地测试文件
    try:
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write(FILE_CONTENT)
        print(f"[*] 本地测试文件 '{FILE_NAME}' 创建成功")
    except IOError as e:
        print(f"[-] 创建本地文件失败: {e}")
        return

    # 2. 初始化 Session 以维护认证状态
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    # 3. 访问首页或登录接口以获取初始 Cookie/Session 状态
    try:
        print(f"[*] 正在访问 {BASE_URL} 以初始化 Session...")
        session.get(BASE_URL, timeout=5)
    except requests.exceptions.RequestException as e:
        print(f"[!] 无法连接到 {BASE_URL}: {e}")

    # 4. 遍历路径列表尝试上传
    for path in UPLOAD_PATHS:
        target_url = BASE_URL.rstrip("/") + path
        print(f"\n[*] 尝试上传至: {target_url}")
        
        try:
            with open(FILE_NAME, "rb") as f:
                files = {"file": (FILE_NAME, f, "text/plain")}
                # 增加 data 字段以防某些接口需要额外的表单参数
                data = {"submit": "upload"}
                
                resp = session.post(target_url, files=files, data=data, timeout=5)
                
                print(f"    [+] 状态码: {resp.status_code}")
                if resp.status_code != 404:
                    print(f"    [+] 响应内容: {resp.text[:500]}")
                    
                    # 简单判断是否成功
                    if resp.status_code == 200 and ("success" in resp.text.lower() or "upload" in resp.text.lower()):
                        print(f"[+] 可能成功上传至: {target_url}")
                        
        except requests.exceptions.Timeout:
            print(f"    [-] 请求超时 (>5s)")
        except requests.exceptions.ConnectionError:
            print(f"    [-] 连接错误")
        except requests.exceptions.RequestException as e:
            print(f"    [-] 请求异常: {e}")

    # 清理本地测试文件
    try:
        if os.path.exists(FILE_NAME):
            os.remove(FILE_NAME)
            print(f"\n[*] 已清理本地测试文件 '{FILE_NAME}'")
    except OSError as e:
        print(f"\n[-] 清理文件失败: {e}")

if __name__ == "__main__":
    main()