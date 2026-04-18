import requests
import re
from html.parser import HTMLParser

TARGET_URL = "http://localhost:8080"
LOGIN_URL = f"{TARGET_URL}/login"
USERNAME = "admin"
PASSWORD = "admin"

PREFERENCE_PATHS = [
    "/preferences",
    "/settings",
    "/api/preferences",
    "/api/settings",
    "/user/preferences",
    "/user/settings",
    "/profile",
    "/api/user/preferences",
    "/api/user/settings",
    "/update_prefs",
    "/api/v1/preferences",
    "/api/v1/settings"
]

class HTMLCommentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.comments = []
        self.hidden_inputs = []
        self.scripts = []
        self.current_script = None

    def handle_comment(self, data):
        self.comments.append(data.strip())

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "input" and attrs_dict.get("type", "").lower() == "hidden":
            self.hidden_inputs.append(attrs_dict)
        elif tag == "script":
            self.current_script = ""
            if "src" in attrs_dict:
                self.scripts.append(f"SRC: {attrs_dict['src']}")

    def handle_data(self, data):
        if self.current_script is not None:
            self.current_script += data

    def handle_endtag(self, tag):
        if tag == "script" and self.current_script is not None:
            if self.current_script.strip():
                self.scripts.append(self.current_script.strip())
            self.current_script = None

def analyze_html(html_content):
    parser = HTMLCommentParser()
    try:
        parser.feed(html_content)
    except Exception as e:
        print(f"[-] HTML parsing error: {e}")
    
    print("\n[+] Hidden Inputs Found:")
    for inp in parser.hidden_inputs:
        print(f"    Name: {inp.get('name')}, Value: {inp.get('value')}")
        
    print("\n[+] HTML Comments Found:")
    for comment in parser.comments:
        print(f"    {comment}")
        
    print("\n[+] Inline Scripts Found:")
    for script in parser.scripts:
        if len(script) > 500:
            print(f"    {script[:500]}...")
        else:
            print(f"    {script}")

    api_endpoints = set(re.findall(r'(?:"|\')\s*(\/api\/[a-zA-Z0-9_\/-]+)\s*(?:"|\')', html_content))
    api_endpoints.update(re.findall(r'(?:"|\')\s*(\/[a-zA-Z0-9_\/-]+\/(?:prefs|settings|preferences|config))\s*(?:"|\')', html_content))
    
    if api_endpoints:
        print("\n[+] Potential API Endpoints Extracted:")
        for ep in api_endpoints:
            print(f"    {ep}")
            
    return parser.hidden_inputs, api_endpoints

def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    print(f"[*] Fetching login page: {LOGIN_URL}")
    try:
        resp = session.get(LOGIN_URL, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[-] Failed to fetch login page: {e}")
        return

    hidden_inputs, extracted_endpoints = analyze_html(resp.text)
    
    login_data = {inp.get('name'): inp.get('value') for inp in hidden_inputs if inp.get('name')}
    login_data.update({"username": USERNAME, "password": PASSWORD})
    
    csrf_token = login_data.get('csrf_token') or login_data.get('token') or login_data.get('csrf')
    if csrf_token:
        print(f"\n[*] Detected CSRF Token: {csrf_token}")

    print(f"\n[*] Attempting login with {USERNAME}:{PASSWORD}")
    try:
        login_resp = session.post(LOGIN_URL, data=login_data, timeout=10, allow_redirects=True)
        if "logout" in login_resp.text.lower() or "dashboard" in login_resp.text.lower() or login_resp.status_code == 200:
            print("[+] Login likely successful!")
        else:
            print("[-] Login might have failed, but continuing with session cookies...")
    except Exception as e:
        print(f"[-] Login request failed: {e}")
        return

    all_paths = list(set(PREFERENCE_PATHS + list(extracted_endpoints)))
    
    print(f"\n[*] Scanning {len(all_paths)} preference/settings paths for deserialization vectors...")
    for path in all_paths:
        url = f"{TARGET_URL}{path}" if path.startswith('/') else path
        try:
            r = session.get(url, timeout=5)
            content_type = r.headers.get("Content-Type", "")
            
            if r.status_code == 200 and ("json" in content_type or "application/octet-stream" in content_type or "java" in content_type):
                print(f"\n[+] Hit: {url} (Status: {r.status_code}, Type: {content_type})")
                print(f"    Response: {r.text[:500]}")
                
                if "serial" in r.text.lower() or "rO0AB" in r.text or "O:4:" in r.text:
                    print("[!] WARNING: Potential serialized object detected!")
                    
            elif r.status_code == 200 and "html" in content_type:
                if "preference" in r.text.lower() or "setting" in r.text.lower() or "deseriali" in r.text.lower():
                    print(f"\n[+] Interesting HTML Hit: {url} (Status: {r.status_code})")
                    if "deseriali" in r.text.lower():
                         print("[!] WARNING: HTML page mentions deserialization!")
                         
            elif r.status_code != 404:
                print(f"[*] Found {url} (Status: {r.status_code})")
                
        except requests.exceptions.Timeout:
            print(f"[-] Timeout accessing {url}")
        except requests.exceptions.RequestException:
            pass

if __name__ == "__main__":
    main()