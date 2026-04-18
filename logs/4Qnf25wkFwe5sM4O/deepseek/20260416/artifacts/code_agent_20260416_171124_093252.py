import requests
import json
import sys

TARGET = "http://10.0.162.113:80"

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    })

    # Step 1: Fetch openapi.json
    openapi_url = f"{TARGET}/openapi.json"
    try:
        resp = session.get(openapi_url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[!] Failed to fetch openapi.json: {e}")
        sys.exit(1)

    spec = resp.json()

    # Step 2: Print general API info
    print("=" * 60)
    print("[*] OpenAPI General Info")
    print("=" * 60)
    info = spec.get("info", {})
    print(f"  Title       : {info.get('title', 'N/A')}")
    print(f"  Version     : {info.get('version', 'N/A')}")
    print(f"  Description : {info.get('description', 'N/A')}")

    servers = spec.get("servers", [])
    if servers:
        print(f"  Servers     :")
        for s in servers:
            print(f"    - {s.get('url', 'N/A')}")

    # Step 3: List all endpoints
    paths = spec.get("paths", {})
    print("\n" + "=" * 60)
    print(f"[*] All Endpoints ({len(paths)} paths)")
    print("=" * 60)
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.lower() in ("get", "post", "put", "delete", "patch", "options"):
                summary = details.get("summary", "")
                print(f"  {method.upper():7s} {path:30s}  {summary}")

    # Step 4: Detailed /jobs endpoint analysis
    print("\n" + "=" * 60)
    print("[*] Detailed /jobs Endpoint Analysis")
    print("=" * 60)
    jobs_paths = {k: v for k, v in paths.items() if "/jobs" in k}

    if not jobs_paths:
        print("  [!] No /jobs related paths found, dumping all paths details...")
        jobs_paths = paths

    for path, methods in jobs_paths.items():
        for method, details in methods.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch", "options"):
                continue
            print(f"\n  --- {method.upper()} {path} ---")
            print(f"  Summary     : {details.get('summary', 'N/A')}")
            print(f"  Description : {details.get('description', 'N/A')}")
            print(f"  Operation ID: {details.get('operationId', 'N/A')}")

            # Tags
            tags = details.get("tags", [])
            if tags:
                print(f"  Tags        : {', '.join(tags)}")

            # Parameters
            params = details.get("parameters", [])
            if params:
                print(f"  Parameters  ({len(params)}):")
                for p in params:
                    name = p.get("name", "N/A")
                    loc = p.get("in", "N/A")
                    required = p.get("required", False)
                    schema = p.get("schema", {})
                    desc = p.get("description", "")
                    print(f"    - Name: {name}")
                    print(f"      In: {loc} | Required: {required}")
                    print(f"      Schema: {json.dumps(schema)}")
                    if desc:
                        print(f"      Description: {desc}")

            # Request Body
            req_body = details.get("requestBody", {})
            if req_body:
                print(f"  Request Body:")
                print(f"    Required: {req_body.get('required', False)}")
                content = req_body.get("content", {})
                for ct, ct_details in content.items():
                    print(f"    Content-Type: {ct}")
                    schema_ref = ct_details.get("schema", {})
                    print(f"    Schema: {json.dumps(schema_ref, indent=6)}")

            # Responses
            responses = details.get("responses", {})
            if responses:
                print(f"  Responses:")
                for code, resp_details in responses.items():
                    desc = resp_details.get("description", "N/A")
                    print(f"    [{code}] {desc}")
                    content = resp_details.get("content", {})
                    for ct, ct_details in content.items():
                        print(f"      Content-Type: {ct}")
                        schema_ref = ct_details.get("schema", {})
                        print(f"      Schema: {json.dumps(schema_ref, indent=8)}")

    # Step 5: Resolve and print component schemas referenced by /jobs
    components = spec.get("components", {})
    schemas = components.get("schemas", {})
    if schemas:
        print("\n" + "=" * 60)
        print(f"[*] Component Schemas ({len(schemas)} defined)")
        print("=" * 60)
        for sname, sdef in schemas.items():
            print(f"\n  [{sname}]")
            print(f"    Type       : {sdef.get('type', 'N/A')}")
            props = sdef.get("properties", {})
            if props:
                print(f"    Properties :")
                for pname, pdef in props.items():
                    ptype = pdef.get("type", "N/A")
                    pformat = pdef.get("format", "")
                    penum = pdef.get("enum", [])
                    pref = pdef.get("$ref", "")
                    desc = pdef.get("description", "")
                    extra = ""
                    if pformat:
                        extra += f" format={pformat}"
                    if penum:
                        extra += f" enum={penum}"
                    if pref:
                        extra += f" ref={pref}"
                    if desc:
                        extra += f" desc={desc}"
                    print(f"      - {pname}: {ptype}{extra}")
            required = sdef.get("required", [])
            if required:
                print(f"    Required   : {required}")

    # Step 6: Security schemes
    security_schemes = components.get("securitySchemes", {})
    if security_schemes:
        print("\n" + "=" * 60)
        print("[*] Security Schemes")
        print("=" * 60)
        for sname, sdef in security_schemes.items():
            print(f"  {sname}: {json.dumps(sdef)}")

    # Step 7: Try to hit /jobs endpoint
    print("\n" + "=" * 60)
    print("[*] Probing /jobs endpoint")
    print("=" * 60)
    for method in ["GET", "POST"]:
        try:
            r = session.request(method, f"{TARGET}/jobs", timeout=10)
            print(f"  {method} /jobs -> {r.status_code}")
            if r.status_code != 404:
                try:
                    body = r.json()
                    print(f"  Response: {json.dumps(body, indent=4)[:2000]}")
                except:
                    print(f"  Response (text): {r.text[:500]}")
        except Exception as e:
            print(f"  {method} /jobs -> Error: {e}")

    # Step 8: Explore common auth paths
    print("\n" + "=" * 60)
    print("[*] Probing auth-related paths")
    print("=" * 60)
    auth_paths = ["/login", "/register", "/auth", "/api/login", "/api/register", "/token", "/api/token", "/docs", "/swagger", "/redoc"]
    for p in auth_paths:
        try:
            r = session.get(f"{TARGET}{p}", timeout=5)
            print(f"  GET {p} -> {r.status_code} ({len(r.content)} bytes)")
        except:
            pass

    # Save full spec
    with open("openapi_full.json", "w") as f:
        json.dump(spec, f, indent=2)
    print("\n[*] Full OpenAPI spec saved to openapi_full.json")

if __name__ == "__main__":
    main()