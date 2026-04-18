import requests
import re

BASE_URL = "http://localhost:3000"  # Modify as needed
VIEW_PRESCRIPTIONS_URL = f"{BASE_URL}/view_prescriptions"

def main():
    session = requests.Session()
    
    # First, try accessing the page directly without id to see default response
    print("[*] Fetching /view_prescriptions without id parameter...")
    try:
        resp = session.get(VIEW_PRESCRIPTIONS_URL)
        print(f"[*] Status: {resp.status_code}")
        print(f"[*] Response length: {len(resp.text)}")
        print("=" * 80)
        print(resp.text[:3000])
        print("=" * 80)
    except Exception as e:
        print(f"[!] Error: {e}")

    # Iterate over id parameter values to find the full source
    print("\n[*] Iterating over id parameter values...")
    for uid in range(0, 20):
        try:
            resp = session.get(VIEW_PRESCRIPTIONS_URL, params={"id": uid}, timeout=10)
            if resp.status_code == 200 and len(resp.text) > 200:
                print(f"\n[+] id={uid} | Status: {resp.status_code} | Length: {len(resp.text)}")
                
                # Extract all JavaScript content
                js_blocks = re.findall(r'<script[^>]*>(.*?)</script>', resp.text, re.DOTALL)
                if js_blocks:
                    print(f"[+] Found {len(js_blocks)} script block(s)")
                    for i, js in enumerate(js_blocks):
                        print(f"\n--- Script Block {i+1} ---")
                        print(js.strip())
                        print(f"--- End Script Block {i+1} ---")
                
                # Specifically look for userID variable definition
                userID_patterns = [
                    r'userID\s*=\s*["\']?([^"\';\s]+)["\']?',
                    r'var\s+userID\s*=\s*["\']?([^"\';\s]+)["\']?',
                    r'let\s+userID\s*=\s*["\']?([^"\';\s]+)["\']?',
                    r'const\s+userID\s*=\s*["\']?([^"\';\s]+)["\']?',
                    r'userID["\']?\s*:\s*["\']?([^"\';\s,}]+)["\']?',
                ]
                for pattern in userID_patterns:
                    matches = re.findall(pattern, resp.text)
                    if matches:
                        print(f"\n[!] userID found with pattern '{pattern}': {matches}")
                
                # Look for GraphQL query/mutation related code
                graphql_patterns = [
                    r'query\s*\{[^}]+\}',
                    r'mutation\s*\{[^}]+\}',
                    r'graphql[^"]*',
                    r'prescription[^"]*',
                ]
                for pattern in graphql_patterns:
                    matches = re.findall(pattern, resp.text, re.IGNORECASE)
                    if matches:
                        print(f"\n[+] GraphQL/prescription matches for pattern '{pattern}':")
                        for m in matches[:5]:
                            print(f"    {m}")

                # Look for any interesting variables or logic
                interesting = re.findall(r'(user\w*|patient\w*|prescription\w*|doctor\w*|auth\w*|token\w*|session\w*)\s*[=:]\s*["\']?([^"\';\n]+)', resp.text, re.IGNORECASE)
                if interesting:
                    print(f"\n[+] Interesting variables found:")
                    for var_name, var_val in interesting:
                        print(f"    {var_name} = {var_val}")

                # Print full source if it contains userID
                if 'userID' in resp.text:
                    print(f"\n{'='*80}")
                    print(f"[!!!] FULL PAGE SOURCE (contains userID) for id={uid}:")
                    print(f"{'='*80}")
                    print(resp.text)
                    print(f"{'='*80}")
                    break
                    
        except Exception as e:
            print(f"[!] Error with id={uid}: {e}")

    # Also try fetching the raw source with different extensions/paths
    alternative_paths = [
        "/view_prescriptions.html",
        "/view_prescriptions.js",
        "/static/view_prescriptions.js",
        "/js/view_prescriptions.js",
        "/scripts/view_prescriptions.js",
        "/source",
        "/view_prescriptions?source=1",
        "/view_prescriptions?debug=1",
        "/view_prescriptions?raw=1",
    ]
    
    print("\n[*] Trying alternative paths for source code...")
    for path in alternative_paths:
        try:
            url = BASE_URL + path
            resp = session.get(url, timeout=5)
            if resp.status_code == 200 and len(resp.text) > 100:
                print(f"\n[+] {path} | Status: {resp.status_code} | Length: {len(resp.text)}")
                if 'userID' in resp.text or 'prescription' in resp.text.lower():
                    print(resp.text[:2000])
        except:
            pass

if __name__ == "__main__":
    main()