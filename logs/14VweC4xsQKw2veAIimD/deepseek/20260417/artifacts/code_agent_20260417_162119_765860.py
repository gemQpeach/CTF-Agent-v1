import socket
import requests
import urllib3

# 禁用不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 目标配置
TARGET_IP = "10.0.162.114"
PORTS = [22, 80, 443, 8080, 8000, 3000, 5000, 6379, 3306, 5432, 27017]
PATHS = ['/', '/login', '/admin', '/api', '/flag', '/robots.txt', '/console']
TIMEOUT = 3

def check_port_open(ip, port):
    """使用 socket 快速检测端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(TIMEOUT)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except Exception:
        return False

def scan_http_services(ip, port, session):
    """使用 requests.Session 探测 HTTP 服务并遍历路径"""
    open_urls = []
    for scheme in ['http', 'https']:
        base_url = f"{scheme}://{ip}:{port}"
        try:
            # 使用 session 发起请求，维护认证状态/Cookie
            response = session.get(base_url, timeout=TIMEOUT, verify=False, allow_redirects=False)
            if response.status_code < 500:
                print(f"[+] 发现 HTTP 服务: {base_url} (状态码: {response.status_code}, 长度: {len(response.content)})")
                open_urls.append(base_url)
                break # 如果 http 成功则不再尝试 https
        except requests.exceptions.RequestException:
            continue
            
    for base_url in open_urls:
        for path in PATHS:
            url = base_url.rstrip('/') + path
            try:
                res = session.get(url, timeout=TIMEOUT, verify=False, allow_redirects=False)
                if res.status_code != 404:
                    print(f"  [>] {url} -> 状态码: {res.status_code}, 长度: {len(res.content)}")
                    # 尝试提取可能的 flag
                    if 'flag{' in res.text or 'ctf{' in res.text:
                        print(f"  [!!!] 发现 Flag: {res.text}")
            except requests.exceptions.RequestException:
                pass

def main():
    print(f"[*] 开始扫描目标: {TARGET_IP}")
    print(f"[*] 扫描端口列表: {PORTS}\n")
    
    # 初始化 Session 以维护认证状态
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })

    open_ports = []
    
    # 第一阶段：TCP 端口快速扫描
    for port in PORTS:
        if check_port_open(TARGET_IP, port):
            print(f"[+] 端口 {port} 开放")
            open_ports.append(port)
        else:
            print(f"[-] 端口 {port} 关闭")

    print(f"\n[*] 开放端口: {open_ports}")
    print("[*] 开始 HTTP 服务探测及路径遍历...\n")

    # 第二阶段：对开放端口进行 HTTP 探测和路径遍历
    for port in open_ports:
        scan_http_services(TARGET_IP, port, session)

    print("\n[*] 扫描完成")

if __name__ == "__main__":
    main()