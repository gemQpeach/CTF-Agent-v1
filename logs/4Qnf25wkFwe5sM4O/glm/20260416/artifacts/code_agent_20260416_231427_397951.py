import requests
import re

BASE_URL = "http://10.0.162.112:80"

PATHS = [
    "/",
    "/index.html",
    "/index.php",
    "/login",
    "/admin",
    "/flag",
    "/robots.txt",
    "/sitemap.xml",
    "/js/app.js",
    "/js/main.js",
    "/static/js/app.js",
    "/static/js/main.js",
    "/script.js",
    "/app.js",
    "/main.js",
    "/api",
    "/api/flag",
    "/api/v1",
    "/debug",
    "/console",
    "/source",
    "/.git",
    "/.env",
    "/config.js",
    "/config.json",
    "/package.json",
]

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    for path in PATHS:
        url = BASE_URL + path
        try:
            resp = session.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.text.strip()) > 0:
                print(f"\n{'='*80}")
                print(f"[+] URL: {url} | Status: {resp.status_code} | Length: {len(resp.text)}")
                print(f"{'='*80}")
                print(resp.text)

                # Extract and print JavaScript content specifically
                js_scripts = re.findall(r'<script[^>]*>(.*?)</script>', resp.text, re.DOTALL)
                if js_scripts:
                    print(f"\n{'~'*80}")
                    print(f"[JS EXTRACTED] Found {len(js_scripts)} <script> block(s):")
                    print(f"{'~'*80}")
                    for i, script in enumerate(js_scripts):
                        if script.strip():
                            print(f"\n--- Script Block {i+1} ---")
                            print(script.strip())

                # Extract src attributes from script tags
                js_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', resp.text)
                if js_srcs:
                    print(f"\n{'~'*80}")
                    print(f"[JS SRC] Found external script(s): {js_srcs}")
                    print(f"{'~'*80}")
                    for src in js_srcs:
                        if not src.startswith("http"):
                            src_url = BASE_URL + ("/" if not src.startswith("/") else "") + src
                        else:
                            src_url = src
                        try:
                            js_resp = session.get(src_url, timeout=10)
                            if js_resp.status_code == 200:
                                print(f"\n--- External JS: {src_url} ---")
                                print(js_resp.text)
                        except Exception as e:
                            print(f"[-] Failed to fetch {src_url}: {e}")

                # Look for flag patterns
                flags = re.findall(r'flag\{[^}]+\}|CTF\{[^}]+\}|ctf\{[^}]+\}', resp.text, re.IGNORECASE)
                if flags:
                    print(f"\n[!!!] FLAG FOUND: {flags}")

                # Look for interesting hidden content in comments
                comments = re.findall(r'<!--(.*?)-->', resp.text, re.DOTALL)
                if comments:
                    print(f"\n[HTML COMMENTS]:")
                    for c in comments:
                        print(c.strip())

            elif resp.status_code != 404:
                print(f"[*] URL: {url} | Status: {resp.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"[-] Error accessing {url}: {e}")

if __name__ == "__main__":
    main()