#!/usr/bin/env python3
# 分析NodeSeek页面中的CSRF token

from curl_cffi import requests
import re
from bs4 import BeautifulSoup

# 读取Cookie
with open('./cookie/NS_COOKIE.txt', 'r') as f:
    cookie = f.read().strip()

# 请求页面
headers = {
    'Cookie': cookie,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print("正在获取页面...")
resp = requests.get('https://www.nodeseek.com/post-456178-1', headers=headers, impersonate='chrome110', timeout=30)
html = resp.text

print(f"页面长度: {len(html)} 字符")

# 使用BeautifulSoup解析
soup = BeautifulSoup(html, 'html.parser')

print("\n=== 搜索Meta标签中的CSRF ===")
meta_tags = soup.find_all('meta')
for meta in meta_tags:
    name = meta.get('name', '').lower()
    content = meta.get('content', '')
    if 'csrf' in name or 'token' in name:
        print(f"Meta标签: name='{meta.get('name')}' content='{content[:50]}...'")

print("\n=== 搜索Input标签中的CSRF ===")
inputs = soup.find_all('input')
for inp in inputs:
    name = inp.get('name', '').lower()
    value = inp.get('value', '')
    if 'csrf' in name or 'token' in name:
        print(f"Input标签: name='{inp.get('name')}' value='{value[:50]}...'")

print("\n=== 搜索Script中的token ===")
scripts = soup.find_all('script')
for script in scripts:
    if script.string:
        content = script.string
        if 'csrf' in content.lower() or '_token' in content.lower():
            # 提取可能的token值
            token_patterns = [
                r'csrf[_-]?token[\'"\s]*[:=]\s*[\'"]([^\'"\s]+)[\'"]',
                r'_token[\'"\s]*[:=]\s*[\'"]([^\'"\s]+)[\'"]',
                r'X-CSRF-TOKEN[\'"\s]*[:=]\s*[\'"]([^\'"\s]+)[\'"]',
            ]
            for pattern in token_patterns:
                matches = re.findall(pattern, content, re.I)
                if matches:
                    print(f"Script中找到token: {matches[0][:20]}...")
                    break

print("\n=== 搜索HTML中的其他token模式 ===")
# 搜索整个HTML中的token模式
token_patterns = [
    r'window\._token\s*=\s*[\'"]([^\'"\s]+)[\'"]',
    r'Laravel\.csrfToken\s*=\s*[\'"]([^\'"\s]+)[\'"]',
    r'csrf_token[\'"\s]*[:=]\s*[\'"]([^\'"\s]+)[\'"]',
]

for pattern in token_patterns:
    matches = re.findall(pattern, html, re.I)
    if matches:
        print(f"找到token模式: {pattern[:30]}... => {matches[0][:20]}...")
