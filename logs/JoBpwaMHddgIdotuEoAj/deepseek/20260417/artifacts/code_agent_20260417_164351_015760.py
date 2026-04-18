import requests
import re
from urllib.parse import urljoin

TARGET_URL = "http://10.0.162.113:80"
LOGIN_URL = f"{TARGET_URL}/login.php"
USERNAME = "admin"
PASSWORD = "admin123"

KEYWORDS = ["合同", "审批", "用户管理", "contract", "approve", "user", "admin", "manage", "list"]

PATHS = [
    "/",
    "/index.php",
    "/admin.php",
    "/dashboard.php",
    "/home.php",
    "/main.php",
    "/user.php",
    "/admin",
    "/user",
    "/manage.php"
]

def extract_links(html, base_url):
    hrefs = re.findall(r'href=["\'](.*?)["\']', html, re.IGNORECASE)
    srcs = re.findall(r'src=["\'](.*?)["\']', html, re.IGNORECASE)
    links = set()
    for link in hrefs + srcs:
        if link and not link.startswith(('#', 'javascript:', 'mailto:', 'data:', 'tel:')):
            full_url = urljoin(base_url, link)
            links.add(full_url)
    return links

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    })

    try:
        print(f"[*] Logging in to {LOGIN_URL} with {USERNAME}/{PASSWORD}...")
        login_data = {
            'username': USERNAME,
            'password': PASSWORD,
            'submit': 'Login'
        }
        
        # Try common username/password field names
        resp = session.post(LOGIN_URL, data=login_data, timeout=10)
        if "logout" not in resp.text.lower() and "welcome" not in resp.text.lower():
            login_data_alt = {
                'user': USERNAME,
                'pass': PASSWORD,
                'submit': 'Login'
            }
            resp = session.post(LOGIN_URL, data=login_data_alt, timeout=10)

        print(f"[*] Login Status Code: {resp.status_code}")
        
        all_links = set()
        all_links.update(extract_links(resp.text, resp.url))
        
        print(f"[*] Traversing predefined paths to discover more links...")
        for path in PATHS:
            url = f"{TARGET_URL}{path}"
            try:
                r = session.get(url, timeout=10)
                if r.status_code == 200 and len(r.text) > 100:
                    all_links.update(extract_links(r.text, url))
            except requests.RequestException:
                pass
            
        print(f"\n[+] Found {len(all_links)} unique links (href & src):")
        for link in sorted(all_links):
            print(f"  - {link}")
            
        print(f"\n[+] Checking for interesting links (Keywords: {KEYWORDS}):")
        interesting_links = set()
        for link in all_links:
            if any(keyword in link.lower() for keyword in [k.lower() for k in KEYWORDS]):
                interesting_links.add(link)
                
        if interesting_links:
            for link in sorted(interesting_links):
                print(f"  [!] {link}")
        else:
            print("  [-] No interesting links found based on keywords in URL.")
            
    except requests.ConnectionError:
        print(f"[!] Connection Error: Unable to connect to {TARGET_URL}")
    except requests.Timeout:
        print(f"[!] Timeout Error: Request to {TARGET_URL} timed out")
    except Exception as e:
        print(f"[!] Unexpected Error: {e}")

if __name__ == "__main__":
    main()