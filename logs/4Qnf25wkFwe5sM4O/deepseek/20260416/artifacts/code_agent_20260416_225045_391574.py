import requests
import re
import json

BASE_URL = "http://10.0.162.112:80"

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    print(f"[*] Fetching homepage: {BASE_URL}")
    try:
        resp = session.get(BASE_URL)
        html = resp.text
        
        print("\n[+] Extracted JavaScript Code:")
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
        js_content = ""
        for script in scripts:
            if script.strip():
                print(script.strip())
                js_content += script.strip() + "\n"
                
        print("\n[+] Extracted Form Details:")
        forms = re.findall(r'<form[^>]*>(.*?)</form>', html, re.DOTALL | re.IGNORECASE)
        form_data = {}
        for form in forms:
            print(f"Form HTML: {form.strip()[:500]}")
            inputs = re.findall(r'<input[^>]*name=["\']([^"\']+)["\'][^>]*>', form, re.IGNORECASE)
            for inp_name in inputs:
                form_data[inp_name] = "test"
                print(f"  Detected Input Name: {inp_name}")

        print("\n[*] Attempting to simulate form submission to /jobs...")
        
        # Attempt 1: Submit as Form Data based on extracted inputs
        if form_data:
            print(f"[*] Trying POST /jobs as Form Data with {form_data}...")
            resp_form = session.post(f"{BASE_URL}/jobs", data=form_data)
            print(f"Status: {resp_form.status_code}, Response: {resp_form.text[:500]}")
        
        # Attempt 2: Submit as JSON (common in fetch API implementations)
        print("[*] Trying POST /jobs as JSON...")
        json_payload = form_data if form_data else {"action": "submit"}
        resp_json = session.post(f"{BASE_URL}/jobs", json=json_payload)
        print(f"Status: {resp_json.status_code}, Response: {resp_json.text[:500]}")

        # Attempt 3: Analyze JS for specific fetch payloads
        if "fetch" in js_content:
            print("\n[+] Analyzing fetch calls in JS...")
            fetch_matches = re.findall(r'fetch\(\s*[\'"](.*?)[\'"]\s*,\s*(\{.*?\})\s*\)', js_content, re.DOTALL)
            for url_match, opts_match in fetch_matches:
                print(f"Found fetch URL: {url_match}")
                print(f"Found fetch Options: {opts_match.strip()}")
                
                headers_match = re.search(r"headers\s*:\s*\{(.*?)\}", opts_match, re.DOTALL)
                body_match = re.search(r"body\s*:\s*JSON\.stringify\(\{(.*?)\}\)", opts_match, re.DOTALL)
                
                req_headers = {}
                if headers_match:
                    header_pairs = re.findall(r"['\"](.*?)['\"]\s*:\s*['\"](.*?)['\"]", headers_match.group(1))
                    req_headers = {k: v for k, v in header_pairs}
                    print(f"Extracted Headers: {req_headers}")
                
                if body_match:
                    body_vars = re.findall(r"['\"](.*?)['\"]\s*:", body_match.group(1))
                    dynamic_payload = {var: "test_value" for var in body_vars}
                    print(f"[*] Trying dynamically generated JSON payload: {dynamic_payload}")
                    resp_dynamic = session.post(f"{BASE_URL}{url_match}", headers=req_headers, json=dynamic_payload)
                    print(f"Status: {resp_dynamic.status_code}, Response: {resp_dynamic.text[:500]}")

        print("\n[*] Enumerating common paths for more clues...")
        paths_to_check = [
            '/robots.txt', '/sitemap.xml', '/api', '/api/v1', '/swagger.json', 
            '/admin', '/login', '/flag', '/source', '/js/app.js', '/index.js',
            '/jobs', '/api/jobs', '/submit', '/run'
        ]
        
        for path in paths_to_check:
            url = f"{BASE_URL}{path}"
            try:
                r = session.get(url)
                if r.status_code != 404:
                    print(f"[+] Found {url} - Status: {r.status_code}")
                    if r.status_code == 200 and len(r.text) < 1000:
                        print(f"    Content: {r.text[:200]}")
            except requests.RequestException:
                pass

    except requests.RequestException as e:
        print(f"[-] Error connecting to {BASE_URL}: {e}")

if __name__ == "__main__":
    main()