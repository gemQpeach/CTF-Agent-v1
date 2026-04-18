import base64
import zlib
import json

def decode_flask_session(cookie_value):
    is_compressed = cookie_value.startswith('.')
    
    if is_compressed:
        payload = cookie_value.split('.')[1]
    else:
        payload = cookie_value.split('.')[0]
        
    # Add base64 padding if necessary
    padding = 4 - len(payload) % 4
    if padding != 4:
        payload += '=' * padding
        
    # Decode URL-safe base64
    decoded_bytes = base64.urlsafe_b64decode(payload)
    
    # Decompress if the cookie was compressed
    if is_compressed:
        decoded_bytes = zlib.decompress(decoded_bytes)
        
    # Parse and return JSON
    try:
        data = json.loads(decoded_bytes)
        return data
    except json.JSONDecodeError:
        return decoded_bytes.decode('utf-8', errors='ignore')

def main():
    cookie = ".eJwlzjsOwjAMANC7ZGaInTh2epkq_gnWlk6Iu1OJ_Q3vU_Y84nyW7X1c8Sj7y8tWwmvqWN4xpjeikWzYExcZUJW-xFRV0CYA4wKZ0o1btOqYjDJxTGxTvTcfqWxpEmCwkDVrQm-Q5HYjdHLi5qBAlDktRWGVO3Kdcfw3WL4_5hUv0A.aeEszA.u-n4-5EJTianjCaNTQd4bYJMhKY"
    
    session_data = decode_flask_session(cookie)
    print("Decoded Flask Session Data:")
    print(json.dumps(session_data, indent=4))

if __name__ == "__main__":
    main()