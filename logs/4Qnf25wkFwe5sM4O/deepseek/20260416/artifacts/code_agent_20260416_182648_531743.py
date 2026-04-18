import requests
import json

def main():
    target_url = "http://10.0.162.112:80"
    jobs_endpoint = f"{target_url}/jobs"
    
    session = requests.Session()
    
    json_body = {"name": "test"}
    
    try:
        response = session.post(jobs_endpoint, json=json_body, timeout=10)
        print(f"[*] Status Code: {response.status_code}")
        print(f"[*] Response Headers: {dict(response.headers)}\n")
        
        try:
            data = response.json()
            print("[*] Parsed JSON Data:")
            print(json.dumps(data, indent=4, ensure_ascii=False))
            
            print("\n[+] Analyzing Jobs for Flags/Sensitive Info:")
            
            if isinstance(data, list):
                jobs = data
            elif isinstance(data, dict):
                jobs = data.get("jobs", data.get("data", data.get("results", [data])))
            else:
                jobs = [data]
                
            for index, job in enumerate(jobs):
                print(f"\n--- Job {index + 1} ---")
                if isinstance(job, dict):
                    for key, value in job.items():
                        print(f"  {key}: {value}")
                        value_str = str(value)
                        if "flag" in key.lower() or "flag" in value_str.lower() or "ctf" in value_str.lower():
                            print(f"  [!!!] POTENTIAL FLAG FOUND: {key} = {value}")
                else:
                    print(f"  {job}")
                    
            print("\n[*] Raw Response Text (for regex/string search):")
            raw_text = response.text
            print(raw_text)
            
            import re
            flag_patterns = [
                r"flag\{.*?\}",
                r"CTF\{.*?\}",
                r"flag\:[a-zA-Z0-9_]+",
                r"[a-f0-9]{32,}",
                r"THM\{.*?\}",
                r"HTB\{.*?\}",
            ]
            
            print("\n[*] Regex Search Results:")
            for pattern in flag_patterns:
                matches = re.findall(pattern, raw_text, re.IGNORECASE)
                if matches:
                    for match in matches:
                        print(f"  [!!!] MATCH ({pattern}): {match}")
                        
        except json.JSONDecodeError:
            print("[!] Response is not valid JSON. Raw text:")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"[!] Request Error: {e}")

if __name__ == "__main__":
    main()