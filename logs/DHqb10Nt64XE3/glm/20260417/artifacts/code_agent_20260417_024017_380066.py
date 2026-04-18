import requests
from requests.exceptions import RequestException

BASE_URL = "http://10.0.162.114:80"
PATHS = ["/", "/index.html", "/login", "/index.php"]

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    })

    for path in PATHS:
        target_url = BASE_URL.rstrip("/") + path
        try:
            print(f"[*] Fetching: {target_url}")
            response = session.get(target_url, timeout=10)
            print(f"[*] Status Code: {response.status_code}")
            print(f"[*] HTML Content:\n{response.text}\n{'='*60}")
            if response.status_code == 200 and response.text.strip():
                break
        except RequestException as e:
            print(f"[-] Error fetching {target_url}: {e}")

if __name__ == "__main__":
    main()