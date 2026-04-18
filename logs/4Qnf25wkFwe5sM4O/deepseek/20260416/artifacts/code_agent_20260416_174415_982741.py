import requests
import json

TARGET_URL = "http://10.0.162.112:80/jobs"

def main():
    session = requests.Session()

    payload = {"type": "front-end"}

    try:
        response = session.post(TARGET_URL, json=payload, timeout=10)

        print("=" * 60)
        print(f"Status Code: {response.status_code}")
        print("=" * 60)

        print("\n[Response Headers]")
        for key, value in response.headers.items():
            print(f"  {key}: {value}")

        print("\n[Response Body - Raw]")
        print(response.text)

        print("\n[Response Body - Parsed JSON]")
        try:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print("  Response is not valid JSON")

        print("\n[Searching for flag in description fields]")
        try:
            data = response.json()
            if isinstance(data, list):
                for idx, item in enumerate(data):
                    desc = item.get("description", "")
                    print(f"  Item {idx} - id: {item.get('id')}, name: {item.get('name')}")
                    print(f"    description: {desc}")
                    if "flag" in desc.lower() or "CTF" in desc or "ctf" in desc:
                        print(f"    >>> FLAG FOUND IN DESCRIPTION: {desc}")
            elif isinstance(data, dict):
                desc = data.get("description", "")
                print(f"  description: {desc}")
                if "flag" in desc.lower() or "CTF" in desc or "ctf" in desc:
                    print(f"  >>> FLAG FOUND IN DESCRIPTION: {desc}")
        except Exception as e:
            print(f"  Error parsing: {e}")

        print("\n[Full Response Text Search for 'flag']")
        text = response.text
        import re
        flags = re.findall(r'flag\{[^}]*\}|CTF\{[^}]*\}|flag\[[^\]]*\]', text, re.IGNORECASE)
        if flags:
            for f in flags:
                print(f"  >>> FOUND: {f}")
        else:
            # Broader search
            for line in text.split('\n'):
                if 'flag' in line.lower():
                    print(f"  >>> Line containing 'flag': {line.strip()}")

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    main()