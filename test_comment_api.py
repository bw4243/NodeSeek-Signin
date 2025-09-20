#!/usr/bin/env python3
# 测试NodeSeek评论API

from curl_cffi import requests
import json

# 读取Cookie
with open('./cookie/NS_COOKIE.txt', 'r') as f:
    cookie = f.read().strip()

print("Cookie长度:", len(cookie))

# 模拟浏览器发起评论请求
headers = {
    'Cookie': cookie,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/plain, */*',
    'Origin': 'https://www.nodeseek.com',
    'Referer': 'https://www.nodeseek.com/post-456178-1'
}

# 尝试发布评论到主要端点
payload = {
    'content': '测试评论',
    'mode': 'new-comment', 
    'postId': 456178
}

print("正在测试评论API...")
try:
    resp = requests.post('https://www.nodeseek.com/api/content/new-comment', 
                        json=payload, headers=headers, impersonate='chrome110', timeout=30)
    print('状态码:', resp.status_code)
    print('响应头:', dict(resp.headers))
    print('响应内容:', resp.text[:500])
    
    if 'application/json' in resp.headers.get('content-type', ''):
        try:
            data = resp.json()
            print('JSON响应:', data)
        except:
            print('JSON解析失败')
            
except Exception as e:
    print('请求错误:', e)

# 也测试一下不带任何CSRF头的请求
print("\n=== 测试不带CSRF头的请求 ===")
try:
    resp2 = requests.post('https://www.nodeseek.com/api/content/new-comment', 
                         json=payload, headers=headers, impersonate='chrome110', timeout=30)
    print('无CSRF头 - 状态码:', resp2.status_code)
    print('无CSRF头 - 响应:', resp2.text[:200])
except Exception as e:
    print('无CSRF头 - 错误:', e)
