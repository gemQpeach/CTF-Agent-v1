import requests

def main():
    base_url = "http://10.0.162.112:80"
    paths = [
        "/js/login.js"
    ]
    
    session = requests.Session()
    
    for path in paths:
        url = base_url + path
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            print(f"[*] Fetched {url} (Status: {response.status_code})")
            print("-" * 50)
            print(response.text)
            print("-" * 50)
        except requests.exceptions.RequestException as e:
            print(f"[!] Error fetching {url}: {e}")

if __name__ == "__main__":
    main()