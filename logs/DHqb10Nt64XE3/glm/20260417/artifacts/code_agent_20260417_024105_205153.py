import requests
from urllib.parse import urljoin

TARGET_BASE = "http://10.0.162.114:80"
PATHS = [
    "/",
    "/login.php",
    "/auth.php",
    "/vault.php",
    "/admin.php",
    "/robots.txt",
    "/.git/HEAD",
    "/.env",
]

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    for path in PATHS:
        url = urljoin(TARGET_BASE, path)
        print("=" * 80)
        print(f"[+] Requesting: {url}")
        print("=" * 80)
        try:
            resp = session.get(url, timeout=10, allow_redirects=True)
            print(f"    Status Code : {resp.status_code}")
            print(f"    Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
            print(f"    Content-Length: {len(resp.content)} bytes")
            print(f"    Final URL   : {resp.url}")
            print("-" * 80)
            print(resp.text)
            print("-" * 80)
        except requests.exceptions.RequestException as e:
            print(f"    [!] Error: {e}")
        print()

if __name__ == "__main__":
    main()