import requests
from urllib.parse import urljoin

TARGET_URL = "http://10.0.162.113:80"

PATHS = [
    "/",
    "/login",
    "/index.html",
    "/index.php",
    "/signin",
    "/auth",
    "/admin",
    "/admin/login",
    "/user/login",
    "/portal",
    "/account/login",
    "/member/login",
]

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    })

    found_login_page = None

    for path in PATHS:
        full_url = urljoin(TARGET_URL, path)
        try:
            print(f"[*] Trying: {full_url}")
            response = session.get(full_url, timeout=10)
            
            if response.status_code == 200:
                text = response.text
                if "<form" in text.lower() and ("password" in text.lower() or "passwd" in text.lower()):
                    print(f"[+] Found login form at: {full_url}")
                    found_login_page = text
                    break
                elif path == "/" and not found_login_page:
                    found_login_page = text
            elif response.status_code in [301, 302]:
                redirect_url = response.headers.get('Location', '')
                print(f"[-] Redirect at {full_url} -> {redirect_url}")
                
        except requests.exceptions.RequestException as e:
            print(f"[!] Error requesting {full_url}: {e}")

    if found_login_page:
        print("\n" + "="*50)
        print("[+] Login Page HTML Source Code:")
        print("="*50)
        print(found_login_page)
    else:
        print("\n[-] No login page found in the provided path list.")

if __name__ == "__main__":
    main()