#!/usr/bin/env python3
# 深度分析NodeSeek的CSRF机制

from curl_cffi import requests
from bs4 import BeautifulSoup
import re
import json

# 读取Cookie
with open('./cookie/NS_COOKIE.txt', 'r') as f:
    cookie = f.read().strip()

headers = {
    'Cookie': cookie,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print("正在分析帖子页面...")
resp = requests.get('https://www.nodeseek.com/post-456178-1', headers=headers, impersonate='chrome110', timeout=30)
html = resp.text

# 1. 查找所有script标签中的配置数据
soup = BeautifulSoup(html, 'html.parser')
scripts = soup.find_all('script')

print("=== 分析Script标签中的配置 ===")
for i, script in enumerate(scripts):
    if script.string:
        content = script.string.strip()
        
        # 查找可能的配置对象
        config_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.+?});',
            r'window\.config\s*=\s*({.+?});',
            r'window\._config\s*=\s*({.+?});',
            r'__NUXT__\s*=\s*({.+?});',
            r'window\.__data\s*=\s*({.+?});',
        ]
        
        for pattern in config_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            if matches:
                try:
                    config_data = json.loads(matches[0])
                    print(f"找到配置对象 (script {i}): {list(config_data.keys())}")
                    
                    # 在配置中查找可能的token
                    def find_tokens(obj, path=""):
                        if isinstance(obj, dict):
                            for k, v in obj.items():
                                if 'token' in k.lower() or 'csrf' in k.lower():
                                    print(f"  Token字段: {path}.{k} = {str(v)[:50]}...")
                                find_tokens(v, f"{path}.{k}")
                        elif isinstance(obj, list):
                            for i, item in enumerate(obj):
                                find_tokens(item, f"{path}[{i}]")
                    
                    find_tokens(config_data)
                except:
                    print(f"Script {i}: JSON解析失败")

# 2. 查找可能的API调用模式
print("\n=== 分析可能的API调用模式 ===")
api_patterns = [
    r'fetch\s*\(\s*[\'"]([^\'"]*api[^\'"]*)[\'"]',
    r'axios\.\w+\s*\(\s*[\'"]([^\'"]*api[^\'"]*)[\'"]',
    r'request\s*\(\s*[\'"]([^\'"]*api[^\'"]*)[\'"]',
]

for pattern in api_patterns:
    matches = re.findall(pattern, html, re.I)
    if matches:
        print(f"找到API调用: {set(matches)}")

# 3. 查找表单相关的隐藏字段
print("\n=== 分析表单和隐藏字段 ===")
forms = soup.find_all('form')
for i, form in enumerate(forms):
    print(f"表单 {i+1}:")
    inputs = form.find_all('input', type='hidden')
    for inp in inputs:
        name = inp.get('name', '')
        value = inp.get('value', '')
        print(f"  隐藏字段: {name} = {value[:50]}...")

# 4. 查找data-*属性
print("\n=== 分析data-*属性 ===")
elements_with_data = soup.find_all(attrs=lambda x: x and any(k.startswith('data-') for k in x.keys()))
for elem in elements_with_data[:5]:  # 只显示前5个
    data_attrs = {k: v for k, v in elem.attrs.items() if k.startswith('data-')}
    if data_attrs:
        print(f"元素 {elem.name}: {data_attrs}")

print("\n分析完成！")
