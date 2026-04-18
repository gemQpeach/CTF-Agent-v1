import requests
import urllib3

# 禁用未验证HTTPS请求的警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET_URL = "http://10.0.162.114:80"

PATHS = [
    # 备份文件
    "backup.tar.gz", "backup.tar", "backup.sql", "backup.zip", "backup.7z", "backup.rar",
    # 配置文件
    "config.php", "config.inc.php", "configuration.php", "settings.php",
    # 敏感文件
    ".gitignore", ".htaccess", "phpinfo.php", "info.php", "test.php",
    # 其他
    "install.php", "upgrade.php", "readme.md", "CHANGELOG.md"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    base_url = TARGET_URL.rstrip('/')
    found_items = []
    
    print(f"[*] Starting scan on {base_url}\n")
    
    for path in PATHS:
        url = f"{base_url}/{path}"
        try:
            resp = session.get(url, timeout=10, verify=False, allow_redirects=False)
            
            # 200 OK 表示文件存在且可访问
            # 403 Forbidden 表示文件存在但无权限访问
            # 301/302 可能是重定向，也值得关注
            if resp.status_code == 200:
                print(f"[+] FOUND (200 OK): {url}")
                found_items.append(url)
                # 如果是文本文件且较小，打印部分内容以供检查
                content_type = resp.headers.get('Content-Type', '')
                if 'text' in content_type and len(resp.content) < 1024:
                    print(f"    [Content Snippet]: {resp.text[:200]}")
            elif resp.status_code == 403:
                print(f"[!] FORBIDDEN (403): {url}")
                found_items.append(url)
            elif resp.status_code in [301, 302]:
                location = resp.headers.get('Location', 'N/A')
                print(f"[*] REDIRECT ({resp.status_code}): {url} -> {location}")
                
        except requests.exceptions.Timeout:
            print(f"[-] TIMEOUT: {url}")
        except requests.exceptions.ConnectionError:
            print(f"[-] CONNECTION ERROR: {url}")
        except requests.exceptions.RequestException as e:
            print(f"[-] ERROR accessing {url}: {e}")
            
    print("\n[*] Scan completed.")
    if found_items:
        print("[*] Summary of found/restricted items:")
        for item in found_items:
            print(f"    - {item}")
    else:
        print("[*] No items found from the list.")

if __name__ == "__main__":
    main()