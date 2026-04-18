import requests

BASE_URL = "http://10.0.162.114:80"

PATHS = [
    "/login", "/register", "/signup", "/home", "/main", "/index.html", 
    "/assets", "/assets/list", "/assets/search", "/assets/report", 
    "/api/v1", "/api/login", "/api/user", "/api/assets", "/api/search", 
    "/api/report", "/user", "/users", "/manage", "/management", "/query", 
    "/export", "/import", "/upload", "/download", "/console", "/debug", 
    "/swagger", "/docs", "/static", "/favicon.ico", "/assets/manage", 
    "/asset/search", "/asset/report", "/asset/list", "/system", "/config", 
    "/info", "/status", "/health", "/api/assets/search", "/api/assets/report", 
    "/report/generate", "/search/asset"
]

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    for path in PATHS:
        url = f"{BASE_URL.rstrip('/')}{path}"
        
        for method in ["GET", "POST"]:
            try:
                if method == "GET":
                    res = session.get(url, allow_redirects=True, timeout=5)
                else:
                    res = session.post(url, allow_redirects=True, timeout=5)
                
                if res.status_code != 404:
                    redirect_info = ""
                    if res.history:
                        redirect_codes = [str(r.status_code) for r in res.history]
                        redirect_info = f" | Redirect: {' -> '.join(redirect_codes)} -> {res.status_code} ({res.url})"
                    
                    print(f"[{method}] {url} - Status: {res.status_code}{redirect_info}")
                    
            except requests.exceptions.RequestException:
                pass

if __name__ == "__main__":
    main()