import requests

BASE_URL = "http://10.0.162.112:80"

PATHS = [
    "/.git/HEAD",
    "/.env",
    "/backup.zip",
    "/api/swagger.json",
    "/api/v1/users",
    "/admin",
    "/actuator/env",
    "/docs",
    "/redoc",
    "/openapi.json"
]

def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    for path in PATHS:
        url = BASE_URL + path
        try:
            resp = session.get(url, timeout=10, verify=False)
            snippet = resp.text[:200].strip() if resp.text else "[No Content]"
            print(f"[{resp.status_code}] {url} -> {snippet}")
        except requests.exceptions.RequestException as e:
            print(f"[ERR] {url} -> {e}")

if __name__ == "__main__":
    main()