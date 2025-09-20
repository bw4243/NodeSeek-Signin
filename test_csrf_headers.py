#!/usr/bin/env python3
# 测试不同的CSRF头部组合

from curl_cffi import requests
import json

# 读取Cookie
with open('./cookie/NS_COOKIE.txt', 'r') as f:
    cookie = f.read().strip()

base_headers = {
    'Cookie': cookie,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.nodeseek.com',
    'Referer': 'https://www.nodeseek.com/post-456178-1'
}

payload = {
    'content': '测试评论',
    'mode': 'new-comment',
    'postId': 456178
}

# 测试不同的头部组合
test_cases = [
    {
        'name': '无CSRF头',
        'extra_headers': {}
    },
    {
        'name': '只有X-Requested-With',
        'extra_headers': {
            'X-Requested-With': 'XMLHttpRequest'
        }
    },
    {
        'name': 'X-Requested-With + Sec-Fetch-*',
        'extra_headers': {
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty'
        }
    },
    {
        'name': '模拟真实浏览器请求头',
        'extra_headers': {
            'X-Requested-With': 'XMLHttpRequest',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-Mode': 'cors', 
            'Sec-Fetch-Dest': 'empty',
            'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
    },
    {
        'name': '空的CSRF token',
        'extra_headers': {
            'X-CSRF-TOKEN': '',
            'X-Requested-With': 'XMLHttpRequest'
        }
    },
    {
        'name': '固定的CSRF token值',
        'extra_headers': {
            'X-CSRF-TOKEN': 'nodeseek-csrf-token',
            'X-Requested-With': 'XMLHttpRequest'
        }
    }
]

print("测试不同的头部组合...")
for test_case in test_cases:
    print(f"\n=== {test_case['name']} ===")
    
    headers = base_headers.copy()
    headers.update(test_case['extra_headers'])
    
    try:
        resp = requests.post('https://www.nodeseek.com/api/content/new-comment',
                            json=payload, headers=headers, impersonate='chrome110', timeout=15)
        
        print(f"状态码: {resp.status_code}")
        
        if resp.headers.get('content-type', '').startswith('application/json'):
            try:
                data = resp.json()
                print(f"响应: {data}")
                
                # 如果成功了，记录这个组合
                if data.get('success'):
                    print("🎉 成功的头部组合!")
                    print("Headers:", test_case['extra_headers'])
                    break
                    
            except:
                print(f"响应文本: {resp.text[:100]}")
        else:
            print(f"非JSON响应: {resp.text[:100]}")
            
    except Exception as e:
        print(f"请求失败: {e}")

print("\n测试完成!")
