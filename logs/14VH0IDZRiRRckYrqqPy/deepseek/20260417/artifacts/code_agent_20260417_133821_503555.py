import requests
import re
from urllib.parse import urljoin

TARGET_URL = "http://10.0.162.113:80"

PATHS = [
    "/",
    "/login",
    "/register",
    "/signup",
    "/index.html",
    "/index.php",
    "/admin",
    "/dashboard",
    "/flag",
    "/robots.txt",
    "/sitemap.xml",
    "/.hidden",
    "/config",
    "/api",
    "/api/users",
    "/api/flag",
    "/debug",
    "/phpinfo.php",
    "/info.php",
    "/test",
    "/backup",
    "/.git",
    "/.env",
    "/swagger",
    "/api-docs",
    "/console",
    "/shell",
    "/cmd",
    "/exec",
    "/search",
    "/upload",
    "/download",
    "/profile",
    "/user",
    "/users",
    "/reset",
    "/forgot",
    "/forgot-password",
    "/change-password",
    "/logout",
    "/secret",
    "/private",
    "/public",
    "/static",
    "/assets",
    "/css",
    "/js",
    "/images",
    "/tmp",
    "/log",
    "/logs",
    "/error",
    "/404",
    "/500",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}


def extract_html_comments(html):
    pattern = r'<!--(.*?)-->'
    return re.findall(pattern, html, re.DOTALL)


def extract_hidden_fields(html):
    pattern = r'<input[^>]*type=["\']hidden["\'][^>]*>'
    return re.findall(pattern, html, re.IGNORECASE)


def extract_all_inputs(html):
    pattern = r'<input[^>]*>'
    return re.findall(pattern, html, re.IGNORECASE)


def extract_forms(html):
    pattern = r'<form[^>]*>(.*?)</form>'
    return re.findall(pattern, html, re.IGNORECASE | re.DOTALL)


def extract_links(html, base_url):
    pattern = r'href=["\']([^"\']+)["\']'
    raw_links = re.findall(pattern, html, re.IGNORECASE)
    full_links = []
    for link in raw_links:
        full_links.append(urljoin(base_url, link))
    return full_links


def extract_scripts(html, base_url):
    pattern = r'src=["\']([^"\']*\.js[^"\']*)["\']'
    raw = re.findall(pattern, html, re.IGNORECASE)
    return [urljoin(base_url, r) for r in raw]


def extract_meta_tags(html):
    pattern = r'<meta[^>]+>'
    return re.findall(pattern, html, re.IGNORECASE)


def analyze_page(session, url):
    print(f"\n{'='*80}")
    print(f"[+] Fetching: {url}")
    print(f"{'='*80}")
    try:
        resp = session.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        print(f"[*] Status: {resp.status_code}")
        print(f"[*] Final URL: {resp.url}")
        print(f"[*] Content-Length: {len(resp.text)}")
        print(f"[*] Content-Type: {resp.headers.get('Content-Type', 'N/A')}")

        html = resp.text

        # Print full HTML if it's the main page
        if url.rstrip('/') == TARGET_URL.rstrip('/') or url.endswith('/login') or url.endswith('/'):
            print(f"\n{'─'*40} FULL HTML {'─'*40}")
            print(html)
            print(f"{'─'*40} END HTML {'─'*41}")

        # HTML Comments
        comments = extract_html_comments(html)
        if comments:
            print(f"\n[!] HTML Comments ({len(comments)}):")
            for c in comments:
                stripped = c.strip()
                if stripped:
                    print(f"    <!-- {stripped} -->")

        # Hidden Fields
        hidden = extract_hidden_fields(html)
        if hidden:
            print(f"\n[!] Hidden Fields ({len(hidden)}):")
            for h in hidden:
                print(f"    {h}")

        # All Inputs
        inputs = extract_all_inputs(html)
        if inputs:
            print(f"\n[*] All Input Fields ({len(inputs)}):")
            for inp in inputs:
                print(f"    {inp}")

        # Forms
        forms = extract_forms(html)
        if forms:
            print(f"\n[*] Forms ({len(forms)}):")
            for i, form in enumerate(forms):
                form_tag = re.search(r'<form[^>]*>', html, re.IGNORECASE | re.DOTALL)
                action = re.search(r'action=["\']([^"\']*)["\']', html, re.IGNORECASE)
                method = re.search(r'method=["\']([^"\']*)["\']', html, re.IGNORECASE)
                print(f"    Form #{i+1}:")
                if action:
                    print(f"      Action: {action.group(1)}")
                if method:
                    print(f"      Method: {method.group(1)}")
                form_inputs = extract_all_inputs(form)
                for fi in form_inputs:
                    print(f"      {fi}")

        # Links
        links = extract_links(html, url)
        if links:
            print(f"\n[*] Links ({len(links)}):")
            seen = set()
            for link in links:
                if link not in seen:
                    seen.add(link)
                    print(f"    {link}")

        # Scripts
        scripts = extract_scripts(html, url)
        if scripts:
            print(f"\n[*] External Scripts ({len(scripts)}):")
            for s in scripts:
                print(f"    {s}")

        # Meta Tags
        metas = extract_meta_tags(html)
        if metas:
            print(f"\n[*] Meta Tags ({len(metas)}):")
            for m in metas:
                print(f"    {m}")

        # Look for flag patterns
        flag_patterns = re.findall(r'flag\{[^}]+\}|CTF\{[^}]+\}|ctf\{[^}]+\}|FLAG\{[^}]+\}', html, re.IGNORECASE)
        if flag_patterns:
            print(f"\n[!!!] FLAGS FOUND:")
            for f in flag_patterns:
                print(f"    {f}")

        # Look for interesting strings
        interesting = re.findall(r'(?:password|secret|key|token|admin|flag|root|debug|config|private|hidden)\s*[:=]\s*["\']?([^\s"\'<>&]+)', html, re.IGNORECASE)
        if interesting:
            print(f"\n[!] Interesting Key-Value Pairs:")
            for val in interesting:
                print(f"    {val}")

        return html, resp.status_code

    except requests.exceptions.RequestException as e:
        print(f"[-] Error fetching {url}: {e}")
        return None, None


def check_path(session, base_url, path):
    url = urljoin(base_url, path)
    try:
        resp = session.get(url, headers=HEADERS, timeout=5, allow_redirects=False)
        if resp.status_code in [200, 301, 302, 401, 403]:
            print(f"  [{resp.status_code}] {url}")
            if resp.status_code == 200 and 'text/html' in resp.headers.get('Content-Type', ''):
                # Quick check for interesting content
                if re.search(r'flag\{|CTF\{|ctf\{|FLAG\{', resp.text, re.IGNORECASE):
                    print(f"    [!!!] FLAG FOUND IN RESPONSE!")
                    print(resp.text[:2000])
                if re.search(r'<form|<input|register|signup', resp.text, re.IGNORECASE):
                    print(f"    [*] Contains form/register content")
            return url, resp.status_code, resp.text
        return url, resp.status_code, None
    except requests.exceptions.RequestException:
        return url, None, None


def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    # Step 1: Analyze main page thoroughly
    print("[*] Phase 1: Deep analysis of main page")
    html, status = analyze_page(session, TARGET_URL)

    # Step 2: If there's a login page, also analyze it
    if html:
        login_links = re.findall(r'href=["\']([^"\']*(?:login|signin|auth)[^"\']*)["\']', html, re.IGNORECASE)
        for link in login_links:
            full_url = urljoin(TARGET_URL, link)
            analyze_page(session, full_url)

        register_links = re.findall(r'href=["\']([^"\']*(?:register|signup|create)[^"\']*)["\']', html, re.IGNORECASE)
        for link in register_links:
            full_url = urljoin(TARGET_URL, link)
            analyze_page(session, full_url)

    # Step 3: Directory/path enumeration
    print(f"\n{'='*80}")
    print("[*] Phase 2: Path enumeration")
    print(f"{'='*80}")

    found_pages = []
    for path in PATHS:
        url, status, content = check_path(session, TARGET_URL, path)
        if status in [200, 301, 302]:
            found_pages.append((url, status, content))

    # Step 4: Deep analyze all found HTML pages
    print(f"\n{'='*80}")
    print("[*] Phase 3: Deep analysis of discovered pages")
    print(f"{'='*80}")

    for url, status, content in found_pages:
        if content and status == 200:
            analyze_page(session, url)

    # Step 5: Check robots.txt specifically
    print(f"\n{'='*80}")
    print("[*] Phase 4: Checking robots.txt")
    print(f"{'='*80}")
    try:
        resp = session.get(urljoin(TARGET_URL, '/robots.txt'), headers=HEADERS, timeout=5)
        if resp.status_code == 200:
            print(resp.text)
            disallowed = re.findall(r'Disallow:\s*(.+)', resp.text, re.IGNORECASE)
            for d in disallowed:
                d = d.strip()
                if d:
                    print(f"\n[*] Checking disallowed path: {d}")
                    analyze_page(session, urljoin(TARGET_URL, d))
    except:
        pass

    print(f"\n{'='*80}")
    print("[*] Scan complete")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()