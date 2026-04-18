import json
import requests

# ============ CONFIG ============
BASE_URL = "http://localhost:8080"
GRAPHQL_PATHS = [
    "/graphql",
    "/graphiql",
    "/api/graphql",
    "/api/graphiql",
    "/v1/graphql",
    "/v2/graphql",
    "/query",
    "/api/query",
    "/gql",
    "/api/gql",
    "/api/v1/graphql",
    "/api/v2/graphql",
]
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
}
# Add auth if needed
AUTH_COOKIES = {}
AUTH_TOKEN = ""

# ============ INTROSPECTION QUERY ============
INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType {
      name
    }
    mutationType {
      name
    }
    subscriptionType {
      name
    }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          name
          description
          type {
            ...TypeRef
          }
          defaultValue
        }
        type {
          ...TypeRef
        }
        isDeprecated
        deprecationReason
      }
      inputFields {
        name
        description
        type {
          ...TypeRef
        }
        defaultValue
      }
      interfaces {
        ...TypeRef
      }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
      possibleTypes {
        ...TypeRef
      }
    }
    directives {
      name
      description
      locations
      args {
        name
        description
        type {
          ...TypeRef
        }
        defaultValue
      }
    }
  }
}

fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
    }
  }
}
"""

def build_introspection_payload():
    return {"query": INTROSPECTION_QUERY}

def extract_queries_mutations(data):
    result = {"queries": [], "mutations": [], "types": {}}
    try:
        schema = data.get("data", {}).get("__schema", {})
        query_type = schema.get("queryType", {})
        mutation_type = schema.get("mutationType", {})
        
        if query_type:
            result["query_type_name"] = query_type.get("name")
        if mutation_type:
            result["mutation_type_name"] = mutation_type.get("name")
        
        for t in schema.get("types", []):
            type_name = t.get("name", "")
            if type_name.startswith("__"):
                continue
            fields = []
            for f in t.get("fields") or []:
                field_info = {
                    "name": f.get("name"),
                    "type": resolve_type(f.get("type")),
                    "args": [
                        {
                            "name": a.get("name"),
                            "type": resolve_type(a.get("type")),
                            "defaultValue": a.get("defaultValue"),
                        }
                        for a in f.get("args", [])
                    ],
                }
                fields.append(field_info)
            
            result["types"][type_name] = {
                "kind": t.get("kind"),
                "fields": fields,
                "enumValues": [e.get("name") for e in t.get("enumValues") or []],
                "inputFields": [
                    {"name": i.get("name"), "type": resolve_type(i.get("type"))}
                    for i in t.get("inputFields") or []
                ],
            }
            
            if query_type and type_name == query_type.get("name"):
                result["queries"] = [f["name"] for f in fields]
            if mutation_type and type_name == mutation_type.get("name"):
                result["mutations"] = [f["name"] for f in fields]
                
    except Exception as e:
        print(f"[!] Error extracting schema: {e}")
    return result

def resolve_type(type_obj):
    if not type_obj:
        return None
    kind = type_obj.get("kind", "")
    name = type_obj.get("name", "")
    ofType = type_obj.get("ofType")
    if name:
        return name
    if ofType:
        inner = resolve_type(ofType)
        if kind == "NON_NULL":
            return f"{inner}!"
        elif kind == "LIST":
            return f"[{inner}]"
    return kind

def main():
    payload = build_introspection_payload()
    
    # Output just the JSON string with the query field
    print("=" * 60)
    print("INTROSPECTION QUERY JSON PAYLOAD:")
    print("=" * 60)
    print(json.dumps(payload))
    print("=" * 60)
    
    session = requests.Session()
    session.headers.update(HEADERS)
    if AUTH_COOKIES:
        session.cookies.update(AUTH_COOKIES)
    if AUTH_TOKEN:
        session.headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    
    found_endpoints = []
    
    for path in GRAPHQL_PATHS:
        url = BASE_URL.rstrip("/") + path
        try:
            print(f"[*] Trying {url} ...")
            resp = session.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if "data" in data and data["data"] is not None:
                        if data["data"].get("__schema") is not None:
                            print(f"[+] Found GraphQL endpoint: {url}")
                            found_endpoints.append((url, data))
                            
                            print("\n" + "=" * 60)
                            print("FULL INTROSPECTION RESULT:")
                            print("=" * 60)
                            print(json.dumps(data, indent=2))
                            
                            extracted = extract_queries_mutations(data)
                            print("\n" + "=" * 60)
                            print("QUERIES:")
                            print("=" * 60)
                            for q in extracted["queries"]:
                                print(f"  - {q}")
                            
                            print("\n" + "=" * 60)
                            print("MUTATIONS:")
                            print("=" * 60)
                            for m in extracted["mutations"]:
                                print(f"  - {m}")
                            
                            print("\n" + "=" * 60)
                            print("ALL TYPES & FIELDS:")
                            print("=" * 60)
                            for type_name, type_info in extracted["types"].items():
                                print(f"\n  [{type_info['kind']}] {type_name}")
                                for f in type_info.get("fields", []):
                                    args_str = ""
                                    if f.get("args"):
                                        args_str = ", ".join(
                                            f"{a['name']}: {a['type']}" for a in f["args"]
                                        )
                                        args_str = f"({args_str})"
                                    print(f"    - {f['name']}{args_str}: {f['type']}")
                                for e in type_info.get("enumValues", []):
                                    print(f"    - ENUM: {e}")
                                for i in type_info.get("inputFields", []):
                                    print(f"    - INPUT: {i['name']}: {i['type']}")
                            
                            # Check for flags in the response
                            resp_text = json.dumps(data)
                            import re
                            flags = re.findall(r'(flag\{[^}]+\}|CTF\{[^}]+\}|ctf\{[^}]+\})', resp_text)
                            if flags:
                                print("\n" + "=" * 60)
                                print("[!!!] FLAGS FOUND:")
                                for flag in flags:
                                    print(f"  {flag}")
                            
                            break
                    elif "errors" in data:
                        errors = data.get("errors", [])
                        error_msg = errors[0].get("message", "") if errors else ""
                        if "introspection" not in error_msg.lower():
                            print(f"[-] {url} - GraphQL error: {error_msg}")
                        else:
                            print(f"[-] {url} - Introspection disabled")
                except json.JSONDecodeError:
                    print(f"[-] {url} - Not JSON response")
            elif resp.status_code == 401:
                print(f"[-] {url} - Unauthorized (need auth)")
            elif resp.status_code == 403:
                print(f"[-] {url} - Forbidden")
            elif resp.status_code == 404:
                pass
            else:
                print(f"[-] {url} - Status: {resp.status_code}")
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
            print(f"[-] {url} - Timeout")
        except Exception as e:
            print(f"[-] {url} - Error: {e}")
    
    if not found_endpoints:
        print("\n[!] No GraphQL endpoints found. Try adjusting BASE_URL or GRAPHQL_PATHS.")

if __name__ == "__main__":
    main()