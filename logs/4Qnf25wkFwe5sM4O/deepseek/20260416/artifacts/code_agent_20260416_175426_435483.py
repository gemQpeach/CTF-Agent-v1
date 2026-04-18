import requests

BASE_URL = "http://10.0.162.112:80"
PATHS = [
    "/.git/HEAD", "/.env", "/backup.zip", "/admin", "/api/v1/users",
    "/actuator/env", "/console", "/phpinfo.php", "/flag", "/flag.txt",
    "/readme.md", "/config", "/config.json", "/api/docs", "/docs",
    "/redoc", "/openapi.json"
]

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    })

    for path in PATHS:
        url = f"{BASE_URL.rstrip('/')}{path}"
        try:
            resp = session.get(url, timeout=10, allow_redirects=False)
            status = resp.status_code
            content = resp.text
            
            print(f"[{status}] {url}")
            
            if "flag{" in content or "FLAG{" in content or "ctf{" in content:
                print(f"  [+] FLAG FOUND in response: {content.strip()}")
            elif status in [200, 301, 302, 403]:
                preview = content.strip()[:150].replace('\n', ' ')
                if preview:
                    print(f"  Content: {preview}")
                    
        except requests.exceptions.RequestException as e:
            print(f"[ERR] {url} - {e}")

if __name__ == "__main__":
    main()