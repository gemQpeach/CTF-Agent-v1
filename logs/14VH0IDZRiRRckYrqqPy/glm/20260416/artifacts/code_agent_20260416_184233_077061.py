import requests

BASE_URL = "http://10.0.162.113:80"
USERNAME = "rootadmin"
PASSWORD = "docpass"
PATHS = ["/preferences", "/import", "/upload", "/dashboard"]

def main():
    session = requests.Session()
    
    # Add a common User-Agent to avoid basic blocks
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    # Step 1: Login
    login_url = f"{BASE_URL}/login"
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }

    try:
        print(f"[*] Attempting to login at {login_url} with credentials {USERNAME}/{PASSWORD}")
        login_resp = session.post(login_url, data=login_data, allow_redirects=True)
        print(f"[*] Login Status Code: {login_resp.status_code}")
        print(f"[*] Cookies after login: {dict(session.cookies)}")
        print("=" * 80)
    except requests.RequestException as e:
        print(f"[!] Login request failed: {e}")
        return

    # Step 2-5: Visit target paths
    for path in PATHS:
        target_url = f"{BASE_URL}{path}"
        print(f"[*] Accessing {target_url}...")
        
        try:
            resp = session.get(target_url)
            print(f"[*] Status Code: {resp.status_code}")
            
            print("\n[+] Response Headers:")
            for key, value in resp.headers.items():
                print(f"    {key}: {value}")
                
            print("\n[+] Response HTML Content:")
            print(resp.text)
            
        except requests.RequestException as e:
            print(f"[!] Failed to access {target_url}: {e}")
            
        print("=" * 80)

if __name__ == "__main__":
    main()